"""Enemies in a real room hurt the player, who is knocked back, shows numbers and can die."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.game.combat import Health
from emberwake.game.enemies import Brain
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60


def start(ctx: GameContext) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx, room="Enemy_Yard")
    scenes.push(game)
    scenes.update(STEP)
    return scenes, game


def kinds(game: GameplayScene) -> list[str]:
    return sorted(brain.kind for _, brain in game.world.query(Brain))


def stand_on(game: GameplayScene, kind: str) -> None:
    for _, body, brain in game.world.query(Body, Brain):
        if brain.kind == kind:
            player = game.body
            player.x, player.y = body.x + 3, body.y - 4
            return
    raise AssertionError(kind)


def test_all_three_kinds_spawn(ctx: GameContext) -> None:
    _, game = start(ctx)
    assert kinds(game) == ["clockrat", "gloomcrawler", "wisp_eater"]


def test_touching_a_clockrat_hurts_and_shows_a_number(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    stand_on(game, "clockrat")
    for _ in range(5):
        scenes.update(STEP)
    assert game.world.get(game.player, Health).current == ctx_hp(game) - 1
    assert game.texts.count >= 1


def ctx_hp(game: GameplayScene) -> int:
    return game.feel.enemies.player_hp


def test_dying_to_an_enemy_respawns_the_player_whole(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    game.world.get(game.player, Health).current = 1
    stand_on(game, "clockrat")
    for _ in range(8):
        scenes.update(STEP)
    assert game.respawn_in > 0 or game.motor.dead
    for _ in range(60):
        scenes.update(STEP)
    health = game.world.get(game.player, Health)
    assert not game.motor.dead
    assert health.current == ctx_hp(game)


def test_swinging_kills_a_clockrat_and_counts_for_achievements(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    rat = next(eid for eid, brain in game.world.query(Brain) if brain.kind == "clockrat")
    game.world.get(game.player, Health).invulnerable = 99.0
    for _ in range(240):
        if rat not in game.world:
            break
        target, player = game.world.get(rat, Body), game.body
        facing = 1 if target.center_x >= player.center_x else -1
        game.motor.facing = facing
        player.x = target.center_x - facing * 14 - player.width / 2
        player.y = target.bottom - player.height
        scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_j))
        scenes.update(STEP)
        scenes.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_j))
        for _ in range(16):
            scenes.update(STEP)
    assert rat not in game.world
    assert ctx.achievements.counter("Killed") >= 1
