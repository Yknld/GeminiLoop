#!/bin/bash
# RunPod Setup Script for GeminiLoop
# Run this ON the RunPod pod after SSH'ing in

set -e

echo "=================================="
echo "🚀 GeminiLoop RunPod Setup"
echo "=================================="
echo

# Get the directory where script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Working directory: $(pwd)"

# Check API key
echo
echo "🔑 Checking API key..."
if [ -z "$GOOGLE_AI_STUDIO_API_KEY" ]; then
    echo "❌ GOOGLE_AI_STUDIO_API_KEY not set!"
    echo "Please run: export GOOGLE_AI_STUDIO_API_KEY=your_key"
    exit 1
fi
echo "✅ API key is set"

# Build Docker image
echo
echo "🐳 Building Docker image (this takes ~5 minutes)..."
docker build -f deploy/runpod/Dockerfile -t gemini-loop:runpod .

echo
echo "✅ Docker image built!"

# Run container
echo
echo "🚀 Starting container..."

# Stop existing container if running
docker stop gemini-loop-test 2>/dev/null || true
docker rm gemini-loop-test 2>/dev/null || true

docker run -d \
  --name gemini-loop-test \
  -p 8080:8080 \
  -p 6080:6080 \
  -e GOOGLE_AI_STUDIO_API_KEY=$GOOGLE_AI_STUDIO_API_KEY \
  -v $(pwd)/runs:/app/runs \
  gemini-loop:runpod

echo "✅ Container started!"

# Wait for startup
echo
echo "⏳ Waiting for services to start..."
sleep 10

# Test health
echo
echo "🏥 Testing health endpoint..."
HEALTH=$(curl -s http://localhost:8080/health)

if echo "$HEALTH" | grep -q "healthy"; then
    echo "✅ Health check PASSED!"
    echo "$HEALTH"
else
    echo "❌ Health check FAILED!"
    echo "Logs:"
    docker logs gemini-loop-test
    exit 1
fi

# Success!
echo
echo "=================================="
echo "✅ Setup Complete!"
echo "=================================="
echo
echo "Container is running. Check logs:"
echo "  docker logs -f gemini-loop-test"
echo
echo "Test preview:"
echo "  curl http://localhost:8080/health"
echo
echo "Run smoke test:"
echo "  docker exec -it gemini-loop-test python3 /app/test_runpod.py"
echo
echo "=================================="
