#!/bin/sh
set -eu
cd "$(dirname "$0")"
P3_PYTHON="${P3_PYTHON:-/usr/local/bin/python3.11}"
"$P3_PYTHON" -c 'import sys; assert sys.version_info[:2] == (3,11), "Python 3.11 required"'
"$P3_PYTHON" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
exec .venv/bin/python -m p3.cli check
