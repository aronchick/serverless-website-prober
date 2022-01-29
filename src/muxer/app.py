import logging
from dotenv import load_dotenv

import sys
import os, sys
from pathlib import Path

sys.path.append(Path(__file__).parent.parent.absolute().name)

# All probers
import estuary_prober.app as estuary_prober
import cid_prober.app as cid_prober

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Open telemetry/honeycomb block
import os
from util.honeycomb import start_honeycomb
from opentelemetry import trace

from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env. (automatic on glitch; this is needed locally)

CONNECTION_TIMEOUT_IN_SECONDS = 10


def no_prober_found(event: dict, context):
    prober_requested = event.get("Prober", "No prober requested in cloud event.")
    raise (ValueError(f"No prober found. Prober requested: {prober_requested}\n Full event: {event}"))


def lambda_handler(event: dict, context):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("global-span"):
        current_span = trace.get_current_span()
        current_span.set_attribute("source code hash", os.environ.get("SOURCE_CODE_HASH", "NO_SOURCE_CODE_HASH"))
        current_span.add_event(f"Begin mux")
        probers = {"estuary_prober": estuary_prober.lambda_handler, "cid_prober": cid_prober.lambda_handler}

        prober_fxn = probers.get(event.get("prober", ""), no_prober_found)
        prober_fxn(event, context)

        current_span.add_event(f"End mux")


if __name__ == "__main__":
    for i in range(1):
        # temp_data_set = "estuary_prober_manual"
        # event = {"host": "shuttle-4.estuary.tech", "runner": "aronchick@localdebugging", "timeout": 10, "region": "ap-south-1", "prober": "estuary_prober"}
        # os.environ["HONEYCOMB_DATASET"] = temp_data_set
        # os.environ["SERVICE_NAME"] = temp_data_set
        # lambda_handler(event, {})

        temp_data_set = "cid_prober_manual"
        event = {
            "runner": "aronchick@localdebugging",
            "timeout": 10,
            "region": "ap-south-1",
            "cid": "QmducxoYHKULWXeq5wtKoeMzie2QggYphNCVwuFuou9eWE",
            "prober": "cid_prober",
        }
        start_honeycomb(event["prober"])
        lambda_handler(event, {})


# {
#     "host": "shuttle-4.estuary.tech", "runner": "lambda@consoledebugging", "timeout": 10, "region": "us-west-1"
# }
