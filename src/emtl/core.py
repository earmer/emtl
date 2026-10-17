import os
import re
from random import SystemRandom
from typing import Any

from ddddocr import DdddOcr
from requests import Response
from requests import Session
from requests import get
from requests.exceptions import HTTPError

from .const import _base_headers
from .const import _urls
from .utils import emt_trade_encrypt
from .utils import get_float
from .utils import get_logger

logger = get_logger(__name__)
session = Session()
_em_validate_key = ""

#: Every request is bounded so a hung upstream cannot block a caller forever.
DEFAULT_TIMEOUT = 30

#: How many captcha images to read before giving up on OCR.
CAPTCHA_ATTEMPTS = 5

_ocr: DdddOcr | None = None


def _get_ocr() -> DdddOcr:
    """Return the shared OCR engine, building it on first use.

    ``DdddOcr()`` loads model files and pulls in onnxruntime, so constructing it
    at import time made ``import emtl`` slow for everyone and made the library
    unusable when the OCR stack was not installed. It is only needed to read a
    login captcha, so it is created lazily here.
    """
    global _ocr
    if _ocr is None:
        _ocr = DdddOcr(show_ad=False)
    return _ocr


def _query_snapshot(symbol_code: str, market: str) -> dict | None:
    url = "https://emhsmarketwg.eastmoneysec.com/api/SHSZQuoteSnapshot"
    params = {"id": symbol_code.strip(), "market": market}
    headers = _base_headers.copy()
    resp = session.get(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
    _check_resp(resp)
    return resp.json()


def get_last_price(symbol_code: str, market: str) -> float:
    ret = _query_snapshot(symbol_code, market)
    if ret is None or "status" not in ret or ret["status"] != 0:
        return float("nan")

    return get_float(ret["realtimequote"], "currentPrice")


def _check_resp(resp: Response) -> None:
    if resp.status_code != 200:
        logger.error(f"request {resp.url} failed, code={resp.status_code}, response={resp.text}")
        raise HTTPError(f"{resp.status_code} error for {resp.url}", response=resp)


def _query_something(tag: str, req_data: dict | None = None) -> Response | None:
    """通用查询函数

    :param tag: 请求类型
    :param req_data: 请求提交数据,可选
    :return:
    """
    global _em_validate_key
    if not _em_validate_key:
        _em_validate_key = login() or ""

    if not _em_validate_key:
        raise RuntimeError(f"not logged in: no validate key available for {tag!r}")

    assert tag in _urls, f"{tag} not in url list"
    url = _urls[tag] + _em_validate_key
    if req_data is None:
        req_data = {
            "qqhs": 100,
            "dwc": "",
        }
    headers = _base_headers.copy()
    headers["X-Requested-With"] = "XMLHttpRequest"
    # Log the endpoint, never the URL: it carries the validate key.
    logger.debug(f"(tag={tag}), (data={req_data}), (endpoint={_urls[tag]})")
    resp = session.post(url, headers=headers, data=req_data, timeout=DEFAULT_TIMEOUT)
    _check_resp(resp)
    return resp


def _get_captcha_code(attempts: int = CAPTCHA_ATTEMPTS) -> tuple[float, Any]:
    """get random number and captcha code."""
    cryptogen = SystemRandom()
    ocr = _get_ocr()
    for _ in range(attempts):
        random_num = cryptogen.random()
        resp = get(f"{_urls['yzm']}{random_num}", headers=_base_headers, timeout=DEFAULT_TIMEOUT)
        _check_resp(resp)
        code = ocr.classification(resp.content)
        try:
            return random_num, int(code)
        except (TypeError, ValueError):
            logger.warning(f"captcha OCR returned {code!r}, retrying")
    raise RuntimeError(f"could not read a captcha after {attempts} attempts")


def _get_em_validate_key() -> str | None:
    """获取 em_validatekey"""
    url = "https://jywg.18.cn/Trade/Buy"
    resp = session.get(url, headers=_base_headers, timeout=DEFAULT_TIMEOUT)
    _check_resp(resp)
    match = re.search(r'id="em_validatekey" type="hidden" value="(.*?)"', resp.text)
    if not match:
        logger.error("could not find em_validatekey on the trade page; login may have failed")
        return None

    global _em_validate_key
    _em_validate_key = match.group(1).strip()
    return _em_validate_key


def login(username: str = "", password: str = "", duration: int = 30) -> str | None:
    """登录接口.

    :param str username: 用户名
    :param str password: 密码(明文)
    :param duration: 在线时长(分钟), defaults to 30
    :type duration: int, optional
    :return:
    """
    if not username:
        username = os.getenv("EM_USERNAME", "")
    if not password:
        password = os.getenv("EM_PASSWORD", "")
    if not username or not password:
        raise ValueError("login needs a username and password (pass them or set EM_USERNAME/EM_PASSWORD)")

    random_num, code = _get_captcha_code()
    headers = _base_headers.copy()
    headers["X-Requested-With"] = "XMLHttpRequest"
    headers["Referer"] = "https://jywg.18.cn/Login?el=1&clear=&returl=%2fTrade%2fBuy"
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    url = _urls["login"]
    data = {
        "userId": username.strip(),
        "password": emt_trade_encrypt(password.strip()),
        "randNumber": random_num,
        "identifyCode": code,
        "duration": duration,
        "authCode": "",
        "type": "Z",
        "secInfo": "",
    }
    resp = session.post(url, headers=headers, data=data, timeout=DEFAULT_TIMEOUT)
    _check_resp(resp)

    try:
        result = resp.json()
    except ValueError:
        logger.error("login returned a non-JSON response")
        return None

    status = result.get("Status") if isinstance(result, dict) else None
    if status not in (0, "0"):
        logger.error(f"login failed: Status={status!r}")
        return None

    logger.debug("login succeeded")
    return _get_em_validate_key()


def query_asset_and_position() -> dict | None:
    """Get asset and position."""
    resp = _query_something("query_asset_and_pos")
    if resp:
        return resp.json()


def query_orders() -> dict | None:
    """查询订单."""
    resp = _query_something("query_orders")
    if resp:
        return resp.json()


def query_trades() -> dict | None:
    """查询成交."""
    resp = _query_something("query_trades")
    if resp:
        return resp.json()


def query_history_orders(size: int, start_time: str, end_time: str) -> dict | None:
    """查询历史订单.

    :param int size: 请求的数据的条目数
    :param str start_time: 起始时间, 格式"%Y-%m-%d"
    :param str end_time: 起始时间, 格式"%Y-%m-%d"
    :return dict:
    """
    resp = _query_something("query_his_orders", {"qqhs": size, "dwc": "", "st": start_time, "et": end_time})
    if resp:
        return resp.json()


def query_history_trades(size: int, start_time: str, end_time: str) -> dict | None:
    """查询历史成交.

    :param int size: 请求的数据的条目数
    :param str start_time: 起始时间, 格式"%Y-%m-%d"
    :param str end_time: 起始时间, 格式"%Y-%m-%d"
    :return dict:
    """
    resp = _query_something("query_his_trades", {"qqhs": size, "dwc": "", "st": start_time, "et": end_time})
    if resp:
        return resp.json()


def query_funds_flow(size: int, start_time: str, end_time: str) -> dict | None:
    """查询资金.

    :param int size: 请求的数据的条目数
    :param str start_time: 起始时间, 格式"%Y-%m-%d"
    :param str end_time: 起始时间, 格式"%Y-%m-%d"
    :return dict:
    """
    resp = _query_something("query_funds_flow", {"qqhs": size, "dwc": "", "st": start_time, "et": end_time})
    if resp:
        return resp.json()


def create_order(stock_code: str, trade_type: str, market: str, price: float, amount: int) -> dict | None:
    """交易接口, 买入或卖出.

    :param str stock_code: 股票代码
    :param str trade_type: 交易方向,B for buy, S for sell
    :param str market: 股票市场,HA 上海, SA
    :param float price: 股票价格
    :param int amount: 买入/卖出数量
    """
    req_data = {
        "stockCode": stock_code,
        "tradeType": trade_type,
        "zqmc": "",
        "market": market,
        "price": price,
        "amount": amount,
    }
    resp = _query_something("create_order", req_data=req_data)
    if resp:
        logger.info(resp.json())
        return resp.json()


def cancel_order(order_str: str) -> str | None:
    """取消交易接口.

    :param str order_str: 订单字符串, 由成交日期+成交编号组成. 在create_order和query_order接口, Wtrq的值是成交日期, Wtbh的值是成交编号, 格式为: 20240520_130662
    """
    data = {"revokes": order_str.strip()}
    resp = _query_something("cancel_order", req_data=data)
    if resp:
        return resp.text.strip()
