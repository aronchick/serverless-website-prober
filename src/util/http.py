import urllib3
import urllib3.exceptions
from opentelemetry import trace


def is_url_valid(url: str, method: str = "GET") -> bool:
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("test-url-is-valid-and-resolves"):
        http = urllib3.PoolManager()
        current_span = trace.get_current_span()

        current_span.set_attribute("url", url)
        current_span.set_attribute("method", method)

        try:
            current_span.add_event(f"Resolving {url} via {method}")
            request_response = http.urlopen(method, url)

            return request_response.status == 200
        except urllib3.exceptions.ConnectionError as e:
            current_span.add_event(f"Connection error resolving {url} via {method}: {e}")
            raise e
        except urllib3.exceptions.MaxRetryError as e:
            current_span.add_event(f"MaxRetryError error resolving {url} via {method}: {e}")
            raise e
        except urllib3.exceptions.TimeoutError as e:
            current_span.add_event(f"Timeout error resolving {url} via {method}: {e}")
            raise e
