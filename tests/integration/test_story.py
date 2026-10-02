"""Story beats in the game: the intro, the Lamprey's reveal and the Great Lamp."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from tests.integration.test_greybox import STEP
from tests.integration.test_how_to_play import press
from tests.integration.test_tower import stand

from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.spawning import Identity
from emberwake.game.components import Sprite
from emberwake.game.interact import Interactable
from emberwake.game.lamps import Lamp
from emberwake.game.scenes.credits import CreditsScene
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.story import GreatLamp

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

SQUARE = (8, 8)
CISTERN = (10, 11)


def begin(ctx: GameContext, room: str | None = None) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx, room=room)
    scenes.push(game)
    scenes.update(STEP)
    return scenes, game


def tick(scenes: SceneManager, seconds: float) -> None:
    for _ in range(round(seconds / STEP)):
        scenes.update(STEP)


def test_a_new_game_opens_on_the_intro_and_it_plays_out(ctx: GameContext) -> None:
    ctx.new_game = True
    scenes, game = begin(ctx)
    assert game.cutscenes.active
    assert game.director.stage.fade > 0.9
    tick(scenes, 8.0)
    assert not game.cutscenes.active
    assert game.facts.flags["story_intro"] == 1
    assert game.director.stage.fade == 0


def test_a_continue_or_a_chosen_room_skips_the_intro(ctx: GameContext) -> None:
    _, game = begin(ctx)
    assert not game.cutscenes.active
    ctx.new_game = True
    _, game = begin(ctx, room="Wake")
    assert not game.cutscenes.active


def test_the_lamprey_reveals_itself_once_when_the_player_drops_in(ctx: GameContext) -> None:
    scenes, game = begin(ctx, room="Cistern")
    stand(game, CISTERN, 30, 3)
    tick(scenes, 0.1)
    assert game.cutscenes.active
    assert game.director.stage.focus is not None
    press(scenes, pygame.K_RETURN)
    assert not game.cutscenes.active
    assert game.facts.flags["story_lamprey_reveal"] == 1
    stand(game, CISTERN, 4, 12)
    tick(scenes, 0.2)
    stand(game, CISTERN, 30, 3)
    tick(scenes, 0.1)
    assert not game.cutscenes.active


def test_no_reveal_once_the_lamprey_is_dead(ctx: GameContext) -> None:
    ctx.flags = {"lamprey_defeated": 1, "lamprey_drained": 1}
    scenes, game = begin(ctx, room="Cistern")
    stand(game, CISTERN, 30, 3)
    tick(scenes, 0.1)
    assert not game.cutscenes.active


def great_lamp(game: GameplayScene) -> Body:
    (body,) = [b for _, b, i in game.world.query(Body, Identity) if i.prefab == "great_lamp"]
    return body


def npcs(game: GameplayScene, prefab: str) -> set[str]:
    return {i.room for _, i in game.world.query(Identity) if i.prefab == prefab}


def test_the_cold_great_lamp_cannot_be_kindled_before_the_lamprey(ctx: GameContext) -> None:
    _, game = begin(ctx, room="Market_Square")
    (eid,) = [e for e, i in game.world.query(Identity) if i.prefab == "great_lamp"]
    assert not game.world.has(eid, Interactable)


def test_kindling_the_great_lamp_lights_the_quarter_and_rolls_the_credits(
    ctx: GameContext,
) -> None:
    ctx.flags = {"lamprey_defeated": 1, "lamprey_drained": 1}
    scenes, game = begin(ctx, room="Market_Square")
    assert npcs(game, "tinker") == {"Tinkers_Nook"}
    body = great_lamp(game)
    game.body.x, game.body.y = body.x - 8, body.bottom - game.body.height
    tick(scenes, 0.1)
    press(scenes, pygame.K_e)
    assert game.cutscenes.active
    press(scenes, pygame.K_RETURN)
    assert isinstance(scenes.top, CreditsScene)
    flags = game.facts.flags
    assert (flags["great_lamp"], flags["hesper_stage"], flags["quill_stage"]) == (1, 1, 2)
    game.spawner.snapshot_all()
    quarter = [
        lamp.iid
        for level in game.rooms.graph.levels.values()
        if (level.field("Area") or "quarter") == "quarter"
        for lamp in level.entities("Lamp")
    ]
    saved = game.spawner.state.entities
    assert quarter
    assert all(saved[iid]["Lamp"]["lit"] for iid in quarter)
    assert all(lamp.lit and lamp.protected for _, lamp in game.world.query(Lamp))
    press(scenes, pygame.K_SPACE)
    assert scenes.top is game
    tick(scenes, 0.1)
    (sprite,) = [s for _, s, _ in game.world.query(Sprite, GreatLamp)]
    assert sprite.active
    assert "Market_Square" in npcs(game, "tinker")
    assert "Tinkers_Nook" not in npcs(game, "tinker")
