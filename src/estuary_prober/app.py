from importlib.metadata import files
import logging
import os
from typing import Tuple
from unicodedata import name
import json
import urllib3
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

CONNECTION_TIMEOUT_IN_SECONDS = 10

DATABASE_HOST = os.environ["DATABASE_HOST"]
DATABASE_USER = os.environ["DATABASE_USER"]
DATABASE_PASSWORD = os.environ["DATABASE_PASSWORD"]
DATABASE_NAME = os.environ["DATABASE_NAME"]
ESTUARY_TOKEN = os.environ["ESTUARY_TOKEN"]

QUERY = """
 SELECT (db_bench_results.result ->> 'BenchStart'::text)::timestamp with time zone AS date,
    (db_bench_results.result -> 'FetchStats'::text) ->> 'StatusCode'::text AS status,
    (((db_bench_results.result -> 'FetchStats'::text) ->> 'TimeToFirstByte'::text)::bigint) / 1000000 AS time_to_first_byte,
    (db_bench_results.result -> 'FetchStats'::text) ->> 'RequestError'::text AS req_err,
    (db_bench_results.result -> 'FetchStats'::text) ->> 'GatewayHost'::text AS gway_host,
    (((db_bench_results.result -> 'IpfsCheck'::text) ->> 'CheckTook'::text)::bigint) / 1000000 AS check_time
   FROM db_bench_results;
"""

FULL_QUERY = """ SELECT * FROM db_bench_results;"""

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
class IpfsStats:
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

    FetchStats: FetchStats = FetchStats()
    IpfsStats: IpfsStats = IpfsStats()


def getFile() -> tuple[str, bytes]:
    return ("goodfile-%s" % secrets.token_urlsafe(4), secrets.token_bytes(1024 * 1024))


def submitFile(fileName, fileData, host, ESTUARY_TOKEN) -> tuple[int, str]:
    API_ENDPOINT = "https://%s/content/add" % host

    req_headers = {"Authorization": "Bearer %s" % ESTUARY_TOKEN}

    http = urllib3.PoolManager()

    fields = {
        "data": (fileName, fileData),
    }
    r = http.request("POST", API_ENDPOINT, headers=req_headers, fields=fields)

    resp_body = r.data.decode("utf-8")
    resp_dict = json.loads(r.data.decode("utf-8"))

    return (r.status, resp_dict)


def ipfsCheck(cid: str, addr: str) -> IpfsStats:
    ipfsStats = IpfsStats()
    startTime = time.time_ns()

    http = urllib3.PoolManager()

    r = http.request("GET", f"https://ipfs-check-backend.ipfs.io/?cid={cid}&multiaddr={addr}")
    resp_body = r.data.decode("utf-8")
    resp_dict = json.loads(r.data.decode("utf-8"))

    ipfsStats.CheckTook = time.time_ns() - startTime
    if r.status != 200:
        ipfsStats.CheckRequestError = resp_dict["ConnectionError"]
        return ipfsStats

    ipfsStats.CidInDHT = resp_dict["CidInDHT"]
    ipfsStats.PeerFoundInDHT = resp_dict["PeerFoundInDHT"]
    ipfsStats.DataAvailableOverBitswap = resp_dict["DataAvailableOverBitswap"]

    return ipfsStats


def benchFetch(cid: str) -> FetchStats:
    fetchStats = FetchStats()
    fetchStats.GatewayURL = f"https://dweb.link/ipfs/{cid}"

    http = urllib3.PoolManager()

    fetchStats.RequestStart = datetime.datetime.now()
    startTimeInNS = time.time_ns()
    r = http.request("GET", fetchStats.GatewayURL, preload_content=False)
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


true = True

foo = {
    "Runner": "why@sirius",
    "FileCID": "bafkreihualqw7j36nhdoszujzvmm2zrdpwsbfdgynjjjnbzvfoe27fj4qq",
    "IpfsCheck": {
        "CidInDHT": true,
        "CheckTook": 1761233397,
        "PeerFoundInDHT": {"/ip4/127.0.0.1/tcp/6745": 10, "/ip4/147.75.86.255/tcp/6745": 10},
        "ConnectionError": "",
        "CheckRequestError": "",
        "DataAvailableOverBitswap": {"Error": "", "Found": true, "Responded": true},
    },
    "BenchStart": "2021-08-25T15:17:09.01191537-07:00",
    "FetchStats": {
        "GatewayURL": "https://dweb.link/ipfs/bafkreihualqw7j36nhdoszujzvmm2zrdpwsbfdgynjjjnbzvfoe27fj4qq",
        "StatusCode": 200,
        "GatewayHost": "gateway-bank3-sjc1",
        "RequestError": "",
        "RequestStart": "2021-08-25T15:17:17.063176299-07:00",
        "ResponseTime": 45170029474,
        "TotalElapsed": 45494443056,
        "TimeToFirstByte": 45170425558,
        "TotalTransferTime": 324017498,
    },
    "AddFileTime": 8051232024,
    "AddFileError": "",
    "AddFileRespTime": 8051161791,
}

bar = {
    "Debugging": true,
    "Runner": "",
    "BenchStart": "2022-01-19T00:40:07.282594",
    "FileCID": "bafkreigqhfmg66yyqnxxuqpkxutjxl4tu5jcygyrtpie7lzpzozusbcft4",
    "AddFileRespTime": 700768593,
    "AddFileTime": 700764653,
    "AddFileErrorCode": 200,
    "AddFileErrorBody": "",
    "FetchStats": {
        "RequestStart": "2022-01-19T00:40:08.798816",
        "GatewayURL": "https://dweb.link/ipfs/bafkreigqhfmg66yyqnxxuqpkxutjxl4tu5jcygyrtpie7lzpzozusbcft4",
        "GatewayHost": "ipfs-bank3-dc13",
        "StatusCode": 200,
        "RequestError": "",
        "ResponseTime": 785736352,
        "TimeToFirstByte": 785744102,
        "TotalTransferTime": 1258520484,
        "TotalElapsed": -1642552807540300382,
    },
    "IpfsStats": {
        "CheckTook": 815210666,
        "CheckRequestError": "",
        "ConnectionError": "",
        "PeerFoundInDHT": {"/ip4/3.134.223.177/tcp/6745": 10},
        "CidInDHT": true,
        "DataAvailableOverBitswap": {"Duration": 46855490, "Found": true, "Responded": true, "Error": ""},
    },
}


def lambda_handler(event: dict, context):
    benchResult = BenchResult()
    benchResult.Debugging = true
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

        fileName, fileData = getFile()

        benchResult.BenchStart = datetime.datetime.now()
        startInNanoSeconds = time.time_ns()
        responseCode, submitFileResult = submitFile(fileName, fileData, host, ESTUARY_TOKEN)
        benchResult.AddFileRespTime = time.time_ns() - startInNanoSeconds

        # Not clear why we need the below - go takes a long to unmarshal json?
        benchResult.AddFileTime = time.time_ns() - startInNanoSeconds

        AddFileResponse.Cid = submitFileResult["cid"]
        AddFileResponse.EstuaryId = submitFileResult["estuaryId"]
        AddFileResponse.Providers = submitFileResult["providers"]

        benchResult.FileCID = AddFileResponse.Cid
        benchResult.AddFileRespTime = time.time_ns() - startInNanoSeconds
        benchResult.Runner = runner
        benchResult.AddFileErrorCode = responseCode

        if responseCode != 200:
            benchResult.AddFileErrorBody = json.dumps(submitFileResult)

        if len(AddFileResponse.Providers) == 0:
            benchResult.IpfsStats.CheckRequestError = "No providers resulted from check"

        else:
            addr = AddFileResponse.Providers[0]
            for potentialProvider in AddFileResponse.Providers:
                if "127.0.0.1" not in potentialProvider:
                    # Excluding any provider not at localhost
                    addr = potentialProvider
                    break

            benchResult.IpfsStats = ipfsCheck(AddFileResponse.Cid, addr)

        benchResult.FetchStats = benchFetch(AddFileResponse.Cid)

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
    event = {"host": "shuttle-4.estuary.tech", "runner": "aronchick@localdebugging"}
    lambda_handler(event, {})
