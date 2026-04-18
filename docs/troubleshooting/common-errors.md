# Common Errors

This document catalogs known errors, their causes, and solutions.

---

## Installation Errors

### IfcOpenShell installation fails

**Symptom:**

```
ERROR: Could not find a version that satisfies the requirement ifcopenshell
```

or

```
ModuleNotFoundError: No module named 'ifcopenshell'
```

**Cause:** IfcOpenShell binary wheels may not be available for your Python version or platform.

**Solution:**

1. Ensure you are using Python 3.13 or later
2. Try installing with pip: `pip install ifcopenshell`
3. If that fails, try conda: `conda install -c conda-forge ifcopenshell`
4. As a last resort, download a pre-built wheel from the [IfcOpenShell releases](https://github.com/IfcOpenShell/IfcOpenShell/releases) page

### pip install fails with "Microsoft Visual C++ 14.0 required" (Windows)

**Symptom:**

```
error: Microsoft Visual C++ 14.0 or greater is required
```

**Cause:** Some Python packages require C++ compilation on Windows.

**Solution:** Install the Visual Studio Build Tools from [visualstudio.microsoft.com](https://visualstudio.microsoft.com/visual-cpp-build-tools/), selecting the "Desktop development with C++" workload.

### npm install fails in frontend

**Symptom:**

```
npm ERR! engine Unsupported engine
```

**Cause:** Node.js version is too old.

**Solution:** Update Node.js to version 18 or later from [nodejs.org](https://nodejs.org/).

---

## Runtime Errors

### "ANTHROPIC_API_KEY not set" / "LLM Service not initialized"

**Symptom:**

```
WARNING: No ANTHROPIC_API_KEY set. LLM calls will fail.
```

or the pipeline fails at the Classification stage with:

```
RuntimeError: LLM Service not initialized. Set ANTHROPIC_API_KEY in .env
```

**Cause:** The `.env` file is missing or does not contain the `ANTHROPIC_API_KEY` variable.

**Solution:**

1. Create a `.env` file in the project root (not in `src/` or `api/`)
2. Add your API key: `ANTHROPIC_API_KEY=sk-ant-api03-your-key-here`
3. Restart the server

### "IFC file not found"

**Symptom:**

```
FileNotFoundError: IFC file not found: path/to/file.ifc
```

**Cause:** The specified file path does not exist or is not accessible.

**Solution:** Verify the file path. When using the CLI, provide the full path to the IFC file. When using the web interface, the file is uploaded and stored automatically.

### "Not an IFC file"

**Symptom:**

```
ValueError: Not an IFC file: path/to/file.dwg
```

or via API:

```
400: Only .ifc files are supported
```

**Cause:** The uploaded file does not have an `.ifc` extension.

**Solution:** Export your building model as IFC format. See [Uploading IFC Files](../user-guide/uploading-ifc.md) for export instructions.

### "Invalid IFC file. File does not appear to be a valid IFC/STEP file."

**Symptom:**

```
400: Invalid IFC file. File does not appear to be a valid IFC/STEP file.
```

**Cause:** The file has an `.ifc` extension but does not start with the `ISO-10303-21` header. The file may be corrupted, empty, or not actually in IFC format.

**Solution:**

1. Open the file in a text editor and check the first line. It should start with `ISO-10303-21;`
2. Try re-exporting the IFC file from your BIM software
3. Verify the file is not a compressed/zipped IFC (`.ifczip` or `.ifcxml` are different formats)

### "File too large. Maximum size is 500 MB."

**Symptom:**

```
413: File too large. Maximum size is 500 MB.
```

**Cause:** The IFC file exceeds the 500 MB upload limit.

**Solution:**

1. Reduce the IFC file size by exporting fewer elements or using a more compact IFC schema
2. If you control the server, modify `MAX_FILE_SIZE` in `api/app.py`

### "Too many uploads. Max 5 per 60s."

**Symptom:**

```
429: Too many uploads. Max 5 per 60s.
```

**Cause:** Rate limiting -- more than 5 files were uploaded from the same IP address within 60 seconds.

**Solution:** Wait 60 seconds and try again. This limit is per client IP address.

---

## Pipeline Stage Failures

### "IFC Parsing produced no elements"

**Symptom:**

```
Pipeline failed at IFC Parsing: IFC Parsing produced no elements.
The file may be empty, corrupt, or contain no recognized building elements.
```

**Cause:** The IFC file was parsed successfully but contained no building elements of recognized types (IfcWall, IfcSlab, IfcColumn, etc.).

**Solution:**

1. Open the IFC file in an IFC viewer to verify it contains building elements
2. Check if the model uses non-standard element types (the pipeline logs unrecognized types)
3. Ensure the IFC export from your BIM tool includes building elements (not just geometry or spaces)

### "Classification failed: no elements were classified"

**Symptom:**

```
Classification failed: no elements were classified.
AI classification may have returned an invalid response.
```

**Cause:** The Claude API returned an invalid or empty response for element classification.

**Solution:**

1. Check your API key is valid and has sufficient credits
2. Check your internet connection
3. Retry the upload -- transient API errors can cause this
4. Check the server logs for detailed error messages from the LLM service

### "Classification largely failed: X/Y elements not classified"

**Symptom:**

```
Classification largely failed: 45/50 elements (90%) were not classified.
```

**Cause:** The AI classified very few elements. This usually indicates a malformed AI response.

**Solution:**

1. Retry -- AI responses can vary between calls
2. Check if the element names are in a non-standard format or language that might confuse the classifier
3. Check the server logs for the raw AI response

### "Quantity calculation produced no results"

**Symptom:**

```
Quantity calculation produced no results. Elements may have no measurable quantities.
```

**Cause:** None of the parsed elements had any quantity data (no Qto property sets and no basic dimensions).

**Solution:**

1. Re-export the IFC file with "Export base quantities" enabled
2. Verify elements have dimensions (Length, Height, Width) or quantity sets in the IFC file

### "Material mapping produced no materials"

**Symptom:**

```
Material mapping produced no materials.
AI mapping may have failed for all element types.
```

**Cause:** The Claude API failed to generate material mappings for any elements.

**Solution:**

1. Check the API key and internet connection
2. Review server logs for AI error messages
3. Retry the upload

### "BOQ generation produced no output"

**Symptom:**

```
BOQ generation produced no output.
```

**Cause:** The material list was empty when the BOQ generator ran. This typically follows a material mapping failure.

**Solution:** Resolve the upstream material mapping issue first.

---

## WebSocket Issues

### Progress bar not updating

**Symptom:** The web interface shows the upload as "processing" but the progress bar does not advance.

**Cause:** WebSocket connection failed or was blocked.

**Solution:**

1. Check browser console for WebSocket errors
2. Verify the backend is running and accessible
3. If behind a reverse proxy, ensure WebSocket upgrade headers are forwarded (see [Production Deployment](../deployment/production.md))
4. Try refreshing the page -- if the project is already complete, the results will be shown immediately

### WebSocket connection closes immediately

**Symptom:** Browser console shows `WebSocket connection to 'ws://...' failed`.

**Cause:** The backend may not be running, or the port may be blocked.

**Solution:**

1. Verify the backend is running on the expected port
2. Check that no firewall is blocking WebSocket connections
3. Ensure `NEXT_PUBLIC_API_URL` in the frontend matches the actual backend URL

---

## AI-Specific Errors

### "Could not parse JSON from Claude after retries"

**Symptom:**

```
ValueError: Could not parse JSON from Claude after retries
```

**Cause:** Claude returned a response that could not be parsed as JSON after 3 attempts.

**Solution:**

1. This is usually a transient issue -- retry the upload
2. If persistent, the input data may be confusing the AI (very unusual element names, extremely large batches)
3. Check the server logs for the raw AI response text

### AI validation warnings in the report

**Symptom:** The BOQ is generated successfully but includes warnings like `[AI Review] Missing waterproofing for basement`.

**Cause:** The AI validator flagged potential issues based on its engineering assessment. These are advisory warnings, not errors.

**Solution:** Review each warning with your engineering judgment. The AI may be correct (you should add waterproofing) or it may be flagging something that is not applicable to your project. AI warnings never prevent BOQ generation.
