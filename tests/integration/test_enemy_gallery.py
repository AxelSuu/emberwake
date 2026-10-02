"""Drip Lurkers and Gearbugs in a real room: they drop, retract, guard and open up."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.game.combat import Health
from emberwake.game.enemies import Brain
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.engine.ecs import EntityId
    from emberwake.game.context import GameContext

STEP = 1 / 60


def start(ctx: GameContext) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx, room="Enemy_Gallery")
    scenes.push(game)
    scenes.update(STEP)
    return scenes, game


def of_kind(game: GameplayScene, kind: str) -> list[EntityId]:
    return sorted(eid for eid, brain in game.world.query(Brain) if brain.kind == kind)


def stand_under(game: GameplayScene, lurker: EntityId) -> None:
    above, player = game.world.get(lurker, Body), game.body
    floor = above.bottom + 8 * 16
    player.x, player.y = above.center_x - player.width / 2, floor - player.height


def retracted(game: GameplayScene) -> EntityId:
    lurkers = of_kind(game, "drip_lurker")
    return next(e for e in lurkers if game.world.get(e, Brain).state == "retract")


def test_both_kinds_spawn_in_the_gallery(ctx: GameContext) -> None:
    _, game = start(ctx)
    assert len(of_kind(game, "drip_lurker")) == 3
    assert len(of_kind(game, "gearbug")) == 2


def test_a_dark_lurker_drops_on_the_player_and_hurts(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    scenes.update(STEP)
    dark = next(e for e in of_kind(game, "drip_lurker") if e != retracted(game))
    start_y = game.world.get(dark, Body).y
    seen = set()
    stand_under(game, dark)
    for _ in range(180):
        scenes.update(STEP)
        seen.add(game.world.get(dark, Brain).state)
    assert {"warn", "drop"} <= seen
    assert game.world.get(dark, Body).y >= start_y
    assert game.world.get(game.player, Health).current < game.feel.enemies.player_hp


def test_a_lurker_under_the_lamp_stays_tucked_away(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    scenes.update(STEP)
    lit = retracted(game)
    stand_under(game, lit)
    for _ in range(180):
        scenes.update(STEP)
    assert game.world.get(lit, Brain).state == "retract"
    assert game.world.get(game.player, Health).current == game.feel.enemies.player_hp


def swing(scenes: SceneManager) -> None:
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_j))
    scenes.update(STEP)
    scenes.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_j))
    for _ in range(16):
        scenes.update(STEP)


def swing_from(scenes: SceneManager, game: GameplayScene, bug: EntityId, side: int) -> None:
    """Swing at the bug from `side` (-1 left, 1 right), holding it and the player in place."""
    target, player = game.world.get(bug, Body), game.body
    game.motor.facing = -side
    player.x = target.center_x + side * 14 - player.width / 2
    player.y = target.bottom - player.height
    game.world.get(game.player, Health).invulnerable = 99.0
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_j))
    scenes.update(STEP)
    scenes.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_j))
    for _ in range(3):
        player.x = target.center_x + side * 14 - player.width / 2
        scenes.update(STEP)


def test_a_gearbug_takes_hits_from_behind_but_not_from_the_front(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    scenes.update(STEP)
    bug = of_kind(game, "gearbug")[0]
    brain = game.world.get(bug, Brain)
    health = game.world.get(bug, Health)
    brain.facing, brain.state, brain.time = -1, "patrol", 0.0
    full = health.current
    swing_from(scenes, game, bug, side=-1)
    assert health.current == full
    for _ in range(20):
        scenes.update(STEP)
    brain.facing, brain.state, brain.time = -1, "patrol", 0.0
    swing_from(scenes, game, bug, side=1)
    assert health.current == full - 1
