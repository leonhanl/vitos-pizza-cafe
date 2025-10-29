#!/usr/bin/env bash
set -euo pipefail

# Configuration parameters
HOST="0.0.0.0"
PORT=8000
MODULE="backend.api:app"
PID_FILE="backend.pid"

# Create logs directory
LOGS_DIR="logs"
mkdir -p "$LOGS_DIR"

# Generate timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${LOGS_DIR}/backend_${TIMESTAMP}.log"

# Check if process is already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Backend is already running with PID $OLD_PID"
        echo "Please stop it first using ./stop_backend.sh"
        exit 1
    else
        # Clean up stale PID file
        rm -f "$PID_FILE"
    fi
fi

# Start Uvicorn in background
echo "Starting Uvicorn server in background on http://${HOST}:${PORT} ..."
echo "Logs will be written to: $LOG_FILE"
echo "PID file: $PID_FILE"
echo ""
echo "To stop the server, run: ./stop_backend.sh"
echo "To view logs in real-time, run: tail -f $LOG_FILE"
echo ""

nohup uvicorn "$MODULE" \
    --reload \
    --host "$HOST" \
    --port "$PORT" \
    >> "$LOG_FILE" 2>&1 &

# Save process PID
echo $! > "$PID_FILE"

echo "Backend started successfully with PID $(cat $PID_FILE)"
