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

    async def run(
        self, ifc_file_path: str, config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Run the complete pipeline on an IFC file.

        Args:
            ifc_file_path: Path to the IFC file.
            config: Optional configuration dict.

        Returns:
            Final ProjectState with all results.
        """
        # Initialize state
        state: dict[str, Any] = {
            "ifc_file_path": ifc_file_path,
            "project_config": config or {},
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
            "status": ProcessingStatus.PENDING,
            "current_step": "",
            "processing_log": [],
        }

        return await self.execute(state)

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the full pipeline."""
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

        for step_name, agent in pipeline:
            self.log(f"Step: {step_name}...")

            try:
                state = await agent.execute(state)
            except Exception as e:
                self.log_error(f"FAILED at {step_name}: {e}")
                state["errors"].append(f"Pipeline failed at {step_name}: {e}")
                state["status"] = ProcessingStatus.FAILED
                break

            # Check if previous step failed
            if state.get("status") == ProcessingStatus.FAILED:
                self.log_error(f"Pipeline stopped at {step_name} due to errors")
                break

        # Export reports if pipeline succeeded and BOQ was generated
        if state.get("boq_data") and state.get("status") != ProcessingStatus.FAILED:
            self.log("Exporting reports...")
            try:
                ifc_name = Path(state["ifc_file_path"]).stem
                output_dir = Path("output") / ifc_name
                output_dir.mkdir(parents=True, exist_ok=True)

                # Excel
                excel_path = self.export_service.export_excel(
                    state["boq_data"], output_dir / f"{ifc_name}_BOQ.xlsx"
                )
                state["boq_file_paths"]["xlsx"] = str(excel_path)

                # CSV
                csv_path = self.export_service.export_csv(
                    state["boq_data"], output_dir / f"{ifc_name}_BOQ.csv"
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
        self.log("=" * 50)
        if state["status"] == ProcessingStatus.COMPLETED:
            self.log("Pipeline COMPLETED successfully")
        else:
            self.log(f"Pipeline ended with status: {state['status']}")

        self.log("Processing log:")
        for entry in state.get("processing_log", []):
            self.log(f"  - {entry}")
        self.log("=" * 50)

        return state
