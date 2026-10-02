"""Lift_Lab: a lever lift up a shaft, a looping platform over spikes and a two-node lift."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from emberwake.engine.input.replay import Replay, ReplayPlayer
from emberwake.engine.physics import Body
from emberwake.engine.platform.storage import MemoryStorage
from emberwake.engine.scene import SceneManager
from emberwake.game.actions import Action
from emberwake.game.data.save import SaveSlot, save_slot
from emberwake.game.interact import Switch
from emberwake.game.platforms import Platform
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60
LAB = "Lift_Lab"
FLOOR = 20 * 16
"""Top of the floor beside the lift pits, room-local."""
DECK = 11 * 16
LEDGE = 16 * 16
LIFT = (3 * 16, FLOOR)
LOOP = (14 * 16, DECK)
TWO = (29 * 16, FLOOR)
"""Where each platform starts, room-local."""


class Lab:
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

    def away_and_back(self) -> None:
        self.scene.rooms.enter("Test_Room")
        self.scene.rooms.enter(LAB)
        self.idle(2)

    def run(self, runs: list[tuple[int, list[str]]]) -> None:
        replay = Replay(LAB, 0, runs)
        self.scene.replay = ReplayPlayer(replay, Action)
        for _ in range(replay.ticks):
            self.scenes.update(STEP)

    def idle(self, ticks: int) -> None:
        self.run([(ticks, [])])

    def put(self, x: float, y: float) -> None:
        body, motor = self.scene.body, self.scene.motor
        body.x, body.y = self.corner[0] + x, self.corner[1] + y
        motor.vx = motor.vy = 0.0
        motor.grounded = False
        self.idle(2)

    def local(self, body: Body) -> tuple[float, float]:
        return body.x - self.corner[0], body.y - self.corner[1]

    def platform(self, home: tuple[int, int]) -> Body:
        """The platform that starts at `home`."""
        for _, body, platform in self.scene.world.query(Body, Platform):
            if platform.points and (
                platform.points[0]
                == (
                    home[0] + self.corner[0],
                    home[1] + self.corner[1],
                )
            ):
                return body
        raise AssertionError(home)

    def player(self) -> tuple[float, float]:
        return self.local(self.scene.body)

    def levers(self) -> list[Switch]:
        return [s for _, s in self.scene.world.query(Switch)]

    def board(self, platform: tuple[int, int], lever_side: float = 2.0) -> None:
        """Stand on a platform at its home, at the side nearest its lever."""
        self.put(platform[0] + lever_side, platform[1] - 20)


@pytest.fixture
def lab(ctx: GameContext) -> Lab:
    return Lab(ctx)


def test_the_lab_has_a_lift_a_loop_and_a_two_node_lift(lab: Lab) -> None:
    assert lab.local(lab.platform(LIFT)) == LIFT
    assert lab.local(lab.platform(LOOP))[1] == DECK
    assert lab.local(lab.platform(TWO)) == TWO


def test_pulling_the_lever_on_the_lift_carries_the_player_up_to_the_deck(lab: Lab) -> None:
    lab.board(LIFT)
    lab.run([(2, ["interact"]), (200, [])])
    assert lab.local(lab.platform(LIFT)) == pytest.approx((3 * 16, DECK))
    assert lab.player()[1] == pytest.approx(DECK - 20)
    lab.run([(60, ["right"])])
    assert lab.player()[0] > 7 * 16
    assert lab.player()[1] == pytest.approx(DECK - 20)


def test_throwing_the_lever_back_brings_the_lift_down(lab: Lab) -> None:
    lab.board(LIFT)
    lab.run([(2, ["interact"]), (200, [])])
    lab.put(2 * 16 - 8, FLOOR - 20)
    lab.run([(2, ["interact"]), (200, [])])
    assert lab.local(lab.platform(LIFT)) == pytest.approx(LIFT)


def test_the_loop_runs_to_and_fro_over_the_spikes(lab: Lab) -> None:
    seen = []
    for _ in range(16):
        lab.idle(30)
        seen.append(lab.local(lab.platform(LOOP))[0])
    assert min(seen) < 16 * 16 < 21 * 16 < max(seen)
    assert all(14 * 16 <= x <= 23 * 16 for x in seen)


def test_the_player_rides_the_loop_across_the_pit(lab: Lab) -> None:
    x, y = lab.local(lab.platform(LOOP))
    lab.put(x + 20, y - 20)
    start = lab.player()[0]
    lab.run([(200, [])])
    assert lab.player()[0] > start + 100
    assert lab.player()[1] == pytest.approx(DECK - 20)
    assert not lab.scene.motor.dead


def test_the_two_node_lift_goes_up_and_across_to_the_ledge(lab: Lab) -> None:
    lab.board(TWO, 1.0)
    lab.run([(2, ["interact"])])
    lab.run([(260, [])])
    assert lab.local(lab.platform(TWO)) == pytest.approx((31 * 16, LEDGE))
    assert lab.player()[1] == pytest.approx(LEDGE - 20)
    lab.run([(60, ["right"])])
    assert lab.player()[0] > 34 * 16
    assert lab.player()[1] == pytest.approx(LEDGE - 20)


def test_a_raised_lift_stays_raised_after_the_room_reloads(lab: Lab) -> None:
    lab.board(LIFT)
    lab.run([(2, ["interact"]), (200, [])])
    lab.away_and_back()
    assert lab.local(lab.platform(LIFT)) == pytest.approx((3 * 16, DECK))


def test_a_raised_lift_stays_raised_after_quitting_and_continuing(lab: Lab) -> None:
    lab.board(LIFT)
    lab.run([(2, ["interact"]), (200, [])])
    lab.quit_and_continue()
    lab.idle(10)
    assert lab.local(lab.platform(LIFT)) == pytest.approx((3 * 16, DECK))


def test_the_same_input_leaves_the_lift_and_rider_in_the_same_places(ctx: GameContext) -> None:
    def play() -> tuple[tuple[float, float], tuple[float, float]]:
        lab = Lab(ctx)
        lab.board(LIFT)
        lab.run([(2, ["interact"]), (80, []), (40, ["left"]), (40, ["right"])])
        out = lab.player(), lab.local(lab.platform(LIFT))
        lab.scenes.close()
        return out

    assert play() == play()
