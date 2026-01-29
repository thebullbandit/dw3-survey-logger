#!/usr/bin/env bash
set -e

if [ ! -d ".venv" ]; then
  echo "[DW3] Creating virtual environment..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi

python main.py
