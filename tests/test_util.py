from http import HTTPStatus
from operator import contains
from unittest.mock import patch
import sys

import urllib3
from src.util.http import is_url_valid


class MockHTTPReturnCode(object):
    def __init__(self, status_code) -> None:
        self.status = 200


@patch("urllib3.PoolManager.urlopen")
def test_is_url_valid_good(mock_urlopen):
    mock_urlopen.return_value = MockHTTPReturnCode(200)

    assert is_url_valid("MOCK_VALID_URL")


@patch("urllib3.PoolManager")
def test_is_url_valid_bad(mock_poolmanager):
    error_string = "MOCK_INVALID_URL is invalid."
    mock_poolmanager.side_effect = urllib3.exceptions.MaxRetryError("", "", error_string)

    try:
        is_url_valid("MOCK_INVALID_URL")

        assert False  # Should have raised invalid URL error
    except urllib3.exceptions.MaxRetryError as e:
        assert "MOCK_INVALID_URL is invalid." in e.reason
