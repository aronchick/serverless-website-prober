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

HONEYCOMB_DATASET = "estuary-prober-dev"
SERVICE_NAME = "estuary-prober-dev"

# Set up tracing
resource = Resource(attributes={"service_name": SERVICE_NAME})

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


def no_prober_found(event: dict, context):
    prober_requested = event.get("Prober", "No prober requested in cloud event.")
    raise (ValueError(f"No prober found. Prober requested: {prober_requested}\n Full event: {event}"))


def lambda_handler(event: dict, context):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("global-span"):
        current_span = trace.get_current_span()
        current_span.add_event(f"Begin mux")
        probers = {"estuary_prober": estuary_prober.lambda_handler, "cid_prober": cid_prober.lambda_handler}

        prober_fxn = probers.get(event.get("prober", ""), no_prober_found)
        prober_fxn(event, context)

        current_span.add_event(f"End mux")


if __name__ == "__main__":
    for i in range(3):
        event = {"host": "shuttle-4.estuary.tech", "runner": "aronchick@localdebugging", "timeout": 10, "region": "ap-south-1", "prober": "estuary_prober"}
        lambda_handler(event, {})

# {
#     "host": "shuttle-4.estuary.tech", "runner": "lambda@consoledebugging", "timeout": 10, "region": "us-west-1"
# }
