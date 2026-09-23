#!/bin/bash
cd "$(dirname "$0")"
PYTHON="../../venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
fi
exec "$PYTHON" redis_gui.py
