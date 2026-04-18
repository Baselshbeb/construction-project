"""
Per-project structured logging utility.

Creates a dedicated log file for each project so that every pipeline run
has a complete, human-readable trace of what happened — from IFC parsing
through to the final BOQ report.

Usage:
    from src.utils.project_logger import ProjectLogger
    plog = ProjectLogger("proj_abc123")
    plog.log_step("IFC_PARSE", "Started parsing residential_v2.ifc")
    plog.log_element("CLASSIFY", 19, "IfcWall", "classified as external_walls")
    plog.log_ai_call("MATERIAL_MAP", "claude-sonnet-4-20250514", input_tokens=820, output_tokens=350)
    plog.log_summary(total_elements=47, ...)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ProjectLogger:
    """Structured logger that writes a per-project pipeline log file.

    Each line follows the format:
        [TIMESTAMP] [STEP] [LEVEL] message | key=value | ...

    The resulting file reads like a narrative of the entire pipeline run.
    """

    def __init__(self, project_id: str) -> None:
        """Initialise the logger and create the log file.

        Args:
            project_id: Unique identifier for the project.
        """
        self.project_id = project_id
        self._log_dir = Path("logs/projects") / project_id
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._log_dir / "pipeline.log"

        # Write a header so the file is immediately recognisable.
        self._write(
            f"{'=' * 80}\n"
            f"  Metraj Pipeline Log — Project {project_id}\n"
            f"  Created: {self._now()}\n"
            f"{'=' * 80}\n"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_step(self, step: str, message: str, **details: Any) -> None:
        """Log a pipeline step event (e.g., 'IFC Parsing started').

        Args:
            step: Pipeline step name (e.g. IFC_PARSE, CLASSIFY).
            message: Human-readable description.
            **details: Arbitrary key-value pairs appended to the line.
        """
        extra = self._format_details(details)
        self._write(f"[{self._now()}] [{step}] [INFO] {message}{extra}\n")

    def log_element(
        self,
        step: str,
        element_id: int,
        element_type: str,
        action: str,
        **details: Any,
    ) -> None:
        """Log an element-level event.

        Args:
            step: Pipeline step name.
            element_id: IFC element ID (e.g. #19).
            element_type: IFC type (e.g. IfcWall).
            action: What happened (e.g. 'classified as external_walls').
            **details: Extra context appended to the line.
        """
        extra = self._format_details(details)
        self._write(
            f"[{self._now()}] [{step}] [INFO] {element_type} #{element_id}: "
            f"{action} | element_id={element_id}{extra}\n"
        )

    def log_ai_call(
        self,
        step: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        batch_size: int = 0,
        success: bool = True,
        error: str = "",
    ) -> None:
        """Log an AI / LLM API call with token usage.

        Args:
            step: Pipeline step that triggered the call.
            model: Model identifier (e.g. claude-sonnet-4-20250514).
            input_tokens: Number of input tokens consumed.
            output_tokens: Number of output tokens produced.
            batch_size: Number of elements in the batch (0 = single call).
            success: Whether the call succeeded.
            error: Error message if the call failed.
        """
        status = "SUCCESS" if success else "FAIL"
        level = "INFO" if success else "ERROR"
        parts = [
            f"[{self._now()}] [{step}] [{level}] AI call {status}",
            f"model={model}",
            f"in_tokens={input_tokens}",
            f"out_tokens={output_tokens}",
        ]
        if batch_size:
            parts.append(f"batch_size={batch_size}")
        if error:
            parts.append(f"error={error}")
        self._write(" | ".join(parts) + "\n")

    def log_validation(
        self,
        check_name: str,
        passed: bool,
        value: Any = None,
        threshold: str = "",
        message: str = "",
    ) -> None:
        """Log a validation check result.

        Args:
            check_name: Name of the validation rule.
            passed: Whether the check passed.
            value: The actual value that was checked.
            threshold: Expected range / limit as a string.
            message: Optional explanatory note.
        """
        verdict = "PASS" if passed else "FAIL"
        level = "INFO" if passed else "WARN"
        parts = [f"[{self._now()}] [VALIDATION] [{level}] [{verdict}] {check_name}"]
        if value is not None:
            parts.append(f"value={value}")
        if threshold:
            parts.append(f"threshold={threshold}")
        if message:
            parts.append(f"message={message}")
        self._write(" | ".join(parts) + "\n")

    def log_error(
        self, step: str, message: str, element_id: int | None = None, **details: Any
    ) -> None:
        """Log an error with full context.

        Args:
            step: Pipeline step where the error occurred.
            message: Error description.
            element_id: Optional element ID related to the error.
            **details: Extra context appended to the line.
        """
        eid_part = f" | element_id={element_id}" if element_id is not None else ""
        extra = self._format_details(details)
        self._write(
            f"[{self._now()}] [{step}] [ERROR] {message}{eid_part}{extra}\n"
        )

    def log_summary(
        self,
        total_elements: int,
        total_materials: int,
        total_boq_items: int,
        confidence_summary: dict,
        warnings: list[str],
        errors: list[str],
        duration_seconds: float,
    ) -> None:
        """Log the final pipeline summary with all stats.

        Args:
            total_elements: Number of IFC elements processed.
            total_materials: Number of distinct materials mapped.
            total_boq_items: Number of BOQ line items generated.
            confidence_summary: Dict of confidence-level counts (e.g. {high: 30, medium: 5}).
            warnings: List of warning messages generated during the run.
            errors: List of error messages generated during the run.
            duration_seconds: Total pipeline duration in seconds.
        """
        divider = "-" * 60
        lines = [
            f"\n{divider}\n",
            f"  PIPELINE SUMMARY — Project {self.project_id}\n",
            f"{divider}\n",
            f"  Duration        : {duration_seconds:.1f}s\n",
            f"  Elements        : {total_elements}\n",
            f"  Materials       : {total_materials}\n",
            f"  BOQ items       : {total_boq_items}\n",
            f"  Confidence      : {confidence_summary}\n",
            f"  Warnings ({len(warnings):>3}) :\n",
        ]
        for w in warnings:
            lines.append(f"    - {w}\n")
        lines.append(f"  Errors   ({len(errors):>3}) :\n")
        for e in errors:
            lines.append(f"    - {e}\n")
        lines.append(f"{divider}\n")
        self._write("".join(lines))

    def get_log_path(self) -> str:
        """Return the absolute path to the log file."""
        return str(self._log_path.resolve())

    def get_log_contents(self) -> str:
        """Read and return the full log file contents."""
        try:
            return self._log_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> str:
        """Return an ISO-8601 timestamp in UTC."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    @staticmethod
    def _format_details(details: dict[str, Any]) -> str:
        """Format keyword arguments as ' | key=value' pairs."""
        if not details:
            return ""
        return " | " + " | ".join(f"{k}={v}" for k, v in details.items())

    def _write(self, text: str) -> None:
        """Append *text* to the log file."""
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(text)
