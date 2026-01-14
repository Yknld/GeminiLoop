#!/bin/bash
#
# Test Visible Browser Mode
#
# Quick script to test noVNC setup locally
#

echo "🧪 Testing Visible Browser Mode"
echo "================================"
echo ""

# Check if running in Docker
if [ -f /.dockerenv ]; then
    echo "✅ Running in Docker container"
else
    echo "ℹ️  Not in Docker (local test)"
fi

# Check required commands
echo "Checking required commands..."

commands=("Xvfb" "x11vnc" "websockify" "fluxbox")
all_found=true

for cmd in "${commands[@]}"; do
    if command -v $cmd &> /dev/null; then
        echo "  ✅ $cmd"
    else
        echo "  ❌ $cmd (not found)"
        all_found=false
    fi
done

if [ "$all_found" = false ]; then
    echo ""
    echo "❌ Missing dependencies. Install with:"
    echo "   sudo apt-get install -y xvfb x11vnc websockify fluxbox"
    echo ""
    echo "Or use Docker:"
    echo "   docker build -f deploy/runpod/Dockerfile -t gemini-loop ."
    echo "   docker run -p 6080:6080 -e VISIBLE_BROWSER=1 gemini-loop"
    exit 1
fi

echo ""
echo "✅ All dependencies found"
echo ""

# Test Xvfb
echo "Testing Xvfb..."
export DISPLAY=:99

# Kill existing Xvfb if running
pkill -9 Xvfb 2>/dev/null || true
sleep 1

# Start Xvfb
Xvfb :99 -screen 0 1440x900x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
sleep 2

if ps -p $XVFB_PID > /dev/null; then
    echo "  ✅ Xvfb running (PID: $XVFB_PID)"
else
    echo "  ❌ Xvfb failed to start"
    exit 1
fi

# Test x11vnc
echo ""
echo "Testing x11vnc..."

pkill -9 x11vnc 2>/dev/null || true
sleep 1

x11vnc -display :99 -forever -shared -rfbport 5900 -passwd secret > /tmp/x11vnc.log 2>&1 &
X11VNC_PID=$!
sleep 2

if ps -p $X11VNC_PID > /dev/null; then
    echo "  ✅ x11vnc running (PID: $X11VNC_PID)"
else
    echo "  ❌ x11vnc failed to start"
    cat /tmp/x11vnc.log
    kill $XVFB_PID 2>/dev/null
    exit 1
fi

# Test websockify
echo ""
echo "Testing websockify..."

pkill -9 websockify 2>/dev/null || true
sleep 1

# Check if noVNC files exist
if [ -d "/usr/share/novnc" ]; then
    NOVNC_PATH="/usr/share/novnc"
elif [ -d "/usr/local/share/novnc" ]; then
    NOVNC_PATH="/usr/local/share/novnc"
else
    echo "  ⚠️  noVNC files not found, websockify will run without web interface"
    NOVNC_PATH=""
fi

if [ -n "$NOVNC_PATH" ]; then
    websockify --web=$NOVNC_PATH 6080 localhost:5900 > /tmp/websockify.log 2>&1 &
else
    websockify 6080 localhost:5900 > /tmp/websockify.log 2>&1 &
fi

WEBSOCKIFY_PID=$!
sleep 2

if ps -p $WEBSOCKIFY_PID > /dev/null; then
    echo "  ✅ websockify running (PID: $WEBSOCKIFY_PID)"
else
    echo "  ❌ websockify failed to start"
    cat /tmp/websockify.log
    kill $X11VNC_PID $XVFB_PID 2>/dev/null
    exit 1
fi

# Test HTTP endpoint
echo ""
echo "Testing HTTP endpoint..."

sleep 2

if curl -sf http://localhost:6080 > /dev/null 2>&1; then
    echo "  ✅ HTTP endpoint responding"
else
    echo "  ❌ HTTP endpoint not responding"
    kill $WEBSOCKIFY_PID $X11VNC_PID $XVFB_PID 2>/dev/null
    exit 1
fi

# Test Playwright
echo ""
echo "Testing Playwright with visible browser..."

export VISIBLE_BROWSER=1
export HEADLESS=false

# Simple test script
cat > /tmp/test_playwright.js << 'EOF'
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({
    headless: false,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const page = await browser.newPage();
  await page.goto('data:text/html,<h1>Test Page</h1>');
  await page.waitForTimeout(3000);
  await browser.close();
  
  console.log('✅ Playwright test successful');
})();
EOF

node /tmp/test_playwright.js

echo ""
echo "================================"
echo "✅ All tests passed!"
echo "================================"
echo ""
echo "noVNC is now accessible at:"
echo "  http://localhost:6080/vnc.html"
echo ""
echo "Password: secret"
echo ""
echo "Press Ctrl+C to stop all services..."
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $WEBSOCKIFY_PID 2>/dev/null && echo "  ✅ websockify stopped"
    kill $X11VNC_PID 2>/dev/null && echo "  ✅ x11vnc stopped"
    kill $XVFB_PID 2>/dev/null && echo "  ✅ Xvfb stopped"
    echo "✅ Cleanup complete"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Keep script running
wait
