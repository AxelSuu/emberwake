from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from tools.levels.ldtk import Json, build_project
from tools.levels.source import Defs, Source, make_room

from emberwake.engine.core.serde import from_data
from emberwake.engine.physics import Tile
from emberwake.engine.world.ldtk import load_project

if TYPE_CHECKING:
    from pathlib import Path

LEGEND = {1: Tile.SOLID, 2: Tile.ONE_WAY, 3: Tile.HAZARD}
WALL, INSIDE = "#" * 20, "#" + "." * 18 + "#"
ALPHA = [WALL, "#P" + "." * 17 + "#", "#=^" + "." * 16 + "#", *[INSIDE] * 7, WALL]
BETA = [WALL, *[INSIDE] * 9, WALL]


def project() -> Json:
    defs = from_data(
        Defs,
        {
            "level_fields": {"Generated": {"type": "Bool", "default": False}},
            "entities": {"PlayerStart": {"color": "#f9c22b"}},
        },
    )
    rooms = [
        make_room("Alpha", (0, 0), "\n".join(ALPHA)),
        make_room("Beta", (1, 0), "\n".join(BETA)),
    ]
    return build_project(Source(defs, rooms))


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    path = tmp_path / "world.ldtk"
    path.write_text(json.dumps(project()))
    return path


def test_levels_and_layers(project_path: Path):
    project = load_project(project_path)
    alpha = project.level("Alpha")
    assert [level.identifier for level in project.all_levels] == ["Alpha", "Beta"]
    assert (alpha.width, alpha.height, alpha.world_x) == (320, 176, 0)
    assert [layer.identifier for layer in alpha.layers] == ["Entities", "Collisions"]
    assert alpha.neighbours[0].dir == "e"


def test_int_grid_to_tile_grid(project_path: Path):
    grid = load_project(project_path).level("Alpha").layer("Collisions").to_tile_grid(LEGEND)
    assert (grid.width, grid.height, grid.tile_size) == (20, 11, 16)
    assert (grid.get(0, 0), grid.get(1, 2), grid.get(2, 2), grid.get(3, 2)) == (
        Tile.SOLID,
        Tile.ONE_WAY,
        Tile.HAZARD,
        Tile.EMPTY,
    )


def test_entities(project_path: Path):
    alpha = load_project(project_path).level("Alpha")
    (start,) = alpha.entities("PlayerStart")
    assert start.px == (24, 32)
    assert start.pivot == (0.5, 1.0)
    assert start.field("missing", 3) == 3
    assert alpha.entities("Nope") == []


def test_missing_layer_and_level(project_path: Path):
    project = load_project(project_path)
    with pytest.raises(KeyError, match="no level"):
        project.level("Gamma")
    with pytest.raises(KeyError, match="no layer"):
        project.level("Alpha").layer("Tiles")
    with pytest.raises(ValueError, match="not IntGrid"):
        project.level("Alpha").layer("Entities").to_tile_grid(LEGEND)


def test_external_levels(tmp_path: Path):
    data = project()
    data["externalLevels"] = True
    for level in data["levels"]:
        body = dict(level)
        name = f"world/{level['identifier']}.ldtkl"
        (tmp_path / "world").mkdir(exist_ok=True)
        (tmp_path / name).write_text(json.dumps(body))
        level["layerInstances"] = None
        level["externalRelPath"] = name
    path = tmp_path / "world.ldtk"
    path.write_text(json.dumps(data))
    alpha = load_project(path).level("Alpha")
    assert alpha.layer("Collisions").columns == 20
