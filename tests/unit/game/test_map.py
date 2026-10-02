from __future__ import annotations

import pygame
from tools.levels.ldtk import build_project
from tools.levels.source import Defs, MarkerSpec, RoomFile, Source, make_room, read_toml

from emberwake.engine.core.serde import from_data
from emberwake.engine.ecs.prefabs import load_prefabs
from emberwake.engine.world.ldtk import Level, Project
from emberwake.engine.world.spawning import WorldState
from emberwake.game import paths
from emberwake.game.map import Icon, Known, MapIcon, MapRoom, MapView, map_view

DEFS = read_toml(Defs, paths.levels("src/defs.toml"))
PREFABS = load_prefabs(paths.content("prefabs.toml"))
WALL, INSIDE = "#" * 20, "#" + "." * 18 + "#"
MARKERS = {
    "k": MarkerSpec("Beacon"),
    "h": MarkerSpec("Hesper", {"Unless": "hesper_stage>=1"}),
    "H": MarkerSpec("Hesper", {"Requires": "hesper_stage>=1"}),
}
BOX = pygame.Rect(10, 20, 320, 400)
"""Twice as tall as the 640x176 quarter at half scale: it sits centred at y 176."""


def build() -> dict[str, Level]:
    """Hall and Cellar side by side in the quarter, a Lab further on; one beacon each."""
    rooms = []
    for column, (name, area, markers) in (
        (0, ("Hall", "quarter", "k.hH")),
        (1, ("Cellar", "quarter", "k")),
        (3, ("Lab", "lab", "k")),
    ):
        row = "#.P" + markers + "." * (16 - len(markers)) + "#"
        text = "\n".join([WALL, *[INSIDE] * 8, row, WALL])
        used = {m: spec for m, spec in MARKERS.items() if m in markers}
        rooms.append(make_room(name, (column, 0), text, RoomFile({"Area": area}, used)))
    levels = from_data(Project, build_project(Source(DEFS, rooms))).all_levels
    return {level.identifier: level for level in levels}


LEVELS = build()


def known(
    *visited: str,
    inventory: dict[str, int] | None = None,
    facts: dict[str, int] | None = None,
    world: WorldState | None = None,
    cinder: tuple[str, float, float] | None = None,
) -> Known:
    return Known(
        discovered=[LEVELS[name].iid for name in visited],
        inventory=inventory or {},
        facts=facts or {},
        world=world or WorldState(),
        cinder=cinder,
    )


def view(state: Known, player: tuple[float, float] = (40, 150), area: str = "quarter") -> MapView:
    return map_view(LEVELS, area, state, prefabs=PREFABS, player=player, box=BOX)


def beacon(room: str) -> str:
    (iid,) = [e.iid for e in LEVELS[room].entities("Beacon")]
    return iid


def test_only_entered_rooms_of_the_area_are_drawn_filled_and_scaled_into_the_box():
    rooms = view(known("Hall", "Lab")).rooms
    assert rooms == [MapRoom(pygame.Rect(10, 176, 160, 88).inflate(-2, -2), visited=True)]


def test_the_area_s_map_outlines_the_rooms_not_yet_entered():
    rooms = view(known("Hall", inventory={"map.quarter": 1})).rooms
    assert [(r.rect.x, r.visited) for r in rooms] == [(11, True), (171, False)]
    other = view(known("Hall", inventory={"map.lab": 1})).rooms
    assert len(other) == 1


def test_beacons_npcs_where_their_stage_puts_them_and_the_player_are_placed():
    lit = WorldState({beacon("Hall"): {"Beacon": {"lit": True}}})
    icons = view(known("Hall", "Cellar", world=lit), player=(328, 0)).icons
    kinds = sorted(icon.kind for icon in icons)
    assert kinds == sorted([Icon.BEACON_LIT, Icon.NPC, Icon.BEACON_COLD, Icon.PLAYER])
    assert MapIcon(Icon.PLAYER, 174, 176) in icons
    staged = view(known("Hall", facts={"hesper_stage": 1})).icons
    (npc,) = [icon for icon in staged if icon.kind is Icon.NPC]
    (early,) = [icon for icon in icons if icon.kind is Icon.NPC]
    assert npc.x > early.x


def test_icons_in_hidden_rooms_are_left_out_and_the_cinder_shows_where_it_lies():
    state = known("Hall", cinder=("Hall", 100.0, 160.0))
    icons = view(state).icons
    assert MapIcon(Icon.CINDER, 60, 256) in icons
    assert Icon.BEACON_COLD in [icon.kind for icon in icons]
    assert len([icon for icon in icons if icon.kind is Icon.BEACON_COLD]) == 1
    elsewhere = view(known("Hall", cinder=("Cellar", 400.0, 160.0))).icons
    assert Icon.CINDER not in [icon.kind for icon in elsewhere]


def test_an_area_without_rooms_draws_nothing():
    assert view(known("Hall"), area="gardens").rooms == []
