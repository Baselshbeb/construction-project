# Data Handling

This document describes what data Metraj collects, where it is stored, what is transmitted to external services, and how long data is retained.

---

## Data Collected

When you use Metraj, the following data is collected and processed:

### IFC Files

- **What:** The IFC building model file you upload
- **Where stored:** `uploads/` directory on the server, saved with a UUID filename (e.g., `a1b2c3d4-e5f6-7890.ifc`)
- **Original filename:** Stored in the SQLite database for display purposes only; never used as a file path (prevents path traversal)

### Processing Results

- **What:** The output of the processing pipeline -- building metadata, element classifications, calculated quantities, material lists, BOQ data, validation reports, warnings, and errors
- **Where stored:** Serialized as JSON in the SQLite database (`data/metraj.db`)
- **Additional files:** Generated reports (Excel, CSV, JSON) stored in the `output/` directory, organized by project ID

### Project Metadata

- **What:** Project ID (UUID), original filename, processing status, language selection, creation timestamp
- **Where stored:** SQLite database

---

## Where Data Is Stored

### Local Storage

All data is stored locally on the server running Metraj:

| Data | Location | Format |
|---|---|---|
| Uploaded IFC files | `uploads/` directory | Binary IFC/STEP files |
| Project database | `data/metraj.db` | SQLite database |
| Generated reports | `output/{project_id}/` | Excel, CSV, JSON files |
| Application logs | Console output (loguru) | Text |

In the default development configuration, all paths are relative to the working directory where the server is started.

### No Cloud Storage (Default)

By default, Metraj stores everything locally. No data is sent to cloud storage services. For production deployment with S3 or similar storage, see [Production Deployment](../deployment/production.md).

---

## What Is Sent to the Anthropic API

Metraj uses the Anthropic Claude API for three pipeline stages. Here is exactly what data is transmitted:

### Classifier Stage

For each building element, the following is sent:

- Element ID (integer)
- IFC type name (e.g., "IfcWall")
- Element name (e.g., "Basic Wall: 200mm Concrete")
- Storey name (e.g., "Ground Floor")
- Whether the element is external (boolean)
- Wall thickness in millimetres
- Material names from the IFC file

### Material Mapper Stage

For each building element:

- Element ID
- IFC type name
- Element name
- External flag
- BOQ category (assigned by classifier)
- Material names from the IFC file
- Calculated quantities (e.g., "Gross wall area: 30.0 m2", "Wall volume: 6.0 m3")

Additionally, the system prompt includes the waste factors table and element rules from `src/data/`.

### Validator Stage

A summary of the entire project:

- Building name and storey list
- Element type counts and category counts
- Material descriptions with quantities and waste factors
- Key ratios (total concrete, total steel, total floor area)
- BOQ section count and titles

### What Is NOT Sent to Anthropic

The following data is **never** transmitted to the Anthropic API:

- The full IFC file
- 3D geometry or coordinate data
- Detailed property sets (beyond IsExternal)
- User identity, email, or contact information
- Server file paths or configuration
- API keys or credentials
- Database contents

---

## Data Retention

### Automatic Cleanup

On server startup, Metraj automatically deletes projects older than **30 days**. This includes:

- The database record
- Note: Uploaded IFC files and generated reports on disk are not automatically deleted by this cleanup. File cleanup should be configured separately for production deployments.

### Manual Deletion

There is currently no API endpoint for manual project deletion. To delete a project manually:

1. Remove the database record from `data/metraj.db`
2. Delete the uploaded file from `uploads/{project_id}.ifc`
3. Delete the output directory `output/{project_id}/`

---

## Anthropic API Data Policy

As of the time of writing, Anthropic's API data policy states:

- Data sent through the API is **not used to train Claude models**
- API inputs and outputs may be **temporarily stored** for abuse monitoring and safety purposes
- Anthropic does not share API data with third parties

This means your building data sent during classification, material mapping, and validation is not used to improve Anthropic's models and is not shared with other users.

For the most current Anthropic data policies, refer to [Anthropic's Usage Policy](https://www.anthropic.com/policies) and [API Terms of Service](https://www.anthropic.com/api-terms).

---

## User Responsibilities

### Proprietary Data

If your IFC files contain proprietary or confidential building designs, be aware that element-level data (names, types, quantities, materials) is sent to the Anthropic API during processing. While Anthropic's policy states this data is not used for training, the data does leave your local network.

If sending any building data to an external API is not acceptable for your organization, Metraj in its current form may not be suitable. The AI-powered stages (Classification, Material Mapping, Validation) require the Claude API to function.

### Data Security

You are responsible for:

- Securing the server running Metraj (access controls, network security)
- Managing the `.env` file containing your Anthropic API key
- Configuring appropriate access controls for the upload and output directories
- Complying with any data handling requirements specific to your organization or jurisdiction
- Backing up data that needs to be retained beyond the 30-day automatic cleanup period

### GDPR and Data Protection

Metraj processes building model data, not personal data. However, if your IFC files contain personal information (e.g., architect names in project metadata, client names in building names), this information may be transmitted to the Anthropic API as part of the building metadata. Consider sanitizing IFC files before upload if this is a concern.
