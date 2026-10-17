import argparse
import getpass
import json
import os
import sys

from .core import cancel_order
from .core import create_order
from .core import login
from .core import query_asset_and_position
from .core import query_funds_flow
from .core import query_history_orders
from .core import query_history_trades
from .core import query_orders
from .core import query_trades
from .utils import get_logger

logger = get_logger(__name__)

_SHANGHAI_PREFIXES = {"5", "6", "9"}


def _market_for(stock_code: str) -> str:
    """Guess the 18.cn market code for a stock from its numeric prefix.

    Shanghai codes start with 5 (funds), 6 (stocks) or 9 (B shares); everything
    else (0/1/2/3) trades in Shenzhen.
    """
    return "HA" if stock_code.strip()[:1] in _SHANGHAI_PREFIXES else "SA"


def _parse_order(spec: str) -> tuple[str, float, int]:
    """Parse the ``CODE-PRICE-AMOUNT`` string accepted by ``--buy``/``--sell``."""
    parts = spec.replace("－", "-").split("-")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(f"应为 代码-价格-数量, 收到 {spec!r}")
    code, price, amount = (part.strip() for part in parts)
    try:
        return code, float(price), int(amount)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"无效的 代码-价格-数量 {spec!r}: {exc}") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="emt", description="东方财富交易接口", epilog="东方财富交易接口")
    parser.add_argument("-u", "--user", default="", help="用户名 (默认读取 EM_USERNAME)")
    parser.add_argument("-p", "--password", default="", help="密码 (默认读取 EM_PASSWORD)")
    parser.add_argument("--duration", type=int, default=30, help="在线时长(分钟), 默认 30")

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-b",
        "--buy",
        type=_parse_order,
        metavar="CODE-PRICE-AMOUNT",
        help="买入, 例如买入一手平安银行: 000001-10.21-100",
    )
    group.add_argument(
        "-s",
        "--sell",
        type=_parse_order,
        metavar="CODE-PRICE-AMOUNT",
        help="卖出, 例如卖出一手平安银行: 000001-10.21-100",
    )
    group.add_argument("-c", "--cancel", metavar="YYYYMMDD_NNNNNN", help="撤单, 例如 20240520_130662")
    group.add_argument(
        "-q",
        "--query",
        choices=["asset", "order", "trade", "history-order", "history-trade", "funds"],
        help="查询账户的资产、挂单、成交、历史订单、历史成交、资金流水",
    )

    parser.add_argument("--market", choices=["HA", "SA"], help="市场, HA 上海 / SA 深圳, 默认按代码推断")
    parser.add_argument("--start", help="历史查询起始日期, 格式 YYYY-MM-DD")
    parser.add_argument("--end", help="历史查询结束日期, 格式 YYYY-MM-DD")
    parser.add_argument("--size", type=int, default=100, help="历史查询条目数, 默认 100")
    return parser


def _validate_action(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Reject a missing or incomplete action before we prompt for credentials."""
    if not (args.buy or args.sell or args.cancel or args.query):
        parser.error("需要指定 -b/--buy, -s/--sell, -c/--cancel 或 -q/--query 之一")

    if args.query in {"history-order", "history-trade", "funds"} and not (args.start and args.end):
        parser.error(f"--query {args.query} 需要 --start 和 --end")


def _run_action(args: argparse.Namespace):
    if args.buy or args.sell:
        code, price, amount = args.buy or args.sell
        market = args.market or _market_for(code)
        trade_type = "B" if args.buy else "S"
        return create_order(code, trade_type, market, price, amount)

    if args.cancel:
        return cancel_order(args.cancel)

    query = args.query
    if query == "asset":
        return query_asset_and_position()
    if query == "order":
        return query_orders()
    if query == "trade":
        return query_trades()
    if query == "history-order":
        return query_history_orders(args.size, args.start, args.end)
    if query == "history-trade":
        return query_history_trades(args.size, args.start, args.end)
    if query == "funds":
        return query_funds_flow(args.size, args.start, args.end)

    return None


def run(args=None) -> int:
    parser = _build_parser()
    namespace = parser.parse_args(args=args)
    _validate_action(parser, namespace)

    username = namespace.user or os.getenv("EM_USERNAME", "")
    password = namespace.password or os.getenv("EM_PASSWORD", "")
    if not username:
        username = input("用户名: ")
    if not password:
        password = getpass.getpass("密码: ")

    try:
        validate_key = login(username, password, duration=namespace.duration)
    except Exception as exc:  # surface any login failure as a clean CLI error
        print(f"登录失败: {exc}", file=sys.stderr)
        return 1

    if not validate_key:
        print("登录失败", file=sys.stderr)
        return 1

    result = _run_action(namespace)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
