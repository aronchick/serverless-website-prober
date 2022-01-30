from urllib import request
import requests
from opentelemetry import trace


def is_url_valid(url: str, ESTUARY_TOKEN: str = "") -> bool:
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("test-url-is-valid-and-resolves"):
        current_span = trace.get_current_span()

        current_span.set_attribute("url", url)

        req_headers = {}
        if len(ESTUARY_TOKEN) > 0:
            req_headers["Authorization"] = f"Bearer {ESTUARY_TOKEN}"

        try:
            current_span.add_event(f"Resolving {url}")
            request_response = requests.head(url, headers=req_headers)

            return request_response.status_code in [200, 404]  # both 200 and 404 are acceptable (the url is valid)
        except requests.ConnectionError as e:
            current_span.add_event(f"Connection error resolving {url}: {e}")
            raise e
        except (requests.ReadTimeout, requests.Timeout) as e:
            current_span.add_event(f"Timeout error resolving {url}: {e}")
            raise e
