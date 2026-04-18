# Docker Deployment

This guide covers deploying Metraj using Docker containers.

---

## Dockerfile (Backend)

Create a `Dockerfile` in the project root:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for IfcOpenShell
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY api/ api/

# Create directories for runtime data
RUN mkdir -p uploads output data

# Expose the API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Run the API server
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Building the Image

```bash
docker build -t metraj-api:latest .
```

---

## Running the Container

### Basic Run

```bash
docker run -d \
  --name metraj-api \
  -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-api03-your-key-here \
  metraj-api:latest
```

### With Persistent Volumes

To persist uploaded files, generated reports, and the database across container restarts:

```bash
docker run -d \
  --name metraj-api \
  -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-api03-your-key-here \
  -e LOG_LEVEL=INFO \
  -v metraj-uploads:/app/uploads \
  -v metraj-output:/app/output \
  -v metraj-data:/app/data \
  metraj-api:latest
```

---

## Environment Variables

Pass environment variables to the container using `-e` flags:

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | -- | Anthropic API key |
| `DEFAULT_MODEL` | No | `claude-sonnet-4-5-20250929` | Default Claude model |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `DEBUG` | No | `false` | Debug mode |

---

## Volumes

| Volume | Container Path | Description |
|---|---|---|
| `metraj-uploads` | `/app/uploads` | Uploaded IFC files |
| `metraj-output` | `/app/output` | Generated reports (Excel, CSV, JSON) |
| `metraj-data` | `/app/data` | SQLite database |

---

## Health Check

The container includes a built-in health check that polls the `/api/health` endpoint every 30 seconds. You can verify the container health:

```bash
docker inspect --format='{{.State.Health.Status}}' metraj-api
```

Or check directly:

```bash
curl http://localhost:8000/api/health
```

---

## Docker Compose

For deploying both backend and frontend together, use the following `docker-compose.yml`:

```yaml
version: "3.8"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: metraj-api
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DEFAULT_MODEL=${DEFAULT_MODEL:-claude-sonnet-4-5-20250929}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    volumes:
      - metraj-uploads:/app/uploads
      - metraj-output:/app/output
      - metraj-data:/app/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: metraj-frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://api:8000
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped

volumes:
  metraj-uploads:
  metraj-output:
  metraj-data:
```

### Frontend Dockerfile

Create `frontend/Dockerfile`:

```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --production=false

COPY . .
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
```

### Running with Docker Compose

Create a `.env` file in the project root with your API key:

```env
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

Then start both services:

```bash
docker compose up -d
```

Check status:

```bash
docker compose ps
docker compose logs -f api
```

Stop:

```bash
docker compose down
```

Stop and remove volumes:

```bash
docker compose down -v
```

---

## Updating

To update to a new version:

```bash
docker compose down
git pull
docker compose build
docker compose up -d
```

Data in volumes is preserved across rebuilds.

---

## Resource Considerations

| Resource | Recommendation |
|---|---|
| **RAM** | Minimum 2 GB. Large IFC files (100+ MB) may require 4+ GB during parsing. |
| **CPU** | 2 cores minimum. Parsing and calculation are CPU-bound. |
| **Disk** | Depends on IFC file sizes. Allow 2x the expected upload volume for temporary storage. |
| **Network** | Outbound HTTPS access to `api.anthropic.com` is required for AI features. |

---

## Troubleshooting Docker

### Container exits immediately

Check the logs:

```bash
docker logs metraj-api
```

Common causes:
- Missing `ANTHROPIC_API_KEY` (warning at startup, but should not crash)
- Port 8000 already in use (change the host port mapping)
- Missing `requirements.txt` or build errors

### IfcOpenShell installation fails during build

The `python:3.13-slim` image may not include all dependencies required by IfcOpenShell. If the build fails, try using the full `python:3.13` image instead of `python:3.13-slim`.

### Cannot connect to API from frontend container

When using Docker Compose, the frontend should use the service name `api` as the hostname (e.g., `http://api:8000`), not `localhost`. The `NEXT_PUBLIC_API_URL` environment variable handles this.

Note: `NEXT_PUBLIC_*` variables in Next.js are embedded at build time. If you need to change the API URL without rebuilding, you may need to use a runtime configuration approach.
