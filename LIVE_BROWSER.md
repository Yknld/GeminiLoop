# Live Browser Viewing

Watch the browser in real-time as it tests your page - see buttons being clicked, forms filled, and pages navigated!

## How It Works

1. **Xvfb** creates a virtual display inside the serverless container
2. **x11vnc** shares that display via VNC protocol
3. **ngrok** creates a public tunnel to the VNC server
4. You connect with any VNC viewer to watch live!

## Setup

### Step 1: Get an ngrok Auth Token

1. Sign up at [ngrok.com](https://ngrok.com) (free tier is fine)
2. Get your auth token from the dashboard
3. Add it to your RunPod endpoint as an environment variable:
   - Key: `NGROK_AUTH_TOKEN`
   - Value: `your_token_here`

### Step 2: Enable Live View in Your Request

Add `"enable_live_view": true` to your job input:

```bash
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
    -H 'Content-Type: application/json' \
    -H 'Authorization: Bearer YOUR_API_KEY' \
    -d '{
      "input": {
        "task": "Create a todo list with add/delete functionality",
        "enable_live_view": true
      }
    }'
```

### Step 3: Get the VNC URL from Response

The response will include a `live_view_url` field:

```json
{
  "run_id": "20260115_091112_4cfa92a1",
  "status": "completed",
  "live_view_url": "tcp://0.tcp.ngrok.io:12345",
  ...
}
```

### Step 4: Connect with a VNC Viewer

**On Mac:**
```bash
# Use built-in Screen Sharing
open vnc://0.tcp.ngrok.io:12345
```

**On Windows:**
- Download [TightVNC Viewer](https://www.tightvnc.com/)
- Connect to: `0.tcp.ngrok.io:12345`

**On Linux:**
```bash
# Use vncviewer
vncviewer 0.tcp.ngrok.io:12345
```

**In Browser (any OS):**
- Use [noVNC web client](https://novnc.com/noVNC/vnc.html)
- Server: `0.tcp.ngrok.io`
- Port: `12345`

## What You'll See

Once connected, you'll see a **1920x1080 desktop** with:
- The Chrome browser running your page
- Real-time interaction as Gemini tests it:
  - 🖱️ Buttons being clicked
  - ⌨️ Forms being filled
  - 📱 Window resizing (desktop → mobile)
  - 📸 Screenshots being captured
  - 🔍 Console being inspected

## Tips

### Timing
- Connect as soon as you get the VNC URL
- The session runs for the duration of the job (usually 1-3 minutes per iteration)
- The tunnel closes when the job completes

### Performance
- VNC uses very little bandwidth (~100KB/s)
- Works great even on slow connections
- Framerate adjusts automatically

### Recording
You can record the VNC session:

**On Mac:**
```bash
# Record with QuickTime Player
# File → New Screen Recording → Select VNC window
```

**On Windows/Linux:**
```bash
# Use VNC recording tools like vncrec
vncrec -record session.vnc 0.tcp.ngrok.io:12345
```

## Troubleshooting

### "Connection refused"
- Make sure you set `NGROK_AUTH_TOKEN` in RunPod
- Check that `enable_live_view: true` was in your request
- Verify the URL is correct (should start with `tcp://`)

### "Tunnel closed"
- The job may have finished already
- ngrok tunnels auto-close when the container stops
- Try submitting a new job

### Black screen
- Wait a few seconds for Xvfb to initialize
- The browser starts after MCP server initializes
- Try refreshing the VNC connection

### No interaction visible
- Make sure you're connected before the job starts iteration 2+
- Iteration 1 might be very fast
- Try a more complex task to see more interaction

## Cost

- **ngrok**: Free tier supports 1 TCP tunnel (perfect for this!)
- **RunPod**: No extra cost - VNC uses minimal CPU/memory
- **VNC viewer**: Free (all platforms)

## Security

- VNC has no password (runs inside isolated serverless container)
- ngrok URL is random and hard to guess
- Tunnel auto-closes after job completes
- No data persists after container shutdown

## Advanced: Persistent Tunnel

Want the tunnel to stay open between jobs? Use a persistent pod instead:

1. Deploy as a pod (not serverless)
2. Start ngrok in the pod's startup script
3. Get a fixed ngrok URL with a paid plan
4. Share the URL with your team for continuous monitoring

See [POD_DEPLOYMENT.md](POD_DEPLOYMENT.md) for pod setup.

## Future Ideas

- [ ] Add audio streaming (hear console errors!)
- [ ] Add remote control (pause/resume tests)
- [ ] Multi-view (watch desktop + mobile simultaneously)
- [ ] Stream to YouTube Live for demos
- [ ] Save VNC recordings to S3 automatically

## Questions?

- ngrok docs: https://ngrok.com/docs
- VNC protocol: https://en.wikipedia.org/wiki/Virtual_Network_Computing
- Playwright tracing: https://playwright.dev/docs/trace-viewer (alternative approach)
