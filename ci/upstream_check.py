#!/usr/bin/env python3
"""Credential-free upstream health check for the 18.cn trading API.

``emtl`` works by reverse-engineering the private web app behind
``https://jywg.18.cn``. Whenever that app changes - a rotated RSA key, a renamed
endpoint, a different captcha - the client breaks and users find out the hard
way. This script is the early-warning system: it verifies the *shape* of the
upstream app that the client depends on, without any account and without ever
placing an order.

It intentionally uses only the standard library so CI can run it with nothing
installed. Exit code is non-zero when a check fails.

Run locally::

    python ci/upstream_check.py
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from random import SystemRandom

BASE = "https://jywg.18.cn"
LOGIN_PAGE = f"{BASE}/Login?el=1"
BUY_PAGE = f"{BASE}/Trade/Buy"
CAPTCHA = f"{BASE}/Login/YZM?randNum="
AUTH_URL = f"{BASE}/Login/Authentication?validatekey="

# JavaScript bundles worth inspecting; BaseJS carries the login RSA public key,
# CommonJS/FinanceCommon wire up the em_validatekey request flow.
JS_BUNDLES = ["/JsBundles/BaseJS", "/JsBundles/LoginSec", "/JsBundles/CommonJS", "/JsBundles/FinanceCommon"]

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"

# Kept in sync with src/emtl/core.py::_get_em_validate_key
VALIDATE_KEY_RE = re.compile(r'id="em_validatekey" type="hidden" value="(.*?)"')
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
PEM_BODY_RE = re.compile(r"-----BEGIN PUBLIC KEY-----(.*?)-----END PUBLIC KEY-----", re.S)

UTILS_PATH = Path(__file__).resolve().parent.parent / "src" / "emtl" / "utils.py"

_checks: list[tuple[bool, str, str]] = []


def normalise_key_body(text: str) -> str | None:
    """Return the base64 body of the first PEM public key, stripped of all noise.

    Works for both real PEM whitespace and JavaScript ``"\\n"`` escapes, so the
    same value can be pulled out of ``utils.py`` and out of a served JS bundle.
    """
    match = PEM_BODY_RE.search(text)
    if match is None:
        return None
    # Drop JavaScript escape sequences (e.g. a literal ``\n``) before filtering,
    # otherwise their trailing letters survive as base64 characters.
    body = re.sub(r"\\[nrt]", "", match.group(1))
    return re.sub(r"[^A-Za-z0-9+/=]", "", body)


def local_public_key_body() -> str | None:
    return normalise_key_body(UTILS_PATH.read_text(encoding="utf-8"))


def extract_validate_key(html: str) -> str | None:
    match = VALIDATE_KEY_RE.search(html)
    return match.group(1).strip() if match else None


def record(ok: bool, name: str, detail: str = "") -> None:
    _checks.append((ok, name, detail))
    suffix = f" - {detail}" if detail else ""
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{suffix}")


def note(name: str, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"[info] {name}{suffix}")


def fetch(url: str, data: dict | None = None, timeout: int = 25):
    """Return (status, headers, body bytes). Follows redirects."""
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Origin": BASE,
            "Referer": LOGIN_PAGE,
        },
    )
    response = urllib.request.urlopen(request, timeout=timeout)
    with response:
        return response.status, dict(response.headers), response.read()


def check_login_page() -> None:
    try:
        status, _, body = fetch(LOGIN_PAGE)
    except Exception as exc:  # report anything as a failure
        record(False, "login page reachable", repr(exc))
        return

    html = body.decode("utf-8", "replace")
    record(status == 200, "login page reachable", f"http {status}")
    # The page is a JS app now, so the em_validatekey input is injected at
    # runtime. We can only assert structurally here; the bundle check below
    # confirms the mechanism still exists.
    key = extract_validate_key(html)
    if key:
        record(bool(UUID_RE.match(key)), "login page has an inline em_validatekey", key)


def check_captcha() -> None:
    try:
        rand = SystemRandom().random()
        status, headers, body = fetch(f"{CAPTCHA}{rand}")
    except Exception as exc:
        record(False, "captcha reachable", repr(exc))
        return

    content_type = headers.get("Content-Type", "")
    record(status == 200, "captcha reachable", f"http {status}")
    record(content_type.startswith("image/"), "captcha is an image", content_type or "<none>")
    record(len(body) > 200, "captcha payload is non-trivial", f"{len(body)} bytes")


def check_auth_endpoint() -> None:
    """The login POST must still answer with JSON carrying a ``Status`` field."""
    payload = {
        "userId": "",
        "password": "",
        "randNumber": "0",
        "identifyCode": "",
        "duration": "30",
        "authCode": "",
        "type": "Z",
        "secInfo": "",
    }
    try:
        status, _, body = fetch(AUTH_URL, data=payload)
    except Exception as exc:
        record(False, "authentication endpoint answers", repr(exc))
        return

    record(status == 200, "authentication endpoint answers", f"http {status}")
    try:
        parsed = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        record(False, "authentication returns JSON", "non-JSON body")
        return
    record("Status" in parsed, "authentication returns JSON with Status", f"Status={parsed.get('Status')!r}")


def check_bundles() -> None:
    """The served JS must still use our exact RSA key and the validatekey flow."""
    local_key = local_public_key_body()
    record(local_key is not None, "utils.py exposes a public key")

    key_ok = False
    validatekey_ok = False
    fetched_any = False

    for path in JS_BUNDLES:
        try:
            status, _, body = fetch(f"{BASE}{path}")
        except Exception as exc:
            note(f"could not fetch {path}", repr(exc))
            continue
        if status != 200:
            note(f"could not fetch {path}", f"http {status}")
            continue

        fetched_any = True
        text = body.decode("utf-8", "replace")
        if local_key and local_key in text.replace("\\n", ""):
            key_ok = True
        if "em_validatekey" in text:
            validatekey_ok = True

    record(fetched_any, "could fetch a JS bundle")
    record(key_ok, "login JS still uses our RSA public key", "key matches src/emtl/utils.py")
    record(validatekey_ok, "login JS still wires up em_validatekey")


def check_buy_page() -> None:
    """Informational: the hidden validatekey input only shows up once logged in."""
    try:
        status, _, body = fetch(BUY_PAGE)
    except urllib.error.HTTPError as exc:
        note("buy page", f"http {exc.code} (expected without a session)")
        return
    except Exception as exc:
        note("buy page", repr(exc))
        return

    html = body.decode("utf-8", "replace")
    key = extract_validate_key(html)
    if key:
        note("buy page exposes em_validatekey", key)
    else:
        note("buy page", f"http {status}, no inline em_validatekey (needs a session)")


def main() -> int:
    print(f"Checking upstream shape of {BASE}\n")
    check_login_page()
    check_captcha()
    check_auth_endpoint()
    check_bundles()
    check_buy_page()

    failures = [name for ok, name, _ in _checks if not ok]
    print()
    print(f"{len(_checks) - len(failures)}/{len(_checks)} checks passed")
    if failures:
        print("FAILED: " + ", ".join(failures))
        print(
            "The 18.cn web app likely changed. Re-check src/emtl/const.py (URLs),\n"
            "src/emtl/core.py::_get_em_validate_key and src/emtl/utils.py (RSA key)."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
