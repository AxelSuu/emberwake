"""The Lamprey in Cistern_Lab: phases, damage windows, the drain, defeat and a player's death."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.physics import Body, Tile
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.spawning import Identity
from emberwake.game.combat import Blocked, Health, hurt
from emberwake.game.data.save import SaveSlot, load_slot, save_slot
from emberwake.game.lamprey import (
    DEFEATED,
    DRAINED,
    Drained,
    Lamprey,
    LampreyDefeated,
    PhaseChanged,
)
from emberwake.game.lamps import Lamp
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.signals import Door
from emberwake.game.switches import Photocell

if TYPE_CHECKING:
    from emberwake.engine.ecs import EntityId
    from emberwake.engine.platform.display import Display
    from emberwake.game.context import GameContext

STEP = 1 / 60


def start(ctx: GameContext, *, from_slot: bool = False) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx) if from_slot else GameplayScene(ctx, room="Cistern_Lab")
    scenes.push(game)
    scenes.update(STEP)
    scenes.update(STEP)
    return scenes, game


def boss_of(game: GameplayScene) -> EntityId:
    (boss,) = (eid for eid, _ in game.world.query(Lamprey))
    return boss


def state(game: GameplayScene) -> Lamprey:
    return game.world.get(boss_of(game), Lamprey)


def health(game: GameplayScene) -> Health:
    return game.world.get(boss_of(game), Health)


def run_until(scenes: SceneManager, game: GameplayScene, mode: str, seconds: float = 30.0) -> None:
    for _ in range(round(seconds / STEP)):
        if state(game).mode == mode:
            return
        game.world.get(game.player, Health).invulnerable = 99.0
        scenes.update(STEP)
    raise AssertionError(f"never reached {mode}, last in {state(game).mode}")


def swing(scenes: SceneManager, game: GameplayScene, *, above: bool) -> None:
    """Swing at the head from level with it, or down onto it from over it."""
    boss, player = boss_of(game), game.body
    game.world.get(game.player, Health).invulnerable = 99.0
    keys = [pygame.K_j, pygame.K_s] if above else [pygame.K_j]

    def place() -> None:
        if boss not in game.world:
            return
        target = game.world.get(boss, Body)
        if above:
            player.x, player.y = target.center_x - player.width / 2, target.y - player.height - 6
        else:
            player.x, player.y = target.x - player.width - 4, target.bottom - player.height
            game.motor.facing = 1
        game.motor.vy = 0.0
        game.motor.grounded = not above

    place()
    for key in keys:
        scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    scenes.update(STEP)
    for key in keys:
        scenes.handle(pygame.event.Event(pygame.KEYUP, key=key))
    for _ in range(17):
        place()
        scenes.update(STEP)


def light_lamps(game: GameplayScene) -> None:
    for _, lamp in game.world.query(Lamp):
        lamp.lit = True


def test_the_lab_holds_the_arena(ctx: GameContext) -> None:
    _, game = start(ctx)
    lamprey = state(game)
    assert lamprey.arena == tuple(game.rooms.graph.rects["Cistern_Lab"])
    assert sum(1 for _ in game.world.query(Lamp)) == 4
    cells = [cell for _, cell in game.world.query(Photocell)]
    assert len(cells) == 2
    assert all(cell.sealed for cell in cells)
    floor = [door for _, door in game.world.query(Door)]
    assert [door.open for door in floor] == [True]
    assert health(game).current == game.feel.lamprey.hp


def test_it_hunts_the_lantern_and_is_open_only_after_biting_stone(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    blocked: list[Blocked] = []
    ctx.bus.subscribe(Blocked, blocked.append)
    run_until(scenes, game, "surface")
    swing(scenes, game, above=False)
    assert blocked
    assert health(game).current == game.feel.lamprey.hp
    run_until(scenes, game, "stunned")
    swing(scenes, game, above=False)
    assert health(game).current == game.feel.lamprey.hp - 1


def test_phases_follow_its_health(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    changed: list[PhaseChanged] = []
    ctx.bus.subscribe(PhaseChanged, changed.append)
    run_until(scenes, game, "surface")
    health(game).current = 12
    scenes.update(STEP)
    assert state(game).phase == 2
    health(game).current = 6
    scenes.update(STEP)
    assert state(game).phase == 3
    assert [event.phase for event in changed] == [2, 3]


def test_a_breaching_back_takes_a_hit_from_above(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    health(game).current = 12
    light_lamps(game)
    run_until(scenes, game, "breach")
    before = health(game).current
    swing(scenes, game, above=True)
    assert health(game).current == before - 1


def drain(scenes: SceneManager, game: GameplayScene) -> None:
    """Phase 3 with the two lamps under the photocells lit.

    It goes for the nearer lamp, so the first is put out once its casing is broken, to send
    the Lamprey to the other (a flare thrown there would do the same), and relit at the end.
    """
    health(game).current = 6
    head = game.world.get(boss_of(game), Body).center_x
    ends = sorted(
        (abs(body.center_x - head), lamp)
        for _, body, lamp in game.world.query(Body, Lamp)
        if abs(body.center_x - head) > 150
    )
    near = [lamp for _, lamp in ends]
    assert len(near) == 2
    first = near[0]
    for lamp in near:
        lamp.lit = True
    for _ in range(round(90.0 / STEP)):
        broken = len(state(game).broken)
        if state(game).drained:
            return
        if broken == 1:
            first.lit = False
        elif broken == 2:
            for lamp in near:
                lamp.lit = True
        game.world.get(game.player, Health).invulnerable = 99.0
        scenes.update(STEP)
    raise AssertionError("never drained")


def test_lunges_break_the_casings_and_lit_photocells_drain_the_arena(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    drained: list[Drained] = []
    ctx.bus.subscribe(Drained, drained.append)
    drain(scenes, game)
    assert len(drained) == 1
    assert game.progress.data.flags[DRAINED] == 1
    assert len(state(game).broken) == 2
    scenes.update(STEP)
    scenes.update(STEP)
    (floor,) = (door for _, door in game.world.query(Door))
    assert not floor.open
    rect = game.rooms.graph.rects["Cistern_Lab"]
    column, row = (rect.x + 20 * 16) // 16, (rect.y + 18 * 16) // 16
    assert game.grid.get(column, row) == Tile.SOLID


def test_drained_it_is_hurt_only_in_its_gasps_and_dies_for_good(ctx: GameContext) -> None:
    save_slot(ctx.storage, ctx.slot, SaveSlot(room="Cistern_Lab"))
    scenes, game = start(ctx, from_slot=True)
    iid = game.world.get(boss_of(game), Identity).iid
    defeated: list[LampreyDefeated] = []
    ctx.bus.subscribe(LampreyDefeated, defeated.append)
    drain(scenes, game)
    health(game).current = 2
    run_until(scenes, game, "thrash")
    swing(scenes, game, above=False)
    assert health(game).current == 2
    run_until(scenes, game, "gasp")
    swing(scenes, game, above=False)
    assert health(game).current == 1
    run_until(scenes, game, "thrash")
    run_until(scenes, game, "gasp")
    swing(scenes, game, above=False)
    assert not list(game.world.query(Lamprey))
    assert len(defeated) == 1
    assert iid in game.progress.data.world.removed
    assert game.progress.data.flags[DEFEATED] == 1
    scenes.close()
    saved = load_slot(ctx.storage, ctx.slot)
    assert saved is not None
    assert iid in saved.world.removed
    assert (saved.flags[DEFEATED], saved.flags[DRAINED]) == (1, 1)

    _, again = start(ctx, from_slot=True)
    assert not list(again.world.query(Lamprey))
    (floor,) = (door for _, door in again.world.query(Door))
    assert not floor.open


def test_the_players_death_resets_the_fight(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    drain(scenes, game)
    health(game).current = 2
    game.world.get(game.player, Health).invulnerable = 0.0
    hurt(game.world, game.player, 99)
    for _ in range(game.feel.juice.respawn_delay + 30):
        scenes.update(STEP)
    assert health(game).current == game.feel.lamprey.hp
    assert (state(game).phase, state(game).drained) == (1, False)
    assert DRAINED not in game.progress.data.flags
    assert all(cell.sealed for _, cell in game.world.query(Photocell))
    (floor,) = (door for _, door in game.world.query(Door))
    assert floor.open


def test_it_draws_in_every_mode(ctx: GameContext, display: Display) -> None:
    scenes, game = start(ctx)
    boss = boss_of(game)
    for mode in ("swim", "warn", "surface", "lunge", "stunned", "breach", "gasp", "thrash"):
        game.world.get(boss, Lamprey).mode = mode
        scenes.update(STEP)
        game.draw(display.canvas, 1.0)
