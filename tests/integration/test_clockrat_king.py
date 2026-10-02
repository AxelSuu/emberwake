"""The Clockrat King in King_Lab: armor, the crown, toppling, rats and a defeat that sticks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.spawning import Identity
from emberwake.game.combat import Blocked, Health
from emberwake.game.data.save import SaveSlot, load_slot, save_slot
from emberwake.game.enemies import Brain, Court, Summoned
from emberwake.game.light import LightSource, light_at
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.engine.ecs import EntityId
    from emberwake.engine.platform.display import Display
    from emberwake.game.context import GameContext

STEP = 1 / 60


def start(ctx: GameContext, *, from_slot: bool = False) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx) if from_slot else GameplayScene(ctx, room="King_Lab")
    scenes.push(game)
    scenes.update(STEP)
    scenes.update(STEP)
    return scenes, game


def of_kind(game: GameplayScene, kind: str) -> list[EntityId]:
    return sorted(eid for eid, brain in game.world.query(Brain) if brain.kind == kind)


def the_king(game: GameplayScene) -> EntityId:
    (boss,) = of_kind(game, "clockrat_king")
    return boss


def swing(scenes: SceneManager, game: GameplayScene, boss: EntityId, *, above: bool) -> None:
    """Swing at the King from level with it, or down onto its crown from over it."""
    target, player = game.world.get(boss, Body), game.body
    game.world.get(game.player, Health).invulnerable = 99.0
    game.motor.vy = 0.0
    if above:
        player.x, player.y = target.center_x - player.width / 2, target.y - player.height - 6
    else:
        player.x = target.x - player.width - 4
        player.y = target.bottom - player.height
        game.motor.facing = 1
    keys = [pygame.K_j, pygame.K_s] if above else [pygame.K_j]
    for key in keys:
        scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    scenes.update(STEP)
    for key in keys:
        scenes.handle(pygame.event.Event(pygame.KEYUP, key=key))
    for _ in range(3):
        if above:
            player.x = target.center_x - player.width / 2
        else:
            player.x = target.x - player.width - 4
        scenes.update(STEP)
    for _ in range(14):
        scenes.update(STEP)


def test_the_lab_holds_a_lit_king_and_its_markers(ctx: GameContext) -> None:
    _, game = start(ctx)
    boss = the_king(game)
    lamp = game.world.get(boss, LightSource)
    assert lamp.strength == 1.0
    body = game.world.get(boss, Body)
    assert light_at(game.world, body.center_x + 40, body.y + 16, lantern=False) > 0
    markers = [i for _, i in game.world.query(Identity) if i.prefab == "rat_spawn"]
    assert len(markers) == 3
    assert not of_kind(game, "clockrat")


def test_swings_at_the_side_clang_and_a_hit_on_the_crown_topples_it(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    boss = the_king(game)
    health = game.world.get(boss, Health)
    blocked: list[Blocked] = []
    ctx.bus.subscribe(Blocked, blocked.append)
    swing(scenes, game, boss, above=False)
    assert health.current == game.feel.enemies.king_hp
    assert blocked
    assert game.world.get(boss, Brain).state != "toppled"
    swing(scenes, game, boss, above=True)
    assert health.current == game.feel.enemies.king_hp - 1
    assert game.world.get(boss, Brain).state == "toppled"
    assert game.world.get(boss, LightSource).strength == 0.0


def test_a_toppled_king_takes_side_swings_then_gets_up(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    boss = the_king(game)
    health, brain = game.world.get(boss, Health), game.world.get(boss, Brain)
    swing(scenes, game, boss, above=True)
    assert brain.state == "toppled"
    swing(scenes, game, boss, above=False)
    assert health.current == game.feel.enemies.king_hp - 2
    for _ in range(round(game.feel.enemies.king_topple_time / STEP)):
        scenes.update(STEP)
    assert brain.state != "toppled"
    assert game.world.get(boss, LightSource).strength == 1.0


def test_it_calls_rats_to_the_markers_and_they_go_with_it(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    boss = the_king(game)
    game.body.x = game.world.get(boss, Body).x - 200
    game.world.get(game.player, Health).invulnerable = 99.0
    called: list[Summoned] = []
    ctx.bus.subscribe(Summoned, called.append)
    game.world.get(boss, Court).idle = game.feel.enemies.king_summon_every
    for _ in range(round((game.feel.enemies.king_call + 0.5) / STEP)):
        scenes.update(STEP)
    rats = of_kind(game, "clockrat")
    assert len(rats) == game.feel.enemies.king_summon_count
    markers = {
        body.center_x for e, body, i in game.world.query(Body, Identity) if i.prefab == "rat_spawn"
    }
    assert len(called) == len(rats)
    assert {event.x for event in called} <= markers
    game.world.get(boss, Health).dead = True
    for _ in range(3):
        scenes.update(STEP)
    assert not of_kind(game, "clockrat")
    assert not of_kind(game, "clockrat_king")


def test_a_defeated_king_stays_defeated_after_quitting_and_continuing(ctx: GameContext) -> None:
    save_slot(ctx.storage, ctx.slot, SaveSlot(room="King_Lab"))
    scenes, game = start(ctx, from_slot=True)
    boss = the_king(game)
    iid = game.world.get(boss, Identity).iid
    game.world.get(boss, Health).current = 1
    swing(scenes, game, boss, above=True)
    assert not of_kind(game, "clockrat_king")
    assert iid in game.progress.data.world.removed
    scenes.close()
    saved = load_slot(ctx.storage, ctx.slot)
    assert saved is not None
    assert iid in saved.world.removed

    _, again = start(ctx, from_slot=True)
    assert not of_kind(again, "clockrat_king")


def test_the_king_draws_upright_and_toppled(ctx: GameContext, display: Display) -> None:
    scenes, game = start(ctx)
    boss = the_king(game)
    game.body.x = game.world.get(boss, Body).x - 60
    scenes.update(STEP)
    game.draw(display.canvas, 1.0)
    swing(scenes, game, boss, above=True)
    assert game.world.get(boss, Brain).state == "toppled"
    game.draw(display.canvas, 1.0)
