"""Unit tests for :mod:`emtl.core`.

These are hermetic: ``session``, OCR and the RSA helper are all replaced with
fakes, so nothing here touches the network or an account. Live behaviour is
covered by ``test_live.py``.
"""

import math

import pytest
from requests.exceptions import HTTPError

from emtl import core
from emtl.tests.helpers import FakeOcr
from emtl.tests.helpers import FakeResponse
from emtl.tests.helpers import FakeSession


def _capturing_query(return_value=None, captured=None):
    """Return a stand-in for ``_query_something`` that records its arguments."""

    def query(tag, req_data=None):
        if captured is not None:
            captured["tag"] = tag
            captured["req_data"] = req_data
        return return_value

    return query


# --------------------------------------------------------------------------- #
# _check_resp
# --------------------------------------------------------------------------- #
def test_check_resp_accepts_200():
    core._check_resp(FakeResponse(status_code=200))


def test_check_resp_raises_http_error_with_response():
    resp = FakeResponse(status_code=500, text="boom", url="http://x/")

    with pytest.raises(HTTPError) as excinfo:
        core._check_resp(resp)

    assert excinfo.value.response is resp


# --------------------------------------------------------------------------- #
# snapshots / quotes
# --------------------------------------------------------------------------- #
def test_query_snapshot_calls_snapshot_endpoint(monkeypatch):
    session = FakeSession(get_response=FakeResponse(200, json_data={"status": 0}))
    monkeypatch.setattr(core, "session", session)

    assert core._query_snapshot("000001", "SA") == {"status": 0}

    call = session.get_calls[0]
    assert call["url"] == "https://emhsmarketwg.eastmoneysec.com/api/SHSZQuoteSnapshot"
    assert call["params"] == {"id": "000001", "market": "SA"}


def test_get_last_price_parses_quote(monkeypatch):
    monkeypatch.setattr(
        core,
        "_query_snapshot",
        lambda code, market: {"status": 0, "realtimequote": {"currentPrice": " 10.55 "}},
    )

    assert core.get_last_price("000001", "SA") == 10.55


@pytest.mark.parametrize("snapshot", [None, {}, {"status": 1}])
def test_get_last_price_returns_nan_when_unavailable(monkeypatch, snapshot):
    monkeypatch.setattr(core, "_query_snapshot", lambda code, market: snapshot)

    assert math.isnan(core.get_last_price("000001", "SA"))


# --------------------------------------------------------------------------- #
# captcha + validate key
# --------------------------------------------------------------------------- #
def test_get_captcha_code_returns_number(monkeypatch):
    monkeypatch.setattr(core, "get", lambda *args, **kwargs: FakeResponse(200, content=b"png"))
    monkeypatch.setattr(core, "_get_ocr", lambda: FakeOcr("1234"))

    random_num, code = core._get_captcha_code()

    assert isinstance(random_num, float)
    assert code == 1234


def test_get_captcha_code_retries_when_ocr_is_not_a_number(monkeypatch):
    monkeypatch.setattr(core, "get", lambda *args, **kwargs: FakeResponse(200, content=b"png"))
    monkeypatch.setattr(core, "_get_ocr", lambda: FakeOcr("abcd", "5678"))

    _, code = core._get_captcha_code()

    assert code == 5678


def test_get_captcha_code_gives_up_after_bounded_attempts(monkeypatch):
    monkeypatch.setattr(core, "get", lambda *args, **kwargs: FakeResponse(200, content=b"png"))
    monkeypatch.setattr(core, "_get_ocr", lambda: FakeOcr(*["nope"] * 3))

    with pytest.raises(RuntimeError, match="3 attempts"):
        core._get_captcha_code(attempts=3)


def test_get_em_validate_key_parses_hidden_input(monkeypatch):
    html = '<input id="em_validatekey" type="hidden" value="b91d8012-b70b-4265-bb5d-f79442531017"/>'
    monkeypatch.setattr(core, "session", FakeSession(get_response=FakeResponse(200, text=html)))
    monkeypatch.setattr(core, "_em_validate_key", "")

    key = core._get_em_validate_key()

    assert key == "b91d8012-b70b-4265-bb5d-f79442531017"
    assert core._em_validate_key == key


def test_get_em_validate_key_returns_none_when_absent(monkeypatch):
    monkeypatch.setattr(core, "session", FakeSession(get_response=FakeResponse(200, text="<html></html>")))

    assert core._get_em_validate_key() is None


# --------------------------------------------------------------------------- #
# login
# --------------------------------------------------------------------------- #
def _login_stubs(monkeypatch, captured, username="user", password="secret", duration=30, status="0"):
    def post(url, **kwargs):
        captured["url"] = url
        captured["data"] = kwargs.get("data")
        captured["headers"] = kwargs.get("headers")
        return FakeResponse(200, json_data={"Status": status})

    monkeypatch.setattr(core, "session", FakeSession(post_response=post))
    monkeypatch.setattr(core, "_get_captcha_code", lambda: (0.5, 4321))
    monkeypatch.setattr(core, "_get_em_validate_key", lambda: "VALIDKEY")
    monkeypatch.setattr(core, "emt_trade_encrypt", lambda value: f"enc({value})")
    return core.login(username, password, duration=duration)


def test_login_posts_encrypted_credentials(monkeypatch):
    captured = {}

    assert _login_stubs(monkeypatch, captured, duration=15) == "VALIDKEY"

    assert captured["url"] == "https://jywg.18.cn/Login/Authentication?validatekey="
    data = captured["data"]
    assert data["userId"] == "user"
    assert data["password"] == "enc(secret)"
    assert data["randNumber"] == 0.5
    assert data["identifyCode"] == 4321
    assert data["duration"] == 15
    assert data["type"] == "Z"


def test_login_falls_back_to_environment_credentials(monkeypatch):
    captured = {}
    monkeypatch.setenv("EM_USERNAME", "envuser")
    monkeypatch.setenv("EM_PASSWORD", "envpass")

    _login_stubs(monkeypatch, captured, username="", password="")

    assert captured["data"]["userId"] == "envuser"
    assert captured["data"]["password"] == "enc(envpass)"


def test_login_without_credentials_raises(monkeypatch):
    monkeypatch.delenv("EM_USERNAME", raising=False)
    monkeypatch.delenv("EM_PASSWORD", raising=False)

    with pytest.raises(ValueError, match="username and password"):
        core.login("", "")


def test_login_returns_none_when_status_is_not_ok(monkeypatch):
    assert _login_stubs(monkeypatch, {}, status="-1") is None


def test_login_returns_none_on_non_json(monkeypatch):
    monkeypatch.setattr(core, "session", FakeSession(post_response=FakeResponse(200, text="<html>")))
    monkeypatch.setattr(core, "_get_captcha_code", lambda: (0.5, 4321))
    monkeypatch.setattr(core, "emt_trade_encrypt", lambda value: "enc")

    assert core.login("user", "secret") is None


# --------------------------------------------------------------------------- #
# _query_something
# --------------------------------------------------------------------------- #
def test_query_something_uses_cached_validate_key(monkeypatch):
    session = FakeSession(post_response=FakeResponse(200))
    monkeypatch.setattr(core, "session", session)
    monkeypatch.setattr(core, "_em_validate_key", "KEY")

    resp = core._query_something("query_orders")

    assert resp.status_code == 200
    call = session.post_calls[0]
    assert call["url"] == core._urls["query_orders"] + "KEY"
    assert call["data"] == {"qqhs": 100, "dwc": ""}
    assert call["headers"]["X-Requested-With"] == "XMLHttpRequest"


def test_query_something_logs_in_when_key_is_missing(monkeypatch):
    session = FakeSession(post_response=FakeResponse(200))
    monkeypatch.setattr(core, "session", session)
    monkeypatch.setattr(core, "_em_validate_key", "")
    calls = []

    def fake_login():
        calls.append(1)
        core._em_validate_key = "FRESH"
        return "FRESH"

    monkeypatch.setattr(core, "login", fake_login)

    core._query_something("query_trades")

    assert len(calls) == 1
    assert session.post_calls[0]["url"].endswith("FRESH")


def test_query_something_raises_when_login_yields_no_key(monkeypatch):
    monkeypatch.setattr(core, "_em_validate_key", "")
    monkeypatch.setattr(core, "login", lambda: None)

    with pytest.raises(RuntimeError, match="not logged in"):
        core._query_something("query_trades")


def test_query_something_rejects_unknown_tag(monkeypatch):
    monkeypatch.setattr(core, "_em_validate_key", "KEY")

    with pytest.raises(AssertionError):
        core._query_something("does_not_exist")


def test_query_something_never_logs_the_validate_key(monkeypatch, caplog):
    monkeypatch.setattr(core, "session", FakeSession(post_response=FakeResponse(200)))
    monkeypatch.setattr(core, "_em_validate_key", "SUPERSECRETKEY")

    with caplog.at_level("DEBUG", logger="emtl.core"):
        core._query_something("query_orders")

    assert "SUPERSECRETKEY" not in caplog.text


# --------------------------------------------------------------------------- #
# query wrappers
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("func", "tag"),
    [
        (core.query_asset_and_position, "query_asset_and_pos"),
        (core.query_orders, "query_orders"),
        (core.query_trades, "query_trades"),
    ],
)
def test_simple_query_wrappers(monkeypatch, func, tag):
    captured = {}
    monkeypatch.setattr(core, "_query_something", _capturing_query(FakeResponse(200, json_data={"Status": 0}), captured))

    assert func() == {"Status": 0}
    assert captured["tag"] == tag
    assert captured["req_data"] is None


@pytest.mark.parametrize(
    ("func", "tag"),
    [
        (core.query_history_orders, "query_his_orders"),
        (core.query_history_trades, "query_his_trades"),
        (core.query_funds_flow, "query_funds_flow"),
    ],
)
def test_history_query_wrappers(monkeypatch, func, tag):
    captured = {}
    monkeypatch.setattr(core, "_query_something", _capturing_query(FakeResponse(200, json_data={"Status": 0}), captured))

    assert func(50, "2024-05-01", "2024-05-31") == {"Status": 0}
    assert captured["tag"] == tag
    assert captured["req_data"] == {"qqhs": 50, "dwc": "", "st": "2024-05-01", "et": "2024-05-31"}


# --------------------------------------------------------------------------- #
# orders
# --------------------------------------------------------------------------- #
def test_create_order_payload(monkeypatch):
    captured = {}
    monkeypatch.setattr(core, "_query_something", _capturing_query(FakeResponse(200, json_data={"Status": 0}), captured))

    assert core.create_order("000002", "B", "SA", 5.01, 100) == {"Status": 0}
    assert captured["tag"] == "create_order"
    assert captured["req_data"] == {
        "stockCode": "000002",
        "tradeType": "B",
        "zqmc": "",
        "market": "SA",
        "price": 5.01,
        "amount": 100,
    }


def test_cancel_order_strips_whitespace(monkeypatch):
    captured = {}
    monkeypatch.setattr(core, "_query_something", _capturing_query(FakeResponse(200, text="130662\n"), captured))

    assert core.cancel_order(" 20240520_130662 ") == "130662"
    assert captured["tag"] == "cancel_order"
    assert captured["req_data"] == {"revokes": "20240520_130662"}
