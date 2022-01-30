from curses.ascii import NUL
from email import message
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

tracer = trace.get_tracer(__name__)

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

    with tracer.start_as_current_span("checking-with-is-url-valid") as current_span:
        is_url_valid(API_ENDPOINT, ESTUARY_TOKEN)

    with tracer.start_as_current_span("posting-to-API-endpoint") as current_span:
        try:
            current_span.set_attributes({"API_ENDPOINT": API_ENDPOINT, "timeout": timeout})
            current_span.add_event(f"starting file post to {API_ENDPOINT}")
            r = http.request("POST", API_ENDPOINT, headers=req_headers, fields=fields, timeout=int(timeout))
            current_span.add_event(f"finished file post to {API_ENDPOINT} with no errors.")
        except (urllib3.exceptions.HTTPError, urllib3.exceptions.TimeoutError) as error:
            current_span.add_event(f"Caught error in posting.")
            logging.error("Failed to post file because %s\nURL: %s", error, API_ENDPOINT)
            return 408, {"Error": f"Failed to post file because {error}\nURL: {API_ENDPOINT}"}

        current_span.add_event("Starting processing JSON response")

        resp_body = r.data.decode("utf-8")
        resp_dict = json.loads(r.data.decode("utf-8"))

        current_span.add_event("Finished processing JSON response")

        return (r.status, resp_dict)


def ipfsChecker(cid: str, addr: str, timeout: int) -> IpfsCheck:
    ipfsCheck = IpfsCheck()
    startTime = time.time_ns()

    http = urllib3.PoolManager()
    url = f"https://ipfs-check-backend.ipfs.io/?cid={cid}&multiaddr={addr}"

    is_url_valid(url)

    with tracer.start_as_current_span("checking-ipfs") as current_span:
        try:
            current_span.add_event(f"Checking IPFS at url: {url}")
            r = http.request("GET", url, timeout=int(timeout))
            current_span.add_event(f"Finished checking IPFS with no errors.")

            resp_body = r.data.decode("utf-8")
            resp_dict: dict = json.loads(r.data.decode("utf-8"))
        except (urllib3.exceptions.HTTPError, urllib3.exceptions.TimeoutError) as error:
            message = f"Failed to get IPFS check {error}\nURL: {url}"
            ipfsCheck.CheckRequestError = message
            current_span.add_event(message)
            return ipfsCheck
        except (json.decoder.JSONDecodeError) as error:
            message = f"No response from request data, so could not decode JSON.: {error} \n response: {r}"
            ipfsCheck.CheckRequestError = message
            current_span.add_event(message)
            return ipfsCheck

        ipfsCheck.CheckTook = time.time_ns() - startTime
        if r.status != 200:
            current_span.add_event(f"Status code for IPFS check not 200: {resp_dict}")
            ipfsCheck.CheckRequestError = resp_dict.get("ConnectionError", "missing-ConnectionError")
            ipfsCheck.LoggingErrorBlob = resp_dict
            return ipfsCheck

        ipfsCheck.CidInDHT = resp_dict.get("CidInDHT", "missing-CidInDHT")
        ipfsCheck.PeerFoundInDHT = resp_dict.get("PeerFoundInDHT", "missing-PeerFoundInDHT")
        ipfsCheck.DataAvailableOverBitswap = resp_dict.get("DataAvailableOverBitswap", "missing-DataAvailableOverBitswap ")

        return ipfsCheck


def benchFetch(cid: str, timeout: int) -> FetchStats:
    fetchStats = FetchStats()
    fetchStats.GatewayURL = f"https://dweb.link/ipfs/{cid}"

    http = urllib3.PoolManager()

    is_url_valid(fetchStats.GatewayURL)

    with tracer.start_as_current_span("fetch-uploaded-file") as current_span:
        fetchStats.RequestStart = datetime.datetime.now()
        current_span.set_attribute("Gateway URL", fetchStats.GatewayURL)
        startTimeInNS = time.time_ns()
        current_span.add_event(f"Begin file GET: {fetchStats.GatewayURL}")
        try:
            current_span.add_event(f"starting http.request at: {fetchStats.GatewayURL}")
            r = http.request("GET", fetchStats.GatewayURL, preload_content=False, timeout=int(timeout))
            current_span.add_event(f"http.request returned")
        except (urllib3.exceptions.HTTPError, urllib3.exceptions.TimeoutError, urllib3.exceptions.MaxRetryError, urllib3.exceptions.ReadTimeoutError) as error:
            current_span.add_event(f"http.request to {fetchStats.GatewayURL} failed: {error}")
            logging.error("Failed to get file %s\nURL: %s", error, fetchStats.GatewayURL)
            fetchStats.StatusCode = 408
            fetchStats.RequestError = str(error)
            return fetchStats

        fetchStats.StatusCode = r.status

        if r.status != 200:
            current_span.add_event(f"Status Code != 200: {r}")
            fetchStats.RequestError = r.headers.get("ConnectionError", "missing-connectionerrror")
            fetchStats.LoggingErrorBlob = str(r)

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
    with tracer.start_as_current_span("estuary-external-benchest"):
        benchResult = BenchResult()
        benchResult.Debugging = True
        try:
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

        return {"statusCode": HTTPStatus.OK.value}


if __name__ == "__main__":
    for i in range(1):
        event = {"host": "shuttle-5.estuary.tech", "runner": "aronchick@localdebugging", "timeout": 10, "region": "ap-south-1", "prober": "estuary_prober"}
        start_honeycomb(event["prober"] + "_manual")
        lambda_handler(event, {})

# {
#     "host": "shuttle-4.estuary.tech", "runner": "lambda@consoledebugging", "timeout": 10, "region": "us-west-1"
# }
