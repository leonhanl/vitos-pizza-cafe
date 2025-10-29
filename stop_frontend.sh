#!/usr/bin/env bash
set -euo pipefail

PID_FILE="frontend.pid"

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo "Frontend is not running (no PID file found)"
    exit 1
fi

# Read PID
PID=$(cat "$PID_FILE")

# Check if process is running
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "Frontend process (PID $PID) is not running"
    echo "Cleaning up stale PID file..."
    rm -f "$PID_FILE"
    exit 1
fi

# Stop process
echo "Stopping frontend server (PID $PID)..."
kill "$PID"

# Wait for process to end
sleep 1

# Verify process has stopped
if ps -p "$PID" > /dev/null 2>&1; then
    echo "Process did not stop gracefully, forcing..."
    kill -9 "$PID" 2>/dev/null || true
    sleep 1
fi

# Clean up PID file
rm -f "$PID_FILE"

echo "Frontend server stopped successfully"
