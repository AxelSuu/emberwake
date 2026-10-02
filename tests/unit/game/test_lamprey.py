from __future__ import annotations

import emberwake.game.components  # noqa: F401
from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import EntityId, World
from emberwake.engine.physics import Body, Tile, TileGrid
from emberwake.engine.world.rooms import WorldGrid
from emberwake.engine.world.spawning import Identity, Spawner, WorldState
from emberwake.game.combat import Blocked, Guard, Health, Hitbox, Hurtbox, Team, combat_system
from emberwake.game.flags import Facts
from emberwake.game.flares import Flare
from emberwake.game.interact import Switch
from emberwake.game.lamprey import (
    DEFEATED,
    DRAINED,
    MODES,
    Bitten,
    Breached,
    CasingBroken,
    Ctx,
    Drained,
    Lamprey,
    LampreyDefeated,
    LampreyTuning,
    PhaseChanged,
    brightest,
    phase_for,
)
from emberwake.game.lamprey_system import lamprey_system
from emberwake.game.lamps import Lamp, LampSnuffed
from emberwake.game.light import LightSource, LightTuning
from emberwake.game.player.controller import Motor
from emberwake.game.switches import Photocell, photocell_system

STEP = 1 / 60
TILE = 16
WATER = 17 * TILE
"""Water line of the test arena, px."""
TUNING = LampreyTuning()


class Arena:
    """A 40x22 tile room, stone all round, with the water line at row 17."""

    def __init__(self, tuning: LampreyTuning = TUNING) -> None:
        self.tuning = tuning
        self.world = World()
        grid = TileGrid(40, 22, TILE, bytearray(40 * 22))
        for column in range(40):
            grid.set(column, 0, Tile.SOLID)
            grid.set(column, 21, Tile.SOLID)
        for row in range(22):
            grid.set(0, row, Tile.SOLID)
            grid.set(39, row, Tile.SOLID)
        self.grid = grid
        self.bus = EventBus()
        self.phases: list[PhaseChanged] = []
        self.bus.subscribe(PhaseChanged, self.phases.append)
        self.breached: list[Breached] = []
        self.bus.subscribe(Breached, self.breached.append)
        self.bitten: list[Bitten] = []
        self.bus.subscribe(Bitten, self.bitten.append)
        self.snuffed: list[LampSnuffed] = []
        self.bus.subscribe(LampSnuffed, self.snuffed.append)
        self.blocked: list[Blocked] = []
        self.bus.subscribe(Blocked, self.blocked.append)
        self.facts = Facts({}, [], {})
        for resource in (tuning, LightTuning(), self.bus, self.facts):
            self.world.insert_resource(resource)
        self.world.insert_resource(grid, key=WorldGrid)
        self.boss = self.world.spawn(Body(18 * TILE, WATER - 16, 32, 16), Lamprey())
        self.world.flush()
        self.player = self.world.spawn(Body(3 * TILE, WATER - 36, 10, 20), Motor(), Health(3))
        self.world.flush()
        self.tick()

    def tick(self, seconds: float = STEP) -> None:
        for _ in range(max(1, round(seconds / STEP))):
            lamprey_system(self.world, STEP)
            combat_system(self.world, STEP)
            photocell_system(self.world, STEP)
            self.world.flush()

    def ctx(self) -> Ctx:
        return Ctx(
            self.world,
            self.boss,
            self.world.get(self.boss, Body),
            self.state,
            self.tuning,
            self.world.resource(WorldGrid),
            self.world.get(self.player, Body),
        )

    @property
    def state(self) -> Lamprey:
        return self.world.get(self.boss, Lamprey)

    @property
    def health(self) -> Health:
        return self.world.get(self.boss, Health)

    def run_until(self, mode: str, seconds: float = 10.0) -> None:
        """Tick until the Lamprey is in `mode`."""
        for _ in range(round(seconds / STEP)):
            if self.state.mode == mode:
                return
            self.tick()
        raise AssertionError(f"never reached {mode}, last in {self.state.mode}")

    def modes(self, seconds: float) -> list[str]:
        """The modes it passes through, each once in a row."""
        seen: list[str] = []
        for _ in range(round(seconds / STEP)):
            self.tick()
            if not seen or seen[-1] != self.state.mode:
                seen.append(self.state.mode)
        return seen

    def strike(self, *, above: bool = False) -> None:
        """A one-tick hit on the head, from the side or from above."""
        head = self.world.get(self.boss, Body)
        x = head.center_x - 5 if above else head.x - 6
        y = head.y - 30 if above else head.bottom - 20
        box = Hitbox(targets=Team.ENEMY, size=(10, 40 if above else 20), active=True)
        attacker = self.world.spawn(Body(x, y, 10, 20), box)
        self.world.flush()
        combat_system(self.world, STEP)
        self.world.despawn(attacker)
        self.world.flush()

    def lamp(self, x: float, *, lit: bool = True, protected: bool = False) -> EntityId:
        eid = self.world.spawn(
            Body(x - 8, WATER - 80, 16, 32),
            Lamp(lit=lit, protected=protected),
            Identity(f"lamp-{x}", "Arena", "lamp"),
        )
        if lit:
            self.world.add(eid, LightSource(radius=80.0))
        self.world.flush()
        return eid

    def photocell(self, x: float, *, sealed: bool = True) -> EntityId:
        """A photocell 40 px above a lamp's centre, where a lunge up at the lamp passes."""
        eid = self.world.spawn(
            Body(x - 8, WATER - 112, 16, 16),
            Photocell(sealed=sealed),
            Switch(),
            Identity(f"cell-{x}-{sealed}", "Arena", "photocell"),
        )
        self.world.flush()
        return eid

    def flare(self, x: float, y: float, strength: float = 1.0) -> EntityId:
        eid = self.world.spawn(Body(x - 3, y - 3, 6, 6), Flare(), LightSource(strength=strength))
        self.world.flush()
        return eid


def test_it_is_equipped_on_its_first_tick_and_starts_submerged() -> None:
    arena = Arena()
    assert arena.health.current == arena.health.max == TUNING.hp
    assert arena.world.get(arena.boss, Hurtbox).team == Team.NONE
    assert arena.world.get(arena.boss, Guard).active
    box = arena.world.get(arena.boss, Hitbox)
    assert (box.targets, box.active) == (Team.PLAYER, False)
    body = arena.world.get(arena.boss, Body)
    assert body.y + body.height / 2 == arena.state.home[1] + TUNING.depth
    assert arena.state.home == (18 * TILE + 16, WATER - 8)


def test_phases_are_thirds_of_its_health() -> None:
    assert [phase_for(hp, 18) for hp in (18, 13, 12, 7, 6, 1)] == [1, 1, 2, 2, 3, 3]


def test_the_phase_follows_its_health_and_never_goes_back() -> None:
    arena = Arena()
    arena.health.current = 12
    arena.tick()
    assert arena.state.phase == 2
    arena.health.current = 18
    arena.tick()
    assert arena.state.phase == 2
    arena.health.current = 5
    arena.tick()
    assert arena.state.phase == 3
    assert [event.phase for event in arena.phases] == [2, 3]


def test_it_sleeps_while_the_player_is_outside_its_arena() -> None:
    arena = Arena()
    arena.state.arena = (0.0, 0.0, 100.0, 100.0)
    arena.health.current = 5
    arena.tick()
    assert not arena.state.awake
    assert arena.state.phase == 1


def test_every_mode_sets_the_hurt_box_hit_box_and_armor() -> None:
    arena = Arena()
    arena.state.tree = None
    boss = arena.boss
    expected = {
        "swim": (Team.NONE, False, True, True),
        "surface": (Team.ENEMY, True, True, True),
        "breach": (Team.ENEMY, True, True, False),
        "stunned": (Team.ENEMY, False, False, False),
        "dazed": (Team.ENEMY, False, True, True),
    }
    for mode, (team, contact, armor, top) in expected.items():
        arena.state.mode = mode
        arena.tick()
        assert arena.world.get(boss, Hurtbox).team == team, mode
        assert arena.world.get(boss, Hitbox).active == contact, mode
        guard = arena.world.get(boss, Guard)
        assert (guard.active, guard.top) == (armor, top), mode
    assert set(expected) <= set(MODES)


def test_it_aims_at_the_brightest_light_flare_over_lamp_over_lantern() -> None:
    arena = Arena()
    arena.world.get(arena.player, Body).x = 5 * TILE
    ctx = arena.ctx()
    player = arena.world.get(arena.player, Body)
    assert brightest(ctx) == (player.center_x, player.y + player.height / 2)
    arena.lamp(300)
    assert brightest(ctx) == (300, WATER - 64)
    arena.flare(500, WATER - 100)
    assert brightest(ctx) == (500, WATER - 100)


def test_a_fading_flare_loses_to_a_lamp_and_an_unlit_lamp_is_no_bait() -> None:
    arena = Arena()
    arena.lamp(200, lit=False)
    arena.lamp(400)
    arena.flare(500, WATER - 100, strength=0.5)
    assert brightest(arena.ctx()) == (400, WATER - 64)


def test_equals_go_to_the_nearest() -> None:
    arena = Arena()
    arena.lamp(100)
    arena.lamp(330)
    arena.lamp(600)
    assert brightest(arena.ctx()) == (330, WATER - 64)


def test_bait_outside_the_arena_is_ignored() -> None:
    arena = Arena()
    arena.state.arena = (0.0, 0.0, 320.0, 352.0)
    arena.lamp(500)
    ctx = arena.ctx()
    player = arena.world.get(arena.player, Body)
    assert brightest(ctx) == (player.center_x, player.y + player.height / 2)


def test_it_comes_up_under_the_light_lunges_into_stone_and_is_stunned() -> None:
    arena = Arena()
    arena.lamp(500)
    arena.run_until("surface")
    head = arena.world.get(arena.boss, Body)
    assert head.center_x == 500
    assert head.y + head.height == WATER
    arena.run_until("lunge")
    arena.run_until("stunned")
    assert arena.state.bit
    assert len(arena.bitten) == 1
    assert head.y < 2 * TILE
    assert arena.world.get(arena.boss, Hurtbox).team == Team.ENEMY
    assert not arena.world.get(arena.boss, Guard).active
    assert not arena.world.get(arena.boss, Hitbox).active


def test_a_lunge_at_a_flare_by_a_wall_bites_the_wall() -> None:
    arena = Arena()
    arena.world.get(arena.player, Body).x = 30 * TILE
    arena.flare(2 * TILE, WATER - 120)
    arena.run_until("stunned")
    head = arena.world.get(arena.boss, Body)
    assert head.center_x == 2 * TILE


def test_a_lunge_that_reaches_nothing_ends_in_the_air() -> None:
    arena = Arena(LampreyTuning(lunge_range=100.0))
    arena.lamp(500)
    arena.run_until("lunge")
    arena.run_until("recover")
    assert not arena.state.bit
    assert not arena.bitten
    assert arena.world.get(arena.boss, Guard).active


def test_the_cycle_is_emerge_stalk_lunge_stun_dive_rest_and_again() -> None:
    arena = Arena()
    arena.lamp(500)
    modes = arena.modes(14.0)
    assert modes[:6] == ["swim", "surface", "lunge", "stunned", "recover", "swim"]
    assert modes[6:8] == ["surface", "lunge"]


def test_a_stunned_head_takes_hits_and_a_surfaced_one_clangs() -> None:
    arena = Arena()
    arena.lamp(500)
    arena.run_until("surface")
    arena.strike()
    assert arena.health.current == TUNING.hp
    assert arena.blocked
    arena.run_until("stunned")
    arena.strike()
    assert arena.health.current == TUNING.hp - 1


def test_a_submerged_head_cannot_be_hit() -> None:
    arena = Arena()
    arena.lamp(500)
    assert arena.state.mode == "swim"
    arena.strike()
    arena.strike(above=True)
    assert arena.health.current == TUNING.hp
    assert not arena.blocked


def test_it_hurts_the_player_it_lunges_at() -> None:
    arena = Arena()
    player = arena.world.get(arena.player, Body)
    player.x = 600
    player.y = WATER - 40
    arena.world.add(arena.player, Hurtbox(Team.PLAYER))
    arena.world.flush()
    arena.run_until("lunge")
    for _ in range(40):
        arena.tick()
    assert arena.world.get(arena.player, Health).current == 2


def test_the_same_lights_give_the_same_fight() -> None:
    def fight() -> tuple[list[str], tuple[float, float]]:
        arena = Arena()
        arena.lamp(500)
        arena.flare(200, WATER - 90)
        modes = arena.modes(20.0)
        head = arena.world.get(arena.boss, Body)
        return modes, (head.x, head.y)

    assert fight() == fight()


def test_a_phase_change_aborts_the_running_step() -> None:
    arena = Arena()
    arena.lamp(500)
    arena.run_until("lunge")
    arena.health.current = 12
    arena.tick()
    assert arena.state.phase == 2
    tree = arena.state.tree
    assert tree is not None
    assert tree.root.children[1].running
    assert not tree.root.children[2].running


def second_phase(arena: Arena) -> None:
    arena.health.current = 12
    arena.tick()
    assert arena.state.phase == 2


def test_phase_two_swims_warns_leaps_and_rests() -> None:
    arena = Arena()
    arena.lamp(500)
    second_phase(arena)
    modes = arena.modes(8.0)
    assert modes[:5] == ["swim", "warn", "swim", "breach", "swim"]
    assert len(arena.breached) >= 2


def test_a_breach_peaks_at_the_lamp_and_snuffs_it() -> None:
    arena = Arena()
    lamp = arena.lamp(500)
    second_phase(arena)
    head = arena.world.get(arena.boss, Body)
    arena.run_until("breach")
    top = (head.center_x, head.y + head.height / 2)
    while arena.state.mode == "breach":
        arena.tick()
        top = min(top, (head.center_x, head.y + head.height / 2), key=lambda p: p[1])
    assert abs(top[0] - 500) < 12
    assert abs(top[1] - (WATER - 64)) < 4
    assert not arena.world.get(lamp, Lamp).lit
    assert len(arena.snuffed) == 1


def test_a_protected_or_dark_lamp_is_left_alone_and_the_player_is_the_quarry() -> None:
    arena = Arena()
    held = arena.lamp(500, protected=True)
    arena.lamp(700, lit=False)
    player = arena.world.get(arena.player, Body)
    player.x = 200
    second_phase(arena)
    arena.run_until("breach")
    arena.tick(0.7)
    head = arena.world.get(arena.boss, Body)
    assert abs(head.center_x - player.center_x) < 100
    arena.run_until("swim")
    assert arena.world.get(held, Lamp).lit
    assert not arena.snuffed


def test_the_breaches_alternate_sides() -> None:
    arena = Arena()
    lamp = arena.lamp(500)
    second_phase(arena)
    starts = []
    for _ in range(2):
        arena.run_until("warn")
        starts.append(arena.world.get(arena.boss, Body).center_x)
        arena.run_until("breach")
        arena.run_until("swim")
        arena.world.get(lamp, Lamp).lit = True
    assert starts[0] != starts[1]
    assert starts[0] + starts[1] == 1000


def test_a_breaching_back_is_open_from_above_only() -> None:
    arena = Arena()
    arena.lamp(500)
    second_phase(arena)
    arena.run_until("breach")
    arena.strike()
    assert arena.health.current == 12
    assert arena.blocked
    arena.strike(above=True)
    assert arena.health.current == 11


def third_phase(arena: Arena) -> None:
    arena.health.current = 6
    arena.tick()
    assert arena.state.phase == 3


def drained_arena() -> tuple[Arena, list[EntityId]]:
    arena = Arena()
    arena.lamp(300)
    arena.lamp(600)
    cells = [arena.photocell(300), arena.photocell(600)]
    third_phase(arena)
    return arena, cells


def test_the_lure_goes_out_in_phase_three() -> None:
    arena = Arena()
    arena.world.add(arena.boss, LightSource())
    arena.world.flush()
    arena.tick()
    assert arena.world.get(arena.boss, LightSource).strength == 0.5
    third_phase(arena)
    assert arena.world.get(arena.boss, LightSource).strength == 0.0


def test_a_sealed_photocell_reads_dark_beside_a_lit_lamp() -> None:
    arena = Arena()
    arena.lamp(300)
    sealed, open_ = arena.photocell(300), arena.photocell(300, sealed=False)
    arena.tick()
    assert not arena.world.get(sealed, Switch).on
    assert arena.world.get(open_, Switch).on


def test_a_stunned_phase_three_head_keeps_its_armor_while_flooded() -> None:
    arena, _ = drained_arena()
    arena.run_until("dazed")
    arena.strike()
    assert arena.health.current == 6
    assert arena.blocked
    assert not arena.world.get(arena.boss, Hitbox).active


def test_a_lunge_through_a_sealed_photocell_breaks_its_casing() -> None:
    arena = Arena()
    arena.lamp(500)
    cell = arena.photocell(500)
    arena.photocell(800)
    broken: list[CasingBroken] = []
    arena.bus.subscribe(CasingBroken, broken.append)
    third_phase(arena)
    arena.run_until("lunge")
    assert arena.world.get(cell, Photocell).sealed
    arena.run_until("dazed")
    assert not arena.world.get(cell, Photocell).sealed
    assert arena.state.broken == [cell]
    assert len(broken) == 1


def test_the_arena_drains_once_every_casing_is_broken_and_lit() -> None:
    arena, cells = drained_arena()
    drained: list[Drained] = []
    arena.bus.subscribe(Drained, drained.append)
    arena.run_until("dazed")
    assert not arena.state.drained
    assert sum(not arena.world.get(c, Photocell).sealed for c in cells) == 1
    arena.world.get(cells[1], Photocell).sealed = False
    arena.tick(0.1)
    assert arena.state.drained
    assert arena.facts.flags[DRAINED] == 1
    assert len(drained) == 1
    head = arena.world.get(arena.boss, Body)
    assert head.y + head.height / 2 == arena.state.home[1]


def test_a_broken_casing_in_the_dark_does_not_drain_it() -> None:
    arena, cells = drained_arena()
    for cell in cells:
        arena.world.get(cell, Photocell).sealed = False
    for eid, lamp in list(arena.world.query(Lamp)):
        lamp.lit = False
        arena.world.remove(eid, LightSource)
    arena.world.flush()
    arena.tick(0.5)
    assert not arena.state.drained
    assert DRAINED not in arena.facts.flags


def test_drained_it_thrashes_at_the_player_then_gasps_open() -> None:
    arena, cells = drained_arena()
    for cell in cells:
        arena.world.get(cell, Photocell).sealed = False
    arena.tick(0.1)
    assert arena.state.drained
    arena.run_until("thrash")
    arena.strike()
    assert arena.health.current == 6
    assert arena.world.get(arena.boss, Hitbox).active
    head, player = arena.world.get(arena.boss, Body), arena.world.get(arena.player, Body)
    x = head.center_x
    arena.tick(0.5)
    assert abs(head.center_x - player.center_x) < abs(x - player.center_x)
    arena.run_until("gasp")
    assert not arena.world.get(arena.boss, Hitbox).active
    arena.strike()
    assert arena.health.current == 5
    assert arena.modes(5.0)[:3] == ["gasp", "thrash", "gasp"]


def test_an_arena_without_casings_drains_as_phase_three_begins() -> None:
    arena = Arena()
    third_phase(arena)
    assert arena.state.drained


def test_a_stale_drained_flag_is_cleared_when_it_spawns() -> None:
    world = World()
    facts = Facts({DRAINED: 1}, [], {})
    for resource in (TUNING, LightTuning(), EventBus(), facts):
        world.insert_resource(resource)
    world.insert_resource(TileGrid(4, 4, TILE, bytearray(16)), key=WorldGrid)
    world.spawn(Body(0, 0, 32, 16), Lamprey())
    world.flush()
    lamprey_system(world, STEP)
    assert DRAINED not in facts.flags


def test_killing_it_retires_it_by_iid_and_sets_the_flags() -> None:
    arena = Arena()
    state = WorldState()
    arena.world.insert_resource(Spawner(arena.world, {}, state))
    arena.world.add(arena.boss, Identity("the-lamprey", "Arena", "lamprey"))
    arena.world.flush()
    defeated: list[LampreyDefeated] = []
    arena.bus.subscribe(LampreyDefeated, defeated.append)
    arena.health.current, arena.health.dead = 0, True
    arena.tick()
    assert state.removed == ["the-lamprey"]
    assert arena.boss not in arena.world
    assert (arena.facts.flags[DEFEATED], arena.facts.flags[DRAINED]) == (1, 1)
    assert len(defeated) == 1


def test_a_dead_player_starts_the_fight_over() -> None:
    arena, cells = drained_arena()
    arena.world.get(arena.boss, Lamprey).side = -1
    for cell in cells:
        arena.world.get(cell, Photocell).sealed = False
    arena.state.broken.extend(cells)
    arena.tick(0.1)
    assert arena.state.drained
    arena.health.current = 2
    arena.world.get(arena.player, Health).dead = True
    arena.tick()
    state = arena.state
    assert (arena.health.current, state.phase, state.drained) == (TUNING.hp, 1, False)
    assert all(arena.world.get(cell, Photocell).sealed for cell in cells)
    assert not state.broken
    assert DRAINED not in arena.facts.flags
    assert state.mode == "swim"
    head = arena.world.get(arena.boss, Body)
    assert head.y + head.height / 2 == state.home[1] + TUNING.depth


def test_a_hazard_that_only_cost_a_pip_does_not_reset_it() -> None:
    arena = Arena()
    arena.health.current = 10
    arena.world.get(arena.player, Motor).dead = True
    arena.tick()
    assert arena.health.current == 10


def test_after_a_reset_the_phases_are_walked_again() -> None:
    arena = Arena()
    arena.health.current = 5
    arena.tick()
    arena.world.get(arena.player, Health).dead = True
    arena.tick()
    arena.world.get(arena.player, Health).dead = False
    arena.health.current = 12
    arena.tick()
    assert arena.state.phase == 2
    assert [event.phase for event in arena.phases] == [3, 2]
