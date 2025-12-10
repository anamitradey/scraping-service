FROM python:3.12-slim

# Prevent prompts etc.
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# System deps needed by Playwright/Chromium.
# (This list is the common baseline for Debian slim images.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    gnupg \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    && rm -rf /var/lib/apt/lists/*

# Install python deps first (better layer caching)
COPY scraper-c/requirements.txt .

# copy shared + service code
COPY common/ ./common/

RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser (Chromium) AFTER installing playwright package
RUN python -m playwright install chromium

# Copy app code
COPY scraper-c/ ./scraper-c/

ENV PYTHONPATH=/app
WORKDIR /app/scraper-c

# EXPOSE 8080

# Gunicorn (threads help when requests are I/O bound; Playwright is heavy, so don't go crazy)
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app", "--workers", "2", "--threads", "4", "--timeout", "120"]
# CMD ["python3", "poller.py"]
