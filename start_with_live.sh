#!/bin/bash
# Start both the live monitoring server and the RunPod handler

echo "🚀 Starting GeminiLoop with Live Monitoring"

# Start the live server in the background
echo "📡 Starting live server on port 8080..."
python3 -m live_server &
LIVE_PID=$!

# Wait a moment for live server to start
sleep 2

# Start the RunPod handler
echo "🎯 Starting RunPod handler..."
python3 -u handler.py

# Cleanup on exit
trap "kill $LIVE_PID 2>/dev/null" EXIT
