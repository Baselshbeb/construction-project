"""
Generate 10 IFC test fixture files for comprehensive testing of the Metraj pipeline.

Each file targets a specific scenario: basic residential, office tower, geometry-only
fallback, mixed sources, rebar extraction, material layers, roof types, foundations,
edge-case element types, and an empty building.

Usage:
    python -m scripts.generate_test_fixtures
    python scripts/generate_test_fixtures.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.guid


OUTPUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "generated"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def create_base_model(
    project_name: str,
    storeys_config: list[dict[str, Any]],
) -> tuple[ifcopenshell.file, Any, dict[str, Any]]:
    """Create an IFC4 model with project, site, building, and storeys.

    Args:
        project_name: Name for the IfcProject and IfcBuilding.
        storeys_config: List of dicts with keys ``name`` and ``elevation``.

    Returns:
        A tuple of (model, body_context, storeys_dict) where *storeys_dict*
        maps storey names to their IfcBuildingStorey entities.
    """
    model = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcProject", name=project_name,
    )
    ifcopenshell.api.run("unit.assign_unit", model)

    context = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body = ifcopenshell.api.run(
        "context.add_context",
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )

    site = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcSite", name="Site",
    )
    ifcopenshell.api.run(
        "aggregate.assign_object", model, relating_object=project, products=[site],
    )

    building = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcBuilding", name=project_name,
    )
    ifcopenshell.api.run(
        "aggregate.assign_object", model, relating_object=site, products=[building],
    )

    storeys_dict: dict[str, Any] = {}
    storey_entities = []
    for cfg in storeys_config:
        storey = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcBuildingStorey",
            name=cfg["name"],
        )
        storey.Elevation = cfg["elevation"]
        storey_entities.append(storey)
        storeys_dict[cfg["name"]] = storey

    ifcopenshell.api.run(
        "aggregate.assign_object",
        model,
        relating_object=building,
        products=storey_entities,
    )

    return model, body, storeys_dict


def add_wall(
    model: ifcopenshell.file,
    ctx: Any,
    storey: Any,
    name: str,
    length: float,
    height: float,
    thickness: float,
    is_external: bool,
    material_name: str,
    add_qto: bool = True,
) -> Any:
    """Create a wall with geometry, optional Qto, Pset, and material."""
    wall = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcWall", name=name,
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=storey, products=[wall],
    )

    # Geometry
    rep = ifcopenshell.api.run(
        "geometry.add_wall_representation",
        model,
        context=ctx,
        length=length,
        height=height,
        thickness=thickness,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", model, product=wall, representation=rep,
    )

    if add_qto:
        qto = ifcopenshell.api.run(
            "pset.add_qto", model, product=wall, name="Qto_WallBaseQuantities",
        )
        ifcopenshell.api.run(
            "pset.edit_qto",
            model,
            qto=qto,
            properties={
                "Length": length,
                "Height": height,
                "Width": thickness,
                "GrossArea": length * height,
                "NetArea": length * height * 0.85,
                "GrossVolume": length * height * thickness,
                "NetVolume": length * height * thickness * 0.85,
            },
        )

    # Property set
    pset = ifcopenshell.api.run(
        "pset.add_pset", model, product=wall, name="Pset_WallCommon",
    )
    ifcopenshell.api.run(
        "pset.edit_pset", model, pset=pset, properties={"IsExternal": is_external},
    )

    # Material
    mat = ifcopenshell.api.run("material.add_material", model, name=material_name)
    ifcopenshell.api.run("material.assign_material", model, products=[wall], material=mat)

    return wall


def add_slab(
    model: ifcopenshell.file,
    ctx: Any,
    storey: Any,
    name: str,
    length: float,
    width: float,
    depth: float,
    material_name: str,
    add_qto: bool = True,
) -> Any:
    """Create a slab with optional Qto and material."""
    slab = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcSlab", name=name,
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=storey, products=[slab],
    )

    # Slab geometry (use wall representation as a proxy slab shape)
    rep = ifcopenshell.api.run(
        "geometry.add_wall_representation",
        model,
        context=ctx,
        length=length,
        height=width,
        thickness=depth,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", model, product=slab, representation=rep,
    )

    if add_qto:
        qto = ifcopenshell.api.run(
            "pset.add_qto", model, product=slab, name="Qto_SlabBaseQuantities",
        )
        ifcopenshell.api.run(
            "pset.edit_qto",
            model,
            qto=qto,
            properties={
                "Length": length,
                "Width": width,
                "Depth": depth,
                "GrossArea": length * width,
                "NetArea": length * width,
                "GrossVolume": length * width * depth,
                "NetVolume": length * width * depth,
                "Perimeter": 2 * (length + width),
            },
        )

    mat = ifcopenshell.api.run("material.add_material", model, name=material_name)
    ifcopenshell.api.run("material.assign_material", model, products=[slab], material=mat)

    return slab


def add_column(
    model: ifcopenshell.file,
    ctx: Any,
    storey: Any,
    name: str,
    height: float,
    section_area: float,
    material_name: str,
    add_qto: bool = True,
) -> Any:
    """Create a column with optional Qto and material."""
    column = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcColumn", name=name,
    )
    ifcopenshell.api.run(
        "spatial.assign_container",
        model,
        relating_structure=storey,
        products=[column],
    )

    # Approximate column as a thin wall for geometry purposes
    import math
    side = math.sqrt(section_area)
    rep = ifcopenshell.api.run(
        "geometry.add_wall_representation",
        model,
        context=ctx,
        length=side,
        height=height,
        thickness=side,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", model, product=column, representation=rep,
    )

    if add_qto:
        qto = ifcopenshell.api.run(
            "pset.add_qto", model, product=column, name="Qto_ColumnBaseQuantities",
        )
        ifcopenshell.api.run(
            "pset.edit_qto",
            model,
            qto=qto,
            properties={
                "Height": height,
                "CrossSectionArea": section_area,
                "GrossVolume": section_area * height,
                "NetVolume": section_area * height,
                "OuterSurfaceArea": 4 * side * height,
            },
        )

    mat = ifcopenshell.api.run("material.add_material", model, name=material_name)
    ifcopenshell.api.run(
        "material.assign_material", model, products=[column], material=mat,
    )

    return column


def add_beam(
    model: ifcopenshell.file,
    ctx: Any,
    storey: Any,
    name: str,
    length: float,
    section_area: float,
    material_name: str,
    add_qto: bool = True,
) -> Any:
    """Create a beam with optional Qto and material."""
    beam = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcBeam", name=name,
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=storey, products=[beam],
    )

    import math
    side = math.sqrt(section_area)
    rep = ifcopenshell.api.run(
        "geometry.add_wall_representation",
        model,
        context=ctx,
        length=length,
        height=side,
        thickness=side,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", model, product=beam, representation=rep,
    )

    if add_qto:
        qto = ifcopenshell.api.run(
            "pset.add_qto", model, product=beam, name="Qto_BeamBaseQuantities",
        )
        ifcopenshell.api.run(
            "pset.edit_qto",
            model,
            qto=qto,
            properties={
                "Length": length,
                "CrossSectionArea": section_area,
                "GrossVolume": section_area * length,
                "NetVolume": section_area * length,
            },
        )

    mat = ifcopenshell.api.run("material.add_material", model, name=material_name)
    ifcopenshell.api.run(
        "material.assign_material", model, products=[beam], material=mat,
    )

    return beam


def add_door(
    model: ifcopenshell.file,
    ctx: Any,
    storey: Any,
    wall: Any,
    name: str,
    width: float,
    height: float,
) -> Any:
    """Create a door with IfcRelVoidsElement linking to a wall, plus Qto."""
    door = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcDoor", name=name,
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=storey, products=[door],
    )
    door.OverallWidth = width
    door.OverallHeight = height

    qto = ifcopenshell.api.run(
        "pset.add_qto", model, product=door, name="Qto_DoorBaseQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto",
        model,
        qto=qto,
        properties={"Width": width, "Height": height, "Area": width * height},
    )

    # Create opening element and void relationship
    opening = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcOpeningElement", name=f"Opening-{name}",
    )
    # Add Qto to the opening so wall-opening deduction can find dimensions
    oqto = ifcopenshell.api.run(
        "pset.add_qto", model, product=opening, name="Qto_OpeningElementBaseQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto",
        model,
        qto=oqto,
        properties={"Width": width, "Height": height, "Area": width * height},
    )

    model.create_entity(
        "IfcRelVoidsElement",
        GlobalId=ifcopenshell.guid.new(),
        RelatingBuildingElement=wall,
        RelatedOpeningElement=opening,
    )

    # Link door as filling of the opening
    model.create_entity(
        "IfcRelFillsElement",
        GlobalId=ifcopenshell.guid.new(),
        RelatingOpeningElement=opening,
        RelatedBuildingElement=door,
    )

    return door


def add_window(
    model: ifcopenshell.file,
    ctx: Any,
    storey: Any,
    wall: Any,
    name: str,
    width: float,
    height: float,
) -> Any:
    """Create a window with IfcRelVoidsElement linking to a wall, plus Qto."""
    window = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcWindow", name=name,
    )
    ifcopenshell.api.run(
        "spatial.assign_container",
        model,
        relating_structure=storey,
        products=[window],
    )
    window.OverallWidth = width
    window.OverallHeight = height

    qto = ifcopenshell.api.run(
        "pset.add_qto", model, product=window, name="Qto_WindowBaseQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto",
        model,
        qto=qto,
        properties={"Width": width, "Height": height, "Area": width * height},
    )

    opening = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcOpeningElement", name=f"Opening-{name}",
    )
    oqto = ifcopenshell.api.run(
        "pset.add_qto", model, product=opening, name="Qto_OpeningElementBaseQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto",
        model,
        qto=oqto,
        properties={"Width": width, "Height": height, "Area": width * height},
    )

    model.create_entity(
        "IfcRelVoidsElement",
        GlobalId=ifcopenshell.guid.new(),
        RelatingBuildingElement=wall,
        RelatedOpeningElement=opening,
    )

    model.create_entity(
        "IfcRelFillsElement",
        GlobalId=ifcopenshell.guid.new(),
        RelatingOpeningElement=opening,
        RelatedBuildingElement=window,
    )

    return window


def add_stair(
    model: ifcopenshell.file,
    ctx: Any,
    storey: Any,
    name: str,
    volume: float,
    area: float,
) -> Any:
    """Create a stair with Qto for volume and area."""
    stair = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcStair", name=name,
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=storey, products=[stair],
    )

    qto = ifcopenshell.api.run(
        "pset.add_qto", model, product=stair, name="Qto_StairBaseQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto",
        model,
        qto=qto,
        properties={"GrossVolume": volume, "GrossArea": area},
    )

    mat = ifcopenshell.api.run("material.add_material", model, name="Concrete C25/30")
    ifcopenshell.api.run(
        "material.assign_material", model, products=[stair], material=mat,
    )

    return stair


def add_rebar(
    model: ifcopenshell.file,
    host: Any,
    name: str,
    diameter: float,
    length: float,
    count: int,
) -> list[Any]:
    """Create reinforcing bars linked to a host element via IfcRelAggregates.

    Args:
        model: The IFC model.
        host: The host building element (wall, column, beam, footing).
        name: Base name for the rebar entities.
        diameter: Bar diameter in metres (e.g. 0.012 for 12mm).
        length: Bar length in metres.
        count: Number of individual bars to create.

    Returns:
        List of created IfcReinforcingBar entities.
    """
    bars = []
    for i in range(count):
        rebar = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcReinforcingBar",
            name=f"{name}-{i + 1}",
        )
        rebar.NominalDiameter = diameter
        rebar.BarLength = length
        rebar.CrossSectionArea = 3.14159265 / 4.0 * diameter ** 2
        bars.append(rebar)

    # Link all bars to the host via IfcRelAggregates
    model.create_entity(
        "IfcRelAggregates",
        GlobalId=ifcopenshell.guid.new(),
        RelatingObject=host,
        RelatedObjects=bars,
    )

    return bars


def add_material_layers(
    model: ifcopenshell.file,
    element: Any,
    layers: list[dict[str, Any]],
) -> None:
    """Assign a material layer set to an element.

    Args:
        model: The IFC model.
        element: The building element to assign layers to.
        layers: List of dicts with keys ``name`` (str) and ``thickness`` (float, mm).
    """
    layer_set = model.create_entity("IfcMaterialLayerSet")
    ifc_layers = []
    for layer_def in layers:
        mat = ifcopenshell.api.run(
            "material.add_material", model, name=layer_def["name"],
        )
        ifc_layer = model.create_entity(
            "IfcMaterialLayer",
            Material=mat,
            LayerThickness=layer_def["thickness"],
        )
        ifc_layers.append(ifc_layer)
    layer_set.MaterialLayers = ifc_layers

    layer_set_usage = model.create_entity(
        "IfcMaterialLayerSetUsage",
        ForLayerSet=layer_set,
        LayerSetDirection="AXIS2",
        DirectionSense="POSITIVE",
        OffsetFromReferenceLine=0.0,
    )

    # Remove any existing material assignment and add the layer set usage
    model.create_entity(
        "IfcRelAssociatesMaterial",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[element],
        RelatingMaterial=layer_set_usage,
    )


# ---------------------------------------------------------------------------
# File generators
# ---------------------------------------------------------------------------


def generate_residential_basic() -> str:
    """File 1: residential_basic.ifc -- 2-storey house with typical elements."""
    model, ctx, storeys = create_base_model(
        "Residential Basic",
        [
            {"name": "Ground Floor", "elevation": 0.0},
            {"name": "First Floor", "elevation": 3.0},
        ],
    )
    gf = storeys["Ground Floor"]
    ff = storeys["First Floor"]

    # --- Ground Floor ---
    # External walls
    w_north = add_wall(model, ctx, gf, "GF-Ext Wall North", 10.0, 3.0, 0.2, True, "Concrete C25/30")
    w_south = add_wall(model, ctx, gf, "GF-Ext Wall South", 10.0, 3.0, 0.2, True, "Concrete C25/30")
    w_east = add_wall(model, ctx, gf, "GF-Ext Wall East", 8.0, 3.0, 0.2, True, "Concrete C25/30")
    w_west = add_wall(model, ctx, gf, "GF-Ext Wall West", 8.0, 3.0, 0.2, True, "Concrete C25/30")

    # Internal walls
    add_wall(model, ctx, gf, "GF-Int Wall 1", 4.0, 3.0, 0.1, False, "Clay Brick")
    add_wall(model, ctx, gf, "GF-Int Wall 2", 4.0, 3.0, 0.1, False, "Clay Brick")

    # Ground slab
    add_slab(model, ctx, gf, "GF-Ground Slab", 10.0, 8.0, 0.2, "Concrete C30/37")

    # Columns
    for i in range(4):
        add_column(model, ctx, gf, f"GF-Column {i + 1}", 3.0, 0.09, "Concrete C30/37")

    # Beams
    add_beam(model, ctx, gf, "GF-Beam 1", 10.0, 0.06, "Concrete C25/30")
    add_beam(model, ctx, gf, "GF-Beam 2", 10.0, 0.06, "Concrete C25/30")

    # Doors in ext walls
    add_door(model, ctx, gf, w_north, "GF-Door 1", 0.9, 2.1)
    add_door(model, ctx, gf, w_south, "GF-Door 2", 0.9, 2.1)

    # Windows in ext walls
    add_window(model, ctx, gf, w_north, "GF-Window 1", 1.5, 1.2)
    add_window(model, ctx, gf, w_south, "GF-Window 2", 1.5, 1.2)
    add_window(model, ctx, gf, w_east, "GF-Window 3", 1.5, 1.2)
    add_window(model, ctx, gf, w_west, "GF-Window 4", 1.5, 1.2)

    # Stair
    add_stair(model, ctx, gf, "GF-Stair", volume=2.5, area=8.0)

    # --- First Floor ---
    ff_north = add_wall(model, ctx, ff, "1F-Ext Wall North", 10.0, 3.0, 0.2, True, "Concrete C25/30")
    ff_south = add_wall(model, ctx, ff, "1F-Ext Wall South", 10.0, 3.0, 0.2, True, "Concrete C25/30")
    ff_east = add_wall(model, ctx, ff, "1F-Ext Wall East", 8.0, 3.0, 0.2, True, "Concrete C25/30")
    ff_west = add_wall(model, ctx, ff, "1F-Ext Wall West", 8.0, 3.0, 0.2, True, "Concrete C25/30")
    add_wall(model, ctx, ff, "1F-Int Wall 1", 4.0, 3.0, 0.1, False, "Clay Brick")
    add_wall(model, ctx, ff, "1F-Int Wall 2", 4.0, 3.0, 0.1, False, "Clay Brick")
    add_slab(model, ctx, ff, "1F-Floor Slab", 10.0, 8.0, 0.2, "Concrete C30/37")
    for i in range(4):
        add_column(model, ctx, ff, f"1F-Column {i + 1}", 3.0, 0.09, "Concrete C30/37")
    add_beam(model, ctx, ff, "1F-Beam 1", 10.0, 0.06, "Concrete C25/30")
    add_beam(model, ctx, ff, "1F-Beam 2", 10.0, 0.06, "Concrete C25/30")
    add_door(model, ctx, ff, ff_north, "1F-Door 1", 0.9, 2.1)
    add_door(model, ctx, ff, ff_south, "1F-Door 2", 0.9, 2.1)
    add_window(model, ctx, ff, ff_north, "1F-Window 1", 1.5, 1.2)
    add_window(model, ctx, ff, ff_south, "1F-Window 2", 1.5, 1.2)
    add_window(model, ctx, ff, ff_east, "1F-Window 3", 1.5, 1.2)
    add_window(model, ctx, ff, ff_west, "1F-Window 4", 1.5, 1.2)

    path = OUTPUT_DIR / "residential_basic.ifc"
    model.write(str(path))
    return str(path)


def generate_office_tower() -> str:
    """File 2: office_tower.ifc -- 5-storey office with 200+ elements."""
    storeys_cfg = [
        {"name": f"{'GF' if i == 0 else f'{i}F'}", "elevation": i * 3.5}
        for i in range(5)
    ]
    model, ctx, storeys = create_base_model("Office Tower", storeys_cfg)

    for storey_name, storey in storeys.items():
        # 8 external walls (4 long + 4 short, alternating)
        ext_walls = []
        for j in range(4):
            w = add_wall(
                model, ctx, storey,
                f"{storey_name}-Ext Wall {j + 1}",
                15.0 if j < 2 else 10.0, 3.5, 0.25, True, "Concrete C30/37",
            )
            ext_walls.append(w)
        for j in range(4):
            w = add_wall(
                model, ctx, storey,
                f"{storey_name}-Ext Wall {j + 5}",
                15.0 if j < 2 else 10.0, 3.5, 0.25, True, "Concrete C30/37",
            )
            ext_walls.append(w)

        # 4 internal walls
        for j in range(4):
            add_wall(
                model, ctx, storey,
                f"{storey_name}-Int Wall {j + 1}",
                6.0, 3.5, 0.12, False, "Gypsum Board",
            )

        # 1 slab
        add_slab(
            model, ctx, storey, f"{storey_name}-Slab",
            15.0, 10.0, 0.25, "Concrete C30/37",
        )

        # 8 columns
        for j in range(8):
            add_column(
                model, ctx, storey,
                f"{storey_name}-Column {j + 1}",
                3.5, 0.1225, "Concrete C40/50",
            )

        # 4 beams
        for j in range(4):
            add_beam(
                model, ctx, storey,
                f"{storey_name}-Beam {j + 1}",
                15.0 if j < 2 else 10.0, 0.075, "Concrete C30/37",
            )

        # 2 doors in ext walls
        add_door(model, ctx, storey, ext_walls[0], f"{storey_name}-Door 1", 1.0, 2.2)
        add_door(model, ctx, storey, ext_walls[1], f"{storey_name}-Door 2", 1.0, 2.2)

        # 6 windows in ext walls
        for j in range(6):
            wall_idx = j % len(ext_walls)
            add_window(
                model, ctx, storey, ext_walls[wall_idx],
                f"{storey_name}-Window {j + 1}", 2.0, 1.5,
            )

        # 1 curtain wall
        cw = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcCurtainWall",
            name=f"{storey_name}-Curtain Wall",
        )
        ifcopenshell.api.run(
            "spatial.assign_container", model,
            relating_structure=storey, products=[cw],
        )
        cw_qto = ifcopenshell.api.run(
            "pset.add_qto", model, product=cw, name="Qto_CurtainWallBaseQuantities",
        )
        ifcopenshell.api.run(
            "pset.edit_qto", model, qto=cw_qto,
            properties={"Length": 15.0, "Height": 3.5, "GrossArea": 15.0 * 3.5},
        )

        # 2 railings
        for j in range(2):
            rail = ifcopenshell.api.run(
                "root.create_entity", model, ifc_class="IfcRailing",
                name=f"{storey_name}-Railing {j + 1}",
            )
            ifcopenshell.api.run(
                "spatial.assign_container", model,
                relating_structure=storey, products=[rail],
            )
            r_qto = ifcopenshell.api.run(
                "pset.add_qto", model, product=rail, name="Qto_RailingBaseQuantities",
            )
            ifcopenshell.api.run(
                "pset.edit_qto", model, qto=r_qto, properties={"Length": 5.0},
            )

    path = OUTPUT_DIR / "office_tower.ifc"
    model.write(str(path))
    return str(path)


def generate_no_qto_geometry_only() -> str:
    """File 3: no_qto_geometry_only.ifc -- elements with geometry but no Qto."""
    model, ctx, storeys = create_base_model(
        "No Qto Building",
        [{"name": "Ground Floor", "elevation": 0.0}],
    )
    gf = storeys["Ground Floor"]

    add_wall(model, ctx, gf, "Wall-NoQto-1", 8.0, 3.0, 0.2, True, "Concrete C25/30", add_qto=False)
    add_wall(model, ctx, gf, "Wall-NoQto-2", 6.0, 3.0, 0.2, True, "Concrete C25/30", add_qto=False)
    add_slab(model, ctx, gf, "Slab-NoQto", 8.0, 6.0, 0.2, "Concrete C30/37", add_qto=False)
    add_column(model, ctx, gf, "Column-NoQto", 3.0, 0.09, "Concrete C30/37", add_qto=False)

    path = OUTPUT_DIR / "no_qto_geometry_only.ifc"
    model.write(str(path))
    return str(path)


def generate_mixed_qto_and_geometry() -> str:
    """File 4: mixed_qto_and_geometry.ifc -- some elements with Qto, some without."""
    model, ctx, storeys = create_base_model(
        "Mixed Sources Building",
        [{"name": "Ground Floor", "elevation": 0.0}],
    )
    gf = storeys["Ground Floor"]

    add_wall(model, ctx, gf, "Wall-WithQto", 10.0, 3.0, 0.2, True, "Concrete C25/30", add_qto=True)
    add_slab(model, ctx, gf, "Slab-NoQto", 10.0, 8.0, 0.2, "Concrete C30/37", add_qto=False)
    add_column(model, ctx, gf, "Column-WithQto", 3.0, 0.09, "Concrete C30/37", add_qto=True)
    add_beam(model, ctx, gf, "Beam-NoQto", 8.0, 0.06, "Concrete C25/30", add_qto=False)

    path = OUTPUT_DIR / "mixed_qto_and_geometry.ifc"
    model.write(str(path))
    return str(path)


def generate_with_rebar() -> str:
    """File 5: with_rebar.ifc -- elements with IfcReinforcingBar children."""
    model, ctx, storeys = create_base_model(
        "Building With Rebar",
        [{"name": "Ground Floor", "elevation": 0.0}],
    )
    gf = storeys["Ground Floor"]

    wall = add_wall(model, ctx, gf, "RC-Wall", 10.0, 3.0, 0.2, True, "Concrete C25/30")
    add_rebar(model, wall, "Wall-Rebar", diameter=0.012, length=9.5, count=4)

    column = add_column(model, ctx, gf, "RC-Column", 3.0, 0.09, "Concrete C30/37")
    add_rebar(model, column, "Column-Rebar", diameter=0.016, length=2.8, count=8)

    beam = add_beam(model, ctx, gf, "RC-Beam", 10.0, 0.06, "Concrete C25/30")
    add_rebar(model, beam, "Beam-Rebar", diameter=0.012, length=9.5, count=6)

    # Footing
    footing = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcFooting", name="RC-Footing",
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=gf, products=[footing],
    )
    fqto = ifcopenshell.api.run(
        "pset.add_qto", model, product=footing, name="Qto_FootingBaseQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto", model, qto=fqto,
        properties={"GrossVolume": 2.0, "GrossArea": 4.0},
    )
    mat = ifcopenshell.api.run("material.add_material", model, name="Concrete C30/37")
    ifcopenshell.api.run("material.assign_material", model, products=[footing], material=mat)
    add_rebar(model, footing, "Footing-Rebar", diameter=0.016, length=3.0, count=10)

    path = OUTPUT_DIR / "with_rebar.ifc"
    model.write(str(path))
    return str(path)


def generate_material_layers() -> str:
    """File 6: material_layers.ifc -- elements with material layer sets."""
    model, ctx, storeys = create_base_model(
        "Layered Materials Building",
        [{"name": "Ground Floor", "elevation": 0.0}],
    )
    gf = storeys["Ground Floor"]

    # External wall with 3 layers
    wall = add_wall(
        model, ctx, gf, "Layered-ExtWall", 10.0, 3.0, 0.215, True, "Concrete C25/30",
    )
    add_material_layers(model, wall, [
        {"name": "Plaster", "thickness": 15.0},       # 15mm
        {"name": "Concrete C25/30", "thickness": 150.0},  # 150mm
        {"name": "EPS Insulation", "thickness": 50.0},    # 50mm
    ])

    # Slab with 3 layers
    slab = add_slab(
        model, ctx, gf, "Layered-Slab", 10.0, 8.0, 0.26, "Concrete C30/37",
    )
    add_material_layers(model, slab, [
        {"name": "Ceramic Tiles", "thickness": 10.0},    # 10mm
        {"name": "Cement Screed", "thickness": 50.0},     # 50mm
        {"name": "Concrete C30/37", "thickness": 200.0},  # 200mm
    ])

    path = OUTPUT_DIR / "material_layers.ifc"
    model.write(str(path))
    return str(path)


def generate_roof_types() -> str:
    """File 7: roof_types.ifc -- different roof slopes."""
    model, ctx, storeys = create_base_model(
        "Roof Types Building",
        [
            {"name": "Ground Floor", "elevation": 0.0},
            {"name": "Roof Level", "elevation": 3.0},
        ],
    )
    gf = storeys["Ground Floor"]
    rl = storeys["Roof Level"]

    # Basic walls and slab on GF
    add_wall(model, ctx, gf, "GF-Wall 1", 10.0, 3.0, 0.2, True, "Concrete C25/30")
    add_slab(model, ctx, gf, "GF-Slab", 10.0, 8.0, 0.2, "Concrete C30/37")

    # Flat roof (slope = 0)
    flat = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcRoof", name="Flat Roof",
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=rl, products=[flat],
    )
    fqto = ifcopenshell.api.run(
        "pset.add_qto", model, product=flat, name="Qto_RoofBaseQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto", model, qto=fqto,
        properties={
            "GrossArea": 10.0 * 8.0,
            "Length": 10.0,
            "Width": 8.0,
            "GrossVolume": 10.0 * 8.0 * 0.15,
        },
    )
    fpset = ifcopenshell.api.run(
        "pset.add_pset", model, product=flat, name="Pset_RoofCommon",
    )
    ifcopenshell.api.run(
        "pset.edit_pset", model, pset=fpset, properties={"PitchAngle": 0.0},
    )

    # Pitched roof (30 deg, two sides 10x4m each)
    pitched = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcRoof", name="Pitched Roof",
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=rl, products=[pitched],
    )
    pqto = ifcopenshell.api.run(
        "pset.add_qto", model, product=pitched, name="Qto_RoofBaseQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto", model, qto=pqto,
        properties={
            "GrossArea": 10.0 * 4.0 * 2,  # both sides footprint
            "Length": 10.0,
            "Width": 8.0,
            "GrossVolume": 10.0 * 8.0 * 0.15,
        },
    )
    ppset = ifcopenshell.api.run(
        "pset.add_pset", model, product=pitched, name="Pset_RoofCommon",
    )
    ifcopenshell.api.run(
        "pset.edit_pset", model, pset=ppset, properties={"PitchAngle": 30.0},
    )

    # Steep roof (45 deg)
    steep = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcRoof", name="Steep Roof",
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=rl, products=[steep],
    )
    sqto = ifcopenshell.api.run(
        "pset.add_qto", model, product=steep, name="Qto_RoofBaseQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto", model, qto=sqto,
        properties={
            "GrossArea": 6.0 * 4.0,
            "Length": 6.0,
            "Width": 4.0,
            "GrossVolume": 6.0 * 4.0 * 0.12,
        },
    )
    spset = ifcopenshell.api.run(
        "pset.add_pset", model, product=steep, name="Pset_RoofCommon",
    )
    ifcopenshell.api.run(
        "pset.edit_pset", model, pset=spset, properties={"PitchAngle": 45.0},
    )

    path = OUTPUT_DIR / "roof_types.ifc"
    model.write(str(path))
    return str(path)


def generate_foundations() -> str:
    """File 8: foundations.ifc -- footings, piles, retaining walls."""
    model, ctx, storeys = create_base_model(
        "Foundation Building",
        [{"name": "Basement", "elevation": -3.0}],
    )
    bm = storeys["Basement"]

    # 4 footings (2x2x0.5m)
    for i in range(4):
        ftg = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcFooting",
            name=f"Footing {i + 1}",
        )
        ifcopenshell.api.run(
            "spatial.assign_container", model, relating_structure=bm, products=[ftg],
        )
        fqto = ifcopenshell.api.run(
            "pset.add_qto", model, product=ftg, name="Qto_FootingBaseQuantities",
        )
        ifcopenshell.api.run(
            "pset.edit_qto", model, qto=fqto,
            properties={
                "GrossVolume": 2.0 * 2.0 * 0.5,
                "GrossArea": 2.0 * 2.0,
                "Length": 2.0,
                "Width": 2.0,
                "Depth": 0.5,
            },
        )
        mat = ifcopenshell.api.run(
            "material.add_material", model, name="Concrete C30/37",
        )
        ifcopenshell.api.run(
            "material.assign_material", model, products=[ftg], material=mat,
        )

    # 2 piles (0.3m dia x 10m)
    import math
    for i in range(2):
        pile = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcPile",
            name=f"Pile {i + 1}",
        )
        ifcopenshell.api.run(
            "spatial.assign_container", model, relating_structure=bm, products=[pile],
        )
        pile_area = math.pi * (0.3 / 2) ** 2
        pqto = ifcopenshell.api.run(
            "pset.add_qto", model, product=pile, name="Qto_PileBaseQuantities",
        )
        ifcopenshell.api.run(
            "pset.edit_qto", model, qto=pqto,
            properties={
                "Length": 10.0,
                "GrossVolume": pile_area * 10.0,
                "GrossArea": pile_area,
            },
        )
        mat = ifcopenshell.api.run(
            "material.add_material", model, name="Concrete C35/45",
        )
        ifcopenshell.api.run(
            "material.assign_material", model, products=[pile], material=mat,
        )

    # 1 ground slab (12x10x0.3m)
    add_slab(model, ctx, bm, "Basement Slab", 12.0, 10.0, 0.3, "Concrete C30/37")

    # 2 retaining walls (10x3x0.3m, external)
    for i in range(2):
        add_wall(
            model, ctx, bm, f"Retaining Wall {i + 1}",
            10.0, 3.0, 0.3, True, "Concrete C30/37",
        )

    path = OUTPUT_DIR / "foundations.ifc"
    model.write(str(path))
    return str(path)


def generate_edge_cases() -> str:
    """File 9: edge_cases.ifc -- unusual / less common IFC types."""
    model, ctx, storeys = create_base_model(
        "Edge Cases Building",
        [{"name": "Ground Floor", "elevation": 0.0}],
    )
    gf = storeys["Ground Floor"]

    # IfcBuildingElementProxy (generic catch-all)
    proxy = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcBuildingElementProxy",
        name="Steel Bracket",
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=gf, products=[proxy],
    )
    pqto = ifcopenshell.api.run(
        "pset.add_qto", model, product=proxy, name="Qto_ProxyQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto", model, qto=pqto,
        properties={"GrossVolume": 0.05, "Length": 0.5},
    )

    # IfcMember (structural member)
    member = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcMember", name="Steel Brace",
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=gf, products=[member],
    )
    mqto = ifcopenshell.api.run(
        "pset.add_qto", model, product=member, name="Qto_MemberBaseQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto", model, qto=mqto,
        properties={"Length": 5.0, "CrossSectionArea": 0.005, "GrossVolume": 0.025},
    )
    mat = ifcopenshell.api.run("material.add_material", model, name="Steel S355")
    ifcopenshell.api.run(
        "material.assign_material", model, products=[member], material=mat,
    )

    # IfcPlate (steel plate / panel)
    plate = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcPlate", name="Steel Plate",
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=gf, products=[plate],
    )
    plqto = ifcopenshell.api.run(
        "pset.add_qto", model, product=plate, name="Qto_PlateBaseQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto", model, qto=plqto,
        properties={"GrossArea": 2.0, "Width": 0.01, "GrossVolume": 0.02},
    )

    # IfcCovering (flooring)
    covering = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcCovering", name="Floor Tiles",
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=gf, products=[covering],
    )
    covering.PredefinedType = "FLOORING"
    cqto = ifcopenshell.api.run(
        "pset.add_qto", model, product=covering, name="Qto_CoveringBaseQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto", model, qto=cqto,
        properties={"GrossArea": 48.0, "Perimeter": 28.0},
    )

    # IfcRamp
    ramp = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcRamp", name="Entrance Ramp",
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=gf, products=[ramp],
    )
    rqto = ifcopenshell.api.run(
        "pset.add_qto", model, product=ramp, name="Qto_RampBaseQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto", model, qto=rqto,
        properties={"GrossVolume": 1.5, "GrossArea": 6.0, "Length": 4.0},
    )

    # IfcRailing
    railing = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcRailing", name="Balcony Railing",
    )
    ifcopenshell.api.run(
        "spatial.assign_container", model, relating_structure=gf, products=[railing],
    )
    rlqto = ifcopenshell.api.run(
        "pset.add_qto", model, product=railing, name="Qto_RailingBaseQuantities",
    )
    ifcopenshell.api.run(
        "pset.edit_qto", model, qto=rlqto, properties={"Length": 4.0},
    )

    path = OUTPUT_DIR / "edge_cases.ifc"
    model.write(str(path))
    return str(path)


def generate_empty_building() -> str:
    """File 10: empty_building.ifc -- project structure only, no elements."""
    model, ctx, storeys = create_base_model(
        "Empty Building",
        [{"name": "Ground Floor", "elevation": 0.0}],
    )

    path = OUTPUT_DIR / "empty_building.ifc"
    model.write(str(path))
    return str(path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

GENERATORS = [
    ("residential_basic.ifc", generate_residential_basic),
    ("office_tower.ifc", generate_office_tower),
    ("no_qto_geometry_only.ifc", generate_no_qto_geometry_only),
    ("mixed_qto_and_geometry.ifc", generate_mixed_qto_and_geometry),
    ("with_rebar.ifc", generate_with_rebar),
    ("material_layers.ifc", generate_material_layers),
    ("roof_types.ifc", generate_roof_types),
    ("foundations.ifc", generate_foundations),
    ("edge_cases.ifc", generate_edge_cases),
    ("empty_building.ifc", generate_empty_building),
]


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating {len(GENERATORS)} IFC test fixtures in {OUTPUT_DIR}\n")

    results: list[tuple[str, str, int]] = []

    for filename, gen_func in GENERATORS:
        try:
            path = gen_func()
            # Count elements in generated file
            import ifcopenshell as _ifc
            m = _ifc.open(path)
            elem_types = [
                "IfcWall", "IfcSlab", "IfcColumn", "IfcBeam", "IfcDoor",
                "IfcWindow", "IfcStair", "IfcRoof", "IfcFooting", "IfcPile",
                "IfcCurtainWall", "IfcRailing", "IfcCovering", "IfcRamp",
                "IfcBuildingElementProxy", "IfcMember", "IfcPlate",
                "IfcReinforcingBar",
            ]
            total = 0
            for et in elem_types:
                try:
                    total += len(m.by_type(et))
                except RuntimeError:
                    pass
            results.append((filename, "OK", total))
            print(f"  [OK]   {filename:40s}  {total:4d} elements")
        except Exception as e:
            results.append((filename, f"FAIL: {e}", 0))
            print(f"  [FAIL] {filename:40s}  {e}")

    print(f"\n{'=' * 60}")
    print(f"Summary: {sum(1 for _, s, _ in results if s == 'OK')}/{len(results)} files generated successfully")
    total_elements = sum(c for _, _, c in results)
    print(f"Total elements across all files: {total_elements}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"{'=' * 60}")
