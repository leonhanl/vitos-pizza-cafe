#!/usr/bin/env bash
set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
LOG_FILE="litellm.log"

# Remove old log file
rm -f "$LOG_FILE"

# Check if containers are already running
RUNNING_CONTAINERS=$(docker-compose ps --services --filter "status=running" 2>/dev/null || true)
if [ -n "$RUNNING_CONTAINERS" ]; then
    echo "LiteLLM containers are already running"
    echo "Please stop them first using ./stop_litellm.sh"
    echo ""
    echo "Current container status:"
    docker-compose ps
    exit 1
fi

echo "Starting LiteLLM proxy with Docker Compose..."
echo "Directory: $SCRIPT_DIR"
echo "Logs will be written to: $LOG_FILE"
echo ""
echo "To stop LiteLLM, run: ./stop_litellm.sh"
echo "To view logs in real-time, run: docker-compose logs -f"
echo "To view application logs, run: tail -f $LOG_FILE"
echo ""

# Start docker-compose services (uses default project name from directory)
docker-compose up -d 2>&1 | tee -a "$LOG_FILE"

# Wait a moment for services to initialize
sleep 2

# Check status
echo ""
echo "Container status:"
docker-compose ps

echo ""
echo "LiteLLM proxy started successfully!"
echo "API endpoint: http://localhost:4000"
echo "UI endpoint: http://localhost:4000/ui"
echo ""
echo "To check logs: docker-compose logs -f litellm"
echo ""

# Wait a moment for LiteLLM to be fully ready
echo "Waiting for LiteLLM to be ready..."
sleep 10

# Open Chrome browser to UI endpoint
echo "Opening LiteLLM UI in Chrome..."
open -a "Google Chrome" "http://localhost:4000/ui" 2>/dev/null || \
    open "http://localhost:4000/ui" 2>/dev/null || \
    echo "Could not open browser automatically. Please visit http://localhost:4000/ui manually."
