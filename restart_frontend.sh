#!/usr/bin/env bash
set -euo pipefail

echo "Restarting frontend server..."
echo ""

# Stop the frontend if it's running
if [ -f "frontend.pid" ]; then
    echo "Stopping existing frontend server..."
    ./stop_frontend.sh || true
    echo ""
    # Give it a moment to fully shut down
    sleep 2
else
    echo "Frontend is not currently running"
    echo ""
fi

# Start the frontend
echo "Starting frontend server..."
./start_frontend.sh

echo ""
echo "Frontend restart complete!"
echo ""
echo "Waiting 2 seconds for server to initialize..."
sleep 2
echo ""
echo "=== Frontend Log (logs/frontend.log) ==="
cat logs/frontend.log
