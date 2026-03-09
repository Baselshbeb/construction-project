# Metraj - AI-Powered Construction Material Estimation System

## Project Overview
An agentic AI system that takes IFC/BIM building models and automatically
produces a Bill of Quantities (BOQ) with all needed construction materials.
"Metraj" is the Turkish term for quantity takeoff / material estimation.

## Tech Stack
- Python 3.13+, FastAPI, LangGraph, IfcOpenShell, Anthropic Claude API
- Frontend: Next.js, Tailwind CSS, shadcn/ui
- Database: SQLite (dev), PostgreSQL (prod)
- Reports: openpyxl (Excel), weasyprint (PDF)

## Project Structure
- src/agents/ - AI agents (orchestrator, parser, classifier, calculator, mapper, generator, validator)
- src/models/ - Pydantic data models (project state, elements, quantities, materials, BOQ)
- src/services/ - Business logic (IFC parsing, LLM calls, calculations, exports)
- src/prompts/ - All AI prompt templates (classifier, material mapper, validator)
- src/data/ - Static data (material DB, waste factors, element-to-material rules)
- src/utils/ - Helpers (geometry, unit conversion, logging)
- tests/ - pytest test files + sample IFC fixtures
- api/ - FastAPI backend (routes for upload, projects, reports)
- frontend/ - Next.js frontend

## Key Commands
- Run: `python -m src.main <ifc_file>`
- Test: `pytest tests/ -v`
- API: `uvicorn api.app:app --reload`
- Frontend: `cd frontend && npm run dev`

## Code Style
- Use type hints everywhere
- Pydantic models for all data structures
- Async/await for all I/O operations
- Docstrings on all public functions
- Logging via loguru, not print()
- All agents inherit from BaseAgent in src/agents/base_agent.py

## Agent Pipeline
IFC File -> IFC Parser -> Classifier -> Quantity Calculator -> Material Mapper -> BOQ Generator -> Validator -> Final Report

## Domain Knowledge
- IFC = Industry Foundation Classes (3D building model format, ISO 16739)
- BOQ = Bill of Quantities (itemized list of materials + quantities + prices)
- Metraj = Turkish term for quantity takeoff / material estimation
- Key IFC types: IfcWall, IfcSlab, IfcColumn, IfcBeam, IfcDoor, IfcWindow, IfcStair, IfcRoof
- Quantities: areas (m2), volumes (m3), lengths (m), weights (kg), counts (nr)
- Always apply waste factors to material quantities
- Always deduct openings (doors/windows) from wall areas
- Use metric units (SI) throughout

## Important Rules
- Never hardcode API keys - always use .env
- Always validate IFC data before processing
- Prompts live in src/prompts/, NOT hardcoded in agent files
- Test with sample IFC files in tests/fixtures/
- Each agent must be independently testable
