# Serverless Quick Start

Deploy GeminiLoop as a serverless endpoint in 10 minutes.

---

## 🚀 Quick Deploy (5 Steps)

### 1. Build Image

```bash
cd GeminiLoop

# Build serverless image
docker build -f deploy/runpod/Dockerfile.serverless -t yourusername/gemini-loop:serverless .

# Login to Docker Hub
docker login

# Push
docker push yourusername/gemini-loop:serverless
```

**Time:** ~10 minutes

---

### 2. Create Endpoint on RunPod

Go to: https://www.runpod.io/console/serverless

**Click:** "New Endpoint"

**Configure:**
- **Name:** `gemini-loop-prod`
- **Docker Image:** `yourusername/gemini-loop:serverless`
- **GPU:** NVIDIA RTX A4000
- **Container Disk:** 20 GB
- **Volume:** 50 GB
- **Max Workers:** 10
- **Idle Timeout:** 5 seconds
- **Execution Timeout:** 600 seconds

**Environment Variables:**
```
GOOGLE_AI_STUDIO_API_KEY=your_key
HEADLESS=true
OPENHANDS_MODE=mock
```

**Click:** "Deploy"

**Time:** ~2 minutes

---

### 3. Get Endpoint ID

After deployment, copy your endpoint ID from the console.

It looks like: `abc123def456789`

---

### 4. Test Request

```bash
# Set credentials
export RUNPOD_ENDPOINT_ID=abc123def456789
export RUNPOD_API_KEY=your_runpod_api_key

# Test request
curl -X POST \
  https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/runsync \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "task": "Create a landing page with hero section",
      "max_iterations": 2
    }
  }'
```

**Expected:** JSON response with run results (~45 seconds)

---

### 5. Verify Results

```bash
# Check response
# Should include:
# - run_id
# - final_score
# - final_passed
# - preview_url
# - artifacts paths
# - screenshots list
```

---

## 🎯 That's It!

You now have a serverless GeminiLoop endpoint that:
- ✅ Auto-scales from 0 to 1000s workers
- ✅ Costs $0 when idle
- ✅ Costs ~$0.018 per run when active
- ✅ Handles concurrent requests
- ✅ Returns complete results

---

## 📡 Using the API

### Python Client

```python
import requests

ENDPOINT_ID = "your_endpoint_id"
API_KEY = "your_runpod_api_key"

def generate_website(task: str):
    url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"input": {"task": task}}
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

# Use it
result = generate_website("Create a quiz app")
print(f"Score: {result['output']['final_score']}")
print(f"Passed: {result['output']['final_passed']}")
```

### JavaScript Client

```javascript
const ENDPOINT_ID = "your_endpoint_id";
const API_KEY = "your_runpod_api_key";

async function generateWebsite(task) {
  const response = await fetch(
    `https://api.runpod.ai/v2/${ENDPOINT_ID}/runsync`,
    {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        input: { task }
      })
    }
  );
  
  return await response.json();
}

// Use it
const result = await generateWebsite("Create contact form");
console.log(`Score: ${result.output.final_score}`);
```

---

## 💰 Pricing

### Serverless Costs (RTX A4000)

**Per request:**
- Average: 45 seconds
- Cost: ~$0.018

**Monthly estimates:**
- 1,000 runs: $18
- 10,000 runs: $180
- 100,000 runs: $1,800

**Plus:**
- Storage: $2/month per 100 GB

### vs Pod

**Pod (24/7):**
- $0.79/hour
- $568/month
- Always running

**Serverless wins if:**
- < 31,000 runs/month
- Variable workload
- Need auto-scaling

---

## 🔧 Advanced Configuration

### With GitHub Integration

```json
{
  "input": {
    "task": "Add dark mode toggle",
    "max_iterations": 2,
    "github_token": "ghp_your_token",
    "github_repo": "username/template",
    "base_branch": "main"
  }
}
```

**Response includes:**
```json
{
  "output": {
    "github_branch": "run/...",
    "github_branch_url": "https://github.com/..."
  }
}
```

### With Custom OpenHands Mode

```json
{
  "input": {
    "task": "Create admin panel",
    "openhands_mode": "local"
  }
}
```

---

## 📊 Monitoring

### Via RunPod Console

1. Go to your endpoint
2. View metrics:
   - Requests/minute
   - Success rate
   - Average duration
   - Queue depth
   - Worker count

### Via API

```bash
# Get endpoint stats
curl https://api.runpod.ai/v2/${ENDPOINT_ID} \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}"
```

---

## 🛡️ Best Practices

### 1. Use Secrets for API Keys

**Don't** pass API keys in request:
```json
{
  "input": {
    "google_api_key": "AIza..."  // ❌ DON'T DO THIS
  }
}
```

**Do** set as environment variable in endpoint config:
```
GOOGLE_AI_STUDIO_API_KEY=AIza...  // ✅ CORRECT
```

### 2. Handle Timeouts

```python
import requests

try:
    result = requests.post(url, json=payload, timeout=120)
except requests.Timeout:
    # Use async endpoint instead
    result = requests.post(async_url, json=payload)
    job_id = result.json()["id"]
    # Poll for results
```

### 3. Implement Retries

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential())
def generate_with_retry(task):
    return run_gemini_loop(task)
```

### 4. Cache Results

```python
import hashlib
import json

def generate_cached(task):
    cache_key = hashlib.md5(task.encode()).hexdigest()
    
    # Check cache
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Generate
    result = run_gemini_loop(task)
    
    # Cache for 1 hour
    redis.setex(cache_key, 3600, json.dumps(result))
    
    return result
```

---

## 🚨 Troubleshooting

### "Endpoint not found"

**Fix:** Check endpoint ID is correct

```bash
# List your endpoints
runpod endpoint list
```

### "Job timed out"

**Fix:** Increase execution timeout or use async

```bash
# Increase timeout in endpoint config: 600 → 900 seconds
```

### "Out of disk space"

**Fix:** Increase container disk or clean up

```bash
# In handler, add cleanup:
import shutil
shutil.rmtree(f"/runpod-volume/runs/{old_run_id}")
```

### "Cold start too slow"

**Fix:** Keep 1 warm worker or optimize image

```json
{
  "min_workers": 1  // Costs more but instant
}
```

---

## 🎉 Summary

**You've gone from pod testing to serverless production!**

✅ Pod validated infrastructure  
✅ Serverless handles production scale  
✅ Auto-scaling from 0 to 1000s  
✅ Pay only for execution  
✅ Full feature parity  

**Your serverless endpoint is ready for production traffic!** 🚀

---

## Quick Commands

```bash
# Build and push
docker build -f deploy/runpod/Dockerfile.serverless -t user/gemini-loop:serverless .
docker push user/gemini-loop:serverless

# Test request
curl -X POST https://api.runpod.ai/v2/${ENDPOINT_ID}/runsync \
  -H "Authorization: Bearer ${API_KEY}" \
  -d '{"input": {"task": "Create quiz"}}'

# Check status
runpod endpoint status ${ENDPOINT_ID}
```

---

**Ready to deploy?** Follow the 5 steps above!
