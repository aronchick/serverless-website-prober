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

import secrets

logger = logging.getLogger()
logger.setLevel(logging.INFO)

load_dotenv()  # take environment variables from .env.

# Open telemetry/honeycomb block
import os
from opentelemetry import trace
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.context.context import Context
import typing
from opentelemetry.propagators import textmap
from opentelemetry.trace.propagation.tracecontext import (
    TraceContextTextMapPropagator,
)
from opentelemetry.propagate import set_global_textmap

from grpc import ssl_channel_credentials
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env. (automatic on glitch; this is needed locally)

# Set up tracing
resource = Resource(attributes={"service_name": os.getenv("SERVICE_NAME", "estuary-prober")})
trace.set_tracer_provider(TracerProvider(resource=resource))

apikey = os.environ.get("HONEYCOMB_API_KEY")
dataset = os.getenv("HONEYCOMB_DATASET")
print("Sending traces to Honeycomb with apikey <" + apikey + "> to dataset " + dataset)

# Send the traces to Honeycomb
hnyExporter = OTLPSpanExporter(
    endpoint="api.honeycomb.io:443", insecure=False, credentials=ssl_channel_credentials(), headers=(("x-honeycomb-team", apikey), ("x-honeycomb-dataset", dataset))
)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(hnyExporter))
trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

# To see spans in the log, uncomment this:

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


@dataclass
class DataAvailableOverBitswap:
    Found: bool = False
    Responded: bool = False
    Error: str = False


@dataclass
class IpfsCheck:
    CheckTook: datetime.timedelta = -1
    CheckRequestError: str = ""
    ConnectionError: str = ""
    PeerFoundInDHT: dict[str, int] = field(default_factory=dict)
    CidInDHT: bool = False

    DataAvailableOverBitswap: DataAvailableOverBitswap = DataAvailableOverBitswap()


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

    try:
        r = http.request("GET", url, timeout=timeout)
    except (urllib3.exceptions.HTTPError, urllib3.exceptions.TimeoutError) as error:
        logging.error("Failed to get IPFS check %s\nURL: %s", error, url)
        ipfsCheck.CheckRequestError = f"Ipfs Connection failed. Error: {error}"
        return ipfsCheck

    resp_body = r.data.decode("utf-8")
    resp_dict = json.loads(r.data.decode("utf-8"))

    ipfsCheck.CheckTook = time.time_ns() - startTime
    if r.status != 200:
        ipfsCheck.CheckRequestError = resp_dict["ConnectionError"]
        return ipfsCheck

    ipfsCheck.CidInDHT = resp_dict["CidInDHT"]
    ipfsCheck.PeerFoundInDHT = resp_dict["PeerFoundInDHT"]
    ipfsCheck.DataAvailableOverBitswap = resp_dict["DataAvailableOverBitswap"]

    return ipfsCheck


def benchFetch(cid: str, timeout: int) -> FetchStats:
    fetchStats = FetchStats()
    fetchStats.GatewayURL = f"https://dweb.link/ipfs/{cid}"

    http = urllib3.PoolManager()

    fetchStats.RequestStart = datetime.datetime.now()
    startTimeInNS = time.time_ns()
    try:
        r = http.request("GET", fetchStats.GatewayURL, preload_content=False, timeout=timeout)
    except (urllib3.exceptions.HTTPError, urllib3.exceptions.TimeoutError, urllib3.exceptions.MaxRetryError, urllib3.exceptions.ReadTimeoutError) as error:
        logging.error("Failed to get file %s\nURL: %s", error, fetchStats.GatewayURL)
        fetchStats.StatusCode = 408
        fetchStats.RequestError = str(error)
        return fetchStats

    fetchStats.StatusCode = r.status

    if r.status != 200:
        fetchStats.RequestError = r.headers["ConnectionError"]

    fetchStats.ResponseTime = time.time_ns() - startTimeInNS

    fetchStats.GatewayHost = r.headers["x-ipfs-gateway-host"]
    xpop = r.headers["x-ipfs-pop"]
    if len(fetchStats.GatewayHost) == 0:
        fetchStats.GatewayHost = xpop

    r.stream(1)
    fetchStats.TimeToFirstByte = time.time_ns() - startTimeInNS

    for chunk in r.stream(32):
        _ = chunk

    fetchStats.TotalTransferTime = time.time_ns() - startTimeInNS
    fetchStats.TotalElapsed = time.time_ns() - startTimeInNS

    return fetchStats


URLLib3Instrumentor().instrument(tracer_provider=trace.get_tracer_provider())


def lambda_handler(event: dict, context):
    benchResult = BenchResult()
    benchResult.Debugging = True
    try:
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

            benchResult.IpfsCheck = ipfsChecker(AddFileResponse.Cid, addr, timeout)

        benchResult.FetchStats = benchFetch(AddFileResponse.Cid, timeout)

        # # do something with the data
        # for record in records:
        #     print(record)

    except Exception as e:  # Catch all for easier error tracing in logs
        logger.error(e, exc_info=True)
        raise Exception("Error occurred during execution: %s" % e)  # notify aws of failure

    full_bench_result = json.dumps(benchResult, cls=EnhancedJSONEncoder)
    print(full_bench_result)

    insert = "insert into db_bench_results(result) values('{}')".format(full_bench_result)
    cursor.execute(insert)
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
