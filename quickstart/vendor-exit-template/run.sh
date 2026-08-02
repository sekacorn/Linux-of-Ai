#!/usr/bin/env sh
set -eu

if command -v python3 >/dev/null 2>&1; then
  exec python3 run.py
fi

exec python run.py
