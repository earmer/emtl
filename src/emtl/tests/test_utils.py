"""Unit tests for :mod:`emtl.utils`."""

import base64
import logging

from emtl.utils import emt_trade_encrypt
from emtl.utils import get_float
from emtl.utils import get_logger


def test_emt_trade_encrypt_produces_a_single_rsa_block():
    encrypted = emt_trade_encrypt("hello")

    raw = base64.b64decode(encrypted)
    # The server's key is 1024-bit, so every PKCS#1 v1.5 block is 128 bytes.
    assert len(raw) == 128


def test_emt_trade_encrypt_is_randomised():
    # PKCS#1 v1.5 padding means identical plaintext must not encrypt identically.
    assert emt_trade_encrypt("hello") != emt_trade_encrypt("hello")


def test_get_float_parses_strings_and_defaults_to_zero():
    assert get_float({"price": " 1.5 "}, "price") == 1.5
    assert get_float({"price": "  "}, "price") == 0.0


def test_get_float_accepts_numeric_values_and_missing_keys():
    assert get_float({"price": 1.5}, "price") == 1.5
    assert get_float({}, "price") == 0.0
    assert get_float({"price": None}, "price") == 0.0


def test_get_logger_returns_named_logger():
    assert get_logger("emtl.tests").name == "emtl.tests"
    assert logging.getLogger("emtl.tests") is not None
