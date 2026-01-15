"""
Live monitoring server for GeminiLoop
Provides real-time updates via Server-Sent Events (SSE)
"""
import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator, Dict, Any
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="GeminiLoop Live Monitor")

# Global event queue for broadcasting updates
event_queues: Dict[str, asyncio.Queue] = {}

# Store active runs
active_runs: Dict[str, Dict[str, Any]] = {}


@app.get("/")
async def root():
    """Serve the live monitor UI"""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>GeminiLoop Live Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: #1a1a1a;
            padding: 16px 24px;
            border-bottom: 1px solid #333;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            font-size: 20px;
            font-weight: 600;
            color: #fff;
        }
        .status {
            display: flex;
            gap: 16px;
            align-items: center;
            font-size: 14px;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #4ade80;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .main {
            display: grid;
            grid-template-columns: 1fr 400px;
            gap: 1px;
            background: #333;
            flex: 1;
            overflow: hidden;
        }
        .preview-panel {
            background: #1a1a1a;
            display: flex;
            flex-direction: column;
        }
        .preview-header {
            padding: 12px 16px;
            background: #222;
            border-bottom: 1px solid #333;
            display: flex;
            gap: 8px;
        }
        .view-toggle {
            padding: 6px 12px;
            background: #333;
            border: none;
            border-radius: 4px;
            color: #e0e0e0;
            cursor: pointer;
            font-size: 13px;
        }
        .view-toggle.active {
            background: #667eea;
            color: #fff;
        }
        .preview-container {
            flex: 1;
            background: #fff;
            position: relative;
            overflow: auto;
        }
        .preview-frame {
            width: 100%;
            height: 100%;
            border: none;
            background: #fff;
        }
        .sidebar {
            background: #1a1a1a;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .sidebar-section {
            border-bottom: 1px solid #333;
        }
        .section-header {
            padding: 12px 16px;
            background: #222;
            font-weight: 600;
            font-size: 13px;
            color: #a0a0a0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .section-content {
            padding: 16px;
        }
        .iteration-info {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        .stat {
            padding: 12px;
            background: #222;
            border-radius: 6px;
        }
        .stat-label {
            font-size: 11px;
            color: #888;
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        .stat-value {
            font-size: 24px;
            font-weight: 600;
            color: #fff;
        }
        .score { color: #4ade80; }
        .feedback {
            margin-top: 12px;
            padding: 12px;
            background: #222;
            border-radius: 6px;
            font-size: 13px;
            line-height: 1.6;
        }
        .log-panel {
            flex: 1;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .log-content {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
            font-family: 'Menlo', 'Monaco', monospace;
            font-size: 12px;
            line-height: 1.6;
        }
        .log-entry {
            margin-bottom: 8px;
            padding: 8px;
            background: #222;
            border-radius: 4px;
            border-left: 3px solid #667eea;
        }
        .log-time {
            color: #888;
            margin-right: 8px;
        }
        .log-phase {
            color: #667eea;
            font-weight: 600;
            margin-right: 8px;
        }
        .connecting {
            text-align: center;
            padding: 40px;
            color: #888;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔄 GeminiLoop Live Monitor</h1>
        <div class="status">
            <span class="status-dot"></span>
            <span id="connection-status">Connected</span>
            <span id="run-id"></span>
        </div>
    </div>
    
    <div class="main">
        <div class="preview-panel">
            <div class="preview-header">
                <button class="view-toggle active" onclick="setView('desktop')">🖥 Desktop</button>
                <button class="view-toggle" onclick="setView('mobile')">📱 Mobile</button>
            </div>
            <div class="preview-container">
                <iframe id="preview" class="preview-frame" src="about:blank"></iframe>
            </div>
        </div>
        
        <div class="sidebar">
            <div class="sidebar-section">
                <div class="section-header">Progress</div>
                <div class="section-content">
                    <div class="iteration-info">
                        <div class="stat">
                            <div class="stat-label">Iteration</div>
                            <div class="stat-value" id="iteration">-</div>
                        </div>
                        <div class="stat">
                            <div class="stat-label">Score</div>
                            <div class="stat-value score" id="score">-</div>
                        </div>
                    </div>
                    <div class="feedback" id="feedback">
                        Waiting for updates...
                    </div>
                </div>
            </div>
            
            <div class="sidebar-section log-panel">
                <div class="section-header">Live Log</div>
                <div class="log-content" id="log"></div>
            </div>
        </div>
    </div>
    
    <script>
        let currentView = 'desktop';
        let runId = null;
        
        function setView(view) {
            currentView = view;
            document.querySelectorAll('.view-toggle').forEach(btn => {
                btn.classList.toggle('active', btn.textContent.includes(view === 'desktop' ? 'Desktop' : 'Mobile'));
            });
            updatePreview();
        }
        
        function updatePreview() {
            if (runId) {
                const url = `/preview/${runId}/index.html`;
                document.getElementById('preview').src = url;
            }
        }
        
        function addLog(message, phase = '') {
            const logEl = document.getElementById('log');
            const time = new Date().toLocaleTimeString();
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.innerHTML = `<span class="log-time">${time}</span>${phase ? `<span class="log-phase">${phase}</span>` : ''}${message}`;
            logEl.appendChild(entry);
            logEl.scrollTop = logEl.scrollHeight;
        }
        
        // Connect to SSE stream
        const eventSource = new EventSource('/stream');
        
        eventSource.onopen = () => {
            document.getElementById('connection-status').textContent = 'Connected';
            addLog('Connected to live stream', 'SYSTEM');
        };
        
        eventSource.onerror = () => {
            document.getElementById('connection-status').textContent = 'Disconnected';
            addLog('Connection lost, reconnecting...', 'ERROR');
        };
        
        eventSource.addEventListener('run_start', (e) => {
            const data = JSON.parse(e.data);
            runId = data.run_id;
            document.getElementById('run-id').textContent = `Run: ${runId}`;
            addLog(`Started: ${data.task}`, 'START');
        });
        
        eventSource.addEventListener('iteration_start', (e) => {
            const data = JSON.parse(e.data);
            document.getElementById('iteration').textContent = data.iteration;
            addLog(`Iteration ${data.iteration} started`, 'ITER');
        });
        
        eventSource.addEventListener('code_generated', (e) => {
            const data = JSON.parse(e.data);
            addLog(`Code generated: ${data.files.join(', ')}`, 'CODE');
            updatePreview();
        });
        
        eventSource.addEventListener('evaluation', (e) => {
            const data = JSON.parse(e.data);
            document.getElementById('score').textContent = data.score;
            document.getElementById('feedback').textContent = data.feedback;
            addLog(`Score: ${data.score}/100 - ${data.passed ? '✅ PASSED' : '❌ FAILED'}`, 'EVAL');
        });
        
        eventSource.addEventListener('patch_applied', (e) => {
            const data = JSON.parse(e.data);
            addLog(`Patch applied: ${data.files.length} files modified`, 'PATCH');
            updatePreview();
        });
        
        eventSource.addEventListener('run_complete', (e) => {
            const data = JSON.parse(e.data);
            addLog(`Completed! Final score: ${data.final_score}/100`, 'DONE');
        });
        
        eventSource.addEventListener('log', (e) => {
            const data = JSON.parse(e.data);
            addLog(data.message, data.level);
        });
    </script>
</body>
</html>
    """)


async def event_stream(run_id: str) -> AsyncGenerator[str, None]:
    """Generate SSE events for a specific run"""
    queue = asyncio.Queue()
    event_queues[run_id] = queue
    
    try:
        while True:
            event = await queue.get()
            
            # Format as SSE
            event_type = event.get("type", "message")
            data = json.dumps(event.get("data", {}))
            
            yield f"event: {event_type}\ndata: {data}\n\n"
            
            # Stop if run is complete
            if event_type == "run_complete":
                break
                
    finally:
        del event_queues[run_id]


@app.get("/stream")
async def stream_events(request: Request):
    """SSE endpoint for live updates"""
    # For now, stream all events (could filter by run_id via query param)
    async def generate():
        queue = asyncio.Queue()
        # Add to a global broadcast queue
        broadcast_id = id(queue)
        event_queues[f"broadcast_{broadcast_id}"] = queue
        
        try:
            while True:
                if await request.is_disconnected():
                    break
                    
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event_type = event.get("type", "message")
                    data = json.dumps(event.get("data", {}))
                    yield f"event: {event_type}\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"
                    
        finally:
            del event_queues[f"broadcast_{broadcast_id}"]
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/preview/{run_id}/{path:path}")
async def serve_preview(run_id: str, path: str):
    """Serve preview files"""
    preview_path = Path(f"/runpod-volume/runs/runs/{run_id}/site") / path
    
    if not preview_path.exists():
        return HTMLResponse(content="<html><body><h1>Preview not yet available</h1></body></html>")
    
    content = preview_path.read_text()
    
    # Determine content type
    if path.endswith('.html'):
        return HTMLResponse(content=content)
    elif path.endswith('.css'):
        return HTMLResponse(content=content, media_type="text/css")
    elif path.endswith('.js'):
        return HTMLResponse(content=content, media_type="application/javascript")
    else:
        return HTMLResponse(content=content)


def broadcast_event(event_type: str, data: Dict[str, Any]):
    """Broadcast an event to all connected clients"""
    event = {"type": event_type, "data": data}
    
    # Send to all queues
    for queue in event_queues.values():
        try:
            queue.put_nowait(event)
        except:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
