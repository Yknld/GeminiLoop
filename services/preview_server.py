#!/usr/bin/env python3
"""
Preview Server

Serves generated HTML sites at /preview/<run_id>/
Also provides API endpoints for orchestrator
"""

import os
from pathlib import Path
from typing import Optional
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="GeminiLoop Preview Server",
    description="Serves generated sites and provides orchestrator API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base directory for runs
RUNS_DIR = Path(os.getenv("RUNS_DIR", "./runs"))
RUNS_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/")
async def root():
    """Root endpoint"""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GeminiLoop Preview Server</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 16px;
            padding: 48px;
            max-width: 600px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            font-size: 32px;
            margin-bottom: 16px;
            color: #1a202c;
        }
        p {
            color: #4a5568;
            margin-bottom: 24px;
            line-height: 1.6;
        }
        .endpoints {
            background: #f7fafc;
            border-radius: 8px;
            padding: 24px;
            margin-top: 24px;
        }
        .endpoint {
            margin-bottom: 12px;
            font-family: 'Monaco', monospace;
            font-size: 14px;
        }
        .endpoint strong {
            color: #667eea;
        }
        .status {
            display: inline-block;
            background: #48bb78;
            color: white;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="container">
        <span class="status">● ONLINE</span>
        <h1>🚀 GeminiLoop Preview Server</h1>
        <p>Server is running and ready to serve generated sites.</p>
        
        <div class="endpoints">
            <div class="endpoint"><strong>GET</strong> /</div>
            <div class="endpoint"><strong>GET</strong> /health</div>
            <div class="endpoint"><strong>GET</strong> /runs</div>
            <div class="endpoint"><strong>GET</strong> /runs/{run_id}</div>
            <div class="endpoint"><strong>GET</strong> /preview/{run_id}/</div>
        </div>
    </div>
</body>
</html>
""")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "gemini-loop-preview",
        "version": "1.0.0"
    }


@app.get("/runs")
async def list_runs():
    """List all runs"""
    runs = []
    
    if not RUNS_DIR.exists():
        return {"runs": []}
    
    for run_dir in sorted(RUNS_DIR.iterdir(), reverse=True):
        if run_dir.is_dir():
            state_file = run_dir / "state.json"
            
            if state_file.exists():
                import json
                try:
                    state = json.loads(state_file.read_text())
                    runs.append({
                        "run_id": run_dir.name,
                        "task": state.get("task", "N/A"),
                        "score": state.get("score", 0),
                        "passed": state.get("passed", False),
                        "preview_url": f"/preview/{run_dir.name}/"
                    })
                except Exception as e:
                    logger.error(f"Error reading state for {run_dir.name}: {e}")
    
    return {"runs": runs, "count": len(runs)}


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get run details"""
    run_dir = RUNS_DIR / run_id
    
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    
    state_file = run_dir / "state.json"
    
    if not state_file.exists():
        raise HTTPException(status_code=404, detail="Run state not found")
    
    import json
    try:
        state = json.loads(state_file.read_text())
        return state
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading state: {e}")


@app.get("/preview/{run_id}/{filepath:path}")
async def serve_preview(run_id: str, filepath: str = "index.html"):
    """Serve generated site files"""
    
    # Default to index.html if no file specified
    if not filepath or filepath == "/":
        filepath = "index.html"
    
    # Construct path to file
    file_path = RUNS_DIR / run_id / "site" / filepath
    
    logger.info(f"Serving: {file_path}")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")
    
    # Security check: ensure file is within run directory
    try:
        file_path.resolve().relative_to(RUNS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(file_path)


@app.get("/artifacts/{run_id}/{filename}")
async def serve_artifact(run_id: str, filename: str):
    """Serve artifacts (screenshots, logs, etc.)"""
    
    file_path = RUNS_DIR / run_id / "artifacts" / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    # Security check
    try:
        file_path.resolve().relative_to(RUNS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(file_path)


def start_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the preview server"""
    logger.info(f"Starting preview server on {host}:{port}")
    logger.info(f"Runs directory: {RUNS_DIR.absolute()}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    start_server()
