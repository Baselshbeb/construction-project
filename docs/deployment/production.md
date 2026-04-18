# Production Deployment

This document covers considerations and recommendations for deploying Metraj in a production environment.

---

## Architecture Overview

A production deployment typically consists of:

```
Internet -> Load Balancer -> Reverse Proxy (nginx) -> Uvicorn (API) + Next.js (Frontend)
                                                          |
                                                    PostgreSQL (DB)
                                                          |
                                                    S3 / Object Storage (Files)
```

---

## Database: PostgreSQL

The development SQLite database should be replaced with PostgreSQL for production.

### Why PostgreSQL

- Concurrent write support (SQLite locks the entire database for writes)
- Better performance under load
- Built-in backup and replication
- Connection pooling

### Migration Steps

1. Install the PostgreSQL driver:
   ```bash
   pip install asyncpg databases[postgresql]
   ```

2. Update the `Database` class in `src/services/database.py` to use PostgreSQL connection strings instead of aiosqlite

3. Set the database URL via environment variable:
   ```env
   DATABASE_URL=postgresql://user:password@host:5432/metraj
   ```

4. Run the schema migration (the `CREATE TABLE` SQL is compatible with PostgreSQL with minor type adjustments)

### Schema

```sql
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    filename    TEXT NOT NULL,
    upload_path TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'uploaded',
    language    TEXT NOT NULL DEFAULT 'en',
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result      JSONB,
    error       TEXT
);

CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_created ON projects(created_at);
```

---

## HTTPS / TLS

All production traffic must be encrypted with TLS.

### Option 1: TLS Termination at Reverse Proxy

Use nginx with a certificate from Let's Encrypt:

```nginx
server {
    listen 443 ssl http2;
    server_name metraj.example.com;

    ssl_certificate /etc/letsencrypt/live/metraj.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/metraj.example.com/privkey.pem;

    # API backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # File upload size limit
        client_max_body_size 500M;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 80;
    server_name metraj.example.com;
    return 301 https://$host$request_uri;
}
```

### Option 2: Cloud Load Balancer

Use AWS ALB, Google Cloud Load Balancer, or Azure Application Gateway with managed TLS certificates.

---

## Reverse Proxy (nginx)

The nginx configuration above handles:

- **TLS termination:** Encrypts traffic between clients and the server
- **WebSocket proxying:** Ensures the `/ws/` endpoint works correctly with connection upgrade headers
- **File upload limits:** The `client_max_body_size` must match or exceed the 500 MB limit in the API
- **Header forwarding:** Passes real client IP for rate limiting
- **HTTP to HTTPS redirect:** Ensures all traffic uses encryption

---

## Environment Variables

Production environment variables:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-api03-production-key

# Models
DEFAULT_MODEL=claude-sonnet-4-5-20250929
EXPENSIVE_MODEL=claude-opus-4-5-20250929

# Application
LOG_LEVEL=WARNING
DEBUG=false

# Database (if using PostgreSQL)
DATABASE_URL=postgresql://metraj:password@db-host:5432/metraj

# File storage (if using S3)
STORAGE_BACKEND=s3
S3_BUCKET=metraj-files
AWS_REGION=eu-west-1
```

**Security:** Never commit production environment variables to version control. Use secrets management (AWS Secrets Manager, HashiCorp Vault, Kubernetes secrets).

---

## File Storage

### Local Filesystem (Simple)

For single-server deployments, local filesystem storage is sufficient. Ensure:
- The `uploads/` and `output/` directories have adequate disk space
- Regular cleanup of old files (the 30-day auto-cleanup handles database records but not files)
- Appropriate file permissions

### Object Storage (S3)

For multi-server deployments or when durability is important:

1. Store uploaded IFC files in S3 after validation
2. Store generated reports in S3
3. Use presigned URLs for downloads instead of serving files through the API
4. Implement file cleanup using S3 lifecycle policies

This requires modifications to the upload handler in `api/app.py` and the download endpoint.

---

## Running Uvicorn in Production

Do not use `--reload` in production. Use multiple workers:

```bash
uvicorn api.app:app --host 0.0.0.0 --port 8000 --workers 4
```

Or use Gunicorn with Uvicorn workers:

```bash
gunicorn api.app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

**Note on workers and WebSocket:** WebSocket connections are stateful. If using multiple workers, you need a shared state mechanism (Redis pub/sub) for WebSocket progress updates. With a single worker, the current in-memory approach works.

---

## CORS Configuration

Update the CORS origins in `api/app.py` to include your production domain:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://metraj.example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Monitoring

### Health Check Endpoint

The `/api/health` endpoint checks:
- API server status
- Upload directory writability
- Available disk space
- API key configuration

Use this endpoint with your monitoring tool (Prometheus, Datadog, UptimeRobot) to detect outages.

### Logging

In production, set `LOG_LEVEL=WARNING` to reduce log volume. For debugging production issues, temporarily set `LOG_LEVEL=INFO` or `LOG_LEVEL=DEBUG`.

Consider shipping logs to a centralized logging service (ELK stack, Datadog, CloudWatch).

### Metrics to Monitor

| Metric | Source | Significance |
|---|---|---|
| API response time | Reverse proxy logs | Detect slow requests |
| Pipeline completion rate | Database (status counts) | Detect processing failures |
| Error rate | Application logs | Detect systematic issues |
| Disk usage | OS metrics | Prevent out-of-space failures |
| Claude API latency | Application logs (LLM service) | Detect API slowdowns |
| WebSocket connection count | Application metrics | Track concurrent users |

---

## Scaling

### Vertical Scaling

Increase server resources (CPU, RAM) for:
- Larger IFC file processing (parsing is memory-intensive)
- More concurrent pipeline runs

### Horizontal Scaling

For multiple API servers:
1. Use PostgreSQL (not SQLite) for shared state
2. Use S3 for shared file storage
3. Use Redis for WebSocket pub/sub across workers
4. Use a load balancer with session affinity for WebSocket connections

---

## Backup Strategy

### Database

- **PostgreSQL:** Use `pg_dump` for regular backups
- Schedule daily automated backups
- Test restore procedures regularly

### Files

- **Upload files:** Can be recreated by re-uploading (consider backup only if upload retention is needed)
- **Generated reports:** Can be regenerated from the IFC file (consider backup for convenience)

### Configuration

- Store `.env` template in version control (without secrets)
- Use secrets management for actual credentials
- Document all configuration in deployment runbooks

---

## Security Checklist

- [ ] TLS enabled for all traffic
- [ ] CORS restricted to production domain
- [ ] API key stored in secrets manager (not in code or plaintext files)
- [ ] File upload validation active (extension, size, magic bytes)
- [ ] Rate limiting configured appropriately for production traffic
- [ ] Authentication added to API endpoints (not included by default)
- [ ] Database credentials use strong passwords
- [ ] Server access restricted (SSH keys, security groups)
- [ ] Automated security updates enabled for OS packages
- [ ] Log monitoring configured for error detection
- [ ] Regular backup verification
- [ ] Disk space monitoring with alerts

---

## Authentication

The current API has no authentication. For production:

1. Add API key authentication for programmatic access
2. Add session-based authentication for the web interface
3. Consider OAuth2/OIDC integration for enterprise deployments
4. Protect the upload and download endpoints at minimum

This is the most critical gap for production readiness and should be addressed before public deployment.
