"""Signal_Lab: swings and flares light braziers, photocells open doors, bells stun."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.spawning import Identity
from emberwake.game.combat import Health, Hitbox
from emberwake.game.data.save import SaveSlot, save_slot
from emberwake.game.enemies import Brain
from emberwake.game.flares import FlareKit, throw_flare
from emberwake.game.interact import Switch
from emberwake.game.light import LightSource
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.signals import Door
from emberwake.game.switches import Bell, Brazier

if TYPE_CHECKING:
    from emberwake.engine.ecs import EntityId
    from emberwake.game.context import GameContext

STEP = 1 / 60
ROOM = "Signal_Lab"
BRAZIER_B, BRAZIER_F = 9, 31
"""Columns of the lab's two braziers."""


def start(ctx: GameContext) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx, room=ROOM)
    scenes.push(game)
    scenes.update(STEP)
    game.world.get(game.player, Health).invulnerable = 999.0
    return scenes, game


def run(scenes: SceneManager, ticks: int) -> None:
    for _ in range(ticks):
        scenes.update(STEP)


def things(game: GameplayScene, prefab: str) -> list[EntityId]:
    found = [e for e, i in game.world.query(Identity) if i.prefab == prefab]
    return sorted(found, key=lambda eid: game.world.get(eid, Body).x)


def brazier_at(game: GameplayScene, column: int) -> EntityId:
    x = game.rooms.graph.rects[ROOM].x + column * 16 + 8
    return next(e for e in things(game, "brazier") if abs(game.world.get(e, Body).center_x - x) < 8)


def swing_at(scenes: SceneManager, game: GameplayScene, target: Body) -> None:
    player = game.body
    game.motor.facing = 1
    player.x = target.x - 14 - player.width / 2
    player.y = target.bottom - player.height
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_j))
    scenes.update(STEP)
    scenes.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_j))
    run(scenes, 20)


def doors(game: GameplayScene) -> list[Door]:
    return [game.world.get(eid, Door) for eid in things(game, "door")]


def test_the_lab_spawns_each_switch_cold(ctx: GameContext) -> None:
    _, game = start(ctx)
    assert len(things(game, "photocell")) == 1
    assert len(things(game, "bell")) == 1
    assert [game.world.get(e, Brazier).lit for e in things(game, "brazier")] == [False, False]
    assert [door.open for door in doors(game)] == [False, False, False]


def test_a_swing_lights_a_brazier_whose_photocell_opens_a_door_for_good(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    cell = game.world.get(things(game, "photocell")[0], Switch)
    assert not cell.on
    brazier = brazier_at(game, BRAZIER_B)
    swing_at(scenes, game, game.world.get(brazier, Body))
    assert game.world.get(brazier, Brazier).lit
    assert game.world.find(brazier, LightSource) is not None
    assert cell.on
    assert doors(game)[0].open
    game.body.x = game.rooms.graph.rects[ROOM].x + 3 * 16
    run(scenes, 30)
    assert doors(game)[0].open


def test_a_flare_lights_a_brazier(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    brazier = brazier_at(game, BRAZIER_F)
    body = game.world.get(brazier, Body)
    throw_flare(game.world, game.world.resource(FlareKit), body.center_x, body.y + 8, 1)
    run(scenes, 5)
    assert game.world.get(brazier, Brazier).lit
    assert doors(game)[2].open


def test_a_bell_stuns_a_nearby_clockrat_and_pulses_its_door(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    bell = things(game, "bell")[0]
    bell_body = game.world.get(bell, Body)
    rat = things(game, "clockrat")[0]
    rat_body = game.world.get(rat, Body)
    rat_body.x = bell_body.x - 40
    run(scenes, 2)
    assert game.world.get(rat, Brain).stagger == 0
    swing_at(scenes, game, bell_body)
    assert game.world.get(rat, Brain).stagger > 0
    assert not game.world.get(rat, Hitbox).active
    assert doors(game)[1].open
    assert game.world.get(bell, Bell).pulse > 0
    run(scenes, 120)
    assert game.world.get(rat, Brain).stagger <= 0
    assert not doors(game)[1].open


def test_a_lit_brazier_survives_a_room_reload_and_a_quit(ctx: GameContext) -> None:
    save_slot(ctx.storage, ctx.slot, SaveSlot(room=ROOM))
    scenes = SceneManager()
    game = GameplayScene(ctx)
    scenes.push(game)
    scenes.apply_pending()
    run(scenes, 2)
    swing_at(scenes, game, game.world.get(brazier_at(game, BRAZIER_B), Body))
    game.rooms.reload(game.rooms.graph)
    run(scenes, 5)
    again = brazier_at(game, BRAZIER_B)
    assert game.world.get(again, Brazier).lit
    assert game.world.find(again, LightSource) is not None
    scenes.close()

    scenes = SceneManager()
    game = GameplayScene(ctx)
    scenes.push(game)
    scenes.apply_pending()
    run(scenes, 5)
    assert game.world.get(brazier_at(game, BRAZIER_B), Brazier).lit
    assert doors(game)[0].open
    assert not game.world.get(brazier_at(game, BRAZIER_F), Brazier).lit
