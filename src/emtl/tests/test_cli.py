"""Unit tests for :mod:`emtl.cli`.

The CLI talks to the account through ``emtl.cli``'s module-level names, so we
monkeypatch those instead of shelling out. Nothing here logs in or trades for
real.
"""

import argparse

import pytest

from emtl import cli


@pytest.fixture(autouse=True)
def _logged_in(monkeypatch):
    monkeypatch.setattr(cli, "login", lambda *args, **kwargs: "VALIDKEY")


def test_market_for_guesses_shanghai_and_shenzhen():
    assert cli._market_for("600000") == "HA"
    assert cli._market_for("510300") == "HA"
    assert cli._market_for("000001") == "SA"
    assert cli._market_for("300750") == "SA"


def test_parse_order_accepts_ascii_and_fullwidth_dashes():
    assert cli._parse_order("000001-10.21-100") == ("000001", 10.21, 100)
    assert cli._parse_order("000001－10.21－100") == ("000001", 10.21, 100)


@pytest.mark.parametrize("spec", ["nope", "000001-10.21", "000001-abc-100"])
def test_parse_order_rejects_bad_specs(spec):
    with pytest.raises(argparse.ArgumentTypeError):
        cli._parse_order(spec)


def test_query_prints_json_and_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(cli, "query_asset_and_position", lambda: {"Status": 0})

    assert cli.run(["-u", "u", "-p", "p", "-q", "asset"]) == 0

    out = capsys.readouterr().out
    assert '"Status": 0' in out


def test_buy_infers_market_and_places_order(monkeypatch):
    captured = {}

    def fake_create_order(stock_code, trade_type, market, price, amount):
        captured.update(stock_code=stock_code, trade_type=trade_type, market=market, price=price, amount=amount)
        return {"Status": 0}

    monkeypatch.setattr(cli, "create_order", fake_create_order)

    assert cli.run(["-u", "u", "-p", "p", "-b", "000001-10.21-100"]) == 0
    assert captured == {"stock_code": "000001", "trade_type": "B", "market": "SA", "price": 10.21, "amount": 100}


def test_sell_respects_market_override(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli, "create_order", lambda *args: captured.update(args=args) or {"Status": 0})

    assert cli.run(["-u", "u", "-p", "p", "-s", "600000-8.5-200", "--market", "HA"]) == 0
    assert captured["args"] == ("600000", "S", "HA", 8.5, 200)


def test_cancel_passes_order_string(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli, "cancel_order", lambda order: captured.setdefault("order", order) or "130662")

    assert cli.run(["-u", "u", "-p", "p", "-c", " 20240520_130662 "]) == 0
    assert captured["order"] == " 20240520_130662 "


def test_history_query_requires_dates():
    with pytest.raises(SystemExit) as excinfo:
        cli.run(["-u", "u", "-p", "p", "-q", "history-order"])

    assert excinfo.value.code == 2


def test_history_query_uses_dates_and_size(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        cli,
        "query_history_orders",
        lambda size, start, end: captured.update(size=size, start=start, end=end) or {"Status": 0},
    )

    assert cli.run(["-u", "u", "-p", "p", "-q", "history-order", "--start", "2024-05-01", "--end", "2024-05-31", "--size", "50"]) == 0
    assert captured == {"size": 50, "start": "2024-05-01", "end": "2024-05-31"}


def test_requires_an_action():
    with pytest.raises(SystemExit) as excinfo:
        cli.run(["-u", "u", "-p", "p"])

    assert excinfo.value.code == 2


def test_rejects_conflicting_actions():
    with pytest.raises(SystemExit) as excinfo:
        cli.run(["-b", "000001-10.21-100", "-q", "asset"])

    assert excinfo.value.code == 2


def test_login_failure_returns_one(monkeypatch, capsys):
    monkeypatch.setattr(cli, "login", lambda *args, **kwargs: None)

    assert cli.run(["-u", "u", "-p", "p", "-q", "asset"]) == 1
    assert "登录失败" in capsys.readouterr().err


def test_login_exception_returns_one(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr(cli, "login", boom)

    assert cli.run(["-u", "u", "-p", "p", "-q", "asset"]) == 1
    assert "登录失败" in capsys.readouterr().err


def test_uses_environment_credentials(monkeypatch):
    monkeypatch.delenv("EM_USERNAME", raising=False)
    monkeypatch.delenv("EM_PASSWORD", raising=False)
    monkeypatch.setenv("EM_USERNAME", "envuser")
    monkeypatch.setenv("EM_PASSWORD", "envpass")
    monkeypatch.setattr(cli, "query_trades", lambda: {"Status": 0})
    captured = {}

    def fake_login(username, password, duration=30):
        captured.update(username=username, password=password, duration=duration)
        return "KEY"

    monkeypatch.setattr(cli, "login", fake_login)

    assert cli.run(["-q", "trade"]) == 0
    assert captured == {"username": "envuser", "password": "envpass", "duration": 30}
