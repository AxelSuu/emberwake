"""Hesper and Quill in Npc_Lab: stages move them, Hesper pays for lights, Quill sells the map."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pytest
from tests.integration.test_tinker import key, pick, talk

from emberwake.engine.physics import Body
from emberwake.engine.platform.storage import MemoryStorage
from emberwake.engine.scene import SceneManager
from emberwake.game.data.save import SaveSlot, load_slot, save_slot
from emberwake.game.dialogue import Npc
from emberwake.game.scenes.dialogue import ShopScene
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.shop import wallet

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60
ROOM = "Npc_Lab"
MAP = "map.quarter"


def start(ctx: GameContext, room: str | None = ROOM) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx, room=room)
    scenes.push(game)
    scenes.update(STEP)
    return scenes, game


def settle(scenes: SceneManager, ticks: int = 3) -> None:
    for _ in range(ticks):
        scenes.update(STEP)


def placed(game: GameplayScene) -> list[tuple[str, int]]:
    """Each NPC in the room as (dialogue, tile column), left to right."""
    left = game.rooms.graph.rects[ROOM].x
    query = game.world.query(Body, Npc)
    found = [(npc.dialogue, int(body.x - left) // 16) for _, body, npc in query]
    return sorted(found, key=lambda item: item[1])


def set_flags(scenes: SceneManager, game: GameplayScene, **flags: int) -> None:
    game.progress.data.flags.update(flags)
    settle(scenes)


def stand_by(scenes: SceneManager, game: GameplayScene, dialogue: str) -> None:
    for _, body, npc in game.world.query(Body, Npc):
        if npc.dialogue == dialogue:
            game.body.x, game.body.y = body.x + 2, body.y - 4
    settle(scenes, 5)


def finish(scenes: SceneManager, game: GameplayScene) -> None:
    for _ in range(40):
        if scenes.top is game:
            return
        key(scenes, pygame.K_ESCAPE)
    raise AssertionError("still in a conversation")


def ask_about_lights(scenes: SceneManager, game: GameplayScene) -> None:
    stand_by(scenes, game, "hesper")
    talk(scenes)
    pick(scenes, "I found a lost light")
    for _ in range(12):
        current = scenes.top.ui.root.current  # ty: ignore[unresolved-attribute]
        if current is not None and current.text.startswith(("How do", "Goodbye")):
            break
        key(scenes, pygame.K_RETURN)
    finish(scenes, game)


def test_stage_zero_places_hesper_by_the_beacon_and_quill_in_the_belfry(ctx: GameContext) -> None:
    _, game = start(ctx)
    assert placed(game) == [("hesper", 12), ("quill", 22)]


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({"hesper_stage": 1}, [("hesper", 16), ("quill", 22)]),
        ({"quill_stage": 1}, [("hesper", 12), ("quill", 27)]),
        ({"quill_stage": 2}, [("hesper", 12), ("quill", 33)]),
        ({"quill_stage": 2, "hesper_stage": 1}, [("hesper", 16), ("quill", 33)]),
    ],
)
def test_a_room_loads_with_everyone_where_their_stage_puts_them(
    ctx: GameContext, flags: dict[str, int], expected: list[tuple[str, int]]
) -> None:
    ctx.flags = flags
    _, game = start(ctx)
    assert placed(game) == expected


def test_a_stage_flag_moves_them_live(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    set_flags(scenes, game, quill_stage=1)
    assert placed(game) == [("hesper", 12), ("quill", 27)]
    set_flags(scenes, game, quill_stage=2, hesper_stage=1)
    assert placed(game) == [("hesper", 16), ("quill", 33)]
    set_flags(scenes, game, quill_stage=0, hesper_stage=0)
    assert placed(game) == [("hesper", 12), ("quill", 22)]


def test_the_lines_change_with_the_place(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    set_flags(scenes, game, quill_stage=1)
    stand_by(scenes, game, "quill")
    assert talk(scenes).runner.text == "dialogue.quill.square"


def test_hesper_pays_each_rescued_light_once(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    data = game.progress.data
    set_flags(scenes, game, lost_lights=1)
    ask_about_lights(scenes, game)
    assert data.stats.embers == 50
    ask_about_lights(scenes, game)
    assert data.stats.embers == 50

    set_flags(scenes, game, lost_lights=2)
    ask_about_lights(scenes, game)
    assert game.loadout.count("flare_pouch") == 1

    set_flags(scenes, game, lost_lights=3)
    ask_about_lights(scenes, game)
    assert game.loadout.count("oil_flask") == 1
    ask_about_lights(scenes, game)
    assert (data.stats.embers, game.loadout.count("flare_pouch")) == (50, 1)


def test_several_owed_rewards_are_all_paid_in_one_visit(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    set_flags(scenes, game, lost_lights=3)
    ask_about_lights(scenes, game)
    assert game.progress.data.stats.embers == 50
    assert game.loadout.count("flare_pouch") == 1
    assert game.loadout.count("oil_flask") == 1


def buy_the_map(scenes: SceneManager, game: GameplayScene) -> None:
    stand_by(scenes, game, "quill")
    talk(scenes)
    pick(scenes, "Do you sell maps")
    assert isinstance(scenes.top, ShopScene)
    pick(scenes, "Map of the Sunken Quarter")
    finish(scenes, game)


def test_quill_sells_the_map_for_embers(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    game.progress.data.stats.embers = 40
    buy_the_map(scenes, game)
    assert game.loadout.count(MAP) == 1
    assert wallet(game.progress.data) == 10
    assert game.toasts


def test_the_map_is_not_sold_to_the_poor_or_twice(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    game.progress.data.stats.embers = 29
    stand_by(scenes, game, "quill")
    talk(scenes)
    pick(scenes, "Do you sell maps")
    shop = scenes.top
    assert isinstance(shop, ShopScene)
    assert not shop.buttons[MAP].enabled
    game.progress.data.stats.embers = 100
    shop._refresh()
    pick(scenes, "Map of the Sunken Quarter")
    assert not shop.buttons[MAP].enabled
    assert wallet(game.progress.data) == 70


def test_a_bought_map_survives_quitting_and_continuing(ctx: GameContext) -> None:
    assert isinstance(ctx.storage, MemoryStorage)
    slot = SaveSlot(room=ROOM)
    slot.stats.embers = 40
    save_slot(ctx.storage, ctx.slot, slot)
    scenes, game = start(ctx, room=None)
    assert game.room == ROOM
    buy_the_map(scenes, game)
    scenes.close()
    saved = load_slot(ctx.storage, ctx.slot)
    assert saved is not None
    assert saved.inventory[MAP] == 1

    _, again = start(ctx, room=None)
    assert again.loadout.count(MAP) == 1
    assert again.facts["has." + MAP] == 1
    assert wallet(again.progress.data) == 10
