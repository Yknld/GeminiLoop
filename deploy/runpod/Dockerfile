# GeminiLoop RunPod Dockerfile
# 
# Multi-stage build for optimized container size
# Includes: Python 3.11, Node.js 18, Playwright with Chromium
# Optional: Xvfb + noVNC for visible browser mode

FROM python:3.11-slim as base

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    NODE_VERSION=18 \
    DISPLAY=:99

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    xvfb \
    x11vnc \
    websockify \
    fluxbox \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Verify installations
RUN python --version && node --version && npm --version

# Create app directory
WORKDIR /app

# Copy package files
COPY requirements.txt package.json ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies
RUN npm install

# Install Playwright browsers (Chromium only for smaller image)
RUN npx playwright install --with-deps chromium

# Copy application code
COPY orchestrator/ ./orchestrator/
COPY services/ ./services/
COPY deploy/runpod/start.sh ./start.sh

# Make start script executable
RUN chmod +x start.sh

# Create runs directory
RUN mkdir -p /app/runs

# Expose ports
# 8080 - Preview server
# 7860 - Optional API port
# 6080 - noVNC (visible browser mode)
EXPOSE 8080 7860 6080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start services
CMD ["./start.sh"]
