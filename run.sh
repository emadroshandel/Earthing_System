#!/usr/bin/env bash
cd "$(dirname "$0")"
python3 -c "import numpy" 2>/dev/null || python3 -m pip install --quiet numpy
exec python3 "${1:-server.py}"
