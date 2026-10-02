"""Runs the Lamprey: equips it, ticks its tree and turns its mode into combat state.

Rules: docs/specs/lamprey.md. The tree is in `lamprey_tree`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.physics import Body
from emberwake.engine.world.rooms import RoomStreamer, WorldGrid
from emberwake.engine.world.spawning import Identity
from emberwake.game.combat import Guard, Health, Hitbox, Hurtbox, Knockback, Team
from emberwake.game.flags import Facts
from emberwake.game.interact import Switch, overlap, player_body
from emberwake.game.lamprey import (
    DEFEATED,
    DRAINED,
    MODES,
    CasingBroken,
    Ctx,
    Drained,
    Lamprey,
    LampreyTuning,
    PhaseChanged,
    inside,
    phase_for,
    place,
    set_mode,
)
from emberwake.game.lamprey_tree import build_tree
from emberwake.game.light import LightSource
from emberwake.game.switches import Photocell

if TYPE_CHECKING:
    from emberwake.engine.ecs import EntityId, World

BREAKING = frozenset({"lunge", "dazed"})
"""Modes in which the head breaks the casing it touches."""
LURE_DIM = 0.5
"""Share of its light the lure gives under water."""


def lamprey_system(world: World, dt: float) -> None:
    """Equip new Lampreys, advance the phase, tick each tree and set combat state by mode."""
    tuning, bus = world.resource(LampreyTuning), world.resource(EventBus)
    grid, player = world.resource(WorldGrid), player_body(world)
    for eid, body, lamprey in list(world.query(Body, Lamprey)):
        if not world.has(eid, Health):
            _equip(world, eid, body, lamprey, tuning)
            continue
        health = world.get(eid, Health)
        ctx = Ctx(world, eid, body, lamprey, tuning, grid, player)
        lamprey.awake = player is not None and inside(lamprey.arena, *_centre(player))
        if lamprey.awake:
            _advance(ctx, health, bus)
            if lamprey.tree is not None:
                lamprey.tree.tick(ctx, dt)
            _drain(ctx, bus)
        lamprey.since += dt
        _apply(world, eid, lamprey)


def _centre(body: Body) -> tuple[float, float]:
    return body.center_x, body.y + body.height / 2


def _equip(
    world: World, eid: EntityId, body: Body, lamprey: Lamprey, tuning: LampreyTuning
) -> None:
    lamprey.home = _centre(body)
    lamprey.arena = _arena(world, eid)
    place(body, lamprey.home[0], lamprey.home[1] + tuning.depth)
    world.add(
        eid,
        Health(tuning.hp, iframes=tuning.iframes),
        Hurtbox(Team.NONE),
        Hitbox(
            damage=tuning.contact_damage,
            targets=Team.PLAYER,
            size=(body.width, body.height),
            knockback=tuning.knockback,
        ),
        Guard(active=True),
    )
    lamprey.tree = build_tree()
    facts = world.resource(Facts)
    if not facts.flags.get(DEFEATED):
        facts.flags.pop(DRAINED, None)


def _arena(world: World, eid: EntityId) -> tuple[float, float, float, float] | None:
    identity = world.find(eid, Identity)
    if identity is None or not world.has_resource(RoomStreamer):
        return None
    rect = world.resource(RoomStreamer).graph.rects.get(identity.room)
    return None if rect is None else (rect.x, rect.y, rect.width, rect.height)


def _advance(ctx: Ctx, health: Health, bus: EventBus) -> None:
    """Move to the phase its health says; the tree starts the new one from its first step."""
    bb = ctx.bb
    phase = max(bb.phase, phase_for(health.current, health.max))
    if phase == bb.phase:
        return
    bb.phase = phase
    if phase == 3:
        bb.casings = [
            cid
            for cid, cell_body, cell in ctx.world.query(Body, Photocell)
            if cell.sealed and inside(bb.arena, *_centre(cell_body))
        ]
    if bb.tree is not None:
        bb.tree.reset(ctx)
    bus.publish(PhaseChanged(phase))


def _drain(ctx: Ctx, bus: EventBus) -> None:
    """Break the casings a lunge reaches; once all are lit the water goes and it slumps."""
    bb, world = ctx.bb, ctx.world
    if bb.phase < 3 or bb.drained:
        return
    if bb.mode in BREAKING:
        for cid in bb.casings:
            if not world.reserved(cid):
                continue
            cell, body = world.get(cid, Photocell), world.get(cid, Body)
            if cell.sealed and overlap(ctx.body, body):
                cell.sealed = False
                bb.broken.append(cid)
                bus.publish(CasingBroken(body.center_x, body.y + body.height / 2))
    if all(world.reserved(cid) and _lit(world, cid) for cid in bb.casings):
        bb.drained = True
        world.resource(Facts).flags[DRAINED] = 1
        if bb.tree is not None:
            bb.tree.reset(ctx)
        place(ctx.body, ctx.centre[0], bb.home[1])
        set_mode(bb, "slump")
        bus.publish(Drained())


def _lit(world: World, eid: EntityId) -> bool:
    cell, switch = world.get(eid, Photocell), world.get(eid, Switch)
    return not cell.sealed and switch.on


def _apply(world: World, eid: EntityId, lamprey: Lamprey) -> None:
    """Hurt box, contact hit box, armor and lure light for the mode it is in."""
    mode = MODES[lamprey.mode]
    hurtbox, hitbox, guard = world.get(eid, Hurtbox), world.get(eid, Hitbox), world.get(eid, Guard)
    hurtbox.team = Team.NONE if mode.submerged else Team.ENEMY
    hitbox.hit.clear()
    hitbox.active = not (mode.submerged or mode.harmless)
    guard.active, guard.facing, guard.top = mode.armor != "off", 0, mode.armor == "full"
    if (lure := world.find(eid, LightSource)) is not None:
        lure.strength = 0.0 if lamprey.phase == 3 else LURE_DIM if mode.submerged else 1.0
    if world.has(eid, Knockback):
        world.remove(eid, Knockback)
