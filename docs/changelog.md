# Changelog

This document summarizes the version history of the Metraj project. For the canonical changelog, see `CHANGELOG.md` in the repository root (if present).

---

## Version History (from Git)

### v1.0.0 -- Geometry Fallback, Confidence Scoring, and Learning Loop

**Latest release.** Adds geometry-based quantity fallback, per-item confidence scoring, user correction learning, and per-project logging.

#### For Users
- Geometry fallback: quantities now computed from 3D geometry when IFC property sets are missing
- Per-wall opening deduction: door/window areas deducted from their specific walls, not storey average
- Confidence scoring: every BOQ item rated HIGH/MEDIUM/LOW so you know what to review
- Per-project logs: detailed step-by-step processing log for each uploaded file
- Learning from corrections: edited BOQ items improve future pipeline runs
- Engineering fixes: door frame perimeter corrected, stair formwork improved, waterproofing added
- 17 element types now supported (was 9): ramps, coverings, curtain walls, railings, members, plates

#### For Developers
- New services: geometry_service.py, rebar_service.py, confidence_service.py, learning_service.py, project_logger.py
- element_rules.json expanded from 6 to 20 entries with waterproofing, insulation, DPC
- waste_factors.json expanded with 5 new categories
- Confidence penalties calibrated: ratio-based rebar 2%, storey-avg openings 3%
- Weighted average confidence instead of worst-case
- Pipeline checkpointing with resume capability
- API: BOQ editing endpoints, project logs endpoint
- Per-project structured logging in logs/projects/{id}/pipeline.log

---

### v0.5.0 -- AI Integration and Web Application

Integrates Claude AI into the core pipeline and adds a complete web application.

#### AI Integration
- Integrated Claude AI into the Classifier, Material Mapper, and Validator agents
- Added Pydantic response validation models for all AI responses (`src/models/ai_responses.py`)
- Added prompt templates in `src/prompts/` for classifier, material mapper, and validator
- Implemented prompt caching for cost optimization (ephemeral cache control on system prompts)
- AI validator errors are downgraded to warnings to prevent AI from blocking the pipeline
- Added retry with error feedback for JSON parse failures (up to 2 retries)

#### Web Application (Phase 5)
- FastAPI backend with REST endpoints for upload, project management, and report download
- WebSocket support for real-time pipeline progress updates
- Next.js frontend with file upload, progress tracking, and report download
- SQLite database for persistent project storage with async access (aiosqlite)
- Rate limiting (5 uploads per 60 seconds per IP)
- File validation (extension, size, IFC magic bytes)
- Automatic cleanup of projects older than 30 days
- Health check endpoint with system status monitoring

#### Report Generation (Phase 4)
- Excel export with professional formatting: BOQ sheet, Material Summary, and Audit Trail
- Section subtotals with SUM formulas and grand total
- Unit-aware number formatting (2 decimals for areas, 3 for volumes, 0 for counts)
- CSV export with all BOQ data including waste factors
- JSON export for programmatic access
- Multi-language support: English, Turkish, Arabic
- Right-to-left (RTL) layout for Arabic Excel reports

#### Testing and Validation (Phase 6)
- Comprehensive testing and validation framework
- Inter-stage validation gates in the orchestrator
- 8 arithmetic validation checks in the Validator agent
- AI-powered engineering review of the complete BOQ

#### Pipeline Enhancements
- Batch processing for classifier (50 elements per batch)
- Batch processing for material mapper (50 elements per type group)
- Material name normalization with fuzzy deduplication
- Weighted-average waste factor computation for aggregated materials
- Opening deduction using actual per-storey door/window ratios
- Quantity key aliases for cross-exporter compatibility (Revit, ArchiCAD, FreeCAD)
- Unit normalization (millimetre detection for Width, Depth, Thickness)

---

## Architecture

The project was built incrementally across six phases:

1. **Phase 1:** Project structure, data models, configuration
2. **Phase 2:** IFC parsing with IfcOpenShell
3. **Phase 3:** Quantity calculation and material mapping (rule-based, later AI-enhanced)
4. **Phase 4:** BOQ report generation (Excel, CSV, JSON)
5. **Phase 5:** Web application (FastAPI + Next.js)
6. **Phase 6:** Testing, validation, and AI integration

---

## Technology Stack

- **Python 3.13+** -- Backend language
- **FastAPI** -- Web API framework
- **IfcOpenShell** -- IFC file parsing
- **Anthropic Claude API** -- AI for classification, material mapping, validation
- **Next.js** -- Frontend framework
- **Tailwind CSS, shadcn/ui** -- Frontend styling
- **SQLite / aiosqlite** -- Development database
- **openpyxl** -- Excel report generation
- **Pydantic** -- Data validation and settings
- **Loguru** -- Structured logging
