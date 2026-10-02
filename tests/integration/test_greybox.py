"""Pilot bots that walk each greybox room and the whole loop, so tuning cannot trap the player."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from emberwake.engine.input.replay import Replay, ReplayPlayer
from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.rooms import RoomEntered
from emberwake.game.actions import Action
from emberwake.game.beacons import BeaconLit
from emberwake.game.enemies import Brain
from emberwake.game.interact import Collected
from emberwake.game.player.controller import wall_side
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60
TS = 16
CELL = (320, 176)
JUMP_HOLD = 14


def at(cell: tuple[int, int], col: float, row: float = 0) -> tuple[float, float]:
    """World px of a tile in a room whose top-left grid cell is `cell`."""
    return cell[0] * CELL[0] + col * TS, cell[1] * CELL[1] + row * TS


@dataclass(frozen=True, slots=True)
class Leg:
    """Walk to world x and stop there; a jump leg also leaves the ground on its way."""

    x: float
    jump: bool = False
    dash: bool = False
    dash_age: int = 4
    interact: bool = False
    down: bool = False
    """Drop through the one-way underfoot."""
    swing: bool = False
    """Swing once on the first tick."""
    fight: bool = False
    """Stop and swing while an enemy is close ahead."""
    limit: int = 240


class Pilot(ReplayPlayer[Action]):
    """Feeds the scene one frame per tick, reading the scene's state to steer."""

    def __init__(self, scene: GameplayScene, legs: list[Leg]) -> None:
        super().__init__(Replay(), Action)
        self.scene, self.legs = scene, legs
        self.leg = self.age = self.blows = 0

    def foe_ahead(self, side: int) -> bool:
        body = self.scene.body
        return any(
            abs(foe.bottom - body.bottom) < 16 and 0 < (foe.center_x - body.center_x) * side < 36
            for _, foe, _brain in self.scene.world.query(Body, Brain)
        )

    def sample(self) -> frozenset[Action]:
        if self.finished:
            return frozenset()
        body, motor = self.scene.body, self.scene.motor
        leg = self.legs[self.leg]
        wait = 6 if leg.down else 3 if leg.jump else 0
        if self.age > wait and abs(body.center_x - leg.x) < 3 and motor.grounded:
            self.leg, self.age = self.leg + 1, 0
            if self.leg == len(self.legs):
                self.finished = True
                return frozenset()
            leg = self.legs[self.leg]
        self.age += 1
        if self.age > leg.limit:
            msg = f"leg {self.leg} to x={leg.x:.0f} timed out at {body.center_x:.0f}"
            raise AssertionError(msg)
        if leg.fight and self.foe_ahead(1 if leg.x > body.center_x else -1):
            self.blows += 1
            return frozenset({Action.SWING}) if self.blows % 14 == 1 else frozenset()
        return self.buttons(leg)

    def buttons(self, leg: Leg) -> frozenset[Action]:
        age, x = self.age, self.scene.body.center_x
        frame = set[Action]()
        if x < leg.x - 2:
            frame.add(Action.RIGHT)
        elif x > leg.x + 2:
            frame.add(Action.LEFT)
        if leg.down:
            frame.add(Action.DOWN)
        pressed = {
            Action.JUMP: (leg.jump and age <= JUMP_HOLD) or (leg.down and 3 <= age <= 5),
            Action.DASH: leg.dash and leg.dash_age <= age < leg.dash_age + 2,
            Action.INTERACT: leg.interact and age == 1,
            Action.SWING: leg.swing and age == 1,
        }
        return frozenset(frame | {action for action, held in pressed.items() if held})


class Climber(ReplayPlayer[Action]):
    """Bounces between the walls of a shaft until it is above `top`, then walks `toward`."""

    def __init__(self, scene: GameplayScene, top: float, toward: int) -> None:
        super().__init__(Replay(), Action)
        self.scene, self.top, self.exit = scene, top, toward
        self.heading, self.hold, self.pressed, self.out = 1, 0, False, False

    def sample(self) -> frozenset[Action]:
        scene, tuning = self.scene, self.scene.feel.player
        body, motor = scene.body, scene.motor
        self.out = self.out or body.bottom <= self.top
        if self.out:
            return frozenset({Action.RIGHT if self.exit > 0 else Action.LEFT})
        side = wall_side(scene.grid, body, tuning.wall_jump_reach)
        jump = self.hold > 0 or (
            not self.pressed and (motor.grounded or (side != 0 and motor.vy > -60))
        )
        if jump and self.hold == 0:
            self.hold = tuning.var_jump
            if side and not motor.grounded:
                self.heading = -side
        self.hold = max(self.hold - 1, 0)
        self.pressed = jump
        frame = {Action.RIGHT if self.heading > 0 else Action.LEFT}
        return frozenset(frame | ({Action.JUMP} if jump else set()))


@dataclass(frozen=True, slots=True)
class Phase:
    """One bot, over once `until` holds or the bot has nothing left to do."""

    make: Callable[[GameplayScene], ReplayPlayer[Action]]
    until: Callable[[GameplayScene], bool] | None = None


def walk(*legs: Leg, until: Callable[[GameplayScene], bool] | None = None) -> Phase:
    return Phase(lambda scene: Pilot(scene, list(legs)), until)


def climb(top: float, toward: int, until: Callable[[GameplayScene], bool]) -> Phase:
    return Phase(lambda scene: Climber(scene, top, toward), until)


def in_room(name: str) -> Callable[[GameplayScene], bool]:
    return lambda scene: scene.room == name


class Route(ReplayPlayer[Action]):
    def __init__(self, scene: GameplayScene, phases: list[Phase]) -> None:
        super().__init__(Replay(), Action)
        self.scene, self.phases, self.index = scene, phases, 0
        self.bot: ReplayPlayer[Action] | None = None

    def sample(self) -> frozenset[Action]:
        if self.index == len(self.phases):
            self.finished = True
            return frozenset()
        phase = self.phases[self.index]
        self.bot = self.bot or phase.make(self.scene)
        reached = phase.until is not None and phase.until(self.scene)
        if reached or (self.bot.finished and phase.until is None):
            self.index, self.bot = self.index + 1, None
            return self.sample()
        return self.bot.sample()


def run(ctx: GameContext, room: str, *phases: Phase, ticks: int = 1500) -> GameplayScene:
    """Play `room` from its first PlayerStart through the phases; fail if dead or not done."""
    scenes = SceneManager()
    scene = GameplayScene(ctx, room=room, replay=Replay(room))
    scenes.push(scene)
    scenes.apply_pending()
    route = Route(scene, list(phases))
    scene.replay = route
    for _ in range(ticks):
        scenes.update(STEP)
        assert not scene.motor.dead, f"died at {scene.body.center_x:.0f},{scene.body.y:.0f}"
        if route.finished:
            return scene
    where = f"{scene.body.center_x:.0f},{scene.body.y:.0f}"
    msg = f"{scene.room}: stuck in phase {route.index} at {where}"
    raise AssertionError(msg)


LAB = 60
EAST = (LAB + 4, 2)
SHAFT = (LAB + 6, 1)
PLATE = (LAB + 7, 1)
UPPER = (LAB + 8, 0)
HALL = (LAB + 4, 0)
TEST = (LAB, 0)
SHAFT_TOP = at(SHAFT, 0, 9)[1]


def plate_room() -> Phase:
    return walk(
        Leg(at(PLATE, 7.5)[0]),
        Leg(at(PLATE, 12.5)[0], jump=True),
        Leg(at(PLATE, 15.5)[0]),
        Leg(at(UPPER, 1.5)[0]),
        until=in_room("Upper_Room"),
    )


def upper_room() -> Phase:
    x = lambda col: at(UPPER, col + 0.5)[0]  # noqa: E731
    return walk(
        Leg(x(4)),
        Leg(x(4), interact=True),
        Leg(x(9)),
        Leg(x(12), jump=True),
        Leg(x(10)),
        Leg(x(6), jump=True),
        Leg(x(8)),
        Leg(x(12), jump=True),
        Leg(x(10)),
        Leg(x(4), jump=True),
        Leg(at(HALL, 79.5)[0]),
        until=in_room("Return_Hall"),
    )


def return_hall() -> Phase:
    return walk(
        Leg(at(HALL, 43.5)[0]),
        Leg(at(HALL, 37.5)[0], jump=True),
        Leg(at(TEST, 79.5)[0]),
        until=in_room("Test_Room"),
    )


def test_shaft_is_climbed_to_its_east_exit(ctx: GameContext):
    run(ctx, "Shaft", climb(SHAFT_TOP, 1, in_room("Lab_Plate_Room")))


def test_plate_room_is_crossed_by_standing_on_the_plate(ctx: GameContext):
    run(ctx, "Lab_Plate_Room", plate_room())


def test_upper_room_lights_its_beacon_and_leaves_west(ctx: GameContext):
    lit: list[BeaconLit] = []
    collected: list[Collected] = []
    ctx.bus.subscribe(BeaconLit, lit.append)
    ctx.bus.subscribe(Collected, collected.append)
    run(ctx, "Upper_Room", upper_room())
    assert len(lit) == 1
    assert len(collected) == 3


def test_return_hall_drops_into_the_test_room(ctx: GameContext):
    run(ctx, "Return_Hall", return_hall())


def test_the_loop_can_be_walked_using_every_mechanism(ctx: GameContext):
    entered: list[str] = []
    lit: list[BeaconLit] = []
    collected: list[Collected] = []
    ctx.bus.subscribe(RoomEntered, lambda event: entered.append(event.room))
    ctx.bus.subscribe(BeaconLit, lit.append)
    ctx.bus.subscribe(Collected, collected.append)
    hall = (LAB + 5, 2)
    run(
        ctx,
        "East_Passage",
        walk(
            Leg(at(EAST, 10.5)[0]),
            Leg(at(EAST, 10.5)[0], interact=True),
            Leg(at(hall, 0.5)[0]),
            until=in_room("Lab_Lever_Hall"),
        ),
        walk(
            Leg(at(hall, 5.5)[0]),
            Leg(at(hall, 5.5)[0], interact=True),
            Leg(at(hall, 16.5)[0]),
            Leg(at(SHAFT, 0.5)[0]),
            until=in_room("Shaft"),
        ),
        climb(SHAFT_TOP, 1, in_room("Lab_Plate_Room")),
        plate_room(),
        upper_room(),
        return_hall(),
        walk(Leg(at(TEST, 77.5)[0]), Leg(at(EAST, 0.5)[0]), until=in_room("East_Passage")),
        ticks=4000,
    )
    assert entered == [
        "Lab_Lever_Hall",
        "Shaft",
        "Lab_Plate_Room",
        "Upper_Room",
        "Return_Hall",
        "Test_Room",
        "East_Passage",
    ]
    assert len(lit) == 2
    assert len(collected) == 4
