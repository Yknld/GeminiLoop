# GeminiLoop RunPod Serverless Dockerfile
# 
# Optimized for serverless deployment with fast cold starts
# Based on RunPod's Python 3.11 base image
# Updated: 2026-01-14 - Fixed Node.js installation

FROM python:3.11-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    NODE_VERSION=18 \
    DISPLAY=:99

# Install system dependencies (full set for Playwright)
RUN set -ex && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    wget \
    git \
    xz-utils \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 && \
    rm -rf /var/lib/apt/lists/* && \
    echo "System dependencies installed successfully"

# Install Node.js 18 (using binary method for reliability)
RUN set -ex && \
    curl -fsSL https://nodejs.org/dist/v18.19.0/node-v18.19.0-linux-x64.tar.xz -o node.tar.xz && \
    tar -xJf node.tar.xz -C /usr/local --strip-components=1 && \
    rm node.tar.xz && \
    node --version && \
    npm --version && \
    echo "Node.js installed successfully"

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy and install Node.js dependencies
COPY package.json ./
RUN npm install --production

# Install Playwright with Chromium
RUN set -ex && \
    npx playwright install chromium && \
    npx playwright install-deps chromium && \
    echo "Playwright installed successfully"

# Copy application code
COPY orchestrator/ ./orchestrator/
COPY services/ ./services/
COPY handler.py ./

# Create runs directory on volume
RUN mkdir -p /runpod-volume/runs

# Expose port for preview server (if needed)
EXPOSE 8080

# Set the handler
CMD ["python", "-u", "handler.py"]
