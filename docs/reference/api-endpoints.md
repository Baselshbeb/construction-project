# API Endpoints Reference

The Metraj API is built with FastAPI and runs on Uvicorn. The base URL for local development is `http://localhost:8000`.

API version: 0.5.0

---

## REST Endpoints

### Health Check

```
GET /api/health
```

Verifies that the API server and its dependencies are operational.

**Response (200 OK):**

```json
{
  "status": "ok",
  "service": "Metraj AI",
  "version": "0.5.0",
  "checks": {
    "api": "ok",
    "uploads_writable": "ok",
    "disk_free_gb": "45.2",
    "disk_space": "ok",
    "api_key_configured": "ok"
  }
}
```

**Check details:**

| Check | Values | Description |
|---|---|---|
| `api` | `ok` | API server is running |
| `uploads_writable` | `ok` / `error` | Upload directory is writable |
| `disk_free_gb` | Number | Free disk space in GB |
| `disk_space` | `ok` / `warning` | Warning if less than 1 GB free |
| `api_key_configured` | `ok` / `missing` | Whether ANTHROPIC_API_KEY is set |

The top-level `status` is `"ok"` if all checks pass, or `"degraded"` if any check fails.

**curl example:**

```bash
curl http://localhost:8000/api/health
```

---

### Upload IFC File

```
POST /api/projects/upload
```

Upload an IFC file and start the processing pipeline. The pipeline runs asynchronously in the background.

**Parameters:**

| Parameter | Type | Location | Required | Description |
|---|---|---|---|---|
| `file` | File | Form data | Yes | The IFC file to process. Must have `.ifc` extension. |
| `language` | String | Query | No | Output language: `en` (default), `tr`, or `ar`. Must match pattern `^(en|tr|ar)$`. |

**Constraints:**

- Maximum file size: 500 MB
- File must have `.ifc` extension
- File must begin with `ISO-10303-21` magic bytes (valid IFC/STEP format)
- Rate limited: 5 uploads per 60 seconds per client IP

**Response (200 OK):**

```json
{
  "project_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "filename": "building.ifc",
  "status": "processing",
  "message": "File uploaded. Connect to WebSocket for progress updates."
}
```

**Error Responses:**

| Code | Condition | Message |
|---|---|---|
| 400 | No file provided | "No file provided" |
| 400 | Wrong extension | "Only .ifc files are supported" |
| 400 | Invalid IFC content | "Invalid IFC file. File does not appear to be a valid IFC/STEP file." |
| 413 | File too large | "File too large. Maximum size is 500 MB." |
| 429 | Rate limited | "Too many uploads. Max 5 per 60s." |

**curl example:**

```bash
curl -X POST http://localhost:8000/api/projects/upload \
  -F "file=@building.ifc" \
  -G -d "language=en"
```

---

### List Projects

```
GET /api/projects
```

Returns all projects ordered by creation date (newest first).

**Response (200 OK):**

```json
{
  "projects": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "filename": "building.ifc",
      "status": "completed",
      "created_at": "2026-04-18T10:30:00.000000"
    },
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "filename": "house.ifc",
      "status": "processing",
      "created_at": "2026-04-18T09:15:00.000000"
    }
  ]
}
```

**curl example:**

```bash
curl http://localhost:8000/api/projects
```

---

### Get Project Details

```
GET /api/projects/{project_id}
```

Returns full details for a specific project, including processing results if completed.

**Parameters:**

| Parameter | Type | Location | Required | Description |
|---|---|---|---|---|
| `project_id` | String (UUID) | Path | Yes | The project ID returned from upload |

**Response (200 OK -- completed):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "filename": "building.ifc",
  "upload_path": "uploads/a1b2c3d4-e5f6-7890-abcd-ef1234567890.ifc",
  "status": "completed",
  "language": "en",
  "created_at": "2026-04-18T10:30:00.000000",
  "result": {
    "building_info": {
      "project_name": "Office Building",
      "building_name": "Main Tower",
      "storeys": ["Foundation", "Ground Floor", "First Floor"],
      "schema_version": "IFC4"
    },
    "classified_elements": {
      "external_walls": 24,
      "internal_walls": 18,
      "frame": 32,
      "upper_floors": 6,
      "doors": 15,
      "windows": 20
    },
    "material_count": 28,
    "materials": [...],
    "boq_data": {...},
    "boq_file_paths": {
      "xlsx": "output/a1b2c3d4/building_BOQ.xlsx",
      "csv": "output/a1b2c3d4/building_BOQ.csv",
      "json": "output/a1b2c3d4/building_BOQ.json"
    },
    "validation_report": {
      "checks": {...},
      "passed": 8,
      "total": 8,
      "score": "8/8",
      "status": "PASS"
    },
    "warnings": [],
    "errors": [],
    "element_count": 115
  },
  "error": null
}
```

**Error Responses:**

| Code | Condition | Message |
|---|---|---|
| 404 | Project not found | "Project not found" |

**curl example:**

```bash
curl http://localhost:8000/api/projects/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

### Reprocess Project

```
POST /api/projects/{project_id}/reprocess
```

Re-runs the pipeline on an existing project, optionally with a different language. Useful for generating the BOQ in a different language without re-uploading the file.

**Parameters:**

| Parameter | Type | Location | Required | Description |
|---|---|---|---|---|
| `project_id` | String (UUID) | Path | Yes | The project ID |
| `language` | String | Query | No | New output language: `en`, `tr`, or `ar`. Defaults to `en`. |

**Response (200 OK):**

```json
{
  "project_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "processing",
  "language": "tr",
  "message": "Re-processing started. Connect to WebSocket for progress updates."
}
```

**Error Responses:**

| Code | Condition | Message |
|---|---|---|
| 400 | IFC file deleted | "Original IFC file no longer available" |
| 404 | Project not found | "Project not found" |

**curl example:**

```bash
curl -X POST "http://localhost:8000/api/projects/a1b2c3d4/reprocess?language=tr"
```

---

### Download Report

```
GET /api/projects/{project_id}/download/{format}
```

Download a generated report file.

**Parameters:**

| Parameter | Type | Location | Required | Description |
|---|---|---|---|---|
| `project_id` | String (UUID) | Path | Yes | The project ID |
| `format` | String | Path | Yes | Report format: `xlsx`, `csv`, or `json` |

**Response (200 OK):**

Returns the file as a download with appropriate Content-Type header.

| Format | Content-Type |
|---|---|
| `xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| `csv` | `text/csv` |
| `json` | `application/json` |

**Error Responses:**

| Code | Condition | Message |
|---|---|---|
| 400 | Not completed | "Project not yet completed" |
| 403 | Path traversal attempt | "Access denied" |
| 404 | Project not found | "Project not found" |
| 404 | Format not available | "Format 'pdf' not available. Available: ['xlsx', 'csv', 'json']" |
| 404 | File missing on disk | "Report file not found on disk" |

**curl example:**

```bash
curl -o building_BOQ.xlsx \
  http://localhost:8000/api/projects/a1b2c3d4/download/xlsx
```

---

## WebSocket Protocol

### Connection

```
WebSocket /ws/{project_id}
```

Connect to receive real-time progress updates for a processing project. If the project is already completed when the connection is established, the complete result is sent immediately.

**JavaScript example:**

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/a1b2c3d4-e5f6-7890-abcd-ef1234567890');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  switch (data.type) {
    case 'progress':
      console.log(`Step ${data.current}/${data.total}: ${data.step} (${data.percent}%)`);
      break;
    case 'complete':
      console.log('Processing complete:', data.result);
      break;
    case 'error':
      console.error('Pipeline error:', data.message);
      break;
  }
};
```

### Message Types

#### Status Update

Sent when the pipeline starts:

```json
{
  "type": "status",
  "status": "processing",
  "step": "Starting pipeline..."
}
```

#### Progress Update

Sent before each pipeline stage:

```json
{
  "type": "progress",
  "step": "Classification",
  "current": 2,
  "total": 6,
  "percent": 33
}
```

| Field | Description |
|---|---|
| `step` | Current stage name: "IFC Parsing", "Classification", "Quantity Calculation", "Material Mapping", "BOQ Generation", "Validation", "Exporting reports" |
| `current` | Current stage number (1-6) |
| `total` | Total stages (6) |
| `percent` | Completion percentage (0-100) |

#### Complete

Sent when processing finishes successfully:

```json
{
  "type": "complete",
  "status": "completed",
  "result": {
    "building_info": {...},
    "classified_elements": {...},
    "material_count": 28,
    "boq_file_paths": {...},
    "validation_report": {...},
    "warnings": [],
    "errors": [],
    "element_count": 115
  }
}
```

#### Error

Sent when the pipeline fails:

```json
{
  "type": "error",
  "message": "Pipeline failed at Classification: API key not configured"
}
```

### Connection Lifecycle

1. Client connects to `/ws/{project_id}`
2. Server accepts the connection
3. If the project is already completed, the server immediately sends a `complete` message
4. During processing, the server sends `status`, `progress`, and finally `complete` or `error` messages
5. The client should keep the connection open until receiving `complete` or `error`
6. When the client disconnects, the server cleans up the connection

---

## Rate Limiting

| Setting | Value |
|---|---|
| Limit | 5 uploads per client IP |
| Window | 60 seconds |
| Scope | Upload endpoint only |
| Response | HTTP 429 with message |

Rate limiting uses the client's IP address (`request.client.host`). The limit applies only to the upload endpoint -- all other endpoints are unrestricted.

---

## File Validation

Uploaded files undergo three validation checks before processing begins:

1. **Extension check:** File must end with `.ifc` (case-insensitive)
2. **Size check:** File must not exceed 500 MB
3. **Magic bytes check:** First 12+ bytes must be `ISO-10303-21` (the STEP file format header)

Files that pass all three checks are saved with a UUID filename (preventing path traversal attacks) and the original filename is stored in the database for display purposes.

---

## Security Notes

- Uploaded files are stored with UUID filenames, not user-provided names
- Download paths are validated against the output directory to prevent path traversal
- CORS is restricted to localhost:3000 by default
- Rate limiting prevents upload abuse
- No authentication is implemented in the current version -- this should be added for production deployment
