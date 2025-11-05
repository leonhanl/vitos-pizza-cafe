#!/usr/bin/env bash
set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if containers exist (running or stopped)
CONTAINER_IDS=$(docker-compose ps -q 2>/dev/null || true)
if [ -z "$CONTAINER_IDS" ]; then
    echo "LiteLLM containers are not running (no containers found)"
    exit 1
fi

echo "Stopping LiteLLM containers..."
echo ""

# Stop and remove containers (uses default project name from directory)
docker-compose down

# Verify containers are stopped
sleep 1

echo ""
echo "LiteLLM containers stopped successfully"
echo ""
echo "Note: Docker volumes are preserved. To remove volumes and data, run:"
echo "  docker-compose down -v"
