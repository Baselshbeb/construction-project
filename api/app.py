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
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.agents.orchestrator import Orchestrator
from src.models.project import ProcessingStatus
from src.utils.logger import get_logger

logger = get_logger("api")

app = FastAPI(
    title="Metraj AI",
    description="AI-Powered Construction Material Estimation System",
    version="0.5.0",
)

# CORS - allow Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory project store (simple dict for now)
projects: dict[str, dict[str, Any]] = {}

# WebSocket connections for live progress
ws_connections: dict[str, list[WebSocket]] = {}

# Directories
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


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


async def run_pipeline(project_id: str, ifc_path: str) -> None:
    """Run the Metraj pipeline in the background and update project state."""
    project = projects[project_id]

    try:
        project["status"] = "processing"
        await notify_progress(project_id, {
            "type": "status",
            "status": "processing",
            "step": "Starting pipeline...",
        })

        orchestrator = Orchestrator()

        # Patch agents to send progress updates
        original_execute = orchestrator.execute

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
                    "percent": int((i / total_steps) * 100),
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

                excel_path = orchestrator.export_service.export_excel(
                    state["boq_data"], output_dir / f"{ifc_name}_BOQ.xlsx"
                )
                state["boq_file_paths"]["xlsx"] = str(excel_path)

                csv_path = orchestrator.export_service.export_csv(
                    state["boq_data"], output_dir / f"{ifc_name}_BOQ.csv"
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
            "status": ProcessingStatus.PENDING,
            "current_step": "",
            "processing_log": [],
        }

        result = await patched_execute(state)

        # Update project record
        project["status"] = result["status"].value if hasattr(result["status"], "value") else str(result["status"])
        project["result"] = {
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

        await notify_progress(project_id, {
            "type": "complete",
            "status": project["status"],
            "result": project["result"],
        })

    except Exception as e:
        logger.error(f"Pipeline error for {project_id}: {e}")
        project["status"] = "failed"
        project["error"] = str(e)
        await notify_progress(project_id, {
            "type": "error",
            "message": str(e),
        })


# ---------- REST Endpoints ----------

@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "Metraj AI", "version": "0.5.0"}


@app.post("/api/projects/upload")
async def upload_ifc(file: UploadFile = File(...)):
    """Upload an IFC file and start processing.

    Returns the project_id to track progress via WebSocket.
    """
    if not file.filename:
        raise HTTPException(400, "No file provided")

    # Validate file extension
    if not file.filename.lower().endswith(".ifc"):
        raise HTTPException(400, "Only .ifc files are supported")

    # Create project
    project_id = str(uuid.uuid4())[:8]
    upload_path = UPLOAD_DIR / f"{project_id}_{file.filename}"

    # Save uploaded file
    content = await file.read()
    upload_path.write_bytes(content)

    # Create project record
    projects[project_id] = {
        "id": project_id,
        "filename": file.filename,
        "upload_path": str(upload_path),
        "status": "uploaded",
        "created_at": datetime.now().isoformat(),
        "result": None,
        "error": None,
    }

    # Start pipeline in background
    asyncio.create_task(run_pipeline(project_id, str(upload_path)))

    return {
        "project_id": project_id,
        "filename": file.filename,
        "status": "processing",
        "message": "File uploaded. Connect to WebSocket for progress updates.",
    }


@app.get("/api/projects")
async def list_projects():
    """List all projects."""
    return {
        "projects": [
            {
                "id": p["id"],
                "filename": p["filename"],
                "status": p["status"],
                "created_at": p["created_at"],
            }
            for p in projects.values()
        ]
    }


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """Get a project's status and results."""
    project = projects.get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@app.get("/api/projects/{project_id}/download/{format}")
async def download_report(project_id: str, format: str):
    """Download a generated report (xlsx, csv, or json)."""
    project = projects.get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if project["status"] != "completed":
        raise HTTPException(400, "Project not yet completed")

    result = project.get("result", {})
    file_paths = result.get("boq_file_paths", {})

    if format not in file_paths:
        raise HTTPException(404, f"Format '{format}' not available. Available: {list(file_paths.keys())}")

    file_path = Path(file_paths[format])
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

    # If project already has results, send them immediately
    project = projects.get(project_id)
    if project and project.get("result"):
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
        ws_connections.get(project_id, []).remove(websocket) if websocket in ws_connections.get(project_id, []) else None
        logger.info(f"WebSocket disconnected for project {project_id}")
