"""Signposts and Echoes: text in the world, and ghosts that replay a lamplighter's last moments.

See ``docs/specs/lore-and-lost-lights.md``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.core.serde import SerdeError
from emberwake.engine.ecs import component
from emberwake.engine.input.replay import REPLAY_CODEC
from emberwake.engine.physics import Body, TileSource
from emberwake.game import paths
from emberwake.game.flags import Facts
from emberwake.game.interact import Interactable, overlap, player_body
from emberwake.game.player.tuning import PlayerTuning
from emberwake.game.rebind import labels
from emberwake.game.trials import Ghost

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.engine.ecs import World
    from emberwake.engine.input.replay import Replay

log = logging.getLogger(__name__)

ECHOES = "echoes"
""":func:`paths.content` folder of the replays, ``<id>.json``."""


@component
@dataclass(slots=True)
class Sign:
    """Shows the string ``sign.<text>`` while the player is within `reach` px."""

    text: str = ""
    reach: float = 28.0


@dataclass(frozen=True, slots=True)
class Speech:
    """A line to show above a point in the world."""

    x: float
    y: float
    text: str


def sign_text(t: Callable[..., str], sign: Sign, keys: dict[str, list[str]]) -> str:
    """The sign's string with ``{jump}`` and friends replaced by the keys now bound, as ``[Z]``."""
    return t(f"sign.{sign.text}", **{action: f"[{key}]" for action, key in labels(keys).items()})


def speeches(world: World, t: Callable[..., str], keys: dict[str, list[str]]) -> list[Speech]:
    """What is being said now: each sign the player stands near, each Echo that is playing."""
    player = player_body(world)
    said = [
        Speech(body.center_x, body.y, sign_text(t, sign, keys))
        for _, body, sign in world.query(Body, Sign)
        if player is not None and overlap(body, player, sign.reach)
    ]
    for _, body, recording, play in world.query(Body, Recording, EchoPlay):
        source = play.ghost.body if play.ghost is not None and play.running else body
        said.append(Speech(source.center_x, source.y, t(f"echo.{recording.id}")))
    return said


@component
@dataclass(slots=True)
class Echo:
    """A lamplighter's memory; `seen` is saved by iid and counts toward light %."""

    seen: bool = False


@component
@dataclass(slots=True)
class Recording:
    """Which replay and string an `Echo` plays: ``content/echoes/<id>.json``, ``echo.<id>``."""

    id: str = ""
    hold: float = 3.0
    """Seconds the line stays after the ghost stops."""


@dataclass(slots=True)
class EchoPlay:
    """An Echo that is playing: its ghost (none without a replay) and how long the line stays."""

    ghost: Ghost | None
    hold: float

    @property
    def running(self) -> bool:
        return self.ghost is not None and not self.ghost.finished and not self.ghost.motor.dead


@dataclass(frozen=True, slots=True)
class EchoHeard:
    id: str
    first: bool
    """It was not heard before."""


@cache
def load_echo(name: str) -> Replay | None:
    """The replay ``content/echoes/<name>.json``, or ``None`` if it is missing or unreadable."""
    path = paths.content(f"{ECHOES}/{name}.json")
    try:
        return REPLAY_CODEC.load(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, SerdeError) as error:
        log.error("Could not load echo %s: %s", name, error)
        return None


def echo_system(world: World, dt: float) -> None:
    """Start the Echoes the player used, and advance the ones that are playing."""
    for eid, interactable, echo, recording in list(world.query(Interactable, Echo, Recording)):
        play = world.find(eid, EchoPlay)
        if interactable.used and not (play and play.running):
            body = world.get(eid, Body)
            replay = load_echo(recording.id)
            tuning = world.resource(PlayerTuning)
            ghost = Ghost(replay, (body.center_x, body.bottom), tuning) if replay else None
            world.add(eid, EchoPlay(ghost, recording.hold))
            _hear(world, echo, recording)
    grid = world.resource(TileSource)
    for eid, play in list(world.query(EchoPlay)):
        if play.running:
            assert play.ghost is not None
            play.ghost.update(grid, dt)
        else:
            play.hold -= dt
            if play.hold <= 0:
                world.remove(eid, EchoPlay)


def _hear(world: World, echo: Echo, recording: Recording) -> None:
    first = not echo.seen
    if first:
        echo.seen = True
        flags = world.resource(Facts).flags
        flags[f"echo_{recording.id}"] = 1
        flags["echoes"] = flags.get("echoes", 0) + 1
    world.resource(EventBus).publish(EchoHeard(recording.id, first))
