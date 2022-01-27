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
from dotenv import load_dotenv
from dataclasses import dataclass, field
import dataclasses
from psycopg2 import connect
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

HONEYCOMB_DATASET = "cid-prober-dev"
SERVICE_NAME = "cid-prober-dev"

# Set up tracing
resource = Resource(attributes={"service_name": SERVICE_NAME})
trace.set_tracer_provider(TracerProvider(resource=resource))

apikey = os.environ.get("HONEYCOMB_API_KEY")
dataset = HONEYCOMB_DATASET
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

    ResponseTime: datetime.timedelta = datetime.MAXYEAR - datetime.MINYEAR
    TimeToFirstByte: datetime.timedelta = datetime.MAXYEAR - datetime.MINYEAR
    TotalTransferTime: datetime.timedelta = datetime.MAXYEAR - datetime.MINYEAR
    TotalElapsed: datetime.timedelta = datetime.MAXYEAR - datetime.MINYEAR

    LoggingErrorBlob: str = ""


@dataclass
class BenchResult:
    Debugging: bool = True
    Runner: str = NULL_STR
    BenchStart: datetime = datetime.MINYEAR
    FileCID: str = NULL_STR
    AddFileRespTime: datetime.timedelta = datetime.MAXYEAR - datetime.MINYEAR
    AddFileTime: datetime.timedelta = datetime.MAXYEAR - datetime.MINYEAR
    AddFileErrorCode: int = 500
    AddFileErrorBody: str = ""
    LoggingErrorBlob: str = ""

    Shuttle: str = NULL_STR
    Region: str = NULL_STR

    FetchStats: FetchStats = FetchStats()


def benchFetch(cid: str, timeout: int) -> FetchStats:
    current_span = trace.get_current_span()
    fetchStats = FetchStats()
    fetchStats.GatewayURL = f"https://dweb.link/ipfs/{cid}"

    http = urllib3.PoolManager()

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


URLLib3Instrumentor().instrument(tracer_provider=trace.get_tracer_provider())


def lambda_handler(event: dict, context):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("cid-prober"):
        benchResult = BenchResult()
        benchResult.BenchStart = datetime.datetime.now()
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

            benchResult.FileCID = event["cid"]
            benchResult.Runner = runner
            benchResult.Region = region
            benchResult.Shuttle = host

            with tracer.start_as_current_span("fetch-uploaded-file"):
                benchResult.FetchStats = benchFetch(benchResult.FileCID, timeout)

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
    for i in range(1):
        event = {"runner": "aronchick@localdebugging", "timeout": 10, "region": "ap-south-1", "cid": "QmducxoYHKULWXeq5wtKoeMzie2QggYphNCVwuFuou9eWE"}
        lambda_handler(event, {})

# {
#     "host": "shuttle-4.estuary.tech", "runner": "lambda@consoledebugging", "timeout": 10, "region": "us-west-1"
# }
