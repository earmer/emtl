from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version

from .core import cancel_order
from .core import create_order
from .core import get_last_price
from .core import login
from .core import query_asset_and_position
from .core import query_funds_flow
from .core import query_history_orders
from .core import query_history_trades
from .core import query_orders
from .core import query_trades

try:
    __version__ = _package_version("emtl")
except PackageNotFoundError:  # pragma: no cover - running from a source checkout
    __version__ = "0.2.6"

__all__ = [
    "__version__",
    "cancel_order",
    "create_order",
    "get_last_price",
    "login",
    "query_asset_and_position",
    "query_funds_flow",
    "query_history_orders",
    "query_history_trades",
    "query_orders",
    "query_trades",
]
