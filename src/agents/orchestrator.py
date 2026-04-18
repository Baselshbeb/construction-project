"""
Orchestrator Agent - coordinates the entire pipeline from IFC to BOQ.

Coach Simple explains:
    "This is the foreman on the construction site. They don't lay bricks
    or pour concrete themselves - they tell each worker what to do and
    in what order. First the Parser reads the blueprint, then the
    Classifier sorts the pieces, then the Calculator measures, then
    the Material Mapper makes the shopping list, and finally the
    Validator checks everything."

This is the main entry point for processing an IFC file.

Usage:
    from src.agents.orchestrator import Orchestrator
    orchestrator = Orchestrator()
    result = await orchestrator.run("path/to/building.ifc")
"""

from __future__ import annotations

from typing import Any

from pathlib import Path

from src.agents.base_agent import BaseAgent
from src.agents.ifc_parser import IFCParserAgent
from src.agents.classifier import ClassifierAgent
from src.agents.calculator import CalculatorAgent
from src.agents.material_mapper import MaterialMapperAgent
from src.agents.boq_generator import BOQGeneratorAgent
from src.agents.validator import ValidatorAgent
from src.models.project import ProcessingStatus
from src.services.export_service import ExportService
from src.services.llm_service import LLMService
from src.utils.logger import get_logger
from src.utils.project_logger import ProjectLogger

logger = get_logger("orchestrator")


class Orchestrator(BaseAgent):
    """Coordinates the full processing pipeline."""

    def __init__(self):
        super().__init__(
            name="orchestrator",
            description="Coordinates the full IFC-to-BOQ pipeline",
        )
        # Shared LLM service for all AI-powered agents
        self.llm_service = LLMService()

        # Initialize all agents (AI agents share the same LLM service)
        self.parser = IFCParserAgent()
        self.classifier = ClassifierAgent(llm_service=self.llm_service)
        self.calculator = CalculatorAgent()
        self.material_mapper = MaterialMapperAgent(llm_service=self.llm_service)
        self.boq_generator = BOQGeneratorAgent()
        self.validator = ValidatorAgent(llm_service=self.llm_service)
        self.export_service = ExportService()

    SUPPORTED_LANGUAGES = {"en", "tr", "ar"}

    async def run(
        self, ifc_file_path: str, config: dict[str, Any] | None = None,
        language: str = "en",
    ) -> dict[str, Any]:
        """Run the complete pipeline on an IFC file.

        Args:
            ifc_file_path: Path to the IFC file.
            config: Optional configuration dict.
            language: Output language for BOQ/reports ("en", "tr", "ar").

        Returns:
            Final ProjectState with all results.

        Raises:
            FileNotFoundError: If the IFC file does not exist.
            ValueError: If the language is not supported.
        """
        # Validate inputs
        ifc_path = Path(ifc_file_path)
        if not ifc_path.exists():
            raise FileNotFoundError(f"IFC file not found: {ifc_file_path}")
        if not ifc_path.suffix.lower() == ".ifc":
            raise ValueError(f"Not an IFC file: {ifc_file_path}")

        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language '{language}'. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_LANGUAGES))}"
            )

        # Initialize state
        state: dict[str, Any] = {
            "ifc_file_path": ifc_file_path,
            "project_config": config or {},
            "language": language,
            "parsed_elements": [],
            "building_info": None,
            "classified_elements": {},
            "calculated_quantities": [],
            "material_list": [],
            "boq_data": None,
            "boq_file_paths": {},
            "validation_report": None,
            "warnings": [],
            "errors": [],
            "failed_elements": [],   # Track elements that failed during processing
            "skipped_elements": [],  # Track elements skipped due to missing data
            "status": ProcessingStatus.PENDING,
            "current_step": "",
            "processing_log": [],
        }

        return await self.execute(state)

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the full pipeline."""
        import time as _time
        pipeline_start = _time.time()

        # Initialize per-project logger
        ifc_path = state.get("ifc_file_path", "")
        project_id = Path(ifc_path).stem if ifc_path else "unknown"
        plog = ProjectLogger(project_id)
        state["_project_logger"] = plog
        plog.log_step("Pipeline", f"Starting Metraj Pipeline for {Path(ifc_path).name}")

        self.log("=" * 50)
        self.log("Starting Metraj Pipeline")
        self.log("=" * 50)

        pipeline = [
            ("IFC Parsing", self.parser),
            ("Classification", self.classifier),
            ("Quantity Calculation", self.calculator),
            ("Material Mapping", self.material_mapper),
            ("BOQ Generation", self.boq_generator),
            ("Validation", self.validator),
        ]

        # Track completed steps for checkpointing
        completed_steps: list[str] = []
        resume_from = state.get("_resume_from")

        for step_name, agent in pipeline:
            # Skip already-completed steps if resuming
            if resume_from and step_name != resume_from and step_name not in completed_steps:
                if not completed_steps or pipeline.index((step_name, agent)) < next(
                    (i for i, (n, _) in enumerate(pipeline) if n == resume_from), 0
                ):
                    self.log(f"Skipping {step_name} (resuming from {resume_from})")
                    continue

            self.log(f"Step: {step_name}...")
            resume_from = None  # Clear after reaching resume point
            step_start = _time.time()
            plog.log_step(step_name, "Starting")

            try:
                state = await agent.execute(state)
            except Exception as e:
                self.log_error(f"FAILED at {step_name}: {e}")
                state["errors"].append(f"Pipeline failed at {step_name}: {e}")
                state["status"] = ProcessingStatus.FAILED
                state["_last_completed_step"] = completed_steps[-1] if completed_steps else None
                plog.log_error(step_name, str(e))
                break

            step_elapsed = _time.time() - step_start
            plog.log_step(step_name, f"Completed in {step_elapsed:.1f}s")
            completed_steps.append(step_name)

            # Check if previous step failed
            if state.get("status") == ProcessingStatus.FAILED:
                self.log_error(f"Pipeline stopped at {step_name} due to errors")
                break

            # Inter-stage validation gates
            gate_error = self._validate_stage(step_name, state)
            if gate_error:
                self.log_error(f"Stage gate failed after {step_name}: {gate_error}")
                state["errors"].append(gate_error)
                state["status"] = ProcessingStatus.FAILED
                plog.log_validation(f"Gate:{step_name}", False, message=gate_error)
                break
            else:
                plog.log_validation(f"Gate:{step_name}", True)

            # Checkpoint: record last successful step
            state["_last_completed_step"] = step_name

        # Export reports only if pipeline completed successfully and BOQ was generated
        if state.get("boq_data") and state.get("status") == ProcessingStatus.COMPLETED:
            self.log("Exporting reports...")
            lang = state.get("language", "en")
            try:
                ifc_name = Path(state["ifc_file_path"]).stem
                output_dir = Path("output") / ifc_name
                output_dir.mkdir(parents=True, exist_ok=True)

                # Excel
                excel_path = self.export_service.export_excel(
                    state["boq_data"], output_dir / f"{ifc_name}_BOQ.xlsx",
                    language=lang,
                )
                state["boq_file_paths"]["xlsx"] = str(excel_path)

                # CSV
                csv_path = self.export_service.export_csv(
                    state["boq_data"], output_dir / f"{ifc_name}_BOQ.csv",
                    language=lang,
                )
                state["boq_file_paths"]["csv"] = str(csv_path)

                # JSON
                json_path = self.export_service.export_json(
                    state["boq_data"], output_dir / f"{ifc_name}_BOQ.json"
                )
                state["boq_file_paths"]["json"] = str(json_path)

                self.log(f"Reports saved to: {output_dir}")
                state["processing_log"].append(
                    f"Export: Excel, CSV, JSON saved to {output_dir}"
                )
            except Exception as e:
                self.log_error(f"Export failed: {e}")
                state["warnings"].append(f"Report export failed: {e}")

        # Final summary
        pipeline_elapsed = _time.time() - pipeline_start

        self.log("=" * 50)
        if state["status"] == ProcessingStatus.COMPLETED:
            self.log("Pipeline COMPLETED successfully")
        else:
            self.log(f"Pipeline ended with status: {state['status']}")

        # Report failed/skipped elements
        failed = state.get("failed_elements", [])
        skipped = state.get("skipped_elements", [])
        if failed:
            self.log_warning(f"Failed elements: {len(failed)}")
        if skipped:
            self.log_warning(f"Skipped elements: {len(skipped)}")

        self.log("Processing log:")
        for entry in state.get("processing_log", []):
            self.log(f"  - {entry}")
        self.log("=" * 50)

        # Write per-project summary log
        boq_data = state.get("boq_data") or {}
        plog.log_summary(
            total_elements=len(state.get("parsed_elements", [])),
            total_materials=len(state.get("material_list", [])),
            total_boq_items=boq_data.get("total_line_items", 0),
            confidence_summary=boq_data.get("confidence_summary", {}),
            warnings=state.get("warnings", []),
            errors=state.get("errors", []),
            duration_seconds=pipeline_elapsed,
        )
        state["_project_log_path"] = plog.get_log_path()

        return state

    @staticmethod
    def _validate_stage(step_name: str, state: dict[str, Any]) -> str | None:
        """Validate state after a pipeline stage. Returns error message or None.

        These are fast, deterministic checks that catch catastrophic failures
        early — before downstream agents waste time on empty or corrupt data.
        """
        if step_name == "IFC Parsing":
            elements = state.get("parsed_elements", [])
            if not elements:
                return (
                    "IFC Parsing produced no elements. "
                    "The file may be empty, corrupt, or contain no recognized building elements."
                )
            building_info = state.get("building_info")
            if not building_info:
                # Non-fatal — add a warning but don't block
                state["warnings"].append(
                    "No building metadata found in IFC file (missing IfcProject/IfcBuilding)"
                )

        elif step_name == "Classification":
            elements = state.get("parsed_elements", [])
            classified = state.get("classified_elements", {})
            total_classified = sum(len(ids) for ids in classified.values())
            if elements and total_classified == 0:
                return (
                    "Classification failed: no elements were classified. "
                    "AI classification may have returned an invalid response."
                )
            # Warn if many elements are unclassified
            unclassified_count = len(elements) - total_classified
            if unclassified_count > 0:
                pct = (unclassified_count / len(elements)) * 100
                if pct > 50:
                    return (
                        f"Classification largely failed: {unclassified_count}/{len(elements)} "
                        f"elements ({pct:.0f}%) were not classified."
                    )
                if pct > 20:
                    state["warnings"].append(
                        f"{unclassified_count}/{len(elements)} elements ({pct:.0f}%) "
                        f"were not classified — BOQ may be incomplete."
                    )

        elif step_name == "Quantity Calculation":
            calc_q = state.get("calculated_quantities", [])
            if not calc_q:
                return (
                    "Quantity calculation produced no results. "
                    "Elements may have no measurable quantities."
                )
            # Check for elements with all-zero quantities
            zero_count = sum(
                1 for cq in calc_q
                if all(q.get("quantity", 0) == 0 for q in cq.get("quantities", []))
            )
            if zero_count > 0:
                state["warnings"].append(
                    f"{zero_count} element(s) have all-zero quantities — "
                    f"check if IFC quantities are populated."
                )

        elif step_name == "Material Mapping":
            materials = state.get("material_list", [])
            if not materials:
                return (
                    "Material mapping produced no materials. "
                    "AI mapping may have failed for all element types."
                )

        elif step_name == "BOQ Generation":
            boq = state.get("boq_data")
            if not boq:
                return "BOQ generation produced no output."
            sections = boq.get("sections", [])
            if not sections:
                state["warnings"].append(
                    "BOQ has no sections — all materials may be uncategorized."
                )

        return None
