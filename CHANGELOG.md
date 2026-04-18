# Changelog

All notable changes to Metraj are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/). Versions use [Semantic Versioning](https://semver.org/).

---

## [0.5.0] - 2026-04-18

### For Users
- File uploads now validate IFC format (magic bytes) and enforce 500 MB size limit
- Pipeline progress bar now correctly reaches 100%
- Page refresh during processing no longer loses progress (auto-reconnects)
- BOQ Excel reports now include section subtotals, grand total, and an Audit Trail sheet
- Material quantities are more accurate: actual door/window openings deducted from walls instead of a flat 15% guess
- Duplicate materials with slightly different names (e.g., "Internal plaster" vs "Interior plaster") are now merged automatically
- Numbers in Excel formatted by unit type: 0 decimals for counts, 2 for areas, 3 for volumes

### For Developers
- **Security:** Fixed path traversal vulnerability in file upload; filename sanitized to project ID only
- **Security:** Added rate limiting (5 uploads per 60 seconds per IP)
- **Security:** File download endpoint validates path is within output directory
- **Type safety:** Added Pydantic validation models for all AI responses (ClassifierResponse, MapperResponse, ValidatorResponse)
- **Reliability:** LLM JSON parsing now uses balanced brace matching with retry (up to 2 retries with error feedback)
- **Reliability:** Added inter-stage validation gates in orchestrator (fail fast on empty data)
- **Reliability:** Failed/skipped elements tracked and reported through pipeline
- **Precision:** Added IFC quantity key aliases for cross-exporter compatibility (Revit, ArchiCAD, generic)
- **Precision:** Added unit normalization (detects mm values, converts to metres)
- **Precision:** Removed all intermediate rounding; full precision preserved until export
- **Precision:** Column surface area estimation uses circumscribed circle formula instead of assuming square cross-section
- **Infrastructure:** Added SQLite database for persistent project storage (replaces in-memory dict)
- **Infrastructure:** Added WebSocket reconnection with exponential backoff on frontend
- **Infrastructure:** Added session persistence (sessionStorage) for page refresh recovery
- **Infrastructure:** Added health check that verifies disk space, uploads dir, and API key
- **Infrastructure:** Added Dockerfile with health check
- **Infrastructure:** Projects auto-cleaned after 30 days
- Fixed waste factor double-counting bug in material aggregation
- Fixed orchestrator export condition (only exports when status is COMPLETED)
- Fixed WebSocket memory leak on disconnect
- Fixed element ID type mismatch (int vs string) in classifier
- Classifier and Material Mapper now batch elements (max 50 per LLM call)
- Added .env existence check with clear warning message
- Language parameter validated against supported list before pipeline starts

## [0.4.1] - 2026-03-11

### For Developers
- AI validator errors downgraded to warnings so AI review cannot block the pipeline
- Arithmetic validation checks remain blocking; AI issues are advisory only

## [0.4.0] - 2026-03-10

### For Users
- AI-powered element classification: Claude categorizes building elements into BOQ sections
- AI-powered material mapping: Claude determines construction materials with industry-standard ratios
- AI-powered validation: intelligent review catches issues that arithmetic checks miss

### For Developers
- Integrated Claude AI into Classifier, Material Mapper, and Validator agents
- Added prompt templates in src/prompts/ for all AI interactions
- Added prompt caching for repeated system prompts (90% token discount)
- LLM service supports both text and JSON response parsing

## [0.3.0] - 2026-03-10

### For Users
- Added comprehensive test suite (123 tests across all pipeline stages)
- System reliability validated end-to-end

### For Developers
- Added pytest test suite with 9 test files covering all agents and services
- Added sample IFC fixtures for testing

## [0.2.0] - 2026-03-09

### For Users
- Web application: upload IFC files through a browser and download BOQ reports
- Real-time progress tracking via WebSocket during processing
- Multi-language support: English, Turkish, Arabic (UI and reports)
- BOQ export in Excel (formatted with sections and headers), CSV, and JSON
- Drag-and-drop file upload with language selector

### For Developers
- FastAPI backend with REST endpoints and WebSocket progress streaming
- Next.js frontend with React 19, Tailwind CSS
- Export service with professional Excel formatting (openpyxl)
- Translation system for backend (strings.py) and frontend (JSON files)
- CORS configured for localhost development

## [0.1.0] - 2026-03-09

### For Users
- Initial working pipeline: IFC file in, BOQ data out
- Supports walls, slabs, columns, beams, doors, windows, stairs, roofs, foundations
- Quantity calculation with area, volume, perimeter, and count
- Material mapping with waste factors from industry data
- Element classification into 12 BOQ categories

### For Developers
- 6-agent pipeline architecture: Parser, Classifier, Calculator, Material Mapper, BOQ Generator, Validator
- Pydantic data models for all pipeline state (ProjectState, ParsedElement, etc.)
- IFC parsing via IfcOpenShell with element extraction
- Rule-based quantity calculation with element-type-specific calculators
- Material mapping with waste factor lookup from JSON data files
- BaseAgent abstract class for consistent agent interface
- Configuration via pydantic-settings with .env file support
- Logging via loguru

## [0.0.1] - 2026-03-09

### For Developers
- Initial project setup
- Project structure and directory layout
- Development environment configuration
- CLAUDE.md with project documentation for AI assistants
