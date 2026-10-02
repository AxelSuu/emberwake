"""Arena_Lab: an encounter of two waves behind a door, its reward, and what persists."""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.engine.physics import Tile
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.spawning import Identity
from emberwake.game.combat import Health
from emberwake.game.data.save import SaveSlot, load_slot, save_slot
from emberwake.game.encounters import Encounter, EncounterCleared, EncounterStarted
from emberwake.game.enemies import Brain, Minion
from emberwake.game.player.controller import Died
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.engine.ecs import EntityId
    from emberwake.engine.platform.display import Display
    from emberwake.game.context import GameContext

STEP = 1 / 60
TS = 16
ROOM = "Arena_Lab"


def start(ctx: GameContext, *, from_slot: bool = False) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx) if from_slot else GameplayScene(ctx, room=ROOM)
    scenes.push(game)
    for _ in range(3):
        scenes.update(STEP)
    return scenes, game


def run(scenes: SceneManager, seconds: float) -> None:
    for _ in range(round(seconds / STEP)):
        scenes.update(STEP)


def stand_at(game: GameplayScene, column: int) -> None:
    rect = game.rooms.graph.rects[ROOM]
    body = game.body
    body.x, body.y = rect.x + column * TS + 3, rect.y + 10 * TS - body.height
    game.motor.previous = (body.x, body.y)
    game.world.get(game.player, Health).invulnerable = 99.0


def solid(game: GameplayScene, column: int, row: int) -> bool:
    rect = game.rooms.graph.rects[ROOM]
    return game.grid.get(rect.x // TS + column, rect.y // TS + row) == Tile.SOLID


def wave(game: GameplayScene) -> list[EntityId]:
    owners = {eid for eid, _ in game.world.query(Encounter)}
    return sorted(e for e, _, m in game.world.query(Brain, Minion) if m.owner in owners)


def kinds(game: GameplayScene) -> list[str]:
    return sorted(game.world.get(e, Brain).kind for e in wave(game))


def kill_wave(scenes: SceneManager, game: GameplayScene) -> None:
    for eid in wave(game):
        game.world.get(eid, Health).dead = True
    run(scenes, 0.1)


def test_the_arena_waits_until_the_player_steps_in(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    run(scenes, 1.0)
    assert not wave(game)
    assert not solid(game, 6, 5)


def test_stepping_in_shuts_the_door_and_sends_two_clockrats(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    started: list[EncounterStarted] = []
    ctx.bus.subscribe(EncounterStarted, started.append)
    stand_at(game, 8)
    run(scenes, 0.2)
    assert started
    assert kinds(game) == ["clockrat", "clockrat"]
    assert solid(game, 6, 5)
    assert solid(game, 36, 8)


def test_the_second_wave_is_the_king_and_clearing_it_opens_the_way(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    done: list[EncounterCleared] = []
    ctx.bus.subscribe(EncounterCleared, done.append)
    stand_at(game, 8)
    run(scenes, 0.2)
    kill_wave(scenes, game)
    assert not wave(game)
    run(scenes, game.feel.encounters.wave_delay + 0.3)
    assert kinds(game) == ["clockrat_king"]
    assert solid(game, 6, 5)
    stand_at(game, 8)
    kill_wave(scenes, game)
    run(scenes, 0.3)
    assert done
    assert not wave(game)
    assert not solid(game, 6, 5)
    assert not solid(game, 36, 8)
    assert not game.progress.data.world.removed


def test_dying_mid_fight_resets_the_arena(ctx: GameContext) -> None:
    save_slot(ctx.storage, ctx.slot, SaveSlot(room=ROOM))
    scenes, game = start(ctx, from_slot=True)
    stand_at(game, 8)
    run(scenes, 0.2)
    assert solid(game, 6, 5)
    ctx.bus.publish(Died(game.body.center_x, game.body.bottom, cause="health"))
    game.motor.dead = True
    run(scenes, 2.0)
    assert not wave(game)
    assert not solid(game, 6, 5)
    stand_at(game, 8)
    run(scenes, 0.2)
    assert kinds(game) == ["clockrat", "clockrat"]


def test_a_cleared_arena_stays_cleared_after_a_reload_and_after_continuing(
    ctx: GameContext,
) -> None:
    save_slot(ctx.storage, ctx.slot, SaveSlot(room=ROOM))
    scenes, game = start(ctx, from_slot=True)
    stand_at(game, 8)
    run(scenes, 0.2)
    kill_wave(scenes, game)
    run(scenes, game.feel.encounters.wave_delay + 0.3)
    kill_wave(scenes, game)
    run(scenes, 0.3)
    ((eid, _),) = game.world.query(Encounter)
    iid = game.world.get(eid, Identity).iid
    assert not solid(game, 36, 8)
    scenes.close()
    saved = load_slot(ctx.storage, ctx.slot)
    assert saved is not None
    assert saved.world.entities[iid]["Switch"]["on"] is True

    scenes, again = start(ctx, from_slot=True)
    stand_at(again, 8)
    run(scenes, 0.5)
    assert not wave(again)
    assert not solid(again, 6, 5)
    assert not solid(again, 36, 8)


def test_the_lab_draws_mid_fight(ctx: GameContext, display: Display) -> None:
    scenes, game = start(ctx)
    stand_at(game, 8)
    run(scenes, 0.3)
    game.draw(display.canvas, 1.0)
