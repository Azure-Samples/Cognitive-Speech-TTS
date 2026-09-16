#!/usr/bin/env sh
set -e
cd "$(CDPATH= cd "$(dirname "$0")/.." && pwd)"
python -m pip install -q -r requirements.txt
python provision_kb.py --require-azd-env
