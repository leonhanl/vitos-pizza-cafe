#!/usr/bin/env bash
set -euo pipefail

PORT=5500
DIR=./frontend

# 起一个本地静态服务器到后台
python3 -m http.server "$PORT" --directory "$DIR" --bind 127.0.0.1 &
SERVER_PID=$!

# 清理：脚本被中断时关掉后台服务器
cleanup() { kill $SERVER_PID 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# 稍等片刻确保端口起来
sleep 1

# 打开正确端口的页面
open -a "Google Chrome" "http://localhost:${PORT}"

# 如果你希望脚本一直挂着直到 Ctrl+C：
wait $SERVER_PID
