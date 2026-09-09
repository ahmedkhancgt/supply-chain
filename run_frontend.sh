#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT/frontend"

echo "==================================================="
echo "Starting Supply Chain Control Tower Frontend UI"
echo "==================================================="

if [ ! -d "node_modules" ]; then
    echo "Installing Frontend Dependencies..."
    npm install
fi

npm run dev
