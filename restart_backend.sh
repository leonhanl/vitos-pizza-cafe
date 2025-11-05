#!/usr/bin/env bash
set -euo pipefail

echo "Restarting backend server..."
echo ""

# Stop the backend if it's running
if [ -f "backend.pid" ]; then
    echo "Stopping existing backend server..."
    ./stop_backend.sh || true
    echo ""
    # Give it a moment to fully shut down
    sleep 2
else
    echo "Backend is not currently running"
    echo ""
fi

# Start the backend
echo "Starting backend server..."
./start_backend.sh

echo ""
echo "Backend restart complete!"
echo ""
echo "Waiting 2 seconds for server to initialize..."
sleep 2
echo ""
echo "=== Backend Log (logs/backend.log) ==="
cat logs/backend.log
