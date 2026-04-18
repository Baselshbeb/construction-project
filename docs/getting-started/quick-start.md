# Quick Start

Process your first IFC file in under 5 minutes. This guide assumes you have completed the [Installation](installation.md) steps.

---

## Step 1: Start the Backend

Open a terminal in the project root and activate your virtual environment, then start the FastAPI server:

```bash
uvicorn api.app:app --reload --port 8000
```

Expected output:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx]
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Database initialized
INFO:     Application startup complete.
```

Verify the server is running by visiting `http://localhost:8000/api/health` in your browser. You should see:

```json
{
  "status": "ok",
  "service": "Metraj AI",
  "version": "0.5.0",
  "checks": {
    "api": "ok",
    "uploads_writable": "ok",
    "disk_space": "ok",
    "api_key_configured": "ok"
  }
}
```

If `api_key_configured` shows `"missing"`, your `.env` file is not set up correctly. See [Installation](installation.md).

---

## Step 2: Start the Frontend

Open a second terminal, navigate to the frontend directory, and start the Next.js development server:

```bash
cd frontend
npm run dev
```

Expected output:

```
  > Ready on http://localhost:3000
```

---

## Step 3: Open the Application

Open your browser and navigate to:

```
http://localhost:3000
```

You will see the Metraj web interface with an upload area for IFC files.

---

## Step 4: Upload an IFC File

1. Click the upload area or drag and drop an IFC file onto it.
2. Select the output language (English, Turkish, or Arabic) if the option is presented.
3. Click **Upload** or the equivalent action button.

The system accepts `.ifc` files up to 500 MB in size. The file must be a valid IFC/STEP file (IFC2x3 or IFC4 schema).

If you do not have an IFC file, you can find sample files at:
- [IFC Model Repository](https://www.ifcwiki.org/index.php?title=KIT_IFC_Examples)
- [buildingSMART Sample Files](https://github.com/buildingSMART/Sample-Test-Files)
- The `tests/fixtures/` directory in this project (if sample files are included)

---

## Step 5: Watch the Pipeline Progress

After uploading, the interface displays a real-time progress indicator showing each pipeline stage:

1. **IFC Parsing** -- Reading the building model and extracting elements
2. **Classification** -- AI categorizes elements into BOQ sections
3. **Quantity Calculation** -- Computing areas, volumes, and counts
4. **Material Mapping** -- AI determines required construction materials
5. **BOQ Generation** -- Assembling the structured Bill of Quantities
6. **Validation** -- Arithmetic checks and AI engineering review

The progress updates are delivered in real time via WebSocket. Each stage typically takes a few seconds, though larger files may take longer during the parsing and AI stages.

---

## Step 6: Download the BOQ

Once processing completes, the interface displays:
- A summary of the results (element count, material count, validation score)
- Download buttons for the generated reports

Available formats:

| Format | Best For |
|---|---|
| **Excel (.xlsx)** | Professional use, procurement, cost estimation. Includes BOQ sheet, Material Summary, and Audit Trail. |
| **CSV (.csv)** | Data import into other systems, spreadsheet analysis. |
| **JSON (.json)** | Programmatic access, integration with other software. |

Click the download button for your preferred format.

---

## Using the Command Line

You can also run Metraj directly from the command line without the web interface:

```bash
python -m src.main path/to/building.ifc
```

This runs the full pipeline and saves reports to the `output/` directory. The command-line interface is useful for batch processing or integration into other workflows.

---

## What Happens Next

- Open the Excel file to review the BOQ -- see [Understanding the BOQ](../user-guide/understanding-boq.md)
- Learn about accuracy expectations -- see [Accuracy and Limitations](../user-guide/accuracy-and-limitations.md)
- Explore the system architecture -- see [System Overview](../architecture/overview.md)
- Configure advanced settings -- see [Configuration](configuration.md)
