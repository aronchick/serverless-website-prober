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
from util.honeycomb import start_honeycomb
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

NULL_STR = "NULL_STRING"


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


def benchFetch(cid: str, timeout: int, stream_full_file: bool = True) -> FetchStats:
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("benchFetch span") as current_span:
        fetchStats = FetchStats()
        fetchStats.GatewayURL = f"https://dweb.link/ipfs/{cid}"

        http = urllib3.PoolManager()

        is_url_valid(fetchStats.GatewayURL)

        fetchStats.RequestStart = datetime.datetime.now()
        current_span.set_attribute("Gateway URL", fetchStats.GatewayURL)
        startTimeInNS = time.time_ns()
        current_span.add_event(f"Begin file GET: {fetchStats.GatewayURL}")
        try:
            r = http.request("GET", fetchStats.GatewayURL, preload_content=False, timeout=int(timeout))
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

        with tracer.start_as_current_span("streaming 1 byte") as current_span:
            r.stream(1)

        fetchStats.TimeToFirstByte = time.time_ns() - startTimeInNS

        if stream_full_file:
            with tracer.start_as_current_span("streaming entire file") as current_span:
                for chunk in r.stream(32):
                    _ = chunk

        fetchStats.TotalTransferTime = time.time_ns() - startTimeInNS
        fetchStats.TotalElapsed = time.time_ns() - startTimeInNS

        return fetchStats
