"""Crate_Lab: push a crate onto its plate, drop one off a ledge, reload, rest, quit, continue."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from emberwake.engine.input.replay import Replay, ReplayPlayer
from emberwake.engine.physics import Body, Tile
from emberwake.engine.platform.storage import MemoryStorage
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.spawning import Identity
from emberwake.game.actions import Action
from emberwake.game.crates import PushCrate
from emberwake.game.data.save import SaveSlot, save_slot
from emberwake.game.interact import PressurePlate, Switch
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.signals import Door

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60
LAB = "Crate_Lab"
FLOOR = 10 * 16
STAND = FLOOR - 20
"""Top of the player standing on the floor."""
HOME = 6 * 16
"""Where the floor crate starts, room-local x."""
PLATE = 16 * 16
DOOR = (22, 5)
LEDGE_TOP = 7 * 16


class Lab:
    """A Crate_Lab session continued from a save slot, so it can be quit and continued."""

    def __init__(self, ctx: GameContext) -> None:
        self.ctx = ctx
        assert isinstance(ctx.storage, MemoryStorage)
        save_slot(ctx.storage, ctx.slot, SaveSlot(room=LAB))
        self.open()

    def open(self) -> None:
        self.scenes = SceneManager()
        self.scene = GameplayScene(self.ctx)
        self.scenes.push(self.scene)
        self.scenes.update(STEP)
        self.corner = self.scene.rooms.graph.rects[LAB].topleft
        assert self.scene.room == LAB

    def quit_and_continue(self) -> None:
        self.scenes.close()
        self.open()

    def run(self, runs: list[tuple[int, list[str]]]) -> None:
        replay = Replay(LAB, 0, runs)
        self.scene.replay = ReplayPlayer(replay, Action)
        for _ in range(replay.ticks):
            self.scenes.update(STEP)

    def idle(self, ticks: int) -> None:
        self.run([(ticks, [])])

    def put(self, x: float, y: float) -> None:
        """Move the player to a room-local position, standing still."""
        body, motor = self.scene.body, self.scene.motor
        body.x, body.y = self.corner[0] + x, self.corner[1] + y
        motor.vx = motor.vy = 0.0
        motor.grounded = False

    def crates(self) -> list[Body]:
        """Both crates, the floor one first."""
        found = [body for _, body, _ in self.scene.world.query(Body, PushCrate)]
        return sorted(found, key=lambda body: body.x)

    def local(self, body: Body) -> tuple[float, float]:
        return body.x - self.corner[0], body.y - self.corner[1]

    def floor_crate(self) -> tuple[float, float]:
        return self.local(self.crates()[0])

    def plate(self) -> Switch:
        return next(switch for _, switch, _ in self.scene.world.query(Switch, PressurePlate))

    def door(self) -> Door:
        return next(d for _, d in self.scene.world.query(Door))

    def tile(self, cell: tuple[int, int]) -> Tile:
        left, top = self.corner[0] // 16, self.corner[1] // 16
        return self.scene.grid.get(left + cell[0], top + cell[1])

    def push_onto_plate(self) -> None:
        for _ in range(600):
            if self.plate().on:
                break
            self.run([(1, ["right"])])
        assert self.plate().on
        self.idle(2)

    def away_and_back(self) -> None:
        self.scene.rooms.enter("Test_Room")
        self.scene.rooms.enter(LAB)
        self.idle(2)

    def rest(self) -> None:
        self.put(4 * 16 - 2, STAND)
        self.run([(3, []), (2, ["interact"]), (3, [])])


@pytest.fixture
def lab(ctx: GameContext) -> Lab:
    return Lab(ctx)


def test_the_lab_has_two_crates_a_plate_and_a_door(lab: Lab) -> None:
    kinds = sorted(identity.prefab for _, identity in lab.scene.world.query(Identity))
    assert kinds.count("push_crate") == 2
    assert kinds.count("pressure_plate") == 1
    assert kinds.count("door") == 1
    assert lab.floor_crate() == (HOME, FLOOR - 16)


def test_walking_into_the_crate_pushes_it_and_the_door_stays_shut_until_it_is_on_the_plate(
    lab: Lab,
) -> None:
    lab.run([(60, ["right"])])
    assert lab.floor_crate()[0] > HOME
    assert not lab.plate().on
    assert lab.tile(DOOR) is Tile.SOLID
    lab.put(PLATE - 20, STAND)
    lab.run([(200, ["right"])])
    assert lab.local(lab.scene.body)[0] < DOOR[0] * 16


def test_a_crate_on_the_plate_opens_the_door_for_the_player_to_walk_through(lab: Lab) -> None:
    lab.push_onto_plate()
    assert lab.door().open
    assert lab.tile(DOOR) is Tile.EMPTY
    lab.run([(14, ["jump", "right"]), (150, ["right"])])
    assert lab.local(lab.scene.body)[0] > (DOOR[0] + 1) * 16
    assert lab.plate().on


def test_the_door_shuts_when_the_crate_is_pushed_off_the_plate(lab: Lab) -> None:
    lab.push_onto_plate()
    lab.run([(60, ["right"])])
    assert not lab.plate().on
    assert lab.tile(DOOR) is Tile.SOLID


def test_a_crate_pushed_off_the_ledge_lands_on_the_one_way_below(lab: Lab) -> None:
    ledge = lab.crates()[1]
    x, y = lab.local(ledge)
    assert (x, y) == (33 * 16, LEDGE_TOP - 16)
    lab.put(x - 14, LEDGE_TOP - 20)
    lab.run([(1, []), (150, ["right"])])
    x, y = lab.local(lab.crates()[1])
    assert x > 34 * 16
    assert y == pytest.approx(8 * 16 - 16)


def test_crates_stay_where_they_were_left_when_the_room_reloads(lab: Lab) -> None:
    lab.run([(90, ["right"])])
    left = lab.floor_crate()
    lab.away_and_back()
    assert lab.floor_crate() == left
    assert lab.floor_crate()[0] > HOME


def test_crates_stay_where_they_were_left_after_quitting_and_continuing(lab: Lab) -> None:
    lab.run([(90, ["right"])])
    left = lab.floor_crate()
    lab.quit_and_continue()
    assert lab.floor_crate() == left


def test_resting_at_the_beacon_sends_crates_home(lab: Lab) -> None:
    lab.run([(90, ["right"])])
    assert lab.floor_crate()[0] > HOME
    lab.rest()
    assert lab.floor_crate() == (HOME, FLOOR - 16)
    lab.away_and_back()
    assert lab.floor_crate() == (HOME, FLOOR - 16)
    lab.quit_and_continue()
    assert lab.floor_crate() == (HOME, FLOOR - 16)
