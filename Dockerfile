# AegisAI Lightweight Production Dockerfile for Render Free Tier (512MB RAM)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NODE_ENV=production \
    PORT=3000

WORKDIR /app

# Install system dependencies (OpenCV GL libraries & Node.js 20)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgl1 \
    libglib2.0-0 \
    procps \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install CPU-only PyTorch first (saves 2GB RAM)
COPY api/requirements.txt ./api/requirements.txt
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r api/requirements.txt

# Install Node.js frontend dependencies
COPY package.json package-lock.json ./
RUN npm install --include=dev

# Copy application source code
COPY . .

# Build Next.js production bundle with telemetry disabled
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

EXPOSE 3000 5332

# Start production server
CMD ["npx", "concurrently", "-k", "-p", "[{name}]", "-c", "cyan.bold,yellow.bold", "-n", "NEXT,FLASK", "npm run start", "env PORT=5332 python api/app.py"]
