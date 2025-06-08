# Base image with Python 3.11
FROM python:3.11-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Configure APT for reliability with better mirrors
RUN echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/10no-check-valid-until \
    && echo 'Acquire::Check-Date "false";' > /etc/apt/apt.conf.d/10no-check-date \
    && echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/80retries \
    && echo 'Acquire::http::Pipeline-Depth "0";' > /etc/apt/apt.conf.d/90fix-hashsum \
    && echo 'Acquire::http::No-Cache "true";' >> /etc/apt/apt.conf.d/90fix-hashsum \
    && echo 'Acquire::BrokenProxy "true";' >> /etc/apt/apt.conf.d/90fix-hashsum

# Install only essential packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        wget \
        gnupg \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for better caching
COPY pyproject.toml ./

# Install Python dependencies
RUN uv pip install --system -e .

# Install Playwright
RUN uv pip install --system playwright

# Install Playwright browser dependencies manually with retries
RUN for i in 1 2 3; do \
        apt-get update && \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --fix-missing --no-install-recommends \
            libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
            libcups2 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxkbcommon0 \
            libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 libxshmfence1 \
            libx11-6 libxcb1 libxext6 libxfixes3 libexpat1 fonts-liberation \
            libvulkan1 xvfb && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/* && \
        break; \
    done

# Install Chromium browser  
RUN PLAYWRIGHT_BROWSERS_PATH=/app/pw-browsers python -m playwright install chromium

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy application code and change ownership
COPY --chown=appuser:appuser scripts/ ./scripts/

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/app/pw-browsers

# Default command
CMD ["python", "scripts/main.py"]