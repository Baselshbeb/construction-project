# Metraj - AI-Powered Construction Material Estimation

**Metraj** (Turkish for "quantity takeoff") is an AI-powered system that takes IFC/BIM building models and automatically produces a professional Bill of Quantities (BOQ) with all needed construction materials, quantities, and waste factors applied.

[Documentation](https://docs.metraj.com) | [API Reference](https://docs.metraj.com/reference/api-endpoints/) | [Changelog](CHANGELOG.md)

---

## What It Does

Upload a 3D building model (IFC file) and get back a complete BOQ in Excel, CSV, or JSON — with materials, quantities, waste factors, and full audit trail. The system uses a 6-agent AI pipeline combining deterministic calculations with Claude AI for intelligent classification and material mapping.

**Supported languages:** English, Turkish, Arabic (UI, reports, and material names)

## Quick Start

```bash
# 1. Clone and set up
git clone https://github.com/Baselshbeb/construction-project.git
cd construction-project
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Run the backend
uvicorn api.app:app --reload --port 8000

# 4. Run the frontend (separate terminal)
cd frontend && npm install && npm run dev

# 5. Open http://localhost:3000 and upload an IFC file
```

## Documentation

Run the docs site locally:

```bash
mkdocs serve
# Open http://localhost:8000
```

Full documentation covers:

- **[Getting Started](docs/getting-started/installation.md)** - Installation, setup, configuration
- **[Architecture](docs/architecture/overview.md)** - System design, agent pipeline, AI transparency
- **[User Guide](docs/user-guide/uploading-ifc.md)** - For construction engineers using the system
- **[Reference](docs/reference/api-endpoints.md)** - API, waste factors, IFC compatibility, glossary
- **[Deployment](docs/deployment/local-development.md)** - Local dev, Docker, production
- **[Troubleshooting](docs/troubleshooting/common-errors.md)** - Error catalog, FAQ

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13+, FastAPI, IfcOpenShell |
| AI | Anthropic Claude API (Sonnet) |
| Frontend | Next.js 16, React 19, Tailwind CSS |
| Database | SQLite (dev), PostgreSQL (prod) |
| Reports | openpyxl (Excel), CSV, JSON |
| Docs | MkDocs Material |

## Pipeline

```
IFC File -> IFC Parser -> Classifier -> Calculator -> Material Mapper -> BOQ Generator -> Validator -> Excel/CSV/JSON
             (code)       (Claude AI)    (code)        (Claude AI)        (code)          (hybrid)
```

## Project Structure

```
src/agents/       - 6 pipeline agents + orchestrator
src/models/       - Pydantic data models
src/services/     - IFC parsing, LLM, export, database
src/prompts/      - Claude AI prompt templates
src/data/         - Waste factors, element-to-material rules
api/              - FastAPI backend
frontend/         - Next.js web application
docs/             - Documentation (this site)
tests/            - pytest test suite
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on code style, pull requests, and documentation updates.

## License

This project is proprietary software. All rights reserved.
