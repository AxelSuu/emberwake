from __future__ import annotations

import emberwake.game.components  # noqa: F401
from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import EntityId, World
from emberwake.engine.physics import Body, Tile, TileGrid
from emberwake.engine.world.rooms import WorldGrid
from emberwake.engine.world.spawning import Identity
from emberwake.game.beacons import Beacon
from emberwake.game.combat import (
    Blocked,
    Damaged,
    Guard,
    Health,
    Hitbox,
    Hurtbox,
    Killed,
    Knockback,
    Team,
    combat_system,
)
from emberwake.game.enemies import (
    Brain,
    Court,
    EnemyTuning,
    RatSpawn,
    Summoned,
    Toppled,
    Vented,
    enemy_system,
)
from emberwake.game.light import LightSource, LightTuning, light_at
from emberwake.game.player.controller import Motor

STEP = 1 / 60
FLOOR = 9
TUNING = EnemyTuning()


class Yard:
    """A 30x10 tile room with a floor, and whatever the test puts in it."""

    def __init__(self, walls: tuple[int, ...] = ()) -> None:
        self.world = World()
        grid = TileGrid(30, 10, 16, bytearray(300))
        for column in range(30):
            grid.set(column, FLOOR, Tile.SOLID)
        for column in walls:
            for row in range(FLOOR):
                grid.set(column, row, Tile.SOLID)
        self.grid = grid
        self.bus = EventBus()
        self.damaged: list[Damaged] = []
        self.killed: list[Killed] = []
        self.bus.subscribe(Damaged, self.damaged.append)
        self.bus.subscribe(Killed, self.killed.append)
        self.vented: list[Vented] = []
        self.bus.subscribe(Vented, self.vented.append)
        for resource in (TUNING, LightTuning(), self.bus):
            self.world.insert_resource(resource)
        self.world.insert_resource(grid, key=WorldGrid)

    def enemy(self, kind: str, x: float, y: float | None = None, facing: int = 1) -> EntityId:
        y = FLOOR * 16 - 16 if y is None else y
        eid = self.world.spawn(Body(x, y, 16, 16), Brain(kind, facing=facing))
        self.world.flush()
        return eid

    def player(self, x: float, y: float = FLOOR * 16 - 20) -> EntityId:
        eid = self.world.spawn(Body(x, y, 10, 20), Motor())
        self.world.flush()
        return eid

    def tick(self, seconds: float = STEP) -> None:
        for _ in range(max(1, round(seconds / STEP))):
            enemy_system(self.world, STEP)
            self.world.flush()

    def brain(self, eid: EntityId) -> Brain:
        return self.world.get(eid, Brain)

    def body(self, eid: EntityId) -> Body:
        return self.world.get(eid, Body)


def test_an_enemy_is_equipped_on_its_first_tick() -> None:
    yard = Yard()
    rat = yard.enemy("clockrat", 100)
    yard.tick()
    assert yard.world.get(rat, Health).current == TUNING.clockrat_hp
    box = yard.world.get(rat, Hitbox)
    assert (box.targets, box.active) == (Team.PLAYER, True)
    assert yard.brain(rat).state == "patrol"


def test_clockrat_patrols_and_turns_at_a_wall() -> None:
    yard = Yard(walls=(10,))
    rat = yard.enemy("clockrat", 100, facing=1)
    start = yard.body(rat).x
    yard.tick(1.0)
    assert yard.body(rat).x > start
    for _ in range(3):
        yard.tick(1.0)
    assert yard.brain(rat).facing == -1
    assert yard.body(rat).x < 10 * 16


def test_clockrat_turns_at_a_ledge() -> None:
    yard = Yard()
    for column in range(8, 12):
        yard.grid.set(column, FLOOR, Tile.EMPTY)
    rat = yard.enemy("clockrat", 100, facing=1)
    yard.tick(3.0)
    assert yard.brain(rat).facing == -1
    assert yard.body(rat).y == FLOOR * 16 - 16


def test_clockrat_charges_when_it_sees_the_player_then_rests() -> None:
    yard = Yard()
    rat = yard.enemy("clockrat", 100, facing=1)
    yard.player(160)
    yard.tick()
    yard.tick()
    assert yard.brain(rat).state == "charge"
    before = yard.body(rat).x
    yard.tick(0.2)
    assert yard.body(rat).x - before > TUNING.clockrat_charge_speed * 0.15
    yard.tick(TUNING.clockrat_charge_time)
    assert yard.brain(rat).state in ("rest", "patrol", "charge")
    yard.tick(TUNING.clockrat_rest_time + 0.1)


def test_clockrat_ignores_a_player_behind_it() -> None:
    yard = Yard()
    rat = yard.enemy("clockrat", 100, facing=1)
    yard.player(40)
    yard.tick(0.1)
    assert yard.brain(rat).state == "patrol"


def test_contact_hurts_the_player_once_then_iframes_protect() -> None:
    yard = Yard()
    yard.enemy("clockrat", 100)
    player = yard.player(104)
    yard.world.add(player, Health(3, iframes=1.0), Hurtbox(Team.PLAYER))
    yard.world.flush()
    for _ in range(30):
        enemy_system(yard.world, STEP)
        yard.world.flush()
        combat_system(yard.world, STEP)
        yard.world.flush()
    assert yard.world.get(player, Health).current == 2
    assert len([d for d in yard.damaged if d.target == player]) == 1


def test_gloomcrawler_burns_in_light_and_dies() -> None:
    yard = Yard(walls=(12,))
    crawler = yard.enemy("gloomcrawler", 100)
    yard.world.spawn(Body(0, 100, 16, 16), LightSource(radius=400))
    yard.world.flush()
    yard.tick(0.1)
    assert yard.world.get(crawler, Health).current == TUNING.gloom_hp
    yard.tick(TUNING.gloom_hp / TUNING.gloom_burn_rate + 1.0)
    assert [k.target for k in yard.killed] == [crawler]
    assert not [e for e, _ in yard.world.query(Brain)]


def test_gloomcrawler_is_unharmed_in_the_dark() -> None:
    yard = Yard()
    crawler = yard.enemy("gloomcrawler", 100)
    yard.tick(5.0)
    assert yard.world.get(crawler, Health).current == TUNING.gloom_hp
    assert not yard.damaged


def test_gloomcrawler_flees_light_and_returns_to_creeping() -> None:
    yard = Yard()
    crawler = yard.enemy("gloomcrawler", 140)
    lamp = yard.world.spawn(Body(120, 120, 16, 16), LightSource(radius=80))
    yard.world.flush()
    yard.tick(0.1)
    assert yard.brain(crawler).state == "flee"
    start = yard.body(crawler).x
    yard.tick(0.5)
    assert yard.body(crawler).x > start
    yard.world.despawn(lamp)
    yard.world.flush()
    yard.tick(0.5)
    assert yard.brain(crawler).state == "creep"


def test_gloomcrawler_creeps_toward_the_player() -> None:
    yard = Yard()
    crawler = yard.enemy("gloomcrawler", 100, facing=-1)
    yard.player(200)
    yard.tick(1.0)
    assert yard.brain(crawler).facing == 1
    assert yard.body(crawler).x > 100


def test_wisp_eater_drifts_toward_light() -> None:
    yard = Yard()
    wisp = yard.enemy("wisp_eater", 100, y=40)
    yard.world.spawn(Body(180, 60, 16, 16), Beacon(lit=True))
    yard.world.flush()
    yard.tick(0.1)
    start = yard.body(wisp).x
    yard.tick(1.0)
    assert yard.body(wisp).x > start


def test_wisp_eater_swoops_then_retreats_home() -> None:
    yard = Yard()
    wisp = yard.enemy("wisp_eater", 100, y=60)
    yard.player(140, 100)
    yard.tick(0.1)
    assert yard.brain(wisp).state == "swoop"
    yard.tick(TUNING.wisp_swoop_time + 0.1)
    assert yard.brain(wisp).state == "retreat"
    home = yard.brain(wisp).home

    def away() -> float:
        body = yard.body(wisp)
        return abs(body.center_x - home[0]) + abs(body.y + 8 - home[1])

    far = away()
    yard.tick(0.5)
    assert away() < far


def test_dead_enemies_are_removed() -> None:
    yard = Yard()
    rat = yard.enemy("clockrat", 100)
    yard.tick()
    yard.world.get(rat, Health).dead = True
    yard.tick()
    assert not [e for e, _ in yard.world.query(Brain)]


def test_sprites_show_their_brain_state_and_how_long() -> None:
    from emberwake.game.components import Sprite  # noqa: PLC0415
    from emberwake.game.render.sprites import sprite_system  # noqa: PLC0415

    yard = Yard()
    rat = yard.enemy("clockrat", 64)
    yard.world.add(rat, Sprite("clockrat"))
    yard.tick()
    sprite_system(yard.world, STEP)
    sprite_system(yard.world, STEP)
    sprite = yard.world.get(rat, Sprite)
    assert sprite.state == "patrol"
    assert sprite.since == STEP


LURKER_Y = 20
"""Where a test lurker hangs; its bottom is 36 and a player on the floor is 88 px below."""


def lurker(yard: Yard, x: float = 100, y: float = LURKER_Y) -> EntityId:
    eid = yard.enemy("drip_lurker", x, y)
    yard.tick()
    return eid


def test_a_lurker_drops_on_a_player_below_in_the_dark_then_climbs_home() -> None:
    yard = Yard()
    bug = lurker(yard)
    yard.player(103)
    yard.tick(TUNING.lurker_rest + 0.1)
    assert yard.brain(bug).state == "warn"
    assert yard.body(bug).y == LURKER_Y
    yard.tick(TUNING.lurker_warn)
    assert yard.brain(bug).state == "drop"
    yard.tick(1.0)
    assert yard.brain(bug).state == "ground"
    assert yard.body(bug).bottom == FLOOR * 16
    yard.tick(TUNING.lurker_ground_time)
    assert yard.brain(bug).state == "climb"
    yard.tick(2.0)
    assert yard.brain(bug).state == "ceiling"
    assert (yard.body(bug).x, yard.body(bug).y) == (100, LURKER_Y)


def test_a_lurker_ignores_a_player_off_to_the_side_or_behind_a_ledge() -> None:
    yard = Yard()
    bug = lurker(yard)
    far = yard.player(160)
    yard.tick(2.0)
    assert yard.brain(bug).state == "ceiling"
    yard.world.get(far, Body).x = 103
    for column in range(5, 9):
        yard.grid.set(column, 5, Tile.ONE_WAY)
    yard.tick(2.0)
    assert yard.brain(bug).state == "ceiling"


def test_a_lurker_stays_up_and_tucked_while_its_spot_is_lit() -> None:
    yard = Yard()
    bug = lurker(yard)
    yard.player(103)
    yard.world.spawn(Body(100, 30, 16, 16), LightSource(radius=80))
    yard.world.flush()
    yard.tick(TUNING.lurker_rest + TUNING.lurker_warn + 0.5)
    assert yard.brain(bug).state == "retract"
    assert yard.body(bug).y == LURKER_Y
    assert not yard.world.get(bug, Hitbox).active
    assert yard.world.get(bug, Guard) == Guard(0, True)


def test_a_lurker_comes_out_again_when_the_light_goes() -> None:
    yard = Yard()
    bug = lurker(yard)
    lamp = yard.world.spawn(Body(100, 30, 16, 16), LightSource(radius=80))
    yard.world.flush()
    yard.tick(0.1)
    assert yard.brain(bug).state == "retract"
    yard.world.despawn(lamp)
    yard.world.flush()
    yard.tick(0.1)
    assert yard.brain(bug).state == "ceiling"
    assert yard.world.get(bug, Hitbox).active
    assert not yard.world.get(bug, Guard).active


def test_light_cancels_a_warning() -> None:
    yard = Yard()
    bug = lurker(yard)
    yard.player(103)
    yard.tick(TUNING.lurker_rest + 0.2)
    assert yard.brain(bug).state == "warn"
    yard.world.spawn(Body(100, 30, 16, 16), LightSource(radius=80))
    yard.world.flush()
    yard.tick(0.1)
    assert yard.brain(bug).state == "retract"
    assert yard.body(bug).y == LURKER_Y


def test_light_sends_a_lurker_on_the_ground_back_up() -> None:
    yard = Yard()
    bug = lurker(yard)
    yard.player(103)
    yard.tick(TUNING.lurker_rest + TUNING.lurker_warn + 1.0)
    assert yard.brain(bug).state == "ground"
    yard.world.spawn(Body(100, 100, 16, 16), LightSource(radius=120))
    yard.world.flush()
    yard.tick(0.1)
    assert yard.brain(bug).state == "climb"


def test_the_players_own_lantern_does_not_scare_a_lurker() -> None:
    yard = Yard()
    bug = lurker(yard, y=90)
    yard.player(103)
    assert light_at(yard.world, 108, 98) >= LightTuning().lit_threshold
    assert light_at(yard.world, 108, 98, lantern=False) == 0
    yard.tick(TUNING.lurker_rest + TUNING.lurker_warn + 0.2)
    assert yard.brain(bug).state in ("drop", "ground")


def test_a_hit_on_a_hanging_lurker_makes_it_drop_without_a_knock() -> None:
    yard = Yard()
    bug = lurker(yard)
    yard.world.add(bug, Knockback(120, -50))
    yard.world.flush()
    yard.tick()
    assert yard.brain(bug).state == "drop"
    assert yard.body(bug).x == 100
    assert yard.brain(bug).stagger == 0


def test_a_lurker_hurts_by_contact_as_it_falls() -> None:
    yard = Yard()
    lurker(yard)
    player = yard.player(103)
    yard.world.add(player, Health(3, iframes=1.0), Hurtbox(Team.PLAYER))
    yard.world.flush()
    for _ in range(150):
        enemy_system(yard.world, STEP)
        yard.world.flush()
        combat_system(yard.world, STEP)
        yard.world.flush()
    assert yard.world.get(player, Health).current == 2


def test_the_gearbug_walks_hisses_vents_and_walks_again() -> None:
    yard = Yard()
    bug = yard.enemy("gearbug", 100, facing=1)
    yard.tick()
    start = yard.body(bug).x
    yard.tick(TUNING.gearbug_cycle - 0.2)
    assert yard.brain(bug).state == "patrol"
    assert yard.body(bug).x > start + 10
    assert yard.world.get(bug, Guard) == Guard(1, True)
    yard.tick(0.4)
    assert yard.brain(bug).state == "hiss"
    stopped = yard.body(bug).x
    yard.tick(TUNING.gearbug_hiss)
    assert yard.brain(bug).state == "vent"
    assert len(yard.vented) == 1
    assert not yard.world.get(bug, Guard).active
    yard.tick(TUNING.gearbug_vent)
    assert yard.brain(bug).state == "patrol"
    assert yard.body(bug).x - stopped < 3
    assert yard.world.get(bug, Guard).active


def test_the_gearbug_guards_the_side_it_faces_and_turns_at_walls() -> None:
    yard = Yard(walls=(10,))
    bug = yard.enemy("gearbug", 100, facing=1)
    yard.tick(TUNING.gearbug_cycle - 0.2)
    assert yard.brain(bug).facing == -1
    assert yard.world.get(bug, Guard).facing == -1


def swing_at(yard: Yard, bug: EntityId, from_side: int) -> int:
    """Hit the bug from the left (-1) or right (1) with a player hitbox; returns its health."""
    target = yard.body(bug)
    owner = yard.world.spawn(Body(target.center_x + from_side * 18 - 5, target.y - 4, 10, 20))
    box = Hitbox(offset=(-6, 2), size=(22, 14), targets=Team.ENEMY, flip=from_side > 0)
    box.activate()
    yard.world.add(owner, box)
    yard.world.flush()
    combat_system(yard.world, STEP)
    yard.world.flush()
    return yard.world.get(bug, Health).current


def test_a_gearbug_shrugs_off_swings_at_its_front_but_not_from_behind() -> None:
    yard = Yard()
    blocked: list[Blocked] = []
    yard.bus.subscribe(Blocked, blocked.append)
    bug = yard.enemy("gearbug", 100, facing=-1)
    yard.tick(0.1)
    assert swing_at(yard, bug, -1) == TUNING.gearbug_hp
    assert len(blocked) == 1
    assert not yard.world.has(bug, Knockback)
    assert swing_at(yard, bug, 1) == TUNING.gearbug_hp - 1


def test_a_venting_gearbug_is_open_to_swings_from_the_front() -> None:
    yard = Yard()
    bug = yard.enemy("gearbug", 100, facing=-1)
    yard.tick(TUNING.gearbug_cycle + TUNING.gearbug_hiss + 0.1)
    assert yard.brain(bug).state == "vent"
    assert swing_at(yard, bug, -1) == TUNING.gearbug_hp - 1


def test_open_enemies_draw_their_active_sprite() -> None:
    from emberwake.game.components import Sprite  # noqa: PLC0415
    from emberwake.game.render.sprites import sprite_system  # noqa: PLC0415

    yard = Yard()
    bug = yard.enemy("gearbug", 100)
    yard.world.add(bug, Sprite("gearbug", "gearbug_open"))
    yard.tick()
    sprite_system(yard.world, STEP)
    assert yard.world.get(bug, Sprite).current == "gearbug"
    yard.tick(TUNING.gearbug_cycle + TUNING.gearbug_hiss + 0.1)
    sprite_system(yard.world, STEP)
    assert yard.world.get(bug, Sprite).current == "gearbug_open"


KING_Y = FLOOR * 16 - 32


def king(yard: Yard, x: float = 200, facing: int = 1, iid: str | None = None) -> EntityId:
    eid = yard.world.spawn(
        Body(x, KING_Y, 32, 32), Brain("clockrat_king", facing=facing), LightSource(88.0)
    )
    if iid is not None:
        yard.world.add(eid, Identity(iid, "Room", "clockrat_king"))
    yard.world.flush()
    yard.tick(2 * STEP)
    return eid


def marker(yard: Yard, x: float) -> None:
    yard.world.spawn(
        Body(x, FLOOR * 16 - 16, 16, 16), RatSpawn(), Identity(f"marker-{x}", "Room", "rat_spawn")
    )
    yard.world.flush()


def hit_king(yard: Yard, boss: EntityId, *, above: bool = False, side: int = 1) -> None:
    """One swing at the King from `side`, from over its crown if `above`."""
    target = yard.body(boss)
    y = target.y - 14 if above else target.y + 12
    owner = yard.world.spawn(Body(target.center_x + side * 22 - 5, y, 10, 20))
    box = Hitbox(offset=(-6, 18 if above else 2), size=(22, 14), targets=Team.ENEMY)
    box.activate()
    yard.world.add(owner, box)
    yard.world.flush()
    combat_system(yard.world, STEP)
    yard.world.flush()
    yard.tick()


def rats(yard: Yard) -> list[EntityId]:
    return [e for e, b in yard.world.query(Brain) if b.kind == "clockrat"]


def test_the_king_patrols_and_turns_at_a_wall() -> None:
    yard = Yard(walls=(16,))
    boss = king(yard, 200, facing=1)
    yard.tick(2.0)
    assert yard.brain(boss).facing == -1
    assert yard.body(boss).x + 32 <= 16 * 16


def test_the_king_rears_charges_and_rests() -> None:
    yard = Yard()
    boss = king(yard, 100)
    yard.player(180)
    yard.tick()
    assert yard.brain(boss).state == "rear"
    before = yard.body(boss).x
    yard.tick(TUNING.king_rear + 0.1)
    assert yard.brain(boss).state == "charge"
    yard.tick(0.3)
    assert yard.body(boss).x - before > TUNING.king_charge_speed * 0.25
    yard.tick(TUNING.king_charge_time)
    assert yard.brain(boss).state in ("rest", "patrol")
    yard.tick(TUNING.king_rest + 0.1)
    assert yard.brain(boss).state != "rest"


def test_the_king_turns_at_a_ledge_after_a_charge() -> None:
    yard = Yard()
    for column in range(10, 14):
        yard.grid.set(column, FLOOR, Tile.EMPTY)
    boss = king(yard, 100, facing=1)
    yard.player(180)
    yard.tick(3.0)
    assert yard.body(boss).y == KING_Y
    assert yard.body(boss).x < 10 * 16


def test_the_king_is_armored_on_every_side_but_above() -> None:
    yard = Yard()
    blocked: list[Blocked] = []
    yard.bus.subscribe(Blocked, blocked.append)
    boss = king(yard)
    guard = yard.world.get(boss, Guard)
    assert (guard.active, guard.facing, guard.top) == (True, 0, False)
    hit_king(yard, boss, side=-1)
    hit_king(yard, boss, side=1)
    assert yard.world.get(boss, Health).current == TUNING.king_hp
    assert len(blocked) == 2
    assert yard.brain(boss).state == "patrol"


def test_a_hit_from_above_hurts_and_topples_without_a_knock() -> None:
    yard = Yard()
    boss = king(yard)
    before = yard.body(boss).x
    hit_king(yard, boss, above=True)
    assert yard.world.get(boss, Health).current == TUNING.king_hp - 1
    assert yard.brain(boss).state == "toppled"
    assert yard.brain(boss).stagger == 0.0
    assert not yard.world.has(boss, Knockback)
    assert abs(yard.body(boss).x - before) < 1


def test_a_hit_topples_it_from_every_upright_state() -> None:
    for state in ("patrol", "rear", "charge", "rest", "call"):
        yard = Yard()
        boss = king(yard)
        yard.brain(boss).state = state
        hit_king(yard, boss, above=True)
        assert yard.brain(boss).state == "toppled", state


def test_a_toppled_king_is_open_dark_and_harmless_then_gets_up() -> None:
    yard = Yard()
    boss = king(yard)
    lamp = yard.world.get(boss, LightSource)
    assert lamp.strength == 1.0
    hit_king(yard, boss, above=True)
    yard.tick()
    assert lamp.strength == 0.0
    assert not yard.world.get(boss, Hitbox).active
    assert not yard.world.get(boss, Guard).active
    health = yard.world.get(boss, Health)
    hit_king(yard, boss, side=1)
    assert health.current == TUNING.king_hp - 2
    yard.tick(TUNING.king_topple_time - 0.5)
    hit_king(yard, boss, side=-1)
    assert yard.brain(boss).state == "toppled"
    yard.tick(0.6)
    assert yard.brain(boss).state == "patrol"
    assert lamp.strength == 1.0
    assert yard.world.get(boss, Guard).active


def test_a_toppled_king_publishes_toppled_once() -> None:
    yard = Yard()
    seen: list[Toppled] = []
    yard.bus.subscribe(Toppled, seen.append)
    boss = king(yard)
    hit_king(yard, boss, above=True)
    yard.tick(1.0)
    assert [event.eid for event in seen] == [boss]


def test_the_king_calls_rats_to_the_markers_of_its_room() -> None:
    yard = Yard()
    marker(yard, 40)
    marker(yard, 330)
    boss = king(yard, 200, iid="a")
    yard.player(260)
    called: list[Summoned] = []
    yard.bus.subscribe(Summoned, called.append)
    yard.world.get(boss, Court).idle = TUNING.king_summon_every
    yard.tick()
    assert yard.brain(boss).state == "call"
    assert not rats(yard)
    yard.tick(TUNING.king_call + 0.1)
    assert len(rats(yard)) == TUNING.king_summon_count
    assert sorted(event.x for event in called) == [48.0, 338.0]
    assert yard.world.get(boss, Court).idle < 1.0


def test_the_king_only_calls_while_the_player_is_near_and_up_to_the_cap() -> None:
    yard = Yard()
    marker(yard, 40)
    marker(yard, 330)
    boss = king(yard, 200, iid="k")
    court = yard.world.get(boss, Court)
    court.idle = TUNING.king_summon_every
    far = yard.player(200 + TUNING.king_alert + 60)
    yard.tick(1.0)
    assert not rats(yard)
    yard.world.get(far, Body).x = 300
    for _ in range(4):
        court.idle = TUNING.king_summon_every
        yard.brain(boss).state = "patrol"
        yard.tick(TUNING.king_call + 0.3)
    assert len(rats(yard)) == TUNING.king_rats_max


def test_markers_come_round_before_any_repeats_and_in_the_same_order_for_an_iid() -> None:
    def calls(iid: str) -> list[float]:
        yard = Yard()
        for x in (40, 100, 330):
            marker(yard, x)
        boss = king(yard, 200, iid=iid)
        court = yard.world.get(boss, Court)
        out: list[Summoned] = []
        yard.bus.subscribe(Summoned, out.append)
        for _ in range(3):
            for rat in rats(yard):
                yard.world.despawn(rat)
            yard.world.flush()
            yard.brain(boss).state, yard.brain(boss).time = "call", TUNING.king_call
            court.rats.clear()
            yard.tick()
        return [event.x for event in out]

    first = calls("king-1")
    assert calls("king-1") == first
    assert len(first) == 6
    assert sorted(first[:3]) == [48.0, 108.0, 338.0]


def test_a_king_ignores_markers_in_other_rooms() -> None:
    yard = Yard()
    yard.world.spawn(Body(40, FLOOR * 16 - 16, 16, 16), RatSpawn(), Identity("m", "Elsewhere", "x"))
    boss = king(yard, 200, iid="a")
    yard.brain(boss).state, yard.brain(boss).time = "call", TUNING.king_call
    yard.tick()
    assert not rats(yard)


def test_rats_go_when_the_king_dies() -> None:
    yard = Yard()
    marker(yard, 40)
    marker(yard, 330)
    boss = king(yard, 200, iid="k")
    yard.brain(boss).state, yard.brain(boss).time = "call", TUNING.king_call
    yard.tick()
    assert len(rats(yard)) == 2
    yard.world.get(boss, Health).dead = True
    yard.tick()
    assert not rats(yard)
    assert boss not in yard.world


def test_rats_go_when_the_king_is_unloaded() -> None:
    yard = Yard()
    marker(yard, 40)
    boss = king(yard, 200, iid="k")
    yard.brain(boss).state, yard.brain(boss).time = "call", TUNING.king_call
    yard.tick()
    assert rats(yard)
    yard.world.despawn(boss)
    yard.world.flush()
    yard.tick()
    assert not rats(yard)


def test_a_dead_king_is_retired_by_iid_and_a_dead_rat_is_not() -> None:
    from emberwake.engine.world.spawning import Spawner, WorldState  # noqa: PLC0415

    yard = Yard()
    state = WorldState()
    yard.world.insert_resource(Spawner(yard.world, {}, state))
    boss = king(yard, 200, iid="the-king")
    rat = yard.enemy("clockrat", 40)
    yard.world.add(rat, Identity("rat", "Room", "clockrat"))
    yard.world.flush()
    yard.tick()
    yard.world.get(boss, Health).dead = True
    yard.world.get(rat, Health).dead = True
    yard.tick()
    assert state.removed == ["the-king"]
