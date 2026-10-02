"""World flags in Enemy_Yard: dialogue, grants, F7, --flags and a SetFlag zone reshape the room."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.spawning import Identity
from emberwake.game.dialogue import Npc
from emberwake.game.flags import SetFlag
from emberwake.game.interact import Pickup
from emberwake.game.scenes.dev import FlagsScene
from emberwake.game.scenes.dialogue import DialogueScene
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.signals import Door

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60


def press(scenes: SceneManager, key: int) -> None:
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    scenes.handle(pygame.event.Event(pygame.KEYUP, key=key))
    scenes.update(STEP)


def start(ctx: GameContext) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx, room="Enemy_Yard")
    scenes.push(game)
    scenes.update(STEP)
    return scenes, game


def settle(scenes: SceneManager, ticks: int = 3) -> None:
    for _ in range(ticks):
        scenes.update(STEP)


def door_open(game: GameplayScene) -> bool:
    ((_, door),) = game.world.query(Door)
    return door.open


def embers(game: GameplayScene) -> int:
    return game.world.count(Pickup)


def braziers(game: GameplayScene) -> int:
    return sum(1 for _, identity in game.world.query(Identity) if identity.prefab == "brazier")


def stand_in(game: GameplayScene, component: type) -> None:
    for _, body, _ in game.world.query(Body, component):
        game.body.x, game.body.y = body.x + 2, body.y + body.height - game.body.height
        return
    raise AssertionError(component)


def meet_the_tinker(scenes: SceneManager, game: GameplayScene) -> None:
    stand_in(game, Npc)
    settle(scenes, 5)
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
    settle(scenes, 2)
    scenes.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_e))
    settle(scenes, 2)
    assert isinstance(scenes.top, DialogueScene)
    while scenes.top is not game:
        current = scenes.top.ui.root.current
        leave = current is not None and current.text.startswith("Goodbye")
        press(scenes, pygame.K_RETURN if leave else pygame.K_DOWN)


def test_the_alcove_starts_shut_bare_and_dark(ctx: GameContext) -> None:
    _, game = start(ctx)
    assert not door_open(game)
    assert embers(game) == 0
    assert braziers(game) == 1
    assert game.world.count(SetFlag) == 1


def test_meeting_the_tinker_opens_the_door_and_his_flare_brings_out_an_ember(
    ctx: GameContext,
) -> None:
    scenes, game = start(ctx)
    meet_the_tinker(scenes, game)
    settle(scenes)
    assert game.progress.data.flags["met_tinker"] == 1
    assert door_open(game)
    assert embers(game) == 1


def test_stepping_into_the_alcove_takes_the_ember_and_lights_the_brazier(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    meet_the_tinker(scenes, game)
    settle(scenes)
    stand_in(game, SetFlag)
    settle(scenes)
    assert game.progress.data.flags["alcove_lit"] == 1
    assert embers(game) == 0
    assert braziers(game) == 2
    assert game.world.count(SetFlag) == 0


def test_a_grant_brings_out_the_ember(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    assert game.loadout.give("flare")
    settle(scenes)
    assert embers(game) == 1


def test_a_collected_ember_stays_gone_when_flags_change(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    game.loadout.give("flare")
    settle(scenes)
    stand_in(game, Pickup)
    settle(scenes)
    assert embers(game) == 0
    game.progress.data.abilities.remove("flare")
    settle(scenes)
    game.progress.data.abilities.append("flare")
    settle(scenes)
    assert embers(game) == 0


def test_f7_toggles_flags_the_levels_read_and_the_world_follows(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    press(scenes, pygame.K_F7)
    flags = scenes.top
    assert isinstance(flags, FlagsScene)
    assert {"met_tinker", "alcove_lit"} <= {row.text for row in flags.list.children}
    while (current := flags.list.current) is not None and current.text != "alcove_lit":
        press(scenes, pygame.K_DOWN)
    press(scenes, pygame.K_RETURN)
    press(scenes, pygame.K_ESCAPE)
    settle(scenes)
    assert scenes.top is game
    assert braziers(game) == 2
    assert game.world.count(SetFlag) == 0


def test_flags_from_the_command_line_are_in_place_before_the_first_spawn(
    ctx: GameContext,
) -> None:
    ctx.flags = {"met_tinker": 1, "alcove_lit": 1}
    scenes = SceneManager()
    game = GameplayScene(ctx, room="Enemy_Yard")
    scenes.push(game)
    scenes.update(STEP)
    assert door_open(game)
    assert braziers(game) == 2
    assert game.world.count(SetFlag) == 0
