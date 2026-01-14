# Visible Browser Mode

Watch the browser during demos with noVNC!

## Overview

GeminiLoop includes an optional **visible browser mode** that allows you to watch Playwright interactions in real-time through a web browser using noVNC.

Perfect for:
- 🎥 Demos and presentations
- 🐛 Debugging browser interactions
- 👀 Understanding what the evaluator sees
- 📚 Training and education

## Architecture

```
┌─────────────────────────────────────────┐
│  RunPod Container                        │
├─────────────────────────────────────────┤
│                                          │
│  Xvfb (Virtual X Server)                │
│    ↓ DISPLAY=:99                        │
│  Chromium Browser (headed mode)         │
│    ↓                                     │
│  x11vnc (VNC Server)                    │
│    ↓ Port 5900                          │
│  websockify (WebSocket Proxy)           │
│    ↓ Port 6080                          │
└─────────────────────────────────────────┘
         ↓ HTTP
    Your Browser
    http://localhost:6080/vnc.html
```

## Setup

### Docker (Recommended)

The Dockerfile includes all necessary components:
- Xvfb (X Virtual Frame Buffer)
- x11vnc (VNC server)
- websockify (WebSocket proxy for noVNC)
- fluxbox (lightweight window manager)

```bash
# Build with visible browser support
docker build -f deploy/runpod/Dockerfile -t gemini-loop:visible .

# Run with visible browser enabled
docker run -p 8080:8080 -p 6080:6080 \
  -e GOOGLE_AI_STUDIO_API_KEY=your_key \
  -e VISIBLE_BROWSER=1 \
  gemini-loop:visible
```

### Local Setup (Optional)

For local development with visible browser:

```bash
# Install dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y xvfb x11vnc websockify fluxbox

# Or macOS (requires XQuartz)
brew install xquartz
# Note: macOS support is limited, Docker recommended

# Set environment variables
export VISIBLE_BROWSER=1
export DISPLAY=:99

# Start services manually
./deploy/runpod/start.sh
```

## Usage

### Enable Visible Browser

Set the environment variable:

```bash
export VISIBLE_BROWSER=1
```

Or in `.env`:
```
VISIBLE_BROWSER=1
```

### Access Browser View

Once the container starts, access noVNC at:

```
http://localhost:6080/vnc.html
```

**Password:** `secret`

### Run Orchestrator

```bash
# With visible browser
export VISIBLE_BROWSER=1
python -m orchestrator.main "Create a landing page"

# Watch the browser at:
# http://localhost:6080/vnc.html
```

## What You'll See

When visible browser mode is enabled, you'll see:

1. **Browser Window** - Chromium running in the virtual display
2. **Live Interactions** - Watch as the evaluator:
   - Navigates to pages
   - Clicks buttons
   - Fills forms
   - Resizes to mobile view
   - Takes screenshots

3. **Window Manager** - Fluxbox provides basic window management

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VISIBLE_BROWSER` | `0` | Set to `1` to enable |
| `DISPLAY` | `:99` | X display number |
| `HEADLESS` | `true` | Auto-set to `false` when visible mode enabled |

### VNC Settings

Default VNC configuration:
- **Port:** 6080 (HTTP/WebSocket)
- **VNC Port:** 5900 (internal)
- **Password:** `secret`
- **Resolution:** 1440x900x24

To change VNC password, edit `start.sh`:
```bash
x11vnc -display $DISPLAY -forever -shared -rfbport 5900 -passwd YOUR_PASSWORD
```

## Performance Impact

### Resource Usage

Visible browser mode adds minimal overhead:

| Component | Memory | CPU |
|-----------|--------|-----|
| Xvfb | ~20MB | < 5% |
| x11vnc | ~10MB | < 5% |
| websockify | ~15MB | < 5% |
| fluxbox | ~5MB | < 2% |
| **Total** | ~50MB | ~17% |

### Timing Impact

Browser interactions are ~5-10% slower in visible mode due to rendering overhead.

**Recommendation:** Use headless mode for production, visible mode for demos.

## Troubleshooting

### Cannot Connect to noVNC

**Check services are running:**
```bash
# Inside container
ps aux | grep -E "Xvfb|x11vnc|websockify"
```

**Check port mapping:**
```bash
docker ps
# Should show: 0.0.0.0:6080->6080/tcp
```

**Test VNC directly:**
```bash
curl http://localhost:6080
# Should return HTML
```

### Black Screen in noVNC

**Restart Xvfb:**
```bash
pkill Xvfb
Xvfb :99 -screen 0 1440x900x24 -ac +extension GLX +render -noreset &
```

**Check DISPLAY variable:**
```bash
echo $DISPLAY
# Should be :99
```

### Browser Not Visible

**Verify HEADLESS is false:**
```bash
echo $HEADLESS
# Should be 'false' when VISIBLE_BROWSER=1
```

**Check Playwright logs:**
```bash
# Look for "Browser launched in VISIBLE mode"
cat runs/*/artifacts/trace.jsonl | grep -i visible
```

### High Latency in noVNC

**Use quality settings:**
- Click settings icon in noVNC
- Reduce quality to "Low"
- Disable "View only" mode
- Enable "Clip to window"

## Security Notes

### Production Deployment

For production use:

1. **Change VNC password:**
   ```bash
   x11vnc -storepasswd YOUR_SECURE_PASSWORD ~/.vnc/passwd
   x11vnc -rfbauth ~/.vnc/passwd ...
   ```

2. **Use authentication:**
   ```bash
   # Add basic auth to websockify
   websockify --auth-plugin BasicHTTPAuth ...
   ```

3. **Enable SSL:**
   ```bash
   websockify --cert=/path/to/cert.pem --key=/path/to/key.pem ...
   ```

4. **Restrict access:**
   - Use firewall rules
   - VPN or SSH tunnel
   - IP whitelisting

### Demo Mode

Default password (`secret`) is fine for:
- Local development
- Private demos
- Internal presentations

## Examples

### Watch Quiz App Evaluation

```bash
# Start with visible browser
export VISIBLE_BROWSER=1
python -m orchestrator.main "Create a quiz app with 5 questions"

# In browser, go to:
http://localhost:6080/vnc.html

# Watch as evaluator:
# 1. Navigates to quiz
# 2. Clicks "Start" button
# 3. Clicks "Next" through questions
# 4. Tests mobile view
```

### Debug Failing Test

```bash
# Enable visible mode for debugging
export VISIBLE_BROWSER=1

# Run the failing test
python -m orchestrator.main "Create contact form"

# Watch browser to see what's failing
# - Does button exist?
# - Is it clickable?
# - Are there console errors?
```

### Demo for Stakeholders

```bash
# Start services
docker run -p 6080:6080 -p 8080:8080 \
  -e VISIBLE_BROWSER=1 \
  -e GOOGLE_AI_STUDIO_API_KEY=$API_KEY \
  gemini-loop:visible

# Share URL with stakeholders
# They can watch browser in real-time
```

## Alternatives

### Local X Display (macOS/Linux)

If you have a local X server:

```bash
# Use local display
export DISPLAY=:0
export HEADLESS=false

# No noVNC needed
python -m orchestrator.main "Your task"
```

### Screen Recording

Record browser activity:

```bash
# Inside container with Xvfb
export VISIBLE_BROWSER=1

# Record with ffmpeg
ffmpeg -video_size 1440x900 -framerate 25 -f x11grab -i :99 \
  -c:v libx264 -preset ultrafast output.mp4 &

# Run orchestrator
python -m orchestrator.main "Your task"

# Stop recording
pkill ffmpeg
```

### Screenshots Only

If you don't need live view:

```bash
# Use headless mode (default)
export VISIBLE_BROWSER=0

# Screenshots are still saved to:
# runs/<run_id>/artifacts/screenshots/
```

## Technical Details

### X Virtual Frame Buffer (Xvfb)

Xvfb provides a virtual X11 display:
- No physical display needed
- Runs in memory
- Full X11 protocol support

```bash
# Start Xvfb
Xvfb :99 -screen 0 1440x900x24 -ac +extension GLX +render -noreset
```

### x11vnc

VNC server for X11 displays:
- Shares X display over VNC protocol
- Port 5900 (standard VNC port)
- Password protected

```bash
# Start x11vnc
x11vnc -display :99 -forever -shared -rfbport 5900 -passwd secret
```

### websockify

WebSocket-to-TCP proxy:
- Converts VNC to WebSocket
- Enables browser access
- Includes noVNC HTML client

```bash
# Start websockify with noVNC
websockify --web=/usr/share/novnc 6080 localhost:5900
```

## Comparison

### Headless vs Visible

| Feature | Headless | Visible |
|---------|----------|---------|
| Memory | Low (~200MB) | Medium (~250MB) |
| CPU | Low | Medium (+17%) |
| Speed | Fast | Slightly slower |
| Debugging | Limited | Excellent |
| Demos | No | Yes |
| Production | ✅ Recommended | ❌ Not recommended |

## Summary

✅ **Easy to enable:** Just set `VISIBLE_BROWSER=1`  
✅ **Web-based viewing:** No VNC client needed  
✅ **Minimal overhead:** ~50MB RAM, ~17% CPU  
✅ **Perfect for demos:** Watch browser in real-time  
✅ **Debugging friendly:** See exactly what's happening  

**Use visible browser mode for demos and debugging, headless mode for production!**

---

## Quick Commands

```bash
# Enable visible browser
export VISIBLE_BROWSER=1

# Access browser view
open http://localhost:6080/vnc.html
# Password: secret

# Run orchestrator
python -m orchestrator.main "Your task"

# Disable visible browser
export VISIBLE_BROWSER=0
```

---

**Questions?** Check the [main README](README.md) or [RunPod Quick Start](README.md#runpod-quick-start)
