# RunPod Serverless Deployment

Convert your validated GeminiLoop setup to a serverless endpoint for production.

## Prerequisites

✅ **Pod testing complete** (you've done this!)  
✅ Docker Hub account (or other container registry)  
✅ RunPod account with credits  

---

## Step 1: Build Serverless Docker Image

### On Your Local Machine:

```bash
cd /Users/danielntumba/match-me/GeminiLoop

# Build the serverless image
docker build -f deploy/runpod/Dockerfile.serverless -t your-dockerhub-username/gemini-loop:serverless .

# Test locally first (optional)
docker run -e GOOGLE_AI_STUDIO_API_KEY=your_key \
  your-dockerhub-username/gemini-loop:serverless \
  python handler.py

# Push to Docker Hub
docker push your-dockerhub-username/gemini-loop:serverless
```

---

## Step 2: Create Serverless Endpoint on RunPod

### Via Web Interface:

1. Go to https://www.runpod.io/console/serverless
2. Click **"New Endpoint"**
3. Configure:
   - **Name**: gemini-loop-serverless
   - **Docker Image**: `your-dockerhub-username/gemini-loop:serverless`
   - **GPU**: NVIDIA RTX A4000 or A5000
   - **Container Disk**: 20 GB
   - **Volume**: 50 GB (persistent storage for runs)
   - **Max Workers**: 10
   - **Idle Timeout**: 5 seconds
   - **Execution Timeout**: 600 seconds (10 minutes)

4. Set Environment Variables:
   ```
   GOOGLE_AI_STUDIO_API_KEY=your_key
   HEADLESS=true
   OPENHANDS_MODE=mock
   RUNS_DIR=/runpod-volume/runs
   ```

5. Click **"Deploy"**

### Via RunPod CLI:

```bash
# Install RunPod CLI
pip install runpod

# Login
runpod config

# Deploy from config
runpod endpoint create --config runpod-config.json
```

---

## Step 3: Test the Endpoint

### Get Your Endpoint ID

From the RunPod console, copy your endpoint ID (looks like: `abc123def456`)

### Make a Test Request

```bash
# Set your endpoint ID and API key
export RUNPOD_ENDPOINT_ID=your_endpoint_id
export RUNPOD_API_KEY=your_runpod_api_key

# Make a test request
curl -X POST \
  https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/runsync \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "task": "Create a simple contact form with name, email, and message fields",
      "max_iterations": 2
    }
  }'
```

### Expected Response:

```json
{
  "id": "request-uuid",
  "status": "COMPLETED",
  "output": {
    "run_id": "20260114_051234_abc123",
    "status": "completed",
    "final_score": 85,
    "final_passed": true,
    "iterations": 2,
    "duration_seconds": 45.67,
    "preview_url": "http://...",
    "artifacts": {
      "report": "runs/.../report.json",
      "manifest": "runs/.../manifest.json",
      "view": "runs/.../view.html"
    },
    "screenshots": [
      "runs/.../screenshots/iter_1/desktop.png",
      "runs/.../screenshots/iter_2/desktop.png"
    ]
  }
}
```

---

## Step 4: Python Client

```python
import requests
import json

ENDPOINT_ID = "your_endpoint_id"
API_KEY = "your_runpod_api_key"

def run_gemini_loop(task: str, max_iterations: int = 2):
    """Run GeminiLoop via serverless endpoint"""
    
    url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "input": {
            "task": task,
            "max_iterations": max_iterations
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

# Test it
result = run_gemini_loop("Create a pricing page with 3 tiers")
print(f"Run ID: {result['output']['run_id']}")
print(f"Score: {result['output']['final_score']}/100")
print(f"Passed: {result['output']['final_passed']}")
```

---

## Step 5: Async Execution (Recommended for Long Tasks)

For tasks that might take longer:

```bash
# Async request
curl -X POST \
  https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/run \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "task": "Create a complex dashboard with charts",
      "max_iterations": 2
    }
  }'

# Returns: {"id": "job-uuid", "status": "IN_QUEUE"}

# Check status
curl https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/status/job-uuid \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}"
```

---

## Serverless vs Pod Comparison

| Feature | Pod | Serverless |
|---------|-----|------------|
| **Cost** | $0.79/hr (always) | $0.0004/sec (only when running) |
| **Cold Start** | None | ~10-30 seconds |
| **Scaling** | Manual | Auto (1000s workers) |
| **Idle Cost** | High | $0 |
| **SSH Access** | Yes | No |
| **Best For** | Testing, debugging | Production, scale |

---

## Pricing Estimate

### Serverless (Production)

**Per request:**
- Average runtime: 45 seconds
- Cost: 45 × $0.0004 = **$0.018 per run**

**1000 runs/day:**
- Daily: $18
- Monthly: $540

**With auto-scaling:**
- Handle 100 concurrent requests
- Zero idle costs
- Pay only for execution time

### Pod (Testing)

**Hourly:**
- Cost: $0.79/hour
- 24/7: $568/month

---

## Environment Variables (Serverless)

Set these in RunPod endpoint configuration:

```bash
# Required
GOOGLE_AI_STUDIO_API_KEY=your_key

# Optional
HEADLESS=true
OPENHANDS_MODE=mock
RUNS_DIR=/runpod-volume/runs
GITHUB_TOKEN=your_github_token (if using GitHub)
GITHUB_REPO=owner/repo (if using GitHub)
BASE_BRANCH=main
```

---

## Accessing Results

### Option 1: Download from Endpoint Response

```python
result = run_gemini_loop("Create quiz")
screenshots = result['output']['screenshots']

# Download each screenshot
for screenshot_path in screenshots:
    # Screenshots are in the persistent volume
    # You'll need to implement a download endpoint or use S3
    pass
```

### Option 2: Add S3 Upload

Update `handler.py` to upload artifacts to S3:

```python
import boto3

s3 = boto3.client('s3')

# After run completes
s3.upload_file(
    f"/runpod-volume/runs/{run_id}/artifacts/report.json",
    "your-bucket",
    f"runs/{run_id}/report.json"
)

# Return S3 URLs in response
response["artifacts_s3"] = {
    "report": f"s3://bucket/runs/{run_id}/report.json",
    "screenshots": [...]
}
```

### Option 3: Serve via Preview Server

Keep preview server running and return URLs:

```python
response["preview_url"] = f"https://your-domain.com/preview/{run_id}/"
response["view_url"] = f"https://your-domain.com/artifacts/{run_id}/view.html"
```

---

## Deployment Checklist

- [ ] Docker image built and tested
- [ ] Image pushed to Docker Hub
- [ ] RunPod endpoint created
- [ ] Environment variables configured
- [ ] Test request successful
- [ ] Async execution tested
- [ ] Monitoring set up
- [ ] Artifact storage configured (S3 or volume)
- [ ] Error handling tested
- [ ] Load testing done

---

## Monitoring

### View Logs

```bash
# Via RunPod CLI
runpod logs endpoint ${ENDPOINT_ID}

# Via API
curl https://api.runpod.ai/v2/${ENDPOINT_ID}/logs \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}"
```

### View Metrics

- Go to RunPod console
- Select your endpoint
- View metrics dashboard:
  - Request count
  - Success rate
  - Average duration
  - Queue depth
  - Worker utilization

---

## Scaling Configuration

### Auto-scaling Rules

```json
{
  "min_workers": 0,
  "max_workers": 10,
  "idle_timeout": 5,
  "scale_up_threshold": 2,
  "scale_down_threshold": 0
}
```

**Behavior:**
- 0 workers when idle (no cost)
- Spins up on first request (~10-30 sec cold start)
- Scales up when queue > 2
- Scales down after 5 sec idle
- Max 10 concurrent workers

---

## Advanced: Custom Domain

1. Deploy endpoint
2. Set up CloudFlare or similar
3. Point domain to RunPod endpoint
4. Enable HTTPS

```bash
# Example: gemini-loop.yourdomain.com
curl -X POST https://gemini-loop.yourdomain.com/run \
  -H "Authorization: Bearer ${API_KEY}" \
  -d '{"input": {"task": "..."}}'
```

---

## Troubleshooting

### Cold Start Too Slow

**Reduce image size:**
- Use multi-stage build
- Remove unnecessary dependencies
- Use pre-warmed base images

**Use warm pools:**
- Set `min_workers: 1` (costs more but instant start)

### Out of Memory

**Increase container disk:**
- 20 GB → 30 GB in endpoint config

**Optimize code:**
- Reduce screenshot sizes
- Limit trace logging
- Clean up temp files

### Timeout Issues

**Increase execution timeout:**
- 600 seconds → 900 seconds

**Or split into multiple steps:**
- Generation endpoint
- Evaluation endpoint
- Patch endpoint

---

## Cost Optimization

### 1. Use Spot Instances
Save 50-70% with spot pricing (may have interruptions)

### 2. Optimize Image Size
Smaller image = faster cold starts = lower costs

### 3. Batch Requests
Process multiple tasks in one invocation

### 4. Cache Results
Store and reuse evaluation results for similar tasks

---

## Next Steps

1. **Test on serverless** with simple tasks
2. **Enable GitHub integration** for production
3. **Add S3 storage** for artifacts
4. **Set up monitoring** and alerts
5. **Load test** with 100+ concurrent requests
6. **Optimize cold start** time
7. **Deploy to production**

---

## Summary

✅ **Handler created** - `handler.py` processes RunPod events  
✅ **Dockerfile optimized** - Fast cold starts  
✅ **Config ready** - `runpod-config.json`  
✅ **Auto-scaling** - 0 to 1000s workers  
✅ **Pay per use** - Only when executing  

**Your validated pod setup is now ready for serverless deployment!** 🚀

---

**Questions?** See [QUICKSTART.md](QUICKSTART.md) or ping in Discord.
