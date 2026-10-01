"""Flares: thrown with F, they fly, land, glow, refill the ember and burn out."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.game.flares import FLARE_LIFE, Flare, FlareKit
from emberwake.game.light import Ember, LightSource
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60


def start(ctx: GameContext) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx, room="Test_Room")
    game.loadout.give("flare")
    scenes.push(game)
    for _ in range(30):
        scenes.update(STEP)
    return scenes, game


def flares(game: GameplayScene) -> list[tuple[Body, Flare, LightSource]]:
    return [(b, f, s) for _, b, f, s in game.world.query(Body, Flare, LightSource)]


def throw(scenes: SceneManager) -> None:
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f))
    scenes.update(STEP)
    scenes.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_f))


def test_f_throws_a_flare_that_flies_and_falls(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    origin = game.body.center_x
    throw(scenes)
    assert len(flares(game)) == 1
    for _ in range(40):
        scenes.update(STEP)
    body, _, _ = flares(game)[0]
    assert body.center_x > origin + 20
    assert body.y > game.body.y - 40


def test_the_throw_has_a_cooldown(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    throw(scenes)
    throw(scenes)
    assert len(flares(game)) == 1
    for _ in range(45):
        scenes.update(STEP)
    throw(scenes)
    assert len(flares(game)) == 2


def test_a_flare_refills_the_ember_and_burns_out(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    ember = game.world.get(game.player, Ember)
    ember.current = 20
    throw(scenes)
    for _ in range(60):
        scenes.update(STEP)
    assert ember.current > 20
    for _ in range(round((FLARE_LIFE + 1) / STEP)):
        scenes.update(STEP)
    assert not flares(game)


def test_a_dying_flare_fades(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    throw(scenes)
    for _ in range(round((FLARE_LIFE - 0.5) / STEP)):
        scenes.update(STEP)
    _, flare, light = flares(game)[0]
    assert flare.life < 1.0
    assert light.strength < 1.0


def test_flares_run_out_and_come_back_in_light(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    kit = game.world.resource(FlareKit)
    for _ in range(kit.max_charges + 1):
        throw(scenes)
        for _ in range(45):
            scenes.update(STEP)
    assert kit.charges == 0
    assert len(flares(game)) == kit.max_charges
    game.world.spawn(Body(game.body.x, game.body.y, 4, 4), LightSource(radius=80))
    for _ in range(round(game.feel.light.flare_refill * 60) + 5):
        scenes.update(STEP)
    assert kit.charges >= 1


def test_no_flares_before_they_are_given(ctx: GameContext) -> None:
    scenes = SceneManager()
    game = GameplayScene(ctx, room="Test_Room")
    scenes.push(game)
    scenes.update(STEP)
    throw(scenes)
    assert not flares(game)
