FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright and Postgres
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY automation-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers and their system dependencies
RUN playwright install --with-deps chromium

# Copy the rest
COPY automation-worker/ ./automation-worker/
COPY shared/ ./shared/

# Add current directory to PYTHONPATH
ENV PYTHONPATH=/app

CMD ["python", "automation-worker/app/main.py"]
