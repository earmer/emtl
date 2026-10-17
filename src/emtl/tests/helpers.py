"""Shared test helpers.

The unit tests in this package never touch the network: they drive ``emtl.core``
with the fakes below. Tests that do talk to the real 18.cn service live in
``test_live.py`` and are opt-in via environment variables.
"""

import os

import pytest

_TRUTHY = {"1", "true", "yes", "on"}


def _enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in _TRUTHY


#: Live tests hit the real service. They are skipped unless EMTL_LIVE=1.
LIVE = _enabled("EMTL_LIVE")

#: Tests that place/cancel real orders need a second, explicit opt-in.
LIVE_TRADE = _enabled("EMTL_LIVE_TRADE")

live = pytest.mark.live
requires_live = pytest.mark.skipif(
    not LIVE,
    reason="live integration test against 18.cn; set EMTL_LIVE=1 to run",
)
requires_live_trade = pytest.mark.skipif(
    not (LIVE and LIVE_TRADE),
    reason="places real orders; set EMTL_LIVE=1 and EMTL_LIVE_TRADE=1 to run",
)


class FakeOcr:
    """Stand-in for ``ddddocr.DdddOcr`` that yields canned classifications."""

    def __init__(self, *results):
        self._results = iter(results)

    def classification(self, content):
        return next(self._results)


class FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(self, status_code=200, json_data=None, text="", content=b"", url="http://test/"):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.content = content
        self.url = url

    def json(self):
        if self._json is None:
            raise ValueError("no json body")
        return self._json


class FakeSession:
    """Records every call and returns canned responses."""

    def __init__(self, get_response=None, post_response=None):
        self._get_response = get_response
        self._post_response = post_response
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append({"url": url, **kwargs})
        return self._resolve(self._get_response, url, kwargs)

    def post(self, url, **kwargs):
        self.post_calls.append({"url": url, **kwargs})
        return self._resolve(self._post_response, url, kwargs)

    @staticmethod
    def _resolve(response, url, kwargs):
        if callable(response):
            return response(url, **kwargs)
        if response is None:
            raise AssertionError("no fake response configured for this request")
        return response
