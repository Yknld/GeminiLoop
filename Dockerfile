# Use Python+Node base for OpenHands SDK
FROM nikolaik/python-nodejs:python3.12-nodejs22

WORKDIR /app

# Install Node.js and system dependencies for Playwright + Chromium + VNC
RUN apt-get update && apt-get install -y \
    curl xz-utils chromium chromium-driver \
    fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 \
    libnspr4 libnss3 libx11-6 libxcb1 libxcomposite1 \
    libxdamage1 libxext6 libxfixes3 libxrandr2 \
    xvfb x11vnc fluxbox novnc websockify \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js binary
RUN curl -fsSL https://nodejs.org/dist/v18.19.0/node-v18.19.0-linux-x64.tar.xz | \
    tar -xJ -C /usr/local --strip-components=1

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install uvx for OpenHands browser tool
RUN pip install uv
RUN uv tool install playwright
ENV PATH="/root/.local/bin:$PATH"
RUN uvx playwright install chromium --with-deps --no-shell

# Install Node dependencies
COPY package.json .
RUN npm install --production

# Also install Playwright via npx for our screenshot service
RUN npx playwright install chromium

# Copy application
COPY orchestrator ./orchestrator
COPY qa_browseruse_mcp ./qa_browseruse_mcp
COPY handler.py .

# Copy template files if they exist
COPY TEMPLATE_SUMMARY.md* ./
COPY template.html* ./
COPY openhandsprompt.txt* ./
COPY openhandsprompt.txt* ./

CMD ["python", "-u", "handler.py"]
