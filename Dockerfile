FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for IfcOpenShell and openpyxl
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ src/
COPY api/ api/
COPY tests/ tests/
COPY pyproject.toml .

# Create necessary directories
RUN mkdir -p uploads output data logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Run the API server
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
