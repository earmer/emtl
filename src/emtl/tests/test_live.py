"""Live integration tests against the real 18.cn service.

Nothing in here runs by default. Enable the read-only checks with::

    EMTL_LIVE=1 EM_USERNAME=... EM_PASSWORD=... pytest -m live -k "not trade"

The order tests additionally require ``EMTL_LIVE_TRADE=1`` because they place
and cancel **real** orders. Only ever run them on a test account you can afford
to trade with.
"""

import datetime
import math
import os

import pytest

from emtl.core import cancel_order
from emtl.core import create_order
from emtl.core import get_last_price
from emtl.core import login
from emtl.core import query_asset_and_position
from emtl.core import query_funds_flow
from emtl.core import query_history_orders
from emtl.core import query_history_trades
from emtl.core import query_orders
from emtl.core import query_trades
from emtl.tests.helpers import requires_live
from emtl.tests.helpers import requires_live_trade

pytestmark = pytest.mark.live


def _last_30_days():
    end_date = datetime.datetime.now(datetime.UTC)
    start_date = end_date - datetime.timedelta(30)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- #
# Read-only
# --------------------------------------------------------------------------- #
@requires_live
def test_login():
    validate_key = login(os.getenv("EM_USERNAME", ""), os.getenv("EM_PASSWORD", ""))

    assert validate_key
    assert len(validate_key) == len("b91d8012-b70b-4265-bb5d-f79442531017")


@requires_live
def test_query_asset_position():
    assert query_asset_and_position()["Status"] == 0


@requires_live
def test_query_orders():
    assert query_orders()["Status"] == 0


@requires_live
def test_query_trades():
    assert query_trades()["Status"] == 0


@requires_live
def test_query_history_orders():
    st, et = _last_30_days()
    assert query_history_orders(100, st, et)["Status"] == 0


@requires_live
def test_query_history_trades():
    st, et = _last_30_days()
    assert query_history_trades(100, st, et)["Status"] == 0


@requires_live
def test_query_funds_flow():
    st, et = _last_30_days()
    assert query_funds_flow(100, st, et)["Status"] == 0


@requires_live
def test_last_price_needs_no_login():
    # The snapshot endpoint is public, so this should return a real price.
    price = get_last_price("000001", "SA")

    assert isinstance(price, float)
    assert not math.isnan(price)


# --------------------------------------------------------------------------- #
# Trades - double opt-in, real money
# --------------------------------------------------------------------------- #
@requires_live_trade
def test_create_order():
    resp = create_order("000002", "B", "SA", 5.01, 100)

    assert resp["Status"] in (0, -1)


@requires_live_trade
def test_cancel_order():
    order = os.getenv("EMTL_TEST_ORDER", "").strip()
    if not order:
        pytest.skip("set EMTL_TEST_ORDER=YYYYMMDD_NNNNNN to cancel a real order")

    assert cancel_order(order).startswith(order.split("_")[-1])
