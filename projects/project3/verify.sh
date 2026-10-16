#!/bin/sh
set -eu
cd "$(dirname "$0")"
.venv/bin/python -m pip check
.venv/bin/python -m unittest discover -s tests -v
