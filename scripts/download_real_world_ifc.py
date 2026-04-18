"""
Download free real-world IFC files from public GitHub repositories.

Downloads 5 sample IFC files covering different IFC versions and building
types for integration testing of the Metraj pipeline.

Usage:
    python -m scripts.download_real_world_ifc
    python scripts/download_real_world_ifc.py
"""

from __future__ import annotations

import ssl
import urllib.request
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "real_world"

DOWNLOADS = [
    {
        "name": "duplex_architecture.ifc",
        "url": "https://raw.githubusercontent.com/buildingSMART/Sample-Test-Files/master/IFC%202x3/Duplex%20Apartment/Duplex_A_20110907.ifc",
        "description": "buildingSMART Duplex Apartment (IFC2x3)",
    },
    {
        "name": "fzk_haus_ifc4.ifc",
        "url": "https://raw.githubusercontent.com/ibpsa/project1-wp-2-2-bim/master/IFC_Files/MISC/AC20-FZK-Haus.ifc",
        "description": "KIT FZK Haus (IFC4)",
    },
    {
        "name": "revit_arc_ifc4.ifc",
        "url": "https://raw.githubusercontent.com/youshengCode/IfcSampleFiles/main/Ifc4_Revit_ARC.ifc",
        "description": "Revit Architecture Export (IFC4)",
    },
    {
        "name": "sample_castle_ifc2x3.ifc",
        "url": "https://raw.githubusercontent.com/youshengCode/IfcSampleFiles/main/Ifc2x3_SampleCastle.ifc",
        "description": "Sample Castle (IFC2x3)",
    },
    {
        "name": "wall_only.ifc",
        "url": "https://raw.githubusercontent.com/opensourceBIM/TestFiles/master/TestData/data/WallOnly.ifc",
        "description": "Wall-only minimal model",
    },
]


def download_files() -> None:
    """Download all IFC files, skipping any that already exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Create an SSL context that works in most environments
    ssl_ctx = ssl.create_default_context()

    print(f"Downloading {len(DOWNLOADS)} IFC files to {OUTPUT_DIR}\n")

    success = 0
    skipped = 0
    failed = 0

    for entry in DOWNLOADS:
        dest = OUTPUT_DIR / entry["name"]

        if dest.exists():
            size_kb = dest.stat().st_size / 1024
            print(f"  [SKIP] {entry['name']:40s}  already exists ({size_kb:.0f} KB)")
            skipped += 1
            continue

        print(f"  [DL]   {entry['name']:40s}  {entry['description']}...", end="", flush=True)
        try:
            req = urllib.request.Request(entry["url"], headers={"User-Agent": "Metraj/1.0"})
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=60) as resp:
                data = resp.read()
            dest.write_bytes(data)
            size_kb = len(data) / 1024
            print(f"  OK ({size_kb:.0f} KB)")
            success += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1

    print(f"\nSummary: {success} downloaded, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    download_files()
