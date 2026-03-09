"""
Hello IFC - Your First IFC File Explorer!

Coach Simple explains:
    "An IFC file is like a detailed blueprint of a building stored as a file.
    Inside it, every wall, floor, column, door, and window is described with
    its measurements, materials, and location.

    This script opens that file and shows you what's inside — like opening
    a LEGO box and counting what pieces you got!"

Run: python hello_ifc.py tests/fixtures/simple_house.ifc
"""

import sys
import ifcopenshell
import ifcopenshell.util.element


def explore_ifc(file_path: str):
    """Open an IFC file and explore its contents."""

    # =====================================================
    # STEP 1: Open the file
    # =====================================================
    print(f"\n{'='*60}")
    print(f"  HELLO IFC! Opening: {file_path}")
    print(f"{'='*60}\n")

    model = ifcopenshell.open(file_path)

    print(f"  Schema version : {model.schema}")
    print(f"  Total entities : {len(list(model))}")

    # =====================================================
    # STEP 2: Show the building hierarchy
    # =====================================================
    # Coach Simple: "A building in IFC is organized like a tree:
    #   Project > Site > Building > Storeys > Elements"

    print(f"\n{'='*60}")
    print(f"  BUILDING HIERARCHY")
    print(f"{'='*60}\n")

    projects = model.by_type("IfcProject")
    for project in projects:
        print(f"  Project: {project.Name}")

    sites = model.by_type("IfcSite")
    for site in sites:
        print(f"    Site: {site.Name}")

    buildings = model.by_type("IfcBuilding")
    for building in buildings:
        print(f"      Building: {building.Name}")

    storeys = model.by_type("IfcBuildingStorey")
    for storey in storeys:
        elevation = storey.Elevation or 0
        print(f"        Storey: {storey.Name} (elevation: {elevation}m)")

    # =====================================================
    # STEP 3: Count all building elements
    # =====================================================
    # Coach Simple: "Now let's count all the LEGO pieces by type!"

    print(f"\n{'='*60}")
    print(f"  ELEMENT COUNT (what's in this building?)")
    print(f"{'='*60}\n")

    element_types = [
        ("IfcWall", "Walls"),
        ("IfcSlab", "Slabs/Floors"),
        ("IfcColumn", "Columns"),
        ("IfcBeam", "Beams"),
        ("IfcDoor", "Doors"),
        ("IfcWindow", "Windows"),
        ("IfcStair", "Stairs"),
        ("IfcRoof", "Roofs"),
        ("IfcRailing", "Railings"),
        ("IfcCovering", "Coverings"),
    ]

    total = 0
    for ifc_type, display_name in element_types:
        elements = model.by_type(ifc_type)
        count = len(elements)
        if count > 0:
            print(f"  {display_name:20s}: {count:3d}")
            total += count

    print(f"  {'-'*28}")
    print(f"  {'TOTAL':20s}: {total:3d}")

    # =====================================================
    # STEP 4: Show details of each wall (with quantities!)
    # =====================================================
    # Coach Simple: "Now let's look closely at each wall.
    #   We want to know: How long? How high? How thick?
    #   What material? Is it an outside wall?"

    print(f"\n{'='*60}")
    print(f"  DETAILED WALL BREAKDOWN")
    print(f"{'='*60}")

    walls = model.by_type("IfcWall")
    for i, wall in enumerate(walls, 1):
        print(f"\n  Wall #{i}: {wall.Name}")
        print(f"  {'-'*40}")

        # Get quantities (measurements)
        qtos = ifcopenshell.util.element.get_psets(wall, qtos_only=True)
        if qtos:
            for qto_name, quantities in qtos.items():
                for prop_name, value in quantities.items():
                    if prop_name == "id":
                        continue
                    if isinstance(value, float):
                        print(f"    {prop_name:20s}: {value:10.2f}")

        # Get properties
        psets = ifcopenshell.util.element.get_psets(wall, psets_only=True)
        if psets:
            for pset_name, properties in psets.items():
                for prop_name, value in properties.items():
                    if prop_name == "id":
                        continue
                    print(f"    {prop_name:20s}: {value}")

        # Get material
        material = ifcopenshell.util.element.get_material(wall)
        if material:
            if hasattr(material, "Name"):
                print(f"    {'Material':20s}: {material.Name}")

        # Get which storey it belongs to
        container = ifcopenshell.util.element.get_container(wall)
        if container:
            print(f"    {'Storey':20s}: {container.Name}")

    # =====================================================
    # STEP 5: Quick summary of ALL quantities
    # =====================================================
    # Coach Simple: "This is the START of what metraj does!
    #   We're adding up all the volumes and areas.
    #   A real metraj system does this + maps to materials."

    print(f"\n{'='*60}")
    print(f"  QUICK QUANTITY SUMMARY (the start of metraj!)")
    print(f"{'='*60}\n")

    total_wall_area = 0
    total_wall_volume = 0
    total_slab_area = 0
    total_slab_volume = 0
    total_column_volume = 0
    total_beam_volume = 0

    # Sum wall quantities
    for wall in model.by_type("IfcWall"):
        qtos = ifcopenshell.util.element.get_psets(wall, qtos_only=True)
        for qto_name, quantities in qtos.items():
            total_wall_area += quantities.get("GrossArea", 0)
            total_wall_volume += quantities.get("GrossVolume", 0)

    # Sum slab quantities
    for slab in model.by_type("IfcSlab"):
        qtos = ifcopenshell.util.element.get_psets(slab, qtos_only=True)
        for qto_name, quantities in qtos.items():
            total_slab_area += quantities.get("Area", 0)
            total_slab_volume += quantities.get("GrossVolume", 0)

    # Sum column quantities
    for column in model.by_type("IfcColumn"):
        qtos = ifcopenshell.util.element.get_psets(column, qtos_only=True)
        for qto_name, quantities in qtos.items():
            total_column_volume += quantities.get("GrossVolume", 0)

    # Sum beam quantities
    for beam in model.by_type("IfcBeam"):
        qtos = ifcopenshell.util.element.get_psets(beam, qtos_only=True)
        for qto_name, quantities in qtos.items():
            total_beam_volume += quantities.get("GrossVolume", 0)

    print(f"  {'Item':30s} {'Quantity':>10s}  {'Unit':>5s}")
    print(f"  {'-'*50}")
    print(f"  {'Total Wall Area':30s} {total_wall_area:10.2f}  {'m2':>5s}")
    print(f"  {'Total Wall Volume':30s} {total_wall_volume:10.2f}  {'m3':>5s}")
    print(f"  {'Total Slab Area':30s} {total_slab_area:10.2f}  {'m2':>5s}")
    print(f"  {'Total Slab Volume':30s} {total_slab_volume:10.2f}  {'m3':>5s}")
    print(f"  {'Total Column Volume':30s} {total_column_volume:10.2f}  {'m3':>5s}")
    print(f"  {'Total Beam Volume':30s} {total_beam_volume:10.2f}  {'m3':>5s}")
    print(f"  {'-'*50}")
    total_concrete = total_wall_volume + total_slab_volume + total_column_volume + total_beam_volume
    print(f"  {'TOTAL CONCRETE NEEDED':30s} {total_concrete:10.2f}  {'m3':>5s}")
    print(f"  {'Est. Reinforcement Steel':30s} {total_concrete * 85:10.0f}  {'kg':>5s}")

    print(f"\n{'='*60}")
    print(f"  Coach Simple says:")
    print(f"  'This is just the beginning! A full metraj system would also")
    print(f"   calculate plaster, paint, tiles, waterproofing, formwork,")
    print(f"   and dozens more materials. That's what our AI agents will do!'")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python hello_ifc.py <path_to_ifc_file>")
        print("Example: python hello_ifc.py tests/fixtures/simple_house.ifc")
        sys.exit(1)

    explore_ifc(sys.argv[1])
