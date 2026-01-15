# GeminiLoop Live Monitoring Mode

Watch your GeminiLoop runs in real-time with the live monitoring interface!

## Features

- **Real-time Preview**: See the page updating as OpenHands edits it
- **Live Evaluation Feedback**: Watch Gemini's scores and feedback stream in
- **Progress Tracking**: Monitor iterations, phases, and logs live
- **Desktop & Mobile Views**: Switch between device previews
- **Event Stream**: Server-Sent Events (SSE) for instant updates

## Usage

### Option 1: Local Development

1. Start the live server:
```bash
python3 -m live_server
```

2. Open your browser to:
```
http://localhost:8080
```

3. Run your GeminiLoop task normally - events will stream to all connected clients

### Option 2: RunPod with Live Mode

The live server can run alongside your RunPod serverless handler.

#### Setup

1. Make sure your Dockerfile exposes port 8080:
```dockerfile
EXPOSE 8080
```

2. Start with live monitoring:
```bash
./start_with_live.sh
```

Or update your Dockerfile CMD:
```dockerfile
CMD ["bash", "start_with_live.sh"]
```

#### Access Live UI

If running on RunPod, you'll need to:
1. Expose port 8080 in your RunPod configuration
2. Access via: `http://your-runpod-ip:8080`

### Option 3: SSH Tunnel (for RunPod Pods)

If you're running on a RunPod pod, create an SSH tunnel:

```bash
# Forward RunPod port 8080 to your local machine
ssh -L 8080:localhost:8080 root@your-pod-ip -p your-ssh-port

# Then open in browser:
open http://localhost:8080
```

## What You'll See

### Header
- Connection status (🟢 Connected)
- Current run ID
- Task description

### Preview Panel
- Live iframe showing your page
- Toggle between desktop and mobile views
- Updates automatically when code changes

### Sidebar - Progress
- Current iteration number
- Live score updates
- Real-time feedback from evaluator
- Category breakdowns

### Sidebar - Live Log
- Timestamped log entries
- Color-coded phases (START, ITER, CODE, EVAL, PATCH, DONE)
- Scrolls automatically to latest

## Event Types

The live monitor receives these events:

- `run_start` - When a new run begins
- `iteration_start` - Start of each iteration
- `code_generated` - When OpenHands generates code
- `evaluation` - When Gemini evaluates the page
- `patch_applied` - When OpenHands applies a patch
- `run_complete` - When the run finishes
- `log` - General log messages

## Architecture

```
┌─────────────┐
│   Handler   │ ──(emits events)──┐
└─────────────┘                    │
                                   ▼
┌─────────────┐              ┌──────────┐
│ Orchestrator│ ──(events)──▶│  Event   │
└─────────────┘              │  Queue   │
                             └──────────┘
┌─────────────┐                    │
│ Live Server │◀─(SSE stream)──────┘
└─────────────┘
       │
       │ (HTTP)
       ▼
┌─────────────┐
│   Browser   │
│   (UI)      │
└─────────────┘
```

## Tips

1. **Multiple Viewers**: Multiple people can watch the same run simultaneously
2. **Reconnection**: The UI automatically reconnects if disconnected
3. **Performance**: Events are lightweight (< 1KB each)
4. **History**: Only shows live events (no replay of past runs)
5. **Preview Updates**: The preview iframe refreshes after code generation and patches

## Customization

### Change Port

Edit `live_server.py`:
```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)  # Change port here
```

### Add Custom Events

In your code:
```python
from orchestrator import events

events.emit_event("custom_event", {
    "my_data": "value"
})
```

Handle in the UI (`live_server.py` HTML):
```javascript
eventSource.addEventListener('custom_event', (e) => {
    const data = JSON.parse(e.data);
    // Handle your custom event
});
```

## Troubleshooting

### Can't Connect to Live Server

1. Check if port 8080 is open: `curl http://localhost:8080`
2. Check logs for live_server startup errors
3. Verify firewall allows port 8080

### Events Not Appearing

1. Make sure `orchestrator/events.py` is being imported
2. Check that event emissions are called (add logging)
3. Verify SSE connection in browser DevTools > Network

### Preview Not Loading

1. Check that files are being written to `/runpod-volume/runs/runs/{run_id}/site/`
2. Verify the preview path is correct
3. Try refreshing the preview manually

## Future Enhancements

- [ ] Add screenshot streaming (base64 encoded)
- [ ] Show diff viewer for code changes
- [ ] Add "replay mode" to watch past runs
- [ ] Multi-run dashboard
- [ ] Export video of run
- [ ] Add pause/resume controls

## Questions?

Check the main [README.md](README.md) or [POD_DEPLOYMENT.md](POD_DEPLOYMENT.md) for more info.
