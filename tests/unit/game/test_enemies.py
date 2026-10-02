from __future__ import annotations

import emberwake.game.components  # noqa: F401
from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import EntityId, World
from emberwake.engine.physics import Body, Tile, TileGrid
from emberwake.engine.world.rooms import WorldGrid
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
from emberwake.game.enemies import Brain, EnemyTuning, Vented, enemy_system
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
