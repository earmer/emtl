
Changelog
=========

Unreleased
----------

* Tests are now hermetic by default: ``emtl.core`` is exercised with fakes, so
  no account or network is required and CI can no longer place orders.
* Live integration tests moved to ``test_live.py`` and are opt-in via
  ``EMTL_LIVE`` (orders additionally need ``EMTL_LIVE_TRADE``).
* Added ``ci/upstream_check.py`` and a weekly ``upstream-canary`` workflow that
  checks whether the upstream 18.cn web app changed.
* Packaging moved to PEP 621 (``pyproject.toml``) and CI now runs on `uv`
  (``uv.lock``, Python 3.11-3.13). Dropped the unused ``rsa`` pin and raised the
  ``requests``/``ddddocr``/``cryptography`` floors; ``ddddocr`` 1.6.1 adds
  Python 3.12/3.13 support. ``requires-python`` is now ``>=3.11`` because
  ``onnxruntime`` no longer ships CPython 3.10 wheels. Added Dependabot and
  refreshed pre-commit.
* ``_check_resp`` now raises ``requests.HTTPError`` (with the response attached)
  instead of a bare ``raise``.
* The validate key is no longer written to the logs, the OCR engine is built
  lazily on first login, and captcha retries are bounded instead of recursing
  forever. Requests now carry a timeout.
* ``login`` fails fast with a clear error when no credentials are available and
  returns ``None`` when the server reports a non-ok ``Status``.
* The ``emt`` command line tool now actually logs in and runs the requested
  query or order instead of printing the username and password.
* Removed dead helpers ``double_equal`` and ``get_int`` and the unused
  ``query_positions`` URL.


0.1.0 (2024-04-14)
------------------

* First release on PyPI.

0.1.1 (2024-04-16)
------------------

* Delete python3.8 python3.9 pypy.

0.1.2 (2024-04-18)
------------------

* add login && add asset position

0.1.3 (2024-04-19)
------------------

* update docs theme

0.1.5 (2024-04-24)
------------------

* update login refrence

0.1.7 (2024-04-27)
------------------

* add insert order api


0.1.8 (2024-04-30)
------------------

* delete macos actions


0.2.0 (2024-05-21)
------------------

* complete all method


0.2.1 (2024-05-29)
------------------

* add auto deploy to pypi


0.2.2 (2024-07-11)
------------------

* replace insert_order with create_order
