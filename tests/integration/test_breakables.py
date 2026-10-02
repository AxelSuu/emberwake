"""Break_Lab: swing at walls, crates and pots, stand on crumbling planks, reload and continue."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pytest

from emberwake.engine.input.replay import Replay, ReplayPlayer
from emberwake.engine.physics import Tile
from emberwake.engine.platform.storage import MemoryStorage
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.spawning import Identity
from emberwake.game.actions import Action
from emberwake.game.breakables import Broken, Crumble
from emberwake.game.data.save import SaveSlot, save_slot
from emberwake.game.interact import Collected
from emberwake.game.player.swing import SwingTuning
from emberwake.game.render.placeholder import ROCK
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60
LAB = "Break_Lab"
SWING = SwingTuning()
SWING_RUN = [(1, ["swing"]), (SWING.length, [])]
WALL = (8, 5)
PLUG = (22, 7)
CRATE = (11, 9)
POT = (15, 9)
STAND = 10 * 16 - 20
"""Top of the player standing on the floor."""
PLATFORM = (30, 7)


class Lab:
    """A Break_Lab session continued from a save slot, so it can be quit and continued."""

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

    def put(self, x: float, y: float, facing: int = 1) -> None:
        """Move the player to a room-local position, standing still."""
        body, motor = self.scene.body, self.scene.motor
        body.x, body.y = self.corner[0] + x, self.corner[1] + y
        motor.vx = motor.vy = 0.0
        motor.grounded = False
        motor.facing = facing

    def tile(self, cell: tuple[int, int]) -> Tile:
        left, top = self.corner[0] // 16, self.corner[1] // 16
        return self.scene.grid.get(left + cell[0], top + cell[1])

    def prefabs(self) -> list[str]:
        return sorted(identity.prefab for _, identity in self.scene.world.query(Identity))

    def local_x(self) -> float:
        return self.scene.body.x - self.corner[0]

    def away_and_back(self) -> None:
        self.scene.rooms.enter("Test_Room")
        self.scene.rooms.enter(LAB)
        self.idle(2)

    def swing_at(self, x: float, y: float, *held: str, facing: int = 1) -> None:
        self.put(x, y, facing)
        self.run([(1, ["swing", *held]), (SWING.length, list(held))])


@pytest.fixture
def lab(ctx: GameContext) -> Lab:
    return Lab(ctx)


def test_break_lab_has_everything_to_break(lab: Lab) -> None:
    kinds = lab.prefabs()
    assert kinds.count("cracked_wall") == 2
    assert kinds.count("crate") == 2
    assert kinds.count("pot") == 1
    assert kinds.count("crumbling_platform") == 2


def test_a_cracked_wall_blocks_until_struck_and_crates_are_solid(lab: Lab) -> None:
    lab.run([(60, ["right"])])
    assert lab.tile(WALL) is Tile.SOLID
    assert lab.local_x() + lab.scene.body.width <= 8 * 16 + 0.5
    lab.run([*SWING_RUN, (50, ["right"])])
    assert lab.tile(WALL) is Tile.EMPTY
    assert lab.local_x() > 9 * 16
    assert lab.local_x() + lab.scene.body.width <= 11 * 16 + 0.5, "the crate is in the way"


def test_the_player_stands_on_a_crate(lab: Lab) -> None:
    lab.put(11 * 16 + 3, 9 * 16 - 20 - 20)
    lab.idle(30)
    assert lab.scene.body.bottom == pytest.approx(lab.corner[1] + 9 * 16)


def test_breaking_a_crate_pays_its_embers_and_gives_feedback(lab: Lab) -> None:
    collected: list[Collected] = []
    felt: list[tuple[int, float, int]] = []
    scene = lab.scene
    lab.ctx.bus.subscribe(Collected, collected.append)

    def felt_now(_: Broken) -> None:
        felt.append((scene.hitstop, scene.camera.shake.trauma, scene.particles.count))

    lab.ctx.bus.subscribe(Broken, felt_now)
    before = scene.progress.data.stats.embers
    lab.swing_at(10 * 16 + 2, STAND)
    assert lab.tile(CRATE) is Tile.EMPTY
    ((hitstop, trauma, debris),) = felt
    assert hitstop >= scene.feel.breakables.hitstop > 0
    assert trauma >= scene.feel.breakables.trauma
    assert debris > 0
    lab.idle(180)
    assert [event.value for event in collected] == [1, 1]
    assert scene.progress.data.stats.embers == before + 2


def test_a_pot_breaks_with_one_ember_and_does_not_block(lab: Lab) -> None:
    assert lab.tile(POT) is Tile.EMPTY
    lab.swing_at(14 * 16, STAND)
    assert "pot" not in lab.prefabs()


def test_an_up_swing_breaks_the_ceiling_above(lab: Lab) -> None:
    lab.swing_at(22 * 16 + 8, 130, "up")
    assert lab.tile(PLUG) is Tile.EMPTY
    assert lab.tile((23, 7)) is Tile.EMPTY


def test_a_down_swing_breaks_the_floor_and_the_player_drops_through(lab: Lab) -> None:
    lab.put(22 * 16 + 8, 80)
    lab.run([(1, ["swing", "down"]), (SWING.length, ["down"])])
    assert lab.tile(PLUG) is Tile.EMPTY
    assert lab.scene.motor.dash_charges == lab.scene.feel.player.dash_charges
    lab.idle(30)
    assert lab.scene.body.y > lab.corner[1] + 8 * 16


def test_broken_things_stay_broken_when_the_room_reloads(lab: Lab) -> None:
    lab.run([*SWING_RUN])
    lab.swing_at(10 * 16 + 2, STAND)
    lab.swing_at(7 * 16 + 4, STAND)
    lab.away_and_back()
    assert lab.tile(WALL) is Tile.EMPTY
    assert lab.tile(CRATE) is Tile.EMPTY
    kinds = lab.prefabs()
    assert kinds.count("cracked_wall") == 1
    assert kinds.count("crate") == 1
    assert lab.tile(PLUG) is Tile.SOLID


def test_broken_things_stay_broken_after_quitting_and_continuing(lab: Lab) -> None:
    lab.swing_at(7 * 16 + 4, STAND)
    lab.swing_at(14 * 16, STAND)
    assert lab.scene.spawner.state.removed
    lab.quit_and_continue()
    assert lab.tile(WALL) is Tile.EMPTY
    assert lab.tile(POT) is Tile.EMPTY
    kinds = lab.prefabs()
    assert kinds.count("cracked_wall") == 1
    assert "pot" not in kinds
    assert kinds.count("crate") == 2


def test_a_crumbling_platform_holds_then_clears_then_returns(lab: Lab) -> None:
    tuning = lab.scene.feel.breakables
    lab.put(30 * 16 + 11, 7 * 16 - 21)
    lab.idle(10)
    assert lab.tile(PLATFORM) is Tile.ONE_WAY
    assert lab.scene.motor.grounded
    states = [crumble.state for _, crumble in lab.scene.world.query(Crumble)]
    assert states.count("shaking") == 1
    lab.idle(round(tuning.crumble_delay / STEP))
    assert lab.tile(PLATFORM) is Tile.EMPTY
    lab.idle(30)
    assert lab.scene.body.y > lab.corner[1] + 7 * 16
    lab.idle(round(tuning.crumble_return / STEP))
    assert lab.tile(PLATFORM) is Tile.ONE_WAY


def test_a_platform_that_reloads_is_whole(lab: Lab) -> None:
    lab.put(30 * 16 + 11, 7 * 16 - 21)
    lab.idle(40)
    assert lab.tile(PLATFORM) is Tile.EMPTY
    lab.put(3 * 16, STAND)
    lab.away_and_back()
    assert lab.tile(PLATFORM) is Tile.ONE_WAY


def test_room_art_does_not_bake_what_entities_own(lab: Lab) -> None:
    lab.idle(5)
    layer, job = lab.scene.layers[LAB]
    assert job is not None
    canvas = pygame.Surface(lab.scene.rooms.graph.rects[LAB].size, pygame.SRCALPHA)
    layer.draw(canvas, lab.corner)
    for column, row in (WALL, CRATE, PLUG, PLATFORM):
        assert canvas.get_at((column * 16 + 8, row * 16 + 8)).a == 0
    assert canvas.get_at((8, 8)) == ROCK
