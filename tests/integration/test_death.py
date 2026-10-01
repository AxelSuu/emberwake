"""Death and recovery: hazards cost a pip, dying sends you to the beacon and drops a Cinder."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.game.cinder import CinderMark
from emberwake.game.combat import Health
from emberwake.game.enemies import Brain
from emberwake.game.player.controller import Died
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.shop import SPENT, wallet

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60
TS = 16


def start(ctx: GameContext, room: str = "Test_Room") -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx, room=room)
    scenes.push(game)
    for _ in range(5):
        scenes.update(STEP)
    return scenes, game


def run(scenes: SceneManager, ticks: int) -> None:
    for _ in range(ticks):
        scenes.update(STEP)


def into_spikes(game: GameplayScene) -> None:
    """Drop the player onto the spike pit of Test_Room (columns 14 to 19, row 31)."""
    rect = game.rooms.graph.rects["Test_Room"]
    body = game.body
    body.x, body.y = rect.x + 16 * TS, rect.y + 28 * TS
    game.motor.previous = (body.x, body.y)


def walk_away(scenes: SceneManager, game: GameplayScene) -> None:
    """Stand on the floor of Test_Room far from where the player respawns."""
    rect = game.rooms.graph.rects["Test_Room"]
    body = game.body
    body.x, body.y = rect.x + 26 * TS, rect.y + 30 * TS - body.height
    game.motor.previous = (body.x, body.y)
    run(scenes, 3)


def die(scenes: SceneManager, game: GameplayScene) -> None:
    game.world.get(game.player, Health).current = 1
    game.ctx.bus.publish(Died(game.body.center_x, game.body.bottom, cause="health"))
    game.motor.dead = True
    juice = game.feel.juice
    run(scenes, juice.respawn_delay + juice.death_hitstop + 4)


def test_a_hazard_costs_one_pip_and_keeps_the_rest(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    health = game.world.get(game.player, Health)
    full = health.current
    into_spikes(game)
    run(scenes, 90)
    assert not game.motor.dead
    assert game.world.get(game.player, Health).current == full - 1
    assert game.body.x < game.rooms.graph.rects["Test_Room"].x + 14 * TS


def test_dying_returns_to_the_beacon_whole_and_drops_the_embers(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    game.progress.data.stats.embers = 12
    walk_away(scenes, game)
    spot = (game.body.center_x, game.body.bottom)
    die(scenes, game)
    data = game.progress.data
    assert data.cinder is not None
    assert (data.cinder.embers, data.cinder.room) == (12, "Test_Room")
    assert (round(data.cinder.x), round(data.cinder.y)) == (round(spot[0]), round(spot[1]))
    assert wallet(data) == 0
    health = game.world.get(game.player, Health)
    assert health.current == health.max
    assert game.world.count(CinderMark) == 1


def test_touching_the_cinder_gives_the_embers_back(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    game.progress.data.stats.embers = 7
    walk_away(scenes, game)
    die(scenes, game)
    cinder = next(eid for eid, _ in game.world.query(CinderMark))
    spot = game.world.get(cinder, Body)
    body = game.body
    body.x, body.y = spot.x, spot.bottom - body.height
    run(scenes, 3)
    assert game.progress.data.cinder is None
    assert wallet(game.progress.data) == 7
    assert game.world.count(CinderMark) == 0


def test_dying_again_loses_the_old_cinder(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    game.progress.data.stats.embers = 5
    walk_away(scenes, game)
    die(scenes, game)
    die(scenes, game)
    data = game.progress.data
    assert data.cinder is None
    assert data.flags[SPENT] == 5
    assert game.world.count(CinderMark) == 0


def test_killed_enemies_come_back_when_you_rest(ctx: GameContext) -> None:
    scenes, game = start(ctx, "Enemy_Yard")
    rat = next(eid for eid, brain in game.world.query(Brain) if brain.kind == "clockrat")
    game.world.get(rat, Health).dead = True
    run(scenes, 2)
    assert all(brain.kind != "clockrat" for _, brain in game.world.query(Brain))
    die(scenes, game)
    run(scenes, 2)
    assert any(brain.kind == "clockrat" for _, brain in game.world.query(Brain))
