FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers and system deps
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application source code
COPY . .

# Create data directories
RUN mkdir -p /app/data /app/data/cookies

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
