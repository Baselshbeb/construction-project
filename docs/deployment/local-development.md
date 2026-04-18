# Local Development

This guide covers setting up a complete local development environment for Metraj, including backend, frontend, tests, and documentation.

---

## Prerequisites

- Python 3.13 or later
- Node.js 18 or later (with npm)
- Git
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com/))

---

## Clone the Repository

```bash
git clone <repository-url>
cd construction-project
```

---

## Backend Setup

### Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

```bash
# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Windows CMD
venv\Scripts\activate.bat

# Linux / macOS
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Create Environment File

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
LOG_LEVEL=DEBUG
DEBUG=true
```

Setting `LOG_LEVEL=DEBUG` shows detailed information including AI API token usage.

### Run the Backend Server

```bash
uvicorn api.app:app --reload --port 8000
```

The `--reload` flag enables auto-restart when source files change. The server will be available at `http://localhost:8000`.

Verify it is running:

```bash
curl http://localhost:8000/api/health
```

---

## Frontend Setup

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`.

To configure a different API URL, create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Running Tests

From the project root (with the virtual environment active):

```bash
pytest tests/ -v
```

To run a specific test file:

```bash
pytest tests/test_calculator.py -v
```

To run with coverage:

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

Test fixtures (sample IFC files) are located in `tests/fixtures/`.

---

## Running the CLI

Process an IFC file directly from the command line:

```bash
python -m src.main path/to/building.ifc
```

This runs the full pipeline and saves reports to `output/<ifc_filename>/`.

To specify a language:

```bash
python -m src.main path/to/building.ifc --language tr
```

---

## Project Structure

```
construction-project/
  api/                    # FastAPI application
    app.py                # Main API server
  frontend/               # Next.js application
    src/
      app/                # Next.js pages
      context/            # React contexts
      translations/       # Frontend i18n
  src/
    agents/               # Pipeline agents
      orchestrator.py     # Pipeline coordinator
      ifc_parser.py       # IFC file reader
      classifier.py       # AI element classifier
      calculator.py       # Quantity calculator
      material_mapper.py  # AI material mapper
      boq_generator.py    # BOQ assembler
      validator.py        # Hybrid validator
      base_agent.py       # Base class for agents
    models/               # Pydantic data models
      project.py          # ProjectState, elements, categories
      ai_responses.py     # AI response validation models
    services/             # Business logic
      ifc_service.py      # IfcOpenShell wrapper
      llm_service.py      # Claude API wrapper
      export_service.py   # Excel/CSV/JSON generation
      database.py         # SQLite persistence
    prompts/              # AI prompt templates
      classifier_prompts.py
      material_mapper_prompts.py
      validator_prompts.py
    data/                 # Static data
      waste_factors.json  # Material waste factors
      element_rules.json  # Element-to-material rules
    translations/         # Backend i18n strings
      strings.py          # BOQ section titles, export labels
    utils/                # Helpers
      logger.py           # Loguru configuration
    config.py             # Settings (from .env)
    main.py               # CLI entry point
  tests/                  # Test files
    fixtures/             # Sample IFC files
  docs/                   # Documentation
  data/                   # Runtime data (database)
  uploads/                # Uploaded IFC files
  output/                 # Generated reports
  .env                    # Environment variables (not in git)
```

---

## Development Workflow

### Making Changes to Agents

1. Edit the agent file in `src/agents/`
2. If modifying AI prompts, edit the corresponding file in `src/prompts/`
3. Run the relevant tests
4. Test with the CLI: `python -m src.main tests/fixtures/sample.ifc`
5. Verify through the web interface

### Making Changes to the API

1. Edit `api/app.py`
2. The `--reload` flag will auto-restart uvicorn
3. Test endpoints with curl or the frontend

### Making Changes to the Frontend

1. Edit files in `frontend/src/`
2. Next.js hot-reload will update the browser automatically

### Modifying Data Files

- `src/data/waste_factors.json` -- change waste percentages
- `src/data/element_rules.json` -- change material rules
- `src/translations/strings.py` -- change BOQ section titles or export labels

Changes to data files take effect on the next pipeline run (no server restart needed for waste_factors.json and element_rules.json, as they are loaded per-run by the Material Mapper agent).

---

## Useful Commands Reference

| Task | Command |
|---|---|
| Start backend | `uvicorn api.app:app --reload --port 8000` |
| Start frontend | `cd frontend && npm run dev` |
| Run all tests | `pytest tests/ -v` |
| Run CLI | `python -m src.main <file.ifc>` |
| Check health | `curl http://localhost:8000/api/health` |
| Format code | `ruff format src/ api/ tests/` |
| Lint code | `ruff check src/ api/ tests/` |
| Type check | `mypy src/` |

---

## Environment Variables for Development

```env
# Required
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# Recommended for development
LOG_LEVEL=DEBUG
DEBUG=true

# Optional model overrides
DEFAULT_MODEL=claude-sonnet-4-5-20250929
EXPENSIVE_MODEL=claude-opus-4-5-20250929
```
