from curses.ascii import NUL
from importlib.metadata import files
import logging
import os
from typing import Tuple
from unicodedata import name
import json
import urllib3
from socket import timeout
from http import HTTPStatus
from psycopg2 import connect
from dotenv import load_dotenv
from dataclasses import dataclass, field
import dataclasses

import datetime
import time

import sys
from pathlib import Path

sys.path.append(Path(__file__).parent.parent.absolute().name)
from util.http import is_url_valid
from util.honeycomb import start_honeycomb
from opentelemetry import trace

import secrets

logger = logging.getLogger()
logger.setLevel(logging.INFO)

load_dotenv()  # take environment variables from .env.

CONNECTION_TIMEOUT_IN_SECONDS = 10

DATABASE_HOST = os.environ["DATABASE_HOST"]
DATABASE_USER = os.environ["DATABASE_USER"]
DATABASE_PASSWORD = os.environ["DATABASE_PASSWORD"]
DATABASE_NAME = os.environ["DATABASE_NAME"]
ESTUARY_TOKEN = os.environ["ESTUARY_TOKEN"]

NULL_STR = "NULL_STRING"


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        elif isinstance(o, (datetime.datetime, datetime.date, datetime.time)):
            return o.isoformat()
        elif isinstance(o, datetime.timedelta):
            return (datetime.datetime.min + o).time().isoformat()
        return super().default(o)


@dataclass
class FetchStats:
    RequestStart: datetime.time = datetime.MINYEAR
    GatewayURL: str = NULL_STR

    GatewayHost: str = NULL_STR
    StatusCode: int = 0
    RequestError: str = ""

    ResponseTime: datetime.timedelta = -1
    TimeToFirstByte: datetime.timedelta = -1
    TotalTransferTime: datetime.timedelta = -1
    TotalElapsed: datetime.timedelta = -1

    LoggingErrorBlob: str = ""


@dataclass
class DataAvailableOverBitswap:
    Found: bool = False
    Responded: bool = False
    Error: str = False

    LoggingErrorBlob: str = ""


@dataclass
class IpfsCheck:
    CheckTook: datetime.timedelta = -1
    CheckRequestError: str = ""
    ConnectionError: str = ""
    PeerFoundInDHT: dict[str, int] = field(default_factory=dict)
    CidInDHT: bool = False

    DataAvailableOverBitswap: DataAvailableOverBitswap = DataAvailableOverBitswap()

    LoggingErrorBlob: str = ""


@dataclass
class AddFileResponse:
    Cid: str = NULL_STR
    EstuaryId: int = -1
    Providers: list[str] = field(default_factory=list)


@dataclass
class BenchResult:
    Debugging: bool = True
    Runner: str = NULL_STR
    BenchStart: datetime = datetime.MINYEAR
    FileCID: str = NULL_STR
    AddFileRespTime: datetime.timedelta = -1
    AddFileTime: datetime.timedelta = -1
    AddFileErrorCode: int = 500
    AddFileErrorBody: str = ""
    LoggingErrorBlob: str = ""

    Shuttle: str = NULL_STR
    Region: str = NULL_STR

    FetchStats: FetchStats = FetchStats()
    IpfsCheck: IpfsCheck = IpfsCheck()


def getFile() -> tuple[str, bytes]:
    return ("goodfile-%s" % secrets.token_urlsafe(4), secrets.token_bytes(1024 * 1024))


def submitFile(fileName: str, fileData: list, host: str, ESTUARY_TOKEN: str, timeout: int) -> tuple[int, str]:
    API_ENDPOINT = "https://%s/content/add" % host

    req_headers = {"Authorization": "Bearer %s" % ESTUARY_TOKEN}

    http = urllib3.PoolManager()

    fields = {
        "data": (fileName, fileData),
    }

    is_url_valid(API_ENDPOINT, "POST")

    try:
        r = http.request("POST", API_ENDPOINT, headers=req_headers, fields=fields, timeout=timeout)
    except (urllib3.exceptions.HTTPError, urllib3.exceptions.TimeoutError) as error:
        logging.error("Failed to post file because %s\nURL: %s", error, API_ENDPOINT)
        return 408, {"Error": f"Failed to post file because {error}\nURL: {API_ENDPOINT}"}

    resp_body = r.data.decode("utf-8")
    resp_dict = json.loads(r.data.decode("utf-8"))

    return (r.status, resp_dict)


def ipfsChecker(cid: str, addr: str, timeout: int) -> IpfsCheck:
    ipfsCheck = IpfsCheck()
    startTime = time.time_ns()

    http = urllib3.PoolManager()
    url = f"https://ipfs-check-backend.ipfs.io/?cid={cid}&multiaddr={addr}"

    is_url_valid(url)

    try:
        r = http.request("GET", url, timeout=timeout)
    except (urllib3.exceptions.HTTPError, urllib3.exceptions.TimeoutError) as error:
        logging.error("Failed to get IPFS check %s\nURL: %s", error, url)
        ipfsCheck.CheckRequestError = f"Ipfs Connection failed. Error: {error}"
        return ipfsCheck

    resp_body = r.data.decode("utf-8")
    resp_dict: dict = json.loads(r.data.decode("utf-8"))

    ipfsCheck.CheckTook = time.time_ns() - startTime
    if r.status != 200:
        ipfsCheck.CheckRequestError = resp_dict.get("ConnectionError", "missing-ConnectionError")
        ipfsCheck.LoggingErrorBlob = json.dumps(resp_dict)
        return ipfsCheck

    ipfsCheck.CidInDHT = resp_dict.get("CidInDHT", "missing-CidInDHT")
    ipfsCheck.PeerFoundInDHT = resp_dict.get("PeerFoundInDHT", "missing-PeerFoundInDHT")
    ipfsCheck.DataAvailableOverBitswap = resp_dict.get("DataAvailableOverBitswap", "missing-DataAvailableOverBitswap ")

    return ipfsCheck


def benchFetch(cid: str, timeout: int) -> FetchStats:
    current_span = trace.get_current_span()
    fetchStats = FetchStats()
    fetchStats.GatewayURL = f"https://dweb.link/ipfs/{cid}"

    http = urllib3.PoolManager()

    is_url_valid(fetchStats.GatewayURL)

    fetchStats.RequestStart = datetime.datetime.now()
    current_span.set_attribute("Gateway URL", fetchStats.GatewayURL)
    startTimeInNS = time.time_ns()
    current_span.add_event(f"Begin file GET: {fetchStats.GatewayURL}")
    try:
        r = http.request("GET", fetchStats.GatewayURL, preload_content=False, timeout=timeout)
        current_span.add_event(f"http.request returned")
    except (urllib3.exceptions.HTTPError, urllib3.exceptions.TimeoutError, urllib3.exceptions.MaxRetryError, urllib3.exceptions.ReadTimeoutError) as error:
        current_span.add_event(f"http.request to {fetchStats.GatewayURL} failed: {error}")
        logging.error("Failed to get file %s\nURL: %s", error, fetchStats.GatewayURL)
        fetchStats.StatusCode = 408
        fetchStats.RequestError = str(error)
        return fetchStats

    fetchStats.StatusCode = r.status

    if r.status != 200:
        current_span.add_event(f"Status Code != 200: {json.dumps(r)}")
        fetchStats.RequestError = r.headers.get("ConnectionError", "missing-connectionerrror")
        fetchStats.LoggingErrorBlob = json.dumps(r)

    fetchStats.ResponseTime = time.time_ns() - startTimeInNS

    fetchStats.GatewayHost = r.headers.get("x-ipfs-gateway-host", "missing-x-ipfs-gateway-host")
    xpop = r.headers.get("x-ipfs-pop", "missing-x-ipfs-pop")
    if len(fetchStats.GatewayHost) == 0:
        fetchStats.GatewayHost = xpop

    current_span.add_event(f"Begin stream 1 byte")
    r.stream(1)
    current_span.add_event(f"End stream 1 byte")

    fetchStats.TimeToFirstByte = time.time_ns() - startTimeInNS

    current_span.add_event(f"Begin stream entire file")
    for chunk in r.stream(32):
        _ = chunk
    current_span.add_event(f"End stream entire file")

    fetchStats.TotalTransferTime = time.time_ns() - startTimeInNS
    fetchStats.TotalElapsed = time.time_ns() - startTimeInNS

    return fetchStats


def lambda_handler(event: dict, context):
    start_honeycomb(event["prober"])
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("estuary-external-benchest"):
        benchResult = BenchResult()
        benchResult.Debugging = True
        try:
            with tracer.start_as_current_span("get-db-cursor"):
                conn = connect(
                    user=DATABASE_USER,
                    password=DATABASE_PASSWORD,
                    host=DATABASE_HOST,
                    port=5432,
                    dbname=DATABASE_NAME,  # Drop forward slash
                    connect_timeout=CONNECTION_TIMEOUT_IN_SECONDS,
                )
                cursor = conn.cursor()

            if not ESTUARY_TOKEN:
                raise ValueError("no estuary token found")

            host = event.get("host", "api.estuary.tech")
            runner = event.get("runner", "")
            timeout = event.get("timeout", 10)
            region = event.get("region", "")

            fileName, fileData = getFile()

            with tracer.start_as_current_span("submit-file"):
                benchResult.BenchStart = datetime.datetime.now()
                startInNanoSeconds = time.time_ns()
                responseCode, submitFileResult = submitFile(fileName, fileData, host, ESTUARY_TOKEN, timeout)
                benchResult.AddFileRespTime = time.time_ns() - startInNanoSeconds

                # Not clear why we need the below - go takes a long to unmarshal json?
                benchResult.AddFileTime = time.time_ns() - startInNanoSeconds

            if "cid" in submitFileResult:
                AddFileResponse.Cid = submitFileResult["cid"]
                AddFileResponse.EstuaryId = submitFileResult["estuaryId"]
                AddFileResponse.Providers = submitFileResult["providers"]
            else:
                AddFileResponse.Cid = NULL_STR
                AddFileResponse.EstuaryId = NULL_STR
                AddFileResponse.Providers = NULL_STR
                benchResult.LoggingErrorBlob = json.dumps(submitFileResult)

            benchResult.FileCID = AddFileResponse.Cid
            benchResult.Runner = runner
            benchResult.AddFileErrorCode = responseCode
            benchResult.Region = region
            benchResult.Shuttle = host

            if responseCode != 200:
                benchResult.AddFileErrorBody = json.dumps(submitFileResult)

            if len(AddFileResponse.Providers) == 0:
                benchResult.IpfsCheck.CheckRequestError = "No providers resulted from check"

            else:
                addr = AddFileResponse.Providers[0]
                for potentialProvider in AddFileResponse.Providers:
                    if "127.0.0.1" not in potentialProvider:
                        # Excluding any provider not at localhost
                        addr = potentialProvider
                        break
                with tracer.start_as_current_span("check-ipfs"):
                    benchResult.IpfsCheck = ipfsChecker(AddFileResponse.Cid, addr, timeout)

            with tracer.start_as_current_span("fetch-uploaded-file"):
                benchResult.FetchStats = benchFetch(AddFileResponse.Cid, timeout)

            # # do something with the data
            # for record in records:
            #     print(record)

        except Exception as e:  # Catch all for easier error tracing in logs
            logger.error(e, exc_info=True)
            raise Exception("Error occurred during execution: %s" % str(e))  # notify aws of failure

        full_bench_result = json.dumps(benchResult, cls=EnhancedJSONEncoder)
        print(full_bench_result)

        with tracer.start_as_current_span("submit-results-to-db"):
            cursor.execute("insert into db_bench_results(result) values(%s)", (full_bench_result,))
            conn.commit()  # <- We MUST commit to reflect the inserted data
            cursor.close()
            conn.close()

        return {"statusCode": HTTPStatus.OK.value}


if __name__ == "__main__":
    for i in range(3):
        event = {"host": "shuttle-4.estuary.tech", "runner": "aronchick@localdebugging", "timeout": 10, "region": "ap-south-1"}
        lambda_handler(event, {})

# {
#     "host": "shuttle-4.estuary.tech", "runner": "lambda@consoledebugging", "timeout": 10, "region": "us-west-1"
# }
