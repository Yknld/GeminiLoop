# GeminiLoop - Quick Start Guide

Get running in 5 minutes.

## Prerequisites

- Python 3.11+
- Node.js 18+
- Google AI Studio API Key

## Local Setup

### 1. Clone and Navigate

```bash
cd GeminiLoop
```

### 2. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your API key
# GOOGLE_AI_STUDIO_API_KEY=your_actual_key_here
```

### 3. Install Dependencies

```bash
# Python dependencies
pip install -r requirements.txt

# Node.js dependencies
npm install

# Playwright browsers
npx playwright install chromium
```

### 4. Start Preview Server

```bash
# In one terminal
python services/preview_server.py
```

Server will start at http://localhost:8080

### 5. Run Orchestrator

```bash
# In another terminal
python -m orchestrator.main "Create a simple todo app"
```

### 6. View Results

Open http://localhost:8080/runs to see all runs, then click on a run to view the preview.

## RunPod Deployment

### Option 1: Using Docker

```bash
# Build image
docker build -f deploy/runpod/Dockerfile -t gemini-loop .

# Run container
docker run -p 8080:8080 \
  -e GOOGLE_AI_STUDIO_API_KEY=your_key \
  gemini-loop
```

### Option 2: Direct Deploy

1. Create RunPod Pod with Python 3.11 template
2. Clone this repo in the pod
3. Set environment variable: `GOOGLE_AI_STUDIO_API_KEY`
4. Run: `bash deploy/runpod/start.sh`

## Testing the Setup

### Test MCP Server

```bash
# This will start the Playwright MCP server
# You should see "Playwright MCP Server starting..."
node orchestrator/playwright_mcp_server.js
```

Press Ctrl+C to stop.

### Test Preview Server

```bash
# Start the preview server
python services/preview_server.py

# In another terminal, test the health endpoint
curl http://localhost:8080/health
```

Should return: `{"status":"healthy","service":"gemini-loop-preview","version":"1.0.0"}`

### Run a Simple Test

```bash
# This will run the full loop with a simple task
python -m orchestrator.main "Create a centered div with 'Hello World'"
```

Expected output:
```
🚀 GeminiLoop Orchestrator
============================
Task: Create a centered div with 'Hello World'
============================

📁 Run ID: 20260113_123456_abc12345
   Workspace: ./runs/20260113_123456_abc12345/workspace
   Artifacts: ./runs/20260113_123456_abc12345/artifacts
   Site: ./runs/20260113_123456_abc12345/site
   Preview: http://localhost:8080/preview/20260113_123456_abc12345/

... (generation, testing, evaluation)

🏁 FINAL RESULTS
============================
   Run ID: 20260113_123456_abc12345
   Iterations: 1
   Final score: 85/100
   Status: ✅ PASSED
   Preview: http://localhost:8080/preview/20260113_123456_abc12345/
```

## Common Issues

### "GOOGLE_AI_STUDIO_API_KEY not set"

Solution: Make sure you have a `.env` file with your API key, or export it:

```bash
export GOOGLE_AI_STUDIO_API_KEY=your_key_here
```

### "Module not found" errors

Solution: Install dependencies again:

```bash
pip install -r requirements.txt
npm install
```

### "Playwright not installed"

Solution: Install Playwright browsers:

```bash
npx playwright install --with-deps chromium
```

### Port 8080 already in use

Solution: Change the port:

```bash
export PREVIEW_PORT=8081
python services/preview_server.py
```

## Next Steps

- Check out the [README](README.md) for full documentation
- Explore the `/runs` directory to see generated artifacts
- Modify `orchestrator/main.py` to customize the loop
- Add your own evaluation criteria in `orchestrator/evaluator.py`

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    GeminiLoop System                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐      ┌──────────────┐                │
│  │   Gemini     │──1──>│   Generate   │                │
│  │  Generator   │      │     Code     │                │
│  └──────────────┘      └──────────────┘                │
│         │                      │                         │
│         │                      v                         │
│         │              ┌──────────────┐                 │
│         │              │  Save to     │                 │
│         │              │  Workspace   │                 │
│         │              └──────────────┘                 │
│         │                      │                         │
│         │                      v                         │
│         │              ┌──────────────┐                 │
│         └────────2────>│  Playwright  │                │
│                        │  MCP Server  │                 │
│                        │   (Browser)  │                 │
│                        └──────────────┘                 │
│                               │                          │
│                               v                          │
│                        ┌──────────────┐                 │
│                        │  Screenshot  │                 │
│                        │   Snapshot   │                 │
│                        └──────────────┘                 │
│                               │                          │
│                               v                          │
│  ┌──────────────┐      ┌──────────────┐                │
│  │   Gemini     │<─3───│   Evaluate   │                │
│  │  Evaluator   │      │    Quality   │                │
│  └──────────────┘      └──────────────┘                │
│         │                                                │
│         v                                                │
│  ┌──────────────┐                                       │
│  │  Pass/Fail?  │──Yes──> Done                         │
│  │   Decision   │                                       │
│  └──────────────┘                                       │
│         │                                                │
│         No (Iterate)                                     │
│         │                                                │
│         └────────────────────┐                          │
│                              │                           │
│  ┌──────────────┐      ┌────v─────────┐                │
│  │   Preview    │<─────│  Save State  │                │
│  │    Server    │      │  Artifacts   │                │
│  └──────────────┘      └──────────────┘                │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

Happy building! 🚀
