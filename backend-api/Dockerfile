FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY backend-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers and their system dependencies
RUN playwright install --with-deps chromium

# Copy the rest of the application
COPY backend-api/ ./backend-api/
COPY shared/ ./shared/

# Add current directory and backend-api to PYTHONPATH
ENV PYTHONPATH=/app:/app/backend-api

EXPOSE 8000

CMD ["uvicorn", "backend-api.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
