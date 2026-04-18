"""
FastAPI application - the web server for Metraj.

Coach Simple explains:
    "This is the front door of our system. When someone opens the website,
    this server handles their requests - uploading files, checking progress,
    and downloading reports. It's like a receptionist who directs visitors."

Usage:
    uvicorn api.app:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.agents.orchestrator import Orchestrator
from src.models.project import ProcessingStatus
from src.services.database import Database
from src.services.learning_service import LearningService
from src.utils.logger import get_logger

logger = get_logger("api")

app = FastAPI(
    title="Metraj AI",
    description="AI-Powered Construction Material Estimation System",
    version="1.0.0",
)

# CORS - allow Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database for persistent project storage
db = Database()

# In-memory cache for active projects (avoids DB reads during processing)
_active_projects: dict[str, dict[str, Any]] = {}

# WebSocket connections for live progress
ws_connections: dict[str, list[WebSocket]] = {}

# Directories
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Simple rate limiter: {ip: [timestamps]}
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_UPLOADS = 5       # max uploads
RATE_LIMIT_WINDOW = 60       # per N seconds


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if the client is rate-limited."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    # Prune old entries
    _rate_limit_store[client_ip] = [
        ts for ts in _rate_limit_store[client_ip] if ts > window_start
    ]
    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_UPLOADS:
        return True
    _rate_limit_store[client_ip].append(now)
    return False


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    await db.initialize()
    logger.info("Database initialized")
    # Clean up old projects (>30 days)
    deleted = await db.delete_old_projects(max_age_days=30)
    if deleted:
        logger.info(f"Cleaned up {deleted} old project(s)")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    # Close all WebSocket connections
    for pid, connections in ws_connections.items():
        for ws in connections:
            try:
                await ws.close()
            except Exception:
                pass
    ws_connections.clear()
    _active_projects.clear()


# ---------- Helper ----------

async def notify_progress(project_id: str, data: dict[str, Any]) -> None:
    """Send progress update to all connected WebSocket clients for a project."""
    connections = ws_connections.get(project_id, [])
    dead = []
    for ws in connections:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connections.remove(ws)


async def run_pipeline(project_id: str, ifc_path: str, language: str = "en") -> None:
    """Run the Metraj pipeline in the background and update project state."""
    try:
        await db.update_project(project_id, status="processing")
        await notify_progress(project_id, {
            "type": "status",
            "status": "processing",
            "step": "Starting pipeline...",
        })

        orchestrator = Orchestrator()

        async def patched_execute(state: dict[str, Any]) -> dict[str, Any]:
            pipeline = [
                ("IFC Parsing", orchestrator.parser),
                ("Classification", orchestrator.classifier),
                ("Quantity Calculation", orchestrator.calculator),
                ("Material Mapping", orchestrator.material_mapper),
                ("BOQ Generation", orchestrator.boq_generator),
                ("Validation", orchestrator.validator),
            ]

            total_steps = len(pipeline)
            for i, (step_name, agent) in enumerate(pipeline):
                await notify_progress(project_id, {
                    "type": "progress",
                    "step": step_name,
                    "current": i + 1,
                    "total": total_steps,
                    "percent": int(((i + 1) / total_steps) * 100),
                })

                try:
                    state = await agent.execute(state)
                except Exception as e:
                    state["errors"].append(f"Pipeline failed at {step_name}: {e}")
                    state["status"] = ProcessingStatus.FAILED
                    break

                if state.get("status") == ProcessingStatus.FAILED:
                    break

            # Export reports
            if state.get("boq_data") and state.get("status") != ProcessingStatus.FAILED:
                await notify_progress(project_id, {
                    "type": "progress",
                    "step": "Exporting reports",
                    "current": total_steps,
                    "total": total_steps,
                    "percent": 95,
                })

                ifc_name = Path(state["ifc_file_path"]).stem
                output_dir = OUTPUT_DIR / project_id
                output_dir.mkdir(parents=True, exist_ok=True)

                lang = state.get("language", "en")

                excel_path = orchestrator.export_service.export_excel(
                    state["boq_data"], output_dir / f"{ifc_name}_BOQ.xlsx",
                    language=lang,
                )
                state["boq_file_paths"]["xlsx"] = str(excel_path)

                csv_path = orchestrator.export_service.export_csv(
                    state["boq_data"], output_dir / f"{ifc_name}_BOQ.csv",
                    language=lang,
                )
                state["boq_file_paths"]["csv"] = str(csv_path)

                json_path = orchestrator.export_service.export_json(
                    state["boq_data"], output_dir / f"{ifc_name}_BOQ.json"
                )
                state["boq_file_paths"]["json"] = str(json_path)

                state["status"] = ProcessingStatus.COMPLETED

            return state

        # Initialize state and run
        state: dict[str, Any] = {
            "ifc_file_path": ifc_path,
            "project_config": {},
            "language": language,
            "parsed_elements": [],
            "building_info": None,
            "classified_elements": {},
            "calculated_quantities": [],
            "material_list": [],
            "boq_data": None,
            "boq_file_paths": {},
            "validation_report": None,
            "warnings": [],
            "errors": [],
            "failed_elements": [],
            "skipped_elements": [],
            "status": ProcessingStatus.PENDING,
            "current_step": "",
            "processing_log": [],
        }

        result = await patched_execute(state)

        # Build result summary for storage
        status_str = result["status"].value if hasattr(result["status"], "value") else str(result["status"])
        result_data = {
            "building_info": result.get("building_info"),
            "classified_elements": {
                k: len(v) for k, v in result.get("classified_elements", {}).items()
            },
            "material_count": len(result.get("material_list", [])),
            "materials": result.get("material_list", []),
            "boq_data": result.get("boq_data"),
            "boq_file_paths": result.get("boq_file_paths", {}),
            "validation_report": result.get("validation_report"),
            "warnings": result.get("warnings", []),
            "errors": result.get("errors", []),
            "element_count": len(result.get("parsed_elements", [])),
        }

        # Persist to database
        await db.update_project(project_id, status=status_str, result=result_data)

        # Update in-memory cache
        _active_projects[project_id] = {"status": status_str, "result": result_data}

        await notify_progress(project_id, {
            "type": "complete",
            "status": status_str,
            "result": result_data,
        })

    except Exception as e:
        logger.error(f"Pipeline error for {project_id}: {e}")
        await db.update_project(project_id, status="failed", error=str(e))
        await notify_progress(project_id, {
            "type": "error",
            "message": str(e),
        })


# ---------- REST Endpoints ----------

@app.get("/api/health")
async def health():
    """Health check endpoint that verifies key system components."""
    import shutil

    checks: dict[str, str] = {"api": "ok"}

    # Check uploads directory is writable
    try:
        test_file = UPLOAD_DIR / ".health_check"
        test_file.write_text("ok")
        test_file.unlink()
        checks["uploads_writable"] = "ok"
    except Exception:
        checks["uploads_writable"] = "error"

    # Check disk space (warn if < 1 GB free)
    try:
        usage = shutil.disk_usage(str(UPLOAD_DIR))
        free_gb = usage.free / (1024**3)
        checks["disk_free_gb"] = f"{free_gb:.1f}"
        if free_gb < 1.0:
            checks["disk_space"] = "warning"
        else:
            checks["disk_space"] = "ok"
    except Exception:
        checks["disk_space"] = "unknown"

    # Check API key configured
    from src.config import settings
    checks["api_key_configured"] = "ok" if settings.anthropic_api_key else "missing"

    all_ok = all(
        v in ("ok", "unknown") or k in ("disk_free_gb",)
        for k, v in checks.items()
    )

    return {
        "status": "ok" if all_ok else "degraded",
        "service": "Metraj AI",
        "version": "0.5.0",
        "checks": checks,
    }


@app.post("/api/projects/upload")
async def upload_ifc(
    request: Request,
    file: UploadFile = File(...),
    language: str = Query("en", pattern="^(en|tr|ar)$"),
):
    """Upload an IFC file and start processing.

    Returns the project_id to track progress via WebSocket.
    """
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if _check_rate_limit(client_ip):
        raise HTTPException(
            429, f"Too many uploads. Max {RATE_LIMIT_UPLOADS} per {RATE_LIMIT_WINDOW}s."
        )

    if not file.filename:
        raise HTTPException(400, "No file provided")

    # Validate file extension
    if not file.filename.lower().endswith(".ifc"):
        raise HTTPException(400, "Only .ifc files are supported")

    # Create project with full UUID to avoid collisions
    project_id = str(uuid.uuid4())

    # Read file with size limit (500 MB)
    MAX_FILE_SIZE = 500 * 1024 * 1024
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large. Maximum size is 500 MB.")

    # Validate IFC magic bytes
    if not content[:15].startswith(b"ISO-10303-21"):
        raise HTTPException(400, "Invalid IFC file. File does not appear to be a valid IFC/STEP file.")

    # Sanitize filename — use only project_id to prevent path traversal
    upload_path = UPLOAD_DIR / f"{project_id}.ifc"
    upload_path.write_bytes(content)

    # Create project in database
    await db.create_project(project_id, file.filename, str(upload_path), language)

    # Start pipeline in background
    asyncio.create_task(run_pipeline(project_id, str(upload_path), language=language))

    return {
        "project_id": project_id,
        "filename": file.filename,
        "status": "processing",
        "message": "File uploaded. Connect to WebSocket for progress updates.",
    }


@app.get("/api/projects")
async def list_projects():
    """List all projects."""
    projects = await db.list_projects()
    return {
        "projects": [
            {
                "id": p["id"],
                "filename": p["filename"],
                "status": p["status"],
                "created_at": p["created_at"],
            }
            for p in projects
        ]
    }


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """Get a project's status and results."""
    # Check in-memory cache first (for active projects)
    if project_id in _active_projects:
        project = await db.get_project(project_id)
        if project:
            project["result"] = _active_projects[project_id].get("result")
            return project

    project = await db.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@app.post("/api/projects/{project_id}/reprocess")
async def reprocess_project(
    project_id: str,
    language: str = Query("en", pattern="^(en|tr|ar)$"),
):
    """Re-run the pipeline on an existing project with a different language."""
    project = await db.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    upload_path = project.get("upload_path")
    if not upload_path or not Path(upload_path).exists():
        raise HTTPException(400, "Original IFC file no longer available")

    # Reset project state in database
    await db.update_project(project_id, status="processing", result=None, error=None)

    # Re-run pipeline in background with the new language
    asyncio.create_task(run_pipeline(project_id, upload_path, language=language))

    return {
        "project_id": project_id,
        "status": "processing",
        "language": language,
        "message": "Re-processing started. Connect to WebSocket for progress updates.",
    }


@app.get("/api/projects/{project_id}/download/{format}")
async def download_report(project_id: str, format: str):
    """Download a generated report (xlsx, csv, or json)."""
    project = await db.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if project["status"] != "completed":
        raise HTTPException(400, "Project not yet completed")

    result = project.get("result", {})
    file_paths = result.get("boq_file_paths", {})

    if format not in file_paths:
        raise HTTPException(404, f"Format '{format}' not available. Available: {list(file_paths.keys())}")

    file_path = Path(file_paths[format]).resolve()
    output_resolved = OUTPUT_DIR.resolve()
    if not str(file_path).startswith(str(output_resolved)):
        raise HTTPException(403, "Access denied")
    if not file_path.exists():
        raise HTTPException(404, "Report file not found on disk")

    media_types = {
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv",
        "json": "application/json",
    }

    return FileResponse(
        path=str(file_path),
        media_type=media_types.get(format, "application/octet-stream"),
        filename=file_path.name,
    )


# ---------- BOQ Editing & Learning ----------


@app.get("/api/projects/{project_id}/boq")
async def get_boq(project_id: str):
    """Get full BOQ data for a project (for frontend editing)."""
    project = await db.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    result = project.get("result", {})
    return result.get("boq_data") or {}


@app.patch("/api/projects/{project_id}/boq/items/{item_no}")
async def update_boq_item(project_id: str, item_no: str, request: Request):
    """Update a BOQ line item (user correction)."""
    # Parse request body
    updates = await request.json()

    # Get project
    project = await db.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    result = project.get("result", {})
    boq_data = result.get("boq_data")
    if not boq_data:
        raise HTTPException(400, "No BOQ data available")

    # Find and update the item
    updated_item = None
    for section in boq_data.get("sections", []):
        for item in section.get("items", []):
            if item["item_no"] == item_no:
                # Record corrections for each changed field
                learning_svc = LearningService(db)
                for field, new_value in updates.items():
                    if field in ("quantity", "description", "unit", "waste_factor") and item.get(field) != new_value:
                        await learning_svc.record_correction(
                            project_id=project_id,
                            item_no=item_no,
                            field_name=field,
                            old_value=str(item.get(field)),
                            new_value=str(new_value),
                            element_type=item.get("category", ""),
                            category=item.get("category", ""),
                        )
                        item[field] = new_value
                updated_item = item
                break
        if updated_item:
            break

    if not updated_item:
        raise HTTPException(404, f"Item {item_no} not found")

    # Save updated BOQ data back to database
    result["boq_data"] = boq_data
    await db.update_project(project_id, result=result)

    return {"status": "updated", "item": updated_item}


@app.post("/api/projects/{project_id}/boq/approve")
async def approve_boq(project_id: str):
    """Mark BOQ as user-approved, boosting learned override confidence."""
    project = await db.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    learning_svc = LearningService(db)
    await learning_svc.approve_project_corrections(project_id)

    return {"status": "approved", "project_id": project_id}


# ---------- WebSocket ----------

@app.websocket("/ws/{project_id}")
async def websocket_progress(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time processing progress."""
    await websocket.accept()

    # Register connection
    if project_id not in ws_connections:
        ws_connections[project_id] = []
    ws_connections[project_id].append(websocket)

    logger.info(f"WebSocket connected for project {project_id}")

    # If project already completed, send results immediately
    project = await db.get_project(project_id)
    if project and project.get("result") and project.get("status") == "completed":
        await websocket.send_json({
            "type": "complete",
            "status": project["status"],
            "result": project["result"],
        })

    try:
        # Keep connection alive until client disconnects
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        # Always cleanup the connection
        if project_id in ws_connections:
            ws_connections[project_id] = [
                ws for ws in ws_connections[project_id] if ws != websocket
            ]
            if not ws_connections[project_id]:
                del ws_connections[project_id]
        logger.info(f"WebSocket disconnected for project {project_id}")
