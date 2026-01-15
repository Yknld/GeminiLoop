# GeminiLoop RunPod Pod Deployment

Deploy GeminiLoop as a persistent RunPod pod with SSH access and API endpoint.

## Why Pod vs Serverless?

**Pod Benefits:**
- ✅ Persistent container (easier debugging)
- ✅ SSH access to troubleshoot
- ✅ See logs in real-time
- ✅ OpenHands CLI easier to verify
- ✅ Can test manually before API calls

## Deployment Steps

### 1. Build Docker Image

```bash
# From GeminiLoop directory
docker build -t your-dockerhub-username/gemini-loop:pod -f Dockerfile .
docker push your-dockerhub-username/gemini-loop:pod
```

### 2. Create Pod on RunPod

1. Go to [RunPod Console](https://www.runpod.io/console/pods)
2. Click **"Deploy"** → **"Pods"**
3. Select GPU type (or CPU if you want cheaper):
   - **CPU Pod**: Cheaper, sufficient for this workload
   - **GPU Pod**: Only needed if you want faster processing (not required)
4. Click **"Customize Deployment"**

### 3. Configure Pod

**Container Configuration:**
- **Container Image:** `your-dockerhub-username/gemini-loop:pod`
- **Container Disk:** 20 GB
- **Volume Disk:** 50 GB
- **Volume Mount Path:** `/runpod-volume`
- **Expose HTTP Ports:** `8080`
- **Expose TCP Port:** `22` (for SSH)

**Environment Variables:**
```
GOOGLE_AI_STUDIO_API_KEY=your_api_key_here
HEADLESS=true
OPENHANDS_MODE=local
RUNS_DIR=/runpod-volume/runs
```

**Docker Command:**
```bash
python -u /app/api_server.py
```

### 4. Access Pod

**Via Web Terminal:**
- Click on your pod → **"Connect"** → **"Start Web Terminal"**

**Via SSH:**
```bash
ssh root@<pod-ip> -p <ssh-port>
# Password will be shown in pod details
```

## Testing

### 1. Check OpenHands Installation

SSH into pod and run:
```bash
# Check if OpenHands package exists
python3 -c "import openhands; print('OpenHands installed')"

# Check for CLI
which openhands || echo "No openhands command"

# Try to run via Python module
python3 -m openhands.cli.entry --help
```

### 2. Test API Endpoint

```bash
curl -X POST http://<pod-ip>:8080/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Create a simple hello world page with a heading"
  }'
```

### 3. Monitor Logs

```bash
# In pod terminal
tail -f /runpod-volume/runs/*/artifacts/trace.jsonl
```

## Debugging OpenHands

If OpenHands isn't detected:

```bash
# Check Python environment
python3 -c "import sys; print('\n'.join(sys.path))"

# Check if OpenHands is in venv
/app/.venv/bin/python -c "import openhands; print(openhands.__file__)"

# Try running OpenHands directly
/app/.venv/bin/python -m openhands.cli.entry --help

# Check installed packages
pip list | grep openhands
```

## Cost Comparison

**Serverless:**
- Pay per second of execution
- No idle cost
- Cold starts (~10-30s)
- **Good for:** Sporadic usage

**Pod:**
- Pay per hour (even when idle)
- No cold starts
- Always ready
- **Good for:** Development, debugging, frequent usage

**Recommendation:** Use pod for development/debugging, serverless for production.

## Migration Path

1. **Develop on Pod:** Debug OpenHands, test workflows
2. **Once stable:** Deploy to serverless for production
3. **Keep pod running:** For quick testing/debugging

## Next Steps

After pod is running:
1. SSH in and verify OpenHands works
2. Test the orchestrator locally
3. Fix any issues with full access
4. Once working, migrate back to serverless if desired
