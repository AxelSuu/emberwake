"""Bots that prove the test room stays traversable as tuning changes."""

from __future__ import annotations

import pytest

from emberwake.engine.input import InputState
from emberwake.engine.world.ldtk import load_project
from emberwake.game import paths
from emberwake.game.actions import Action
from emberwake.game.feel import load_feel
from emberwake.game.player.controller import Player, step, wall_side
from emberwake.game.scenes.gameplay import COLLISIONS, DEFAULT_ROOM, WORLD

TS = 16
DT = 1 / 60
TUNING = load_feel(paths.content("feel.toml")).player
GRID = (
    load_project(paths.levels(WORLD))
    .level(DEFAULT_ROOM)
    .layer("Collisions")
    .to_tile_grid(COLLISIONS)
)
R, J, D = Action.RIGHT, Action.JUMP, Action.DASH


def test_shaft_can_be_climbed_by_bouncing_between_walls():
    p = Player.spawn(34 * TS + 8, 30 * TS, TUNING)
    actions = InputState[Action]()
    toward, hold, pressed = 1, 0, False
    for _ in range(600):
        side = wall_side(GRID, p.body, TUNING.wall_jump_reach)
        jump = hold > 0 or (not pressed and (p.grounded or (side != 0 and p.vy > -60)))
        if jump and hold == 0:
            hold = TUNING.var_jump
            if side and not p.grounded:
                toward = -side
        hold = max(hold - 1, 0)
        pressed = jump
        frame = {Action.RIGHT if toward > 0 else Action.LEFT} | ({J} if jump else set())
        actions.advance(frozenset(frame))
        step(p, actions, GRID, TUNING, DT)
        if p.body.bottom <= 9 * TS and p.body.x > 37 * TS:
            return
    pytest.fail("could not climb the shaft")


@pytest.mark.parametrize(("dash_after", "crosses"), [(None, False), (10, True), (16, True)])
def test_dash_gap_needs_a_dash(dash_after: int | None, crosses: bool):
    p = Player.spawn(60 * TS + 8, 30 * TS, TUNING)
    actions = InputState[Action]()
    jumped_at = None
    for tick in range(240):
        if jumped_at is None and p.body.x + p.body.width >= 67 * TS - 1:
            jumped_at = tick
        since = None if jumped_at is None else tick - jumped_at
        frame = {R} | ({J} if since is not None and since < 12 else set())
        if since is not None and since == dash_after:
            frame.add(D)
        actions.advance(frozenset(frame))
        step(p, actions, GRID, TUNING, DT)
        if p.dead or (p.grounded and p.body.x > 77 * TS - 8):
            break
    assert (not p.dead) is crosses
