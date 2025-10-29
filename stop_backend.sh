#!/usr/bin/env bash
set -euo pipefail

PID_FILE="backend.pid"

# 检查 PID 文件是否存在
if [ ! -f "$PID_FILE" ]; then
    echo "Backend is not running (no PID file found)"
    exit 1
fi

# 读取 PID
PID=$(cat "$PID_FILE")

# 检查进程是否在运行
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "Backend process (PID $PID) is not running"
    echo "Cleaning up stale PID file..."
    rm -f "$PID_FILE"
    exit 1
fi

# 停止进程
echo "Stopping backend server (PID $PID)..."
kill "$PID"

# 等待进程结束
sleep 1

# 验证进程是否已停止
if ps -p "$PID" > /dev/null 2>&1; then
    echo "Process did not stop gracefully, forcing..."
    kill -9 "$PID" 2>/dev/null || true
    sleep 1
fi

# 清理 PID 文件
rm -f "$PID_FILE"

echo "Backend server stopped successfully"
