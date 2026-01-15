FROM python:3.12-slim

# Copy uv from official image (recommended approach)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl wget git xz-utils ca-certificates \
    fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 \
    libnspr4 libnss3 libx11-6 libxcb1 libxcomposite1 \
    libxdamage1 libxext6 libxfixes3 libxrandr2 \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js
RUN curl -fsSL https://nodejs.org/dist/v18.19.0/node-v18.19.0-linux-x64.tar.xz | \
    tar -xJ -C /usr/local --strip-components=1

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install OpenHands using uv
RUN uv tool install --python 3.12 openhands-ai
ENV PATH="/root/.local/bin:$PATH"

# Install Node dependencies
COPY package.json .
RUN npm install --production

# Install Playwright
RUN npx playwright install chromium
RUN npx playwright install-deps chromium

# Copy application
COPY orchestrator ./orchestrator
COPY services ./services
COPY handler.py .

CMD ["python", "-u", "handler.py"]
