# Open telemetry/honeycomb block
import os
from opentelemetry import trace
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
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


def start_honeycomb(dataset_name):
    HONEYCOMB_DATASET = dataset_name
    SERVICE_NAME = dataset_name

    URLLib3Instrumentor().instrument(tracer_provider=trace.get_tracer_provider())
    RequestsInstrumentor().instrument(tracer_provider=trace.get_tracer_provider())

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
