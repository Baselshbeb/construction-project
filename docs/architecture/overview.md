# System Architecture Overview

Metraj is a three-tier application: a Next.js frontend, a FastAPI backend, and a six-agent AI processing pipeline. This document describes the overall architecture, technology stack, and data flow.

---

## High-Level Architecture

```mermaid
graph TB
    subgraph Frontend["Frontend (Next.js)"]
        UI[Web Interface]
        WS_Client[WebSocket Client]
    end

    subgraph Backend["Backend (FastAPI)"]
        API[REST API]
        WS_Server[WebSocket Server]
        Pipeline[Agent Pipeline]
        DB[(SQLite Database)]
        Export[Export Service]
    end

    subgraph External["External Services"]
        Claude[Anthropic Claude API]
    end

    subgraph Storage["File Storage"]
        Uploads[uploads/ directory]
        Output[output/ directory]
    end

    UI -->|HTTP POST /api/projects/upload| API
    UI -->|HTTP GET /api/projects/:id| API
    UI -->|HTTP GET /api/projects/:id/download/:format| API
    WS_Client <-->|WebSocket /ws/:id| WS_Server

    API --> Pipeline
    API --> DB
    Pipeline --> Claude
    Pipeline --> Export
    Pipeline --> DB

    API --> Uploads
    Export --> Output
```

---

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | Next.js, Tailwind CSS, shadcn/ui | Web interface for file upload, progress tracking, report download |
| **API Server** | FastAPI, Uvicorn | REST endpoints, WebSocket for real-time progress, file handling |
| **AI Agents** | Custom Python agents | Six-stage processing pipeline |
| **AI Provider** | Anthropic Claude API | Element classification, material mapping, BOQ validation |
| **IFC Parsing** | IfcOpenShell | Reading BIM/IFC files (ISO 16739) |
| **Database** | SQLite (dev) / PostgreSQL (prod) | Project metadata and results persistence |
| **Reports** | openpyxl | Professional Excel spreadsheet generation |
| **Configuration** | Pydantic Settings, python-dotenv | Type-safe configuration from environment variables |
| **Logging** | Loguru | Structured logging across all components |

---

## Agent Pipeline

The core of Metraj is a six-agent pipeline that transforms an IFC file into a BOQ. Each agent reads from and writes to a shared state dictionary that flows through the pipeline.

```mermaid
graph LR
    IFC[IFC File] --> P[IFC Parser]
    P --> C[Classifier]
    C --> Q[Calculator]
    Q --> M[Material Mapper]
    M --> B[BOQ Generator]
    B --> V[Validator]
    V --> R[Reports]

    style P fill:#4a9eff,color:#fff
    style C fill:#ff9f43,color:#fff
    style Q fill:#4a9eff,color:#fff
    style M fill:#ff9f43,color:#fff
    style B fill:#4a9eff,color:#fff
    style V fill:#a855f7,color:#fff
```

**Legend:**
- Blue agents are **code-driven** (deterministic, no AI calls)
- Orange agents are **AI-powered** (use Claude API)
- Purple agents are **hybrid** (arithmetic checks + AI review)

| # | Agent | Type | Purpose |
|---|---|---|---|
| 1 | IFC Parser | Code | Extract building elements from IFC file |
| 2 | Classifier | AI | Categorize elements into BOQ sections |
| 3 | Calculator | Code | Compute construction quantities |
| 4 | Material Mapper | AI | Determine required materials per element |
| 5 | BOQ Generator | Code | Assemble structured BOQ from materials |
| 6 | Validator | Hybrid | Cross-check quantities and materials |

For detailed information about each agent, see [Agent Pipeline](agent-pipeline.md).

---

## Data Flow

The following diagram shows how data transforms as it passes through the pipeline:

```mermaid
graph TD
    subgraph Input
        IFC["IFC File<br/>(3D building model)"]
    end

    subgraph "Stage 1: Parse"
        Elements["Parsed Elements<br/>- ifc_id, ifc_type, name<br/>- quantities (Length, Height, Area...)<br/>- properties (IsExternal...)<br/>- materials (from IFC layers)<br/>- storey assignment"]
        BuildingInfo["Building Info<br/>- project name<br/>- storeys<br/>- schema version"]
    end

    subgraph "Stage 2: Classify"
        Classified["Classified Elements<br/>Each element gets a category:<br/>substructure, frame, external_walls,<br/>internal_walls, upper_floors, roof,<br/>doors, windows, stairs, finishes..."]
    end

    subgraph "Stage 3: Calculate"
        Quantities["Calculated Quantities<br/>Per element:<br/>- Gross/net wall area (m2)<br/>- Volume (m3)<br/>- Perimeter (m)<br/>- Surface area (m2)<br/>- Formwork area (m2)<br/>- Count (nr)"]
    end

    subgraph "Stage 4: Map Materials"
        Materials["Material List<br/>Per element type:<br/>- Concrete C25/30: 45.2 m3<br/>- Reinforcement steel: 5,420 kg<br/>- Formwork: 312 m2<br/>- Internal plaster: 280 m2<br/>- Paint: 560 m2<br/>(with waste factors applied)"]
    end

    subgraph "Stage 5: Generate BOQ"
        BOQ["Structured BOQ<br/>Sections with item numbers:<br/>1. Substructure<br/>2. Frame<br/>3. External Walls<br/>...each with line items"]
    end

    subgraph "Stage 6: Validate"
        Report["Validation Report<br/>- 8 arithmetic checks<br/>- AI engineering review<br/>- Warnings and observations<br/>- Score: 8/8 PASS"]
    end

    subgraph Output
        Excel["Excel Report<br/>(3 sheets)"]
        CSV["CSV Report"]
        JSON["JSON Report"]
    end

    IFC --> Elements
    IFC --> BuildingInfo
    Elements --> Classified
    Classified --> Quantities
    Quantities --> Materials
    Materials --> BOQ
    BOQ --> Report
    Report --> Excel
    Report --> CSV
    Report --> JSON
```

---

## State Management

The pipeline uses a shared state dictionary (`dict[str, Any]`) that is passed from agent to agent. The state contains:

| Key | Set By | Description |
|---|---|---|
| `ifc_file_path` | Orchestrator | Path to the uploaded IFC file |
| `language` | Orchestrator | Output language: `en`, `tr`, or `ar` |
| `parsed_elements` | IFC Parser | List of element data dicts |
| `building_info` | IFC Parser | Project and building metadata |
| `classified_elements` | Classifier | Category to element ID mapping |
| `calculated_quantities` | Calculator | Per-element quantity breakdowns |
| `material_list` | Material Mapper | Aggregated material list with waste |
| `boq_data` | BOQ Generator | Structured BOQ sections and items |
| `validation_report` | Validator | Check results and AI assessment |
| `boq_file_paths` | Orchestrator (export) | Paths to generated report files |
| `status` | Each agent | Current processing status |
| `warnings` | Multiple agents | Non-fatal issues accumulated |
| `errors` | Multiple agents | Fatal issues that stop the pipeline |

---

## Inter-Stage Validation Gates

Between each pipeline stage, the Orchestrator runs validation gates -- fast, deterministic checks that catch catastrophic failures before downstream agents waste time on empty or corrupt data:

| After Stage | Gate Check |
|---|---|
| IFC Parsing | At least one element was parsed; building info is present (warning only if absent) |
| Classification | At least some elements were classified; fails if >50% unclassified, warns if >20% |
| Quantity Calculation | At least one quantity was computed; warns about all-zero quantities |
| Material Mapping | At least one material was produced |
| BOQ Generation | BOQ data structure is not empty; warns about empty sections |

If any gate fails, the pipeline stops immediately and reports the error. Warnings are accumulated but do not block processing.

---

## Request Lifecycle

When a user uploads an IFC file through the web interface:

1. The frontend sends the file via `POST /api/projects/upload`
2. The API validates the file (extension, size, IFC magic bytes), saves it, creates a database record
3. The pipeline runs asynchronously in the background via `asyncio.create_task`
4. Progress updates are pushed to the frontend via WebSocket (`/ws/{project_id}`)
5. On completion, results are persisted to the database and report files are generated
6. The frontend receives the `complete` WebSocket message and enables download buttons
7. The user downloads reports via `GET /api/projects/{project_id}/download/{format}`
