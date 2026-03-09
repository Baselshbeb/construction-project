"""
Metraj - AI-Powered Construction Material Estimation System

Main entry point: run the full pipeline on an IFC file.

Usage:
    python -m src.main <ifc_file_path>
    python -m src.main tests/fixtures/simple_house.ifc
"""

from __future__ import annotations

import asyncio
import sys

from src.agents.orchestrator import Orchestrator


async def main(ifc_path: str) -> None:
    """Run the full Metraj pipeline."""
    orchestrator = Orchestrator()
    state = await orchestrator.run(ifc_path)

    # Print results summary
    print()
    print("=" * 60)
    print("  METRAJ - Material Estimation Results")
    print("=" * 60)

    # Building info
    bi = state.get("building_info")
    if bi:
        name = bi.get("building_name") or bi.get("project_name") or "Unknown"
        storeys = bi.get("storeys", [])
        print(f"\n  Building : {name}")
        print(f"  Storeys  : {', '.join(storeys)}")
        print(f"  Elements : {len(state.get('parsed_elements', []))}")

    # Classification
    classified = state.get("classified_elements", {})
    if classified:
        print(f"\n  Classification:")
        for cat, ids in sorted(classified.items()):
            print(f"    {cat:<20s}: {len(ids):>3d} elements")

    # Material list
    materials = state.get("material_list", [])
    if materials:
        print(f"\n  {'Material':<40s} {'Qty':>10s} {'Unit':>5s}  {'(+waste)':>10s}")
        print(f"  {'-'*70}")
        for mat in materials:
            desc = mat["description"][:38]
            print(
                f"  {desc:<40s} {mat['quantity']:>10.2f} {mat['unit']:>5s}"
                f"  {mat['total_quantity']:>10.2f}"
            )

    # Validation
    vr = state.get("validation_report")
    if vr:
        print(f"\n  Validation: {vr['score']} checks passed - {vr['status']}")
        summary = vr.get("summary", {})
        if summary:
            print(f"    Total concrete : {summary.get('total_concrete_m3', 0):>10.2f} m3")
            print(f"    Total steel    : {summary.get('total_steel_kg', 0):>10.0f} kg")
            print(f"    Floor area     : {summary.get('total_floor_area_m2', 0):>10.2f} m2")

    # Warnings
    warnings = state.get("warnings", [])
    if warnings:
        print(f"\n  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"    ! {w}")

    # Errors
    errors = state.get("errors", [])
    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    X {e}")

    print()
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.main <path_to_ifc_file>")
        print("Example: python -m src.main tests/fixtures/simple_house.ifc")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))
