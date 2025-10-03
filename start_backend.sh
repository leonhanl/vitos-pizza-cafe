#!/usr/bin/env bash
set -euo pipefail

# 配置参数
HOST="0.0.0.0"
PORT=8000
MODULE="backend.api:app"

# 启动 Uvicorn
echo "Starting Uvicorn server on http://${HOST}:${PORT} ..."
uvicorn "$MODULE" \
    --reload \
    --host "$HOST" \
    --port "$PORT"
