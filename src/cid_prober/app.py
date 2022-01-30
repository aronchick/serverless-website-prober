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

import sys
from pathlib import Path

sys.path.append(Path(__file__).parent.parent.absolute().name)
from util.http import is_url_valid
from util.bench import FetchStats, benchFetch
from util.honeycomb import start_honeycomb
from opentelemetry import trace

logger = logging.getLogger()
logger.setLevel(logging.INFO)

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


def lambda_handler(event: dict, context):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("estuary-external-file-test") as external_file_test_span:
        try:
            if not ESTUARY_TOKEN:
                raise ValueError("no estuary token found")

            runner = event.get("runner", "")
            timeout = event.get("timeout", 10)
            region = event.get("region", "")

            with tracer.start_as_current_span("fetch-specified-file") as fetch_file_span:
                fetch_file_span.add_event("Starting bench fetch.")
                fetch_file_span.set_attribute("CID", event["cid"])
                fetch_file_span.set_attribute("Timeout", event["timeout"])

                fetchStats = benchFetch(cid=event["cid"], timeout=event["timeout"], stream_full_file=False)
                fetch_file_span.add_event("Ending bench fetch.")

        except Exception as e:  # Catch all for easier error tracing in logs
            logger.error(e, exc_info=True)
            raise Exception("Error occurred during execution: %s" % str(e))  # notify aws of failure

        full_bench_result = json.dumps(fetchStats, cls=EnhancedJSONEncoder)
        print(full_bench_result)

        return {"statusCode": HTTPStatus.OK.value}


if __name__ == "__main__":
    for i in range(1):
        event = {"runner": "aronchick@localdebugging", "timeout": 10, "region": "ap-south-1", "cid": "QmducxoYHKULWXeq5wtKoeMzie2QggYphNCVwuFuou9eWE", "prober": "cid_prober"}
        start_honeycomb("cid_prober_manual")

        lambda_handler(event, {})

# {
#     "host": "shuttle-4.estuary.tech", "runner": "lambda@consoledebugging", "timeout": 10, "region": "us-west-1"
# }
