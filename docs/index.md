# Metraj -- AI-Powered Construction Material Estimation

**Metraj** is an intelligent system that transforms IFC/BIM building models into complete Bills of Quantities (BOQ) with all required construction materials. Named after the Turkish term for quantity takeoff, Metraj combines the precision of automated geometry extraction with the domain expertise of Claude AI to produce professional-grade material estimates.

Upload an IFC file. Receive a ready-to-use BOQ in Excel, CSV, or JSON -- complete with waste factors, audit trails, and AI-powered validation.

---

## Feature Highlights

### Automated IFC Parsing

Metraj reads Industry Foundation Classes (IFC) files -- the open standard for BIM data exchange -- and extracts every building element with its geometry, properties, and material layers. Supports IFC2x3 and IFC4 schemas from all major BIM tools including Revit, ArchiCAD, and FreeCAD.

### AI-Powered Element Classification

Using Claude AI, each building element is intelligently classified into standard BOQ sections (substructure, frame, walls, doors, windows, and more). The AI handles edge cases that rule-based systems miss, such as transfer beams, shear walls, and unconventional element naming.

### Precise Quantity Calculation

Calculates construction-relevant quantities from raw IFC data: gross and net wall areas with actual opening deductions per storey, slab volumes with formwork areas, column surface areas for plaster estimation, and more. Handles unit normalization (mm to m detection) and cross-exporter quantity key differences.

### Intelligent Material Mapping

Claude AI acts as a virtual quantity surveyor, determining exactly which construction materials are needed for each element -- concrete, reinforcement steel, formwork, plaster, paint, waterproofing, insulation, and finishing materials. Industry-standard waste factors are applied automatically.

### Professional Report Generation

Exports the BOQ as a professionally formatted Excel spreadsheet with section subtotals, grand total formulas, a material summary sheet, and a full audit trail. Also available in CSV and JSON formats. Reports are generated in English, Turkish, or Arabic.

### Hybrid Validation

Every BOQ passes through both arithmetic checks (negative quantities, concrete-to-steel ratios, storey coverage) and an AI-powered engineering review that catches issues simple math cannot -- missing waterproofing, contradictory material combinations, or unusual quantity ratios.

---

## Documentation

### Getting Started

- [Installation](getting-started/installation.md) -- Prerequisites and setup instructions
- [Quick Start](getting-started/quick-start.md) -- Process your first IFC file in 5 minutes
- [Configuration](getting-started/configuration.md) -- Environment variables and settings

### Architecture

- [System Overview](architecture/overview.md) -- High-level architecture and data flow
- [Agent Pipeline](architecture/agent-pipeline.md) -- The six-agent processing pipeline in detail
- [AI Transparency](architecture/ai-transparency.md) -- What data is sent to AI, what decisions it makes, and how errors are handled

### Reference

- [Glossary](reference/glossary.md) -- Trilingual glossary of construction and technical terms
- [Waste Factors](reference/waste-factors.md) -- Material waste factor reference table
- [Element Rules](reference/element-rules.md) -- IFC element to material mapping rules
- [IFC Compatibility](reference/ifc-compatibility.md) -- Supported schemas, element types, and BIM tools
- [API Endpoints](reference/api-endpoints.md) -- Complete REST and WebSocket API reference

### User Guide

- [Uploading IFC Files](user-guide/uploading-ifc.md) -- How to export and upload IFC files
- [Understanding the BOQ](user-guide/understanding-boq.md) -- Reading and using the generated BOQ
- [Accuracy and Limitations](user-guide/accuracy-and-limitations.md) -- What to expect and what to verify

### Legal

- [Data Handling](legal/data-handling.md) -- Privacy, data storage, and AI data policy
- [Accuracy Disclaimer](legal/accuracy-disclaimer.md) -- Formal disclaimer on estimation accuracy

### Deployment

- [Local Development](deployment/local-development.md) -- Setting up a development environment
- [Docker](deployment/docker.md) -- Container-based deployment
- [Production](deployment/production.md) -- Production deployment considerations

### Troubleshooting

- [Common Errors](troubleshooting/common-errors.md) -- Error catalog with solutions
- [FAQ](troubleshooting/faq.md) -- Frequently asked questions

### Project

- [Changelog](changelog.md) -- Version history and release notes
