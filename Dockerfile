# ---- Base Stage: Python base image ----
FROM python:3.12-slim-bookworm AS base

# Set environment variables to reduce Python output and improve performance
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

WORKDIR /app

# ---- Dependencies Stage: Install Python dependencies ----
FROM base AS dependencies

# Copy uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

# Install minimal build dependencies with retry
RUN set -e; \
    for i in $(seq 1 3); do \
      apt-get update --fix-missing && \
      apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ca-certificates && \
      apt-get clean && \
      rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
      break || \
      if [ $i -lt 3 ]; then \
        echo "Attempt $i failed! Retrying in 5 seconds..."; \
        sleep 5; \
      fi; \
    done

# Copy only requirements files first to leverage Docker cache
COPY requirements.txt .
COPY pyproject.toml .

# Install Python dependencies with uv
RUN uv pip install --no-cache-dir -r requirements.txt --system

# ---- Playwright Stage: Prepare browser dependencies ----
FROM base AS playwright

# Install minimal Playwright dependencies with retry
RUN set -e; \
    for i in $(seq 1 3); do \
      apt-get update --fix-missing && \
      apt-get install -y --no-install-recommends \
        ca-certificates \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libglib2.0-0 \
        libnspr4 \
        libnss3 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        xvfb \
        libexpat1 \
        libatspi2.0-0 \
        libx11-6 \
        libxext6 && \
      apt-get clean && \
      rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
      break || \
      if [ $i -lt 3 ]; then \
        echo "Attempt $i failed! Retrying in 5 seconds..."; \
        sleep 5; \
      fi; \
    done

# Copy Python packages from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Download and install only Chromium without system dependencies
RUN mkdir -p /opt/pw-browsers && \
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers playwright install chromium

# ---- Final Stage: Runtime image ----
FROM playwright AS final

# Set browser path environment variable
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers

# Create necessary directories
RUN mkdir -p /app/scripts

# Copy application code
COPY ./scripts /app/scripts

# Set up a non-root user
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Entrypoint and command
ENTRYPOINT ["python"]
CMD ["scripts/main.py"]