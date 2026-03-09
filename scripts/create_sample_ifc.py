"""
Create a sample IFC file with realistic building elements for testing.
This generates a simple 2-story house with walls, slabs, columns, doors, and windows.

Coach Simple explains:
    "Think of this like building a digital LEGO house. We place walls, add floors,
    put in doors and windows, and save it as an IFC file. Then our AI agents
    can practice reading this file and calculating materials."
"""

import ifcopenshell
import ifcopenshell.api


def create_sample_building():
    """Create a simple 2-story building with common elements."""

    # Start a new IFC file
    model = ifcopenshell.api.run("project.create_file", version="IFC4")

    # Create project structure: Project > Site > Building > Storeys
    project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="Sample House")

    # Set up units (metric)
    ifcopenshell.api.run("unit.assign_unit", model)

    # Create geometric contexts
    context = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body = ifcopenshell.api.run(
        "context.add_context", model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )

    # Create site and building
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Construction Site")
    building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="Sample House")

    # Create 2 storeys
    ground_floor = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcBuildingStorey", name="Ground Floor"
    )
    first_floor = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcBuildingStorey", name="First Floor"
    )

    # Set up spatial hierarchy
    ifcopenshell.api.run("aggregate.assign_object", model, products=[site], relating_object=project)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[building], relating_object=site)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[ground_floor, first_floor], relating_object=building)

    # Set storey elevations
    ground_floor.Elevation = 0.0
    first_floor.Elevation = 3.0

    # ---- CREATE BUILDING ELEMENTS ----

    # Helper to create a wall
    def create_wall(name, storey, length, height, thickness, is_external=True):
        wall = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWall", name=name)
        ifcopenshell.api.run("spatial.assign_container", model, products=[wall], relating_structure=storey)

        # Add quantity set
        qto = ifcopenshell.api.run("pset.add_qto", model, product=wall, name="Qto_WallBaseQuantities")
        ifcopenshell.api.run("pset.edit_qto", model, qto=qto, properties={
            "Length": length,
            "Height": height,
            "Width": thickness,
            "GrossArea": length * height,          # Total wall face area (one side)
            "NetArea": length * height * 0.85,      # Minus openings (~15% openings)
            "GrossVolume": length * height * thickness,
            "NetVolume": length * height * thickness * 0.85,
            "GrossSideArea": length * height,
            "NetSideArea": length * height * 0.85,
        })

        # Add property set
        pset = ifcopenshell.api.run("pset.add_pset", model, product=wall, name="Pset_WallCommon")
        ifcopenshell.api.run("pset.edit_pset", model, pset=pset, properties={
            "IsExternal": is_external,
            "FireRating": "2HR" if is_external else "1HR",
            "Reference": "RC200" if is_external else "BRICK100",
        })

        # Add material
        material = ifcopenshell.api.run("material.add_material", model,
                                         name="Concrete C25/30" if is_external else "Clay Brick")
        ifcopenshell.api.run("material.assign_material", model, products=[wall], material=material)

        return wall

    # Helper to create a slab
    def create_slab(name, storey, length, width, thickness):
        slab = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSlab", name=name)
        ifcopenshell.api.run("spatial.assign_container", model, products=[slab], relating_structure=storey)

        qto = ifcopenshell.api.run("pset.add_qto", model, product=slab, name="Qto_SlabBaseQuantities")
        ifcopenshell.api.run("pset.edit_qto", model, qto=qto, properties={
            "Length": length,
            "Width": width,
            "Depth": thickness,
            "Area": length * width,
            "NetArea": length * width,
            "GrossVolume": length * width * thickness,
            "NetVolume": length * width * thickness,
            "Perimeter": 2 * (length + width),
        })

        material = ifcopenshell.api.run("material.add_material", model, name="Concrete C30/37")
        ifcopenshell.api.run("material.assign_material", model, products=[slab], material=material)

        return slab

    # Helper to create a column
    def create_column(name, storey, width, depth, height):
        column = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcColumn", name=name)
        ifcopenshell.api.run("spatial.assign_container", model, products=[column], relating_structure=storey)

        qto = ifcopenshell.api.run("pset.add_qto", model, product=column, name="Qto_ColumnBaseQuantities")
        ifcopenshell.api.run("pset.edit_qto", model, qto=qto, properties={
            "Length": height,
            "CrossSectionArea": width * depth,
            "OuterSurfaceArea": 2 * (width + depth) * height,
            "GrossVolume": width * depth * height,
            "NetVolume": width * depth * height,
        })

        material = ifcopenshell.api.run("material.add_material", model, name="Concrete C30/37")
        ifcopenshell.api.run("material.assign_material", model, products=[column], material=material)

        return column

    # Helper to create a beam
    def create_beam(name, storey, length, width, depth):
        beam = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBeam", name=name)
        ifcopenshell.api.run("spatial.assign_container", model, products=[beam], relating_structure=storey)

        qto = ifcopenshell.api.run("pset.add_qto", model, product=beam, name="Qto_BeamBaseQuantities")
        ifcopenshell.api.run("pset.edit_qto", model, qto=qto, properties={
            "Length": length,
            "CrossSectionArea": width * depth,
            "OuterSurfaceArea": 2 * (width + depth) * length,
            "GrossVolume": width * depth * length,
            "NetVolume": width * depth * length,
        })

        material = ifcopenshell.api.run("material.add_material", model, name="Concrete C25/30")
        ifcopenshell.api.run("material.assign_material", model, products=[beam], material=material)

        return beam

    # Helper to create door
    def create_door(name, storey, width, height):
        door = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcDoor", name=name)
        ifcopenshell.api.run("spatial.assign_container", model, products=[door], relating_structure=storey)
        door.OverallWidth = width
        door.OverallHeight = height

        qto = ifcopenshell.api.run("pset.add_qto", model, product=door, name="Qto_DoorBaseQuantities")
        ifcopenshell.api.run("pset.edit_qto", model, qto=qto, properties={
            "Width": width,
            "Height": height,
            "Area": width * height,
        })

        return door

    # Helper to create window
    def create_window(name, storey, width, height):
        window = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWindow", name=name)
        ifcopenshell.api.run("spatial.assign_container", model, products=[window], relating_structure=storey)
        window.OverallWidth = width
        window.OverallHeight = height

        qto = ifcopenshell.api.run("pset.add_qto", model, product=window, name="Qto_WindowBaseQuantities")
        ifcopenshell.api.run("pset.edit_qto", model, qto=qto, properties={
            "Width": width,
            "Height": height,
            "Area": width * height,
        })

        return window

    # =====================================================
    # GROUND FLOOR ELEMENTS
    # =====================================================

    # External walls (10m x 8m house, 3m high, 0.2m thick concrete)
    create_wall("GF-External Wall North", ground_floor, 10.0, 3.0, 0.20, is_external=True)
    create_wall("GF-External Wall South", ground_floor, 10.0, 3.0, 0.20, is_external=True)
    create_wall("GF-External Wall East", ground_floor, 8.0, 3.0, 0.20, is_external=True)
    create_wall("GF-External Wall West", ground_floor, 8.0, 3.0, 0.20, is_external=True)

    # Internal walls (partitions, 0.1m thick brick)
    create_wall("GF-Internal Wall 1", ground_floor, 4.0, 3.0, 0.10, is_external=False)
    create_wall("GF-Internal Wall 2", ground_floor, 3.5, 3.0, 0.10, is_external=False)

    # Ground floor slab (10m x 8m, 0.2m thick)
    create_slab("Ground Floor Slab", ground_floor, 10.0, 8.0, 0.20)

    # Columns (4 corners + 2 middle, 0.3m x 0.3m, 3m high)
    for i, name in enumerate(["C1-NW", "C2-NE", "C3-SW", "C4-SE", "C5-Mid-N", "C6-Mid-S"]):
        create_column(f"GF-Column {name}", ground_floor, 0.30, 0.30, 3.0)

    # Beams (spanning between columns)
    create_beam("GF-Beam North", ground_floor, 10.0, 0.25, 0.40)
    create_beam("GF-Beam South", ground_floor, 10.0, 0.25, 0.40)
    create_beam("GF-Beam East", ground_floor, 8.0, 0.25, 0.40)
    create_beam("GF-Beam West", ground_floor, 8.0, 0.25, 0.40)
    create_beam("GF-Beam Middle", ground_floor, 8.0, 0.25, 0.40)

    # Doors
    create_door("GF-Front Door", ground_floor, 1.0, 2.1)
    create_door("GF-Back Door", ground_floor, 0.9, 2.1)
    create_door("GF-Room Door 1", ground_floor, 0.8, 2.1)
    create_door("GF-Room Door 2", ground_floor, 0.8, 2.1)

    # Windows
    create_window("GF-Window North 1", ground_floor, 1.5, 1.2)
    create_window("GF-Window North 2", ground_floor, 1.5, 1.2)
    create_window("GF-Window South 1", ground_floor, 1.5, 1.2)
    create_window("GF-Window East 1", ground_floor, 1.2, 1.2)
    create_window("GF-Window West 1", ground_floor, 1.2, 1.2)

    # =====================================================
    # FIRST FLOOR ELEMENTS
    # =====================================================

    # External walls
    create_wall("1F-External Wall North", first_floor, 10.0, 3.0, 0.20, is_external=True)
    create_wall("1F-External Wall South", first_floor, 10.0, 3.0, 0.20, is_external=True)
    create_wall("1F-External Wall East", first_floor, 8.0, 3.0, 0.20, is_external=True)
    create_wall("1F-External Wall West", first_floor, 8.0, 3.0, 0.20, is_external=True)

    # Internal walls
    create_wall("1F-Internal Wall 1", first_floor, 5.0, 3.0, 0.10, is_external=False)
    create_wall("1F-Internal Wall 2", first_floor, 4.0, 3.0, 0.10, is_external=False)
    create_wall("1F-Internal Wall 3", first_floor, 3.0, 3.0, 0.10, is_external=False)

    # First floor slab
    create_slab("First Floor Slab", first_floor, 10.0, 8.0, 0.20)

    # Roof slab
    create_slab("Roof Slab", first_floor, 10.0, 8.0, 0.15)

    # Columns
    for i, name in enumerate(["C1-NW", "C2-NE", "C3-SW", "C4-SE", "C5-Mid-N", "C6-Mid-S"]):
        create_column(f"1F-Column {name}", first_floor, 0.30, 0.30, 3.0)

    # Beams
    create_beam("1F-Beam North", first_floor, 10.0, 0.25, 0.40)
    create_beam("1F-Beam South", first_floor, 10.0, 0.25, 0.40)
    create_beam("1F-Beam East", first_floor, 8.0, 0.25, 0.40)
    create_beam("1F-Beam West", first_floor, 8.0, 0.25, 0.40)
    create_beam("1F-Beam Middle", first_floor, 8.0, 0.25, 0.40)

    # Doors
    create_door("1F-Room Door 1", first_floor, 0.8, 2.1)
    create_door("1F-Room Door 2", first_floor, 0.8, 2.1)
    create_door("1F-Room Door 3", first_floor, 0.8, 2.1)
    create_door("1F-Bathroom Door", first_floor, 0.7, 2.1)

    # Windows
    create_window("1F-Window North 1", first_floor, 1.5, 1.2)
    create_window("1F-Window North 2", first_floor, 1.5, 1.2)
    create_window("1F-Window South 1", first_floor, 1.8, 1.5)
    create_window("1F-Window East 1", first_floor, 1.2, 1.2)
    create_window("1F-Window West 1", first_floor, 1.2, 1.2)

    # Save the file
    output_path = "tests/fixtures/simple_house.ifc"
    model.write(output_path)
    print(f"Sample IFC file created: {output_path}")

    # Print summary
    print(f"\n{'='*50}")
    print(f"BUILDING SUMMARY")
    print(f"{'='*50}")
    for element_type in ["IfcWall", "IfcSlab", "IfcColumn", "IfcBeam", "IfcDoor", "IfcWindow"]:
        elements = model.by_type(element_type)
        print(f"  {element_type:20s}: {len(elements):3d} elements")
    print(f"  {'TOTAL':20s}: {sum(len(model.by_type(t)) for t in ['IfcWall','IfcSlab','IfcColumn','IfcBeam','IfcDoor','IfcWindow']):3d} elements")
    print(f"{'='*50}")

    return model


if __name__ == "__main__":
    create_sample_building()
