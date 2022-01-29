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
    with tracer.start_as_current_span("estuary-external-benchest"):
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

            with tracer.start_as_current_span("fetch-uploaded-file"):
                fetchStats = benchFetch(cid=event["cid"], timeout=event["timeout"])

        except Exception as e:  # Catch all for easier error tracing in logs
            logger.error(e, exc_info=True)
            raise Exception("Error occurred during execution: %s" % str(e))  # notify aws of failure

        full_bench_result = json.dumps(fetchStats, cls=EnhancedJSONEncoder)
        print(full_bench_result)

        with tracer.start_as_current_span("submit-results-to-db"):
            cursor.execute("insert into db_bench_results(result) values(%s)", (full_bench_result,))
            conn.commit()  # <- We MUST commit to reflect the inserted data
            cursor.close()
            conn.close()

        return {"statusCode": HTTPStatus.OK.value}


if __name__ == "__main__":
    for i in range(1):
        event = {"runner": "aronchick@localdebugging", "timeout": 10, "region": "ap-south-1", "cid": "QmducxoYHKULWXeq5wtKoeMzie2QggYphNCVwuFuou9eWE", "prober": "cid_prober_dev"}
        start_honeycomb(event["prober"])

        lambda_handler(event, {})

# {
#     "host": "shuttle-4.estuary.tech", "runner": "lambda@consoledebugging", "timeout": 10, "region": "us-west-1"
# }
