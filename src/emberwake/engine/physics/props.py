"""Physical props: boxes and circles that fall, tumble and bounce against the tile grid.

`PropWorld` hides two backends. With pymunk installed, props are rigid bodies in a real physics
space: tiles are merged into a few static boxes (greedy meshing), and the player is mirrored as
a kinematic body so props can be pushed. Without pymunk (the browser build), props fall back to
simple kinematics: gravity, bounce and friction against tiles, and no collision with each other
or the player.

Characters never use this; they move with `emberwake.engine.physics.kinematic` (ADR 0007).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from emberwake.engine.physics.kinematic import Body, move
from emberwake.engine.physics.tiles import Tile

if TYPE_CHECKING:
    from collections.abc import Collection

    from emberwake.engine.physics.tiles import TileSource

try:
    import pymunk
except ImportError:  # pragma: no cover - exercised by forcing the simple backend
    pymunk = None

HAS_PYMUNK = pymunk is not None
GRAVITY = 700.0
SOLID_ONLY = frozenset({Tile.SOLID})

type Cells = tuple[int, int, int, int]
"""A block of tiles: ``(column, row, columns, rows)``."""


def greedy_boxes(
    grid: TileSource, region: Cells, kinds: Collection[Tile] = SOLID_ONLY
) -> list[Cells]:
    """Merge the tiles of `kinds` inside `region` into as few boxes as possible.

    Runs of tiles along each row are merged first, then equal runs in consecutive rows, so a
    solid floor becomes one box however many tiles it has.
    """
    column0, row0, columns, rows = region
    open_runs: dict[tuple[int, int], list[int]] = {}
    boxes: list[Cells] = []
    for row in range(row0, row0 + rows):
        runs: set[tuple[int, int]] = set()
        start = None
        for column in range(column0, column0 + columns + 1):
            solid = column < column0 + columns and grid.get(column, row) in kinds
            if solid and start is None:
                start = column
            elif not solid and start is not None:
                runs.add((start, column - start))
                start = None
        for key in list(open_runs):
            if key not in runs:
                top, height = open_runs.pop(key)
                boxes.append((key[0], top, key[1], height))
        for key in runs:
            if key in open_runs:
                open_runs[key][1] += 1
            else:
                open_runs[key] = [row, 1]
    for key, (top, height) in open_runs.items():
        boxes.append((key[0], top, key[1], height))
    return sorted(boxes, key=lambda b: (b[1], b[0]))


type Rect = tuple[float, float, float, float]
"""``(x, y, width, height)`` in px."""


@dataclass(frozen=True, slots=True)
class PropSpec:
    """What to create: a ``"box"`` or ``"circle"`` of `size` centred at (`x`, `y`)."""

    shape: str
    x: float
    y: float
    size: tuple[float, float]
    mass: float
    bounce: float


@dataclass(frozen=True, slots=True)
class PropState:
    """Where a prop is: centre, rotation in degrees, and velocity in px/s."""

    x: float
    y: float
    angle: float
    vx: float
    vy: float


class _Backend(Protocol):
    name: str

    def set_statics(self, boxes: list[Rect]) -> None: ...
    def add(self, spec: PropSpec) -> int: ...
    def remove(self, handle: int) -> None: ...
    def push(self, handle: int, vx: float, vy: float) -> None: ...
    def set_player(self, box: Rect, vx: float, vy: float) -> None: ...
    def step(self, dt: float) -> None: ...
    def state(self, handle: int) -> PropState: ...


class PropWorld:
    """Props over a tile grid, on whichever backend is available.

    Args:
        grid: Static collision: solid tiles stop props.
        region: The tiles to build static geometry from, `refresh` rebuilds it.
        backend: ``"auto"`` (pymunk if installed), ``"pymunk"`` or ``"simple"``.
    """

    def __init__(self, grid: TileSource, region: Cells, backend: str = "auto") -> None:
        if backend == "pymunk" and not HAS_PYMUNK:
            raise RuntimeError("pymunk is not installed")
        use_pymunk = HAS_PYMUNK and backend in ("auto", "pymunk")
        self.grid = grid
        self.region = region
        self._backend: _Backend = _PymunkBackend() if use_pymunk else _SimpleBackend(grid)
        self.refresh()

    @property
    def backend(self) -> str:
        """``"pymunk"`` or ``"simple"``."""
        return self._backend.name

    def refresh(self, region: Cells | None = None) -> None:
        """Rebuild static geometry from the grid, after tiles changed or the region moved."""
        self.region = region or self.region
        size = self.grid.tile_size
        meshed = greedy_boxes(self.grid, self.region)
        boxes: list[Rect] = [(c * size, r * size, w * size, h * size) for c, r, w, h in meshed]
        self._backend.set_statics(boxes)

    def add_box(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        mass: float = 1.0,
        bounce: float = 0.3,
    ) -> int:
        """A box centred at (`x`, `y`). Returns its handle."""
        return self._backend.add(PropSpec("box", x, y, (width, height), mass, bounce))

    def add_circle(
        self, x: float, y: float, radius: float, *, mass: float = 1.0, bounce: float = 0.5
    ) -> int:
        """A circle centred at (`x`, `y`). Returns its handle."""
        return self._backend.add(PropSpec("circle", x, y, (radius * 2, radius * 2), mass, bounce))

    def remove(self, handle: int) -> None:
        """Take a prop out of the world."""
        self._backend.remove(handle)

    def push(self, handle: int, vx: float, vy: float) -> None:
        """Set a prop's velocity, for throwing it."""
        self._backend.push(handle, vx, vy)

    def set_player(self, body: Body, vx: float = 0.0, vy: float = 0.0) -> None:
        """Mirror the player's box (moving at `vx`, `vy`) so props can be pushed by it."""
        self._backend.set_player((body.x, body.y, body.width, body.height), vx, vy)

    def step(self, dt: float) -> None:
        """Advance every prop by `dt` seconds."""
        self._backend.step(dt)

    def state(self, handle: int) -> PropState:
        """The prop's current position, angle and velocity."""
        return self._backend.state(handle)


class _SimpleBackend:
    """Fallback: boxes with gravity, bounce and friction, resolved by the tile mover."""

    name = "simple"
    FRICTION = 6.0
    SPIN_DECAY = 3.0

    def __init__(self, grid: TileSource) -> None:
        self.grid = grid
        self._next = 0
        self._props: dict[int, dict[str, Any]] = {}

    def set_statics(self, boxes: list[Rect]) -> None:
        """Nothing to build: collision reads the grid directly."""

    def add(self, spec: PropSpec) -> int:
        handle = self._next
        self._next += 1
        w, h = spec.size
        self._props[handle] = {
            "body": Body(spec.x - w / 2, spec.y - h / 2, w, h),
            "v": [0.0, 0.0],
            "bounce": spec.bounce,
            "angle": 0.0,
            "spin": 0.0,
        }
        return handle

    def remove(self, handle: int) -> None:
        self._props.pop(handle, None)

    def push(self, handle: int, vx: float, vy: float) -> None:
        prop = self._props[handle]
        prop["v"] = [vx, vy]
        prop["spin"] = vx * 2.0

    def set_player(self, box: Rect, vx: float, vy: float) -> None:
        """The player does not push props in the simple backend."""

    def step(self, dt: float) -> None:
        for prop in self._props.values():
            body, velocity = prop["body"], prop["v"]
            velocity[1] += GRAVITY * dt
            contacts = move(self.grid, body, velocity[0] * dt, velocity[1] * dt)
            if contacts.ground or contacts.ceiling:
                velocity[1] = -velocity[1] * prop["bounce"] if abs(velocity[1]) > 40 else 0.0
            if contacts.left or contacts.right:
                velocity[0] = -velocity[0] * prop["bounce"]
            if contacts.ground:
                velocity[0] *= max(0.0, 1.0 - self.FRICTION * dt)
                prop["spin"] = velocity[0] * 2.0
            prop["angle"] += prop["spin"] * dt
            prop["spin"] *= max(0.0, 1.0 - self.SPIN_DECAY * dt)

    def state(self, handle: int) -> PropState:
        prop = self._props[handle]
        body = prop["body"]
        return PropState(
            body.center_x, body.y + body.height / 2, prop["angle"], prop["v"][0], prop["v"][1]
        )


class _PymunkBackend:
    """Rigid bodies in a pymunk space, with greedy-meshed static tiles and a kinematic player."""

    name = "pymunk"

    def __init__(self) -> None:
        assert pymunk is not None
        self.space = pymunk.Space()
        self.space.gravity = (0.0, GRAVITY)
        self._statics: list[Any] = []
        self._bodies: dict[int, Any] = {}
        self._next = 0
        self._player: Any = None
        self._player_shape: Any = None

    def set_statics(self, boxes: list[Rect]) -> None:
        assert pymunk is not None
        if self._statics:
            self.space.remove(*self._statics)
        shapes = []
        for x, y, w, h in boxes:
            corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            shape = pymunk.Poly(self.space.static_body, corners)
            shape.friction = 0.8
            shape.elasticity = 1.0
            shapes.append(shape)
        self.space.add(*shapes)
        self._statics = shapes

    def add(self, spec: PropSpec) -> int:
        assert pymunk is not None
        w, h = spec.size
        if spec.shape == "circle":
            body = pymunk.Body(spec.mass, pymunk.moment_for_circle(spec.mass, 0, w / 2))
            form = pymunk.Circle(body, w / 2)
        else:
            body = pymunk.Body(spec.mass, pymunk.moment_for_box(spec.mass, (w, h)))
            form = pymunk.Poly.create_box(body, (w, h))
        body.position = (spec.x, spec.y)
        form.elasticity = spec.bounce
        form.friction = 0.7
        self.space.add(body, form)
        handle = self._next
        self._next += 1
        self._bodies[handle] = body
        return handle

    def remove(self, handle: int) -> None:
        body = self._bodies.pop(handle, None)
        if body is not None:
            self.space.remove(body, *body.shapes)

    def push(self, handle: int, vx: float, vy: float) -> None:
        self._bodies[handle].velocity = (vx, vy)

    def set_player(self, box: Rect, vx: float, vy: float) -> None:
        assert pymunk is not None
        x, y, w, h = box
        if self._player is None:
            self._player = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
            self._player_shape = pymunk.Poly.create_box(self._player, (w, h))
            self._player_shape.friction = 0.6
            self.space.add(self._player, self._player_shape)
        self._player.position = (x + w / 2, y + h / 2)
        self._player.velocity = (vx, vy)

    def step(self, dt: float) -> None:
        self.space.step(dt)

    def state(self, handle: int) -> PropState:
        body = self._bodies[handle]
        return PropState(
            body.position.x,
            body.position.y,
            math.degrees(body.angle),
            body.velocity.x,
            body.velocity.y,
        )
