# Configuration

Metraj is configured through environment variables loaded from a `.env` file in the project root. The configuration system is built on Pydantic Settings, which automatically reads environment variables and validates their types.

Configuration is managed in `src/config.py` via the `Settings` class.

---

## Environment Variables

### API Keys

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | `""` (empty) | Your Anthropic API key for Claude. Required for AI features (classification, material mapping, validation). Obtain from [console.anthropic.com](https://console.anthropic.com/). Format: `sk-ant-api03-...` |

### Model Settings

| Variable | Required | Default | Description |
|---|---|---|---|
| `DEFAULT_MODEL` | No | `claude-sonnet-4-5-20250929` | The Claude model used for most agent tasks (classification, material mapping, validation). Claude Sonnet provides a good balance of speed and accuracy. |
| `EXPENSIVE_MODEL` | No | `claude-opus-4-5-20250929` | Reserved for tasks that require stronger reasoning. Not currently used in the default pipeline but available for future enhancements. |

The Classifier Agent overrides the default model and uses `claude-haiku-4-5-20251001` for classification tasks, as this is a simpler categorization task that benefits from Haiku's speed.

### Application Settings

| Variable | Required | Default | Description |
|---|---|---|---|
| `LOG_LEVEL` | No | `INFO` | Logging verbosity. Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Use `DEBUG` to see full AI request/response details including token usage. |
| `DEBUG` | No | `false` | Enable debug mode. When `true`, provides additional diagnostic information. |

### Path Settings

These are derived automatically from the project root and generally do not need to be changed:

| Setting | Default Value | Description |
|---|---|---|
| `project_root` | Auto-detected | Root directory of the project (parent of `src/`) |
| `data_dir` | `<project_root>/src/data` | Location of static data files (waste_factors.json, element_rules.json) |
| `output_dir` | `<project_root>/output` | Where generated BOQ reports are saved |
| `fixtures_dir` | `<project_root>/tests/fixtures` | Test fixture files |

---

## API Server Settings

The following settings are configured in `api/app.py`:

### CORS Origins

The API server allows cross-origin requests from the following origins by default:

```
http://localhost:3000
http://127.0.0.1:3000
```

These correspond to the Next.js development server. For production deployment, update the `allow_origins` list in `api/app.py` to include your production domain.

### Rate Limiting

| Setting | Value | Description |
|---|---|---|
| `RATE_LIMIT_UPLOADS` | 5 | Maximum number of file uploads per client IP |
| `RATE_LIMIT_WINDOW` | 60 seconds | Time window for rate limiting |

When the limit is exceeded, the API returns HTTP 429 (Too Many Requests).

### File Size Limit

| Setting | Value |
|---|---|
| Maximum upload size | 500 MB |

Files exceeding this limit receive HTTP 413 (Request Entity Too Large).

### Upload and Output Directories

| Directory | Path | Description |
|---|---|---|
| `uploads/` | Relative to working directory | Uploaded IFC files stored here with UUID filenames |
| `output/` | Relative to working directory | Generated reports stored here, organized by project ID |

---

## Frontend Settings

The Next.js frontend uses the following environment variables, configured in `frontend/.env.local`:

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL of the Metraj API server. Change this when deploying the backend to a different host or port. |

---

## Database Settings

Metraj uses SQLite for development and stores its database at `data/metraj.db` relative to the project root. The database is created automatically on first startup.

The database stores:
- Project metadata (ID, filename, status, creation date)
- Processing results (serialized as JSON)
- Language selection per project

Old projects are automatically cleaned up after 30 days on server startup.

For production deployment with PostgreSQL, see [Production Deployment](../deployment/production.md).

---

## Example .env File

```env
# Required
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# Optional: Model selection
DEFAULT_MODEL=claude-sonnet-4-5-20250929
EXPENSIVE_MODEL=claude-opus-4-5-20250929

# Optional: Logging
LOG_LEVEL=INFO
DEBUG=false
```

---

## Configuration Loading Order

1. Default values defined in the `Settings` class in `src/config.py`
2. Values from the `.env` file in the project root
3. System environment variables (override `.env` file values)

Environment variables are case-insensitive. The system uses `pydantic-settings` with no prefix -- variable names map directly to setting names.

If the `.env` file is missing, a warning is emitted at startup but the application will still attempt to run (AI features will fail without the API key).
