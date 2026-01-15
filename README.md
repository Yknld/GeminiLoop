# GeminiLoop

![GeminiLoop Architecture](assets/gemini-loop-architecture.svg)

**Architecture Overview:** GeminiLoop is a closed-loop agent system where Gemini generates code, Playwright MCP evaluates it in a real browser session, and the orchestrator iterates with fixes until evaluation passes. Each run creates an isolated workspace with all artifacts preserved for debugging and transparency.

## How It Works

The system combines four key components in a continuous feedback loop:

1. **GitHub Template (Optional)** - Clone template repository to workspace
2. **Gemini Code Generator** - Generates HTML/CSS/JS based on requirements
3. **Gemini-Controlled Browser QA** - Interactive testing with Playwright MCP
   - Tests functionality (buttons, forms, links)
   - Captures desktop (1440x900) and mobile (375px) screenshots
   - Collects console logs and DOM snapshots
   - Evaluates against 5-category rubric (functionality, UX, accessibility, responsiveness, robustness)
4. **Gemini Vision Evaluation** - Comprehensive analysis with structured feedback
   - Category scores (total: 100 points)
   - Detailed issues with severity and repro steps
   - Actionable fix suggestions
5. **OpenHands Integration** - Automatically applies patches when evaluation fails (score < 70)
6. **GitHub Integration (Optional)** - Track iterations in GitHub branches

Each run creates an isolated workspace and artifact store, with all screenshots, logs, evaluation data, and patch history preserved.

## 🔴 Live Monitoring (NEW!)

Watch your GeminiLoop runs in **real-time** with the live monitoring interface:

- 📺 **Real-time preview** - See the page update as OpenHands edits it
- 📊 **Live scores** - Watch Gemini evaluation feedback stream in
- 📝 **Progress logs** - Monitor every phase and iteration live
- 🖥️ 📱 **Device views** - Toggle between desktop and mobile previews

**Quick Start:**
```bash
# Start with live monitoring
python3 -m live_server

# Open browser to http://localhost:8080
# Run your task - watch it live!
```

See [LIVE_MODE.md](LIVE_MODE.md) for full setup and SSH tunnel instructions for RunPod.

## RunPod Quick Start

### Prerequisites

- RunPod account
- Google AI Studio API key ([Get one here](https://makersuite.google.com/app/apikey))

### Visible Browser Mode (Optional)

For demos, you can watch the browser in action via noVNC:

```bash
# Enable visible browser
docker run -p 8080:8080 -p 6080:6080 \
  -e GOOGLE_AI_STUDIO_API_KEY=your_key \
  -e VISIBLE_BROWSER=1 \
  gemini-loop

# Access browser view at:
# http://localhost:6080/vnc.html (password: secret)
```

See [VISIBLE_BROWSER.md](VISIBLE_BROWSER.md) for details.

### Option 1: Deploy to RunPod

1. **Create a new RunPod template:**
   - Go to RunPod Dashboard
   - Navigate to Templates
   - Click "New Template"

2. **Configure the template:**
   ```
   Container Image: python:3.11-slim
   Container Disk: 10 GB
   Expose HTTP Ports: 8080
   Environment Variables:
     GOOGLE_AI_STUDIO_API_KEY=your_api_key_here
   ```

3. **Deploy from this repository:**
   ```bash
   git clone https://github.com/yourusername/GeminiLoop.git /workspace
   cd /workspace/GeminiLoop
   bash deploy/runpod/start.sh
   ```

### Option 2: Build Docker Image

```bash
cd GeminiLoop

# Build the image
docker build -f deploy/runpod/Dockerfile -t gemini-loop:latest .

# Run locally
docker run -p 8080:8080 \
  -e GOOGLE_AI_STUDIO_API_KEY=your_api_key \
  -v $(pwd)/runs:/app/runs \
  gemini-loop:latest

# Push to Docker Hub (for RunPod)
docker tag gemini-loop:latest yourusername/gemini-loop:latest
docker push yourusername/gemini-loop:latest
```

### Option 3: Local Development

```bash
cd GeminiLoop

# Setup environment
cp .env.example .env
# Edit .env and add your GOOGLE_AI_STUDIO_API_KEY

# Install dependencies
pip install -r requirements.txt
npm install

# Install Playwright browsers
npx playwright install chromium

# Start preview server
python services/preview_server.py &

# Run orchestrator
python -m orchestrator.main "Create a beautiful landing page"
```

## Usage

### Run the Orchestrator

```bash
# Basic usage
python -m orchestrator.main "Create a todo app with add/delete functionality"

# The orchestrator will:
# 1. Generate code with Gemini
# 2. Test it with Playwright MCP
# 3. Evaluate with Gemini Vision
# 4. Iterate until passing (max 3 iterations)
```

### View Results

After running, check the preview server:

```bash
# List all runs
curl http://localhost:8080/runs

# View a specific run
curl http://localhost:8080/runs/<run_id>

# Preview generated site
open http://localhost:8080/preview/<run_id>/
```

### Folder Structure

Each run creates this structure:

```
runs/
  └── <run_id>/
      ├── workspace/       # Generated code workspace
      │   └── index.html
      ├── artifacts/       # Screenshots, logs, evaluations
      │   ├── screenshot_iter_1.png
      │   └── evaluation_iter_1.json
      ├── site/           # Served HTML files
      │   └── index.html
      └── state.json      # Run state and results
```

## API Endpoints

### Preview Server (Port 8080)

- `GET /` - Server info page
- `GET /health` - Health check
- `GET /runs` - List all runs
- `GET /runs/{run_id}` - Get run details
- `GET /preview/{run_id}/` - Serve generated site
- `GET /artifacts/{run_id}/{filename}` - Serve artifacts

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_AI_STUDIO_API_KEY` | **Required** - Google AI API key | - |
| `RUNS_DIR` | Directory for run data | `./runs` |
| `PREVIEW_PORT` | Preview server port | `8080` |
| `HEADLESS` | Run browser in headless mode | `true` |
| `OPENHANDS_MODE` | OpenHands mode (mock or local) | `mock` |
| `VISIBLE_BROWSER` | Enable noVNC browser view (0 or 1) | `0` |
| `GITHUB_TOKEN` | GitHub personal access token | - |
| `GITHUB_REPO` | Repository in owner/repo format | - |
| `BASE_BRANCH` | Base branch for creating run branches | `main` |

## Architecture

### Components

1. **orchestrator/main.py** - Main control loop
2. **orchestrator/gemini_generator.py** - Code generation with Gemini
3. **orchestrator/evaluator.py** - Quality evaluation with Gemini Vision
4. **orchestrator/mcp_real_client.py** - MCP protocol client (JSON-RPC 2.0)
5. **orchestrator/playwright_mcp_server.js** - Node.js Playwright MCP server
6. **orchestrator/run_state.py** - Run state management
7. **services/preview_server.py** - FastAPI preview server

### MCP Protocol

The system uses the Model Context Protocol (JSON-RPC 2.0 over stdio) for browser automation:

```
Python Orchestrator  <--JSON-RPC-->  Node.js MCP Server  <-->  Playwright/Chromium
```

This design allows the orchestrator to control a browser through a standardized protocol.

## Development

### Project Structure

```
GeminiLoop/
├── orchestrator/           # Core orchestrator code
│   ├── main.py            # Entry point
│   ├── gemini_generator.py
│   ├── evaluator.py
│   ├── mcp_real_client.py
│   ├── playwright_mcp_server.js
│   └── run_state.py
├── services/              # Web services
│   └── preview_server.py
├── deploy/                # Deployment configs
│   └── runpod/
│       ├── Dockerfile
│       └── start.sh
├── requirements.txt       # Python deps
├── package.json          # Node.js deps
└── README.md
```

### Running Tests

```bash
# Test MCP server directly
node orchestrator/playwright_mcp_server.js

# Test preview server
python services/preview_server.py

# Run full loop
python -m orchestrator.main "Test task"
```

## Future Enhancements

- [ ] GitHub integration (automated PR creation)
- [ ] OpenHands integration (full dev environment)
- [ ] noVNC support (browser visibility in RunPod)
- [ ] Multi-file project support
- [ ] Advanced evaluation criteria
- [ ] Webhook notifications
- [ ] Run history dashboard

## Troubleshooting

### "GOOGLE_AI_STUDIO_API_KEY not set"
Set the environment variable in your `.env` file or RunPod template.

### "MCP server closed connection"
Ensure Node.js is installed and `playwright_mcp_server.js` is executable.

### "Port 8080 already in use"
Change the port with `PREVIEW_PORT=8081` environment variable.

### Playwright installation issues
Run `npx playwright install --with-deps chromium` to install browsers.

## License

MIT

## Contributing

Contributions welcome! This is a demo-ready MVP, not production-perfect.

---

**Questions?** Open an issue or check the `/docs` folder for more details.
