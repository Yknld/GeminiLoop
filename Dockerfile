# Use the official OpenHands recommended base image (has both Python 3.12 and Node.js)
FROM nikolaik/python-nodejs:python3.12-nodejs22

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 \
    libnspr4 libnss3 libx11-6 libxcb1 libxcomposite1 \
    libxdamage1 libxext6 libxfixes3 libxrandr2 \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary for OpenHands installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install OpenHands CLI
RUN uv tool install openhands-ai
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
