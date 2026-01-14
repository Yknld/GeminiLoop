# Deploy RunPod Serverless from GitHub

Deploy GeminiLoop serverless endpoint directly from your GitHub repository.

---

## Step-by-Step Configuration

### 1. Configure GitHub Repository

On the RunPod "Configure GitHub Repository" page:

#### **Branch:**
```
main
```

#### **Dockerfile Path:**
```
deploy/runpod/Dockerfile.serverless
```

#### **Build Context:**
```
.
```
(This is the root of your repository)

---

### 2. Add GitHub Credentials

#### If Repository is Public:
- Select "No Credentials"
- Click "Next"

#### If Repository is Private:
1. Click "+ Add Credentials"
2. Generate a GitHub Personal Access Token:
   - Go to: https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Select scopes: `repo` (Full control of private repositories)
   - Copy the token
3. Paste token in RunPod
4. Click "Next"

---

### 3. Configure Endpoint Settings

#### **Basic Settings:**
- **Name:** `gemini-loop-prod`
- **GPU Type:** NVIDIA RTX A4000 or RTX A5000
- **Container Disk:** 20 GB
- **Volume Size:** 50 GB

#### **Scaling Settings:**
- **Min Workers:** 0
- **Max Workers:** 10
- **Idle Timeout:** 5 seconds
- **Execution Timeout:** 600 seconds (10 minutes)

#### **Environment Variables:**
Click "Add Environment Variable" for each:

```bash
GOOGLE_AI_STUDIO_API_KEY=your_actual_api_key_here
HEADLESS=true
OPENHANDS_MODE=mock
RUNS_DIR=/runpod-volume/runs
```

**Optional (for GitHub integration in runs):**
```bash
GITHUB_TOKEN=your_github_token
GITHUB_REPO=Yknld/GeminiLoop
BASE_BRANCH=main
```

---

### 4. Review and Deploy

1. Review all settings
2. Click "Deploy"
3. Wait for build to complete (~10-15 minutes first time)

---

## Expected Build Process

### Build Stages:
1. ✅ Clone repository from GitHub
2. ✅ Build Docker image using `deploy/runpod/Dockerfile.serverless`
3. ✅ Install Python dependencies
4. ✅ Install Node.js dependencies
5. ✅ Install Playwright + Chromium
6. ✅ Push image to RunPod registry
7. ✅ Deploy endpoint

### Build Time:
- **First build:** ~10-15 minutes
- **Subsequent builds:** ~5-8 minutes (cached layers)

---

## After Deployment

### Get Endpoint ID

From the RunPod console, copy your endpoint ID.

Example: `abc123def456789`

### Test the Endpoint

```bash
# Set credentials
export RUNPOD_ENDPOINT_ID=your_endpoint_id
export RUNPOD_API_KEY=your_runpod_api_key

# Make test request
curl -X POST \
  https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/runsync \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "task": "Create a simple contact form with validation",
      "max_iterations": 2
    }
  }'
```

### Expected Response (~45 seconds):

```json
{
  "id": "request-uuid",
  "status": "COMPLETED",
  "output": {
    "run_id": "20260114_123456_abc",
    "status": "completed",
    "final_score": 85,
    "final_passed": true,
    "iterations": 2,
    "duration_seconds": 43.2,
    "artifacts": {
      "report": "runs/.../report.json",
      "manifest": "runs/.../manifest.json"
    },
    "screenshots": [
      "runs/.../screenshots/iter_1/desktop.png",
      "runs/.../screenshots/iter_2/desktop.png"
    ]
  }
}
```

---

## Updating Your Deployment

### When You Push to GitHub:

1. Push changes to `main` branch
2. Go to RunPod console
3. Find your endpoint
4. Click "Rebuild"
5. Wait ~5-8 minutes
6. New version deployed automatically

### Or Auto-rebuild on Push:

RunPod can automatically rebuild when you push to GitHub:

1. In endpoint settings, enable "Auto Deploy"
2. Select branch: `main`
3. Every push to `main` triggers rebuild

---

## Troubleshooting Build Issues

### Build Failed: "Cannot find Dockerfile"

**Fix:** Check Dockerfile path is exactly:
```
deploy/runpod/Dockerfile.serverless
```

### Build Failed: "Permission denied"

**Fix:** Repository is private. Add GitHub credentials:
1. Generate token: https://github.com/settings/tokens
2. Scope: `repo`
3. Add to RunPod credentials

### Build Failed: "Out of memory"

**Fix:** Increase build resources in RunPod settings

### Build Takes Too Long

**Normal:** First build takes 10-15 minutes
**Subsequent builds:** Should be 5-8 minutes due to layer caching

---

## Configuration Summary

**For RunPod GitHub Deploy:**

| Setting | Value |
|---------|-------|
| Branch | `main` |
| Dockerfile Path | `deploy/runpod/Dockerfile.serverless` |
| Build Context | `.` |
| Container Disk | 20 GB |
| Volume | 50 GB |
| GPU | RTX A4000 |
| Max Workers | 10 |
| Idle Timeout | 5 seconds |
| Execution Timeout | 600 seconds |

**Environment Variables:**
- `GOOGLE_AI_STUDIO_API_KEY` (required)
- `HEADLESS=true`
- `OPENHANDS_MODE=mock`
- `RUNS_DIR=/runpod-volume/runs`

---

## Benefits of GitHub Deploy

✅ **No local Docker build** - Build happens in RunPod cloud  
✅ **Automatic updates** - Push to GitHub, rebuild endpoint  
✅ **Version control** - Every deploy tracked in git  
✅ **Easy rollback** - Redeploy from any commit  
✅ **Team collaboration** - Anyone with access can deploy  

---

## Next Steps After Deploy

1. ✅ Test with simple task
2. ✅ Test with GitHub integration enabled
3. ✅ Monitor first few runs
4. ✅ Set up async execution for long tasks
5. ✅ Implement error handling in your app
6. ✅ Add monitoring/alerting
7. ✅ Scale up max workers if needed

---

## Questions?

**Stuck on build?** Check RunPod logs in console  
**API errors?** Verify `GOOGLE_AI_STUDIO_API_KEY` is set  
**Want to test?** Use the curl command above  

**Your serverless endpoint is deploying from GitHub!** 🚀
