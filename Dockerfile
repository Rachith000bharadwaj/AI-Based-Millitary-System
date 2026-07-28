# AegisAI Production Unified Dockerfile for Render Web Service
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
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python backend dependencies
COPY api/requirements.txt ./api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

# Install Node.js frontend dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy application source code
COPY . .

# Build Next.js production bundle
RUN npm run build

EXPOSE 3000 5332

# Start both Next.js and Python Flask backend concurrently
CMD ["npx", "concurrently", "-k", "-p", "[{name}]", "-c", "cyan.bold,yellow.bold", "-n", "NEXT,FLASK", "npm run start", "python api/app.py"]
