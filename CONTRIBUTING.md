# Contributing to Metraj

Thank you for your interest in contributing to Metraj. This document explains how to set up your development environment, submit changes, and maintain documentation.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/Baselshbeb/construction-project.git
cd construction-project

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# Run tests
pytest tests/ -v

# Start the backend
uvicorn api.app:app --reload --port 8000

# Start the frontend (separate terminal)
cd frontend && npm install && npm run dev

# Start the docs site (separate terminal)
mkdocs serve
```

## Code Style

All code must follow the style guide defined in [CLAUDE.md](CLAUDE.md):

- **Type hints** on all function parameters and return values
- **Pydantic models** for all data structures
- **Async/await** for all I/O operations
- **Docstrings** on all public functions
- **Logging** via loguru (`from src.utils.logger import get_logger`), never `print()`
- All agents inherit from `BaseAgent` in `src/agents/base_agent.py`
- Prompts live in `src/prompts/`, never hardcoded in agent files

## Submitting Changes

### Pull Request Process

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the code style above.

3. Run the test suite and ensure all tests pass:
   ```bash
   pytest tests/ -v
   ```

4. If your change affects user-visible behavior, update the relevant documentation in `docs/`.

5. Write a clear commit message describing what changed and why:
   ```
   feat: add support for IfcCurtainWall elements
   
   Adds IfcCurtainWall to the recognized element types list and adds
   a dedicated calculator that handles curtain wall panel areas and
   mullion lengths. Fixes #42.
   ```

6. Push your branch and create a pull request against `main`.

### Documentation Requirements

If your PR changes any of the following, you **must** update the corresponding documentation:

| What Changed | Update This Doc |
|---|---|
| CLI commands or entry points | `docs/getting-started/quick-start.md` |
| Environment variables | `docs/getting-started/configuration.md` |
| API endpoints | `docs/reference/api-endpoints.md` |
| Supported IFC element types | `docs/reference/ifc-compatibility.md` |
| Waste factors or element rules | `docs/reference/waste-factors.md`, `docs/reference/element-rules.md` |
| AI prompts or behavior | `docs/architecture/ai-transparency.md` |
| Pipeline agents | `docs/architecture/agent-pipeline.md` |
| Deployment configuration | `docs/deployment/` |

### Commit Message Format

We use descriptive commit messages. Prefix with the type of change:

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `refactor:` — Code change that neither fixes a bug nor adds a feature
- `test:` — Adding or updating tests
- `chore:` — Build process, dependencies, or tooling changes

## Adding Translations

### Backend (Python)

Translation strings for reports and BOQ sections are in `src/translations/strings.py`. To add a new language:

1. Add a new key to `BOQ_SECTIONS` with all 13 section titles translated.
2. Add a new key to `EXPORT_LABELS` with all export labels translated.
3. Add the language code to `Orchestrator.SUPPORTED_LANGUAGES` in `src/agents/orchestrator.py`.
4. Add language-specific instructions to `MAPPER_LANGUAGE_INSTRUCTIONS` in `src/prompts/material_mapper_prompts.py`.

### Frontend (Next.js)

Frontend translations are in `frontend/src/translations/`. To add a new language:

1. Create a new JSON file (e.g., `de.json`) following the structure of `en.json`.
2. Import and register it in `frontend/src/context/LanguageContext.tsx`.
3. Update the language selector component.

**Important:** Do not use machine translation for construction terminology. Terms like "metraj," "hakedi," and "kesilecek" have specific professional meanings that generic translation tools will get wrong.

## Reporting Issues

When reporting a bug, include:

1. Steps to reproduce
2. Expected behavior
3. Actual behavior
4. IFC file details (if applicable): which BIM tool exported it, IFC schema version, approximate element count
5. Error messages from the browser console or server logs

## Questions

If you have questions about the codebase, start with:

1. [CLAUDE.md](CLAUDE.md) — Project overview, structure, and conventions
2. [Documentation site](docs/) — Run `mkdocs serve` for the full docs
3. Agent docstrings — Every agent file has a "Coach Simple" explanation at the top
