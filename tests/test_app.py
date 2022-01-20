from unittest.mock import patch
import sys

import urllib3
from src.estuary_prober.app import submitFile, ipfsChecker, IpfsCheck


def test_print_python_version():
    print(f"{sys.version=}")


@patch("urllib3.PoolManager")
def test_http_timeout(mock_poolmanager):
    mock_http = mock_poolmanager()
    mock_http.request.side_effect = urllib3.exceptions.HTTPError("Timeout error")

    code, value = submitFile("", [], "", "", 0)
    assert code == 408


@patch("urllib3.PoolManager")
def test_http_timeout(mock_poolmanager):
    mock_http = mock_poolmanager()
    mock_http.request.side_effect = urllib3.exceptions.HTTPError("Timeout error")

    ipfsCheck = ipfsChecker("", "", 0)
    assert len(ipfsCheck.CheckRequestError)
