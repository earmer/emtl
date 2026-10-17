"""Unit tests for the CI canary in ``ci/upstream_check.py``.

The canary itself needs the network, but its parsing helpers are pure and are
exactly the part most likely to rot silently, so we test them here.
"""

import importlib.util
from pathlib import Path

import pytest

from emtl.utils import rsa_public_key

_SCRIPT = Path(__file__).resolve().parents[3] / "ci" / "upstream_check.py"

if not _SCRIPT.exists():  # pragma: no cover - only for non-editable installs
    pytest.skip("ci/upstream_check.py is not in this install", allow_module_level=True)

_spec = importlib.util.spec_from_file_location("upstream_check", _SCRIPT)
upstream_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(upstream_check)


def test_normalise_key_body_from_python_pem():
    pem = "-----BEGIN PUBLIC KEY-----\nABC\ndef==\n-----END PUBLIC KEY-----"

    assert upstream_check.normalise_key_body(pem) == "ABCdef=="


def test_normalise_key_body_from_javascript_escapes():
    # JS bundles embed the key with literal ``\n`` sequences.
    js = 'var k="-----BEGIN PUBLIC KEY-----\\nABC\\ndef==\\n-----END PUBLIC KEY-----";'

    assert upstream_check.normalise_key_body(js) == "ABCdef=="


def test_normalise_key_body_missing_returns_none():
    assert upstream_check.normalise_key_body("no key here") is None


def test_local_public_key_body_matches_utils():
    assert upstream_check.local_public_key_body() == upstream_check.normalise_key_body(rsa_public_key)


def test_extract_validate_key():
    html = '<input id="em_validatekey" type="hidden" value="b91d8012-b70b-4265-bb5d-f79442531017"/>'

    assert upstream_check.extract_validate_key(html) == "b91d8012-b70b-4265-bb5d-f79442531017"


def test_extract_validate_key_absent():
    assert upstream_check.extract_validate_key("<html></html>") is None


def test_uuid_regex():
    assert upstream_check.UUID_RE.match("b91d8012-b70b-4265-bb5d-f79442531017")
    assert not upstream_check.UUID_RE.match("not-a-uuid")


def test_script_is_importable_without_side_effects():
    # Importing the module must not run any network check.
    assert upstream_check.BASE == "https://jywg.18.cn"
    assert callable(upstream_check.main)
