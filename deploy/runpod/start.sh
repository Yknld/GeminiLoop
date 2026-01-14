#!/bin/bash
#
# GeminiLoop RunPod Startup Script
#
# Starts:
# 1. Preview server (FastAPI on port 8080)
# 2. Optional: Xvfb + noVNC for visible browser (port 6080)
#

set -e

echo "=========================================="
echo "🚀 GeminiLoop RunPod Startup"
echo "=========================================="

# Check environment variables
if [ -z "$GOOGLE_AI_STUDIO_API_KEY" ]; then
    echo "⚠️  WARNING: GOOGLE_AI_STUDIO_API_KEY not set"
    echo "   The orchestrator will not work without it"
fi

# Set default environment variables
export RUNS_DIR="${RUNS_DIR:-/app/runs}"
export PREVIEW_PORT="${PREVIEW_PORT:-8080}"
export HEADLESS="${HEADLESS:-true}"
export VISIBLE_BROWSER="${VISIBLE_BROWSER:-0}"
export DISPLAY="${DISPLAY:-:99}"

echo ""
echo "Configuration:"
echo "  - Runs directory: $RUNS_DIR"
echo "  - Preview port: $PREVIEW_PORT"
echo "  - Headless mode: $HEADLESS"
echo "  - Visible browser: $VISIBLE_BROWSER"
echo "  - Display: $DISPLAY"
echo ""

# Create runs directory if it doesn't exist
mkdir -p "$RUNS_DIR"

# Start visible browser services if enabled
if [ "$VISIBLE_BROWSER" = "1" ]; then
    echo "🖥️  Starting visible browser services..."
    
    # Start Xvfb (X Virtual Frame Buffer)
    echo "   Starting Xvfb on $DISPLAY..."
    Xvfb $DISPLAY -screen 0 1440x900x24 -ac +extension GLX +render -noreset &
    XVFB_PID=$!
    echo "   Xvfb started (PID: $XVFB_PID)"
    
    # Wait for X server to start
    sleep 2
    
    # Start window manager (fluxbox)
    echo "   Starting Fluxbox window manager..."
    DISPLAY=$DISPLAY fluxbox &
    FLUXBOX_PID=$!
    echo "   Fluxbox started (PID: $FLUXBOX_PID)"
    
    # Start x11vnc (VNC server for X11)
    echo "   Starting x11vnc on port 5900..."
    x11vnc -display $DISPLAY -forever -shared -rfbport 5900 -passwd secret &
    X11VNC_PID=$!
    echo "   x11vnc started (PID: $X11VNC_PID)"
    
    # Wait for VNC server to start
    sleep 2
    
    # Start websockify (WebSocket proxy for noVNC)
    echo "   Starting websockify on port 6080..."
    websockify --web=/usr/share/novnc 6080 localhost:5900 &
    WEBSOCKIFY_PID=$!
    echo "   Websockify started (PID: $WEBSOCKIFY_PID)"
    
    # Wait for websockify to start
    sleep 2
    
    echo "   ✅ Visible browser services ready"
    echo "   📺 noVNC URL: http://localhost:6080/vnc.html"
    echo "   🔑 VNC Password: secret"
    echo ""
    
    # Set Playwright to use visible mode
    export HEADLESS=false
fi

# Start preview server in background
echo "📡 Starting preview server..."
python -m services.preview_server &
PREVIEW_PID=$!

echo "   Preview server PID: $PREVIEW_PID"
echo "   Preview URL: http://0.0.0.0:$PREVIEW_PORT"

# Wait a moment for server to start
sleep 3

# Check if preview server is running
if curl -sf http://localhost:$PREVIEW_PORT/health > /dev/null 2>&1; then
    echo "✅ Preview server is healthy"
else
    echo "❌ Preview server health check failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ GeminiLoop Ready"
echo "=========================================="
echo ""
echo "Services:"
echo "  - Preview Server: http://0.0.0.0:$PREVIEW_PORT"
echo "  - Health Check: http://0.0.0.0:$PREVIEW_PORT/health"
echo "  - List Runs: http://0.0.0.0:$PREVIEW_PORT/runs"

if [ "$VISIBLE_BROWSER" = "1" ]; then
    echo "  - Browser View (noVNC): http://0.0.0.0:6080/vnc.html"
    echo "    Password: secret"
fi

echo ""
echo "To run orchestrator:"
echo "  python -m orchestrator.main \"Your task description\""
echo ""
echo "=========================================="

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    
    if [ ! -z "$PREVIEW_PID" ]; then
        kill $PREVIEW_PID 2>/dev/null || true
        echo "   Preview server stopped"
    fi
    
    if [ "$VISIBLE_BROWSER" = "1" ]; then
        if [ ! -z "$WEBSOCKIFY_PID" ]; then
            kill $WEBSOCKIFY_PID 2>/dev/null || true
            echo "   Websockify stopped"
        fi
        
        if [ ! -z "$X11VNC_PID" ]; then
            kill $X11VNC_PID 2>/dev/null || true
            echo "   x11vnc stopped"
        fi
        
        if [ ! -z "$FLUXBOX_PID" ]; then
            kill $FLUXBOX_PID 2>/dev/null || true
            echo "   Fluxbox stopped"
        fi
        
        if [ ! -z "$XVFB_PID" ]; then
            kill $XVFB_PID 2>/dev/null || true
            echo "   Xvfb stopped"
        fi
    fi
    
    echo "✅ Cleanup complete"
    exit 0
}

# Register cleanup on exit
trap cleanup SIGTERM SIGINT EXIT

# Keep container running and monitor preview server
wait $PREVIEW_PID
