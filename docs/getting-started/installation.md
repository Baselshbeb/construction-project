# Installation

This guide covers setting up Metraj on your local machine for development or evaluation.

---

## Prerequisites

| Requirement | Version | Purpose |
|---|---|---|
| Python | 3.13 or later | Backend runtime |
| Node.js | 18 or later | Frontend runtime |
| pip | Latest | Python package manager |
| npm | Bundled with Node.js | Frontend package manager |
| Git | Any recent version | Source code management |

You will also need an **Anthropic API key** to use the AI-powered features (classification, material mapping, validation). Obtain one from [console.anthropic.com](https://console.anthropic.com/).

---

## Backend Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd construction-project
```

### 2. Create a Python virtual environment

```bash
python -m venv venv
```

Activate the virtual environment:

- **Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
- **Windows (CMD):**
  ```cmd
  venv\Scripts\activate.bat
  ```
- **Linux/macOS:**
  ```bash
  source venv/bin/activate
  ```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs the following key packages:

- `fastapi` and `uvicorn` -- Web API server
- `ifcopenshell` -- IFC file parsing (BIM data)
- `anthropic` -- Claude AI API client
- `openpyxl` -- Excel report generation
- `pydantic` and `pydantic-settings` -- Data validation and configuration
- `aiosqlite` -- Async SQLite database
- `loguru` -- Structured logging
- `python-dotenv` -- Environment variable management

### 4. Create the .env file

Create a file named `.env` in the project root directory:

```env
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

**About the API key:** Metraj uses the Anthropic Claude API for three pipeline stages: element classification, material mapping, and BOQ validation. Without a valid API key, the pipeline will fail at the classification stage. The key is never logged or transmitted anywhere other than Anthropic's API servers.

Optional environment variables you can add:

```env
# Model selection (defaults shown)
DEFAULT_MODEL=claude-sonnet-4-5-20250929
EXPENSIVE_MODEL=claude-opus-4-5-20250929

# Logging
LOG_LEVEL=INFO
DEBUG=false
```

---

## Frontend Setup

### 1. Navigate to the frontend directory

```bash
cd frontend
```

### 2. Install Node.js dependencies

```bash
npm install
```

### 3. Configure the API URL

The frontend expects the backend API at `http://localhost:8000` by default. If you need to change this, create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Windows-Specific Notes for IfcOpenShell

IfcOpenShell can sometimes be difficult to install on Windows. Here are common solutions:

### Option 1: pip install (recommended)

```bash
pip install ifcopenshell
```

This works on most systems with Python 3.13+. If it fails, try Option 2.

### Option 2: Conda install

If pip installation fails, install via conda:

```bash
conda install -c conda-forge ifcopenshell
```

### Option 3: Pre-built wheels

Download a pre-built wheel from the [IfcOpenShell releases page](https://github.com/IfcOpenShell/IfcOpenShell/releases) matching your Python version and platform, then install:

```bash
pip install path/to/ifcopenshell-xxx.whl
```

### Verifying IfcOpenShell installation

```bash
python -c "import ifcopenshell; print(ifcopenshell.version)"
```

If this prints a version number without errors, the installation is correct.

---

## Common Installation Issues

### "No module named 'ifcopenshell'"

See the Windows-Specific Notes section above. Ensure you are installing into the correct virtual environment.

### "ANTHROPIC_API_KEY not set"

Create the `.env` file in the project root (not in `src/` or `api/`). The file must be named exactly `.env` with the leading dot.

### pip install fails with "Python 3.13 required"

Verify your Python version:

```bash
python --version
```

If you have multiple Python versions installed, use `python3.13` or the full path to the correct interpreter when creating the virtual environment.

### npm install fails in frontend

Ensure you have Node.js 18 or later:

```bash
node --version
```

If using an older version, update Node.js from [nodejs.org](https://nodejs.org/).

### "Microsoft Visual C++ 14.0 or greater is required"

Some Python packages on Windows require the Visual C++ Build Tools. Install them from [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/), selecting the "Desktop development with C++" workload.

---

## Next Steps

Once installation is complete, proceed to the [Quick Start](quick-start.md) guide to process your first IFC file.
