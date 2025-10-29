#!/usr/bin/env bash
set -euo pipefail

PORT=5500
DIR=./frontend
PID_FILE="frontend.pid"

# Create logs directory
LOGS_DIR="logs"
mkdir -p "$LOGS_DIR"

# Generate timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${LOGS_DIR}/frontend_${TIMESTAMP}.log"

# Check if process is already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Frontend is already running with PID $OLD_PID"
        echo "Please stop it first using ./stop_frontend.sh"
        exit 1
    else
        # Clean up stale PID file
        rm -f "$PID_FILE"
    fi
fi

# Start HTTP server in background
echo "Starting frontend server in background on http://localhost:${PORT} ..."
echo "Logs will be written to: $LOG_FILE"
echo "PID file: $PID_FILE"
echo ""
echo "To stop the server, run: ./stop_frontend.sh"
echo "To view logs in real-time, run: tail -f $LOG_FILE"
echo ""

nohup python3 -m http.server "$PORT" --directory "$DIR" --bind 0.0.0.0 \
    >> "$LOG_FILE" 2>&1 &

# Save process PID
echo $! > "$PID_FILE"

echo "Frontend started successfully with PID $(cat $PID_FILE)"

# Wait a moment to ensure server is up
sleep 1

# Open browser
open -a "Google Chrome" "http://localhost:${PORT}"
