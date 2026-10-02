"""Encounters: an arena that shuts its doors, sends waves of enemies and powers its targets.

An `Encounter` is a zone; `WaveSpawn` markers in its room say which enemy appears where in which
wave. Its `Switch` is on once cleared, which is what is saved by iid. Wave enemies are owned by
the encounter through `Minion`, like the Clockrat King's rats, and are never saved.
See docs/specs/encounters.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.ecs import EntityId, component
from emberwake.engine.ecs.prefabs import build
from emberwake.engine.physics import Body
from emberwake.engine.world.spawning import Identity, Spawner
from emberwake.game import enemies
from emberwake.game.interact import Switch, overlap, player_body, set_switch
from emberwake.game.signals import Receiver, Wiring

if TYPE_CHECKING:
    from emberwake.engine.ecs import World

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EncounterTuning:
    """Encounter pacing (content/feel.toml, ``[encounters]``): seconds."""

    wave_delay: float = 1.0
    """From a wave's last death to the next wave."""
    leave_grace: float = 1.5
    """How long the player may be outside the zone before a running encounter resets."""
    trauma: float = 0.2
    """Screen shake when an encounter starts and when it is cleared."""


@component
@dataclass(slots=True)
class Encounter:
    """A zone that runs waves; cleared once its `Switch` is on."""

    doors: list[str] = field(default_factory=list)
    """Iids of the doors it shuts while it runs."""
    active: bool = False
    wave: int = 0
    """The wave being fought, from 1."""
    enemies: list[EntityId] = field(default_factory=list)
    """The current wave's enemies."""
    delay: float = -1.0
    """Seconds until the next wave once the current one is dead; negative while it is not."""
    away: float = 0.0
    """Seconds the player has been outside the zone."""


@component
@dataclass(slots=True)
class WaveSpawn:
    """Where an enemy of `kind` appears for `wave` of the encounter `encounter` (an iid)."""

    encounter: str = ""
    wave: int = 1
    kind: str = "clockrat"


@dataclass(frozen=True, slots=True)
class EncounterStarted:
    iid: str
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class EncounterCleared:
    iid: str
    x: float
    y: float


def encounter_system(world: World, dt: float) -> None:
    """Start encounters the player walks into, run their waves, clear or reset them."""
    tuning, bus, player = (
        world.resource(EncounterTuning),
        world.resource(EventBus),
        player_body(world),
    )
    for eid, body, switch, encounter in list(world.query(Body, Switch, Encounter)):
        if switch.on:
            continue
        centre = body.center_x, body.y + body.height / 2
        if not encounter.active:
            if player is not None and overlap(body, player):
                encounter.active, encounter.away = True, 0.0
                _spawn_wave(world, eid, encounter, 1)
                bus.publish(EncounterStarted(_iid(world, eid), *centre))
            continue
        inside = player is not None and overlap(body, player)
        encounter.away = 0.0 if inside else encounter.away + dt
        if player is None or encounter.away > tuning.leave_grace:
            reset(world, eid)
            continue
        encounter.enemies = [enemy for enemy in encounter.enemies if world.reserved(enemy)]
        if encounter.enemies:
            continue
        if not _markers(world, eid, encounter.wave + 1):
            encounter.active = False
            set_switch(world, eid, switch, True)
            bus.publish(EncounterCleared(_iid(world, eid), *centre))
            continue
        if encounter.delay < 0:
            encounter.delay = tuning.wave_delay
        encounter.delay -= dt
        if encounter.delay <= 0:
            _spawn_wave(world, eid, encounter, encounter.wave + 1)


def lock_system(world: World, dt: float) -> None:
    """Doors an encounter shuts are open unless one of their encounters is running."""
    wiring, spawner = world.resource(Wiring), world.resource(Spawner)

    def running(iid: str) -> bool:
        eid = spawner.resolve(iid)
        encounter = world.find(eid, Encounter) if eid is not None else None
        return encounter is not None and encounter.active

    for _, identity, receiver in world.query(Identity, Receiver):
        if (shut := wiring.locks.get(identity.iid)) is not None:
            receiver.powered = not any(running(iid) for iid in shut)


def reset(world: World, eid: EntityId) -> None:
    """Send a running encounter back to idle: its wave enemies go and its doors open."""
    encounter = world.get(eid, Encounter)
    for enemy in encounter.enemies:
        world.despawn(enemy)
    encounter.active, encounter.wave, encounter.away, encounter.delay = False, 0, 0.0, -1.0
    encounter.enemies = []


def _iid(world: World, eid: EntityId) -> str:
    return world.get(eid, Identity).iid


def _markers(world: World, eid: EntityId, wave: int) -> list[tuple[float, float, str, str]]:
    """The (x, y, kind, iid) of `wave`'s markers in the encounter's room, in position order."""
    iid, room = _iid(world, eid), world.get(eid, Identity).room
    return sorted(
        (body.center_x, body.bottom, spawn.kind, identity.iid)
        for _, body, spawn, identity in world.query(Body, WaveSpawn, Identity)
        if spawn.encounter == iid and spawn.wave == wave and identity.room == room
    )


def _spawn_wave(world: World, eid: EntityId, encounter: Encounter, wave: int) -> None:
    """Spawn `wave`'s enemies at their markers; each is owned by the encounter."""
    spawner, bus, player = world.resource(Spawner), world.resource(EventBus), player_body(world)
    room = world.get(eid, Identity).room
    encounter.wave, encounter.delay, encounter.enemies = wave, -1.0, []
    for x, y, kind, marker in _markers(world, eid, wave):
        enemy = _spawn_enemy(world, spawner, eid, kind, marker, room, (x, y), player)
        if enemy is not None:
            encounter.enemies.append(enemy)
            bus.publish(enemies.Summoned(enemy, x, y))


def _spawn_enemy(  # noqa: PLR0917
    world: World,
    spawner: Spawner,
    owner: EntityId,
    kind: str,
    marker: str,
    room: str,
    feet: tuple[float, float],
    player: Body | None,
) -> EntityId | None:
    prefab = spawner.prefabs.get(kind)
    if prefab is None or kind not in enemies.KINDS:
        log.error("Encounter marker %s names %r, which is not an enemy", marker, kind)
        return None
    x, y = feet
    width, height = enemies.KINDS[kind].size
    parts = build(prefab, {}, spawner.registry)
    brain = parts["Brain"]
    assert isinstance(brain, enemies.Brain)
    if player is not None:
        brain.facing = 1 if player.center_x >= x else -1
    return world.spawn(
        Identity(f"{marker}:wave", room, kind),
        Body(x - width / 2, y - height, width, height),
        enemies.Minion(owner),
        *parts.values(),
    )
