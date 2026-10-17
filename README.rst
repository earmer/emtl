========
Overview
========

.. start-badges

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs|
    * - tests
      - |github-actions| |codecov|
    * - package
      - |version| |wheel| |supported-versions| |supported-implementations| |commits-since|
.. |docs| image:: https://readthedocs.org/projects/emtl/badge/?style=flat
    :target: https://readthedocs.org/projects/emtl/
    :alt: Documentation Status

.. |github-actions| image:: https://github.com/riiy/emtl/actions/workflows/github-actions.yml/badge.svg
    :alt: GitHub Actions Build Status
    :target: https://github.com/riiy/emtl/actions

.. |codecov| image:: https://codecov.io/gh/riiy/emtl/branch/master/graphs/badge.svg?branch=master
    :alt: Coverage Status
    :target: https://app.codecov.io/github/riiy/emtl

.. |version| image:: https://img.shields.io/pypi/v/emtl.svg
    :alt: PyPI Package latest release
    :target: https://pypi.org/project/emtl

.. |wheel| image:: https://img.shields.io/pypi/wheel/emtl.svg
    :alt: PyPI Wheel
    :target: https://pypi.org/project/emtl

.. |supported-versions| image:: https://img.shields.io/pypi/pyversions/emtl.svg
    :alt: Supported versions
    :target: https://pypi.org/project/emtl

.. |supported-implementations| image:: https://img.shields.io/pypi/implementation/emtl.svg
    :alt: Supported implementations
    :target: https://pypi.org/project/emtl

.. |commits-since| image:: https://img.shields.io/github/commits-since/riiy/emtl/v0.2.6.svg
    :alt: Commits since latest release
    :target: https://github.com/riiy/emtl/compare/v0.2.6...master



.. end-badges

东方财富自动交易接口

* Free software: MIT license

Installation
============

::

    pip install emtl

You can also install the in-development version with::

    pip install https://github.com/riiy/emtl/archive/master.zip


Documentation
=============


https://emtl.readthedocs.io/


Development
===========

建议使用 Python 3.11+ 和 `uv <https://docs.astral.sh/uv/>`_。

Set up the environment and run the hermetic checks with::

    uv sync          # create .venv and install the project + dev tools
    uv run pytest    # run the unit tests
    uv run ruff check
    uv run black --check .

``uv sync --locked`` reproduces the exact versions in ``uv.lock``.

Tests are split in two:

* **Unit tests** (the default) are hermetic. They never touch the network and
  never need an account, so they run anywhere::

      uv run pytest

* **Live tests** talk to the real 18.cn service. They are skipped unless you
  opt in, and they need credentials::

      EMTL_LIVE=1 EM_USERNAME=... EM_PASSWORD=... uv run pytest -m live -k "not trade"

  Order tests additionally require ``EMTL_LIVE_TRADE=1`` because they place and
  cancel **real** orders. Never run them against an account you are not willing
  to trade with.

Because the client reverse-engineers a private web app, it can break without
any change here. A weekly `upstream-canary` workflow runs
``ci/upstream_check.py`` to detect that the app's RSA key, endpoints, captcha or
validatekey flow changed, and files an issue when it does::

    uv run --no-project python ci/upstream_check.py


Getting help
============


Join `Telegram group <https://t.me/em_trade_lib>`_. Asking a question here is often the quickest way to get a pointer in the right direction.
