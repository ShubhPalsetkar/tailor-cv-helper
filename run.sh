#!/usr/bin/env bash
# Tailor launcher for Mac and Linux. Run with:  ./run.sh
set -e
cd "$(dirname "$0")"
PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python is not installed. Get it from https://www.python.org/downloads/"
  exit 1
fi
if [ ! -d ".venv" ]; then
  echo "First run: setting things up. This takes a minute..."
  "$PY" -m venv .venv
fi
. .venv/bin/activate
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
python app.py
