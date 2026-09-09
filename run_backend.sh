#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

echo "==================================================="
echo "Starting Supply Chain AI Decision-Intelligence Backend"
echo "==================================================="

if [ -d "venv" ]; then
    source venv/bin/activate
fi

export PYTHONPATH=.
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
