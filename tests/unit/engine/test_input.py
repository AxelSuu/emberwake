from __future__ import annotations

from enum import StrEnum

import pygame
import pytest

from emberwake.engine.input import Bindings, InputMapper, InputState


class Act(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    JUMP = "jump"


def run(frames: list[set[Act]]) -> InputState[Act]:
    state = InputState[Act]()
    for frame in frames:
        state.advance(frozenset(frame))
    return state


def test_edges():
    state = InputState[Act]()
    state.advance(frozenset({Act.JUMP}))
    assert state.pressed(Act.JUMP)
    assert state.down(Act.JUMP)
    state.advance(frozenset({Act.JUMP}))
    assert not state.pressed(Act.JUMP)
    assert state.down(Act.JUMP)
    state.advance(frozenset())
    assert state.released(Act.JUMP)
    assert not state.down(Act.JUMP)


@pytest.mark.parametrize(("idle_ticks", "buffered"), [(0, True), (2, True), (3, False)])
def test_pressed_within(idle_ticks: int, buffered: bool):
    state = run([{Act.JUMP}] + [set()] * idle_ticks)
    assert state.pressed_within(Act.JUMP, 3) is buffered


def test_consume_clears_buffer():
    state = run([{Act.JUMP}, set()])
    state.consume(Act.JUMP)
    assert not state.pressed_within(Act.JUMP, 10)


def test_axis():
    assert run([{Act.LEFT}]).axis(Act.LEFT, Act.RIGHT) == -1
    assert run([{Act.LEFT, Act.RIGHT}]).axis(Act.LEFT, Act.RIGHT) == 0
    assert run([{Act.RIGHT}]).axis(Act.LEFT, Act.RIGHT) == 1


@pytest.fixture
def mapper() -> InputMapper[Act]:
    pygame.init()
    bindings = Bindings(
        keys={"left": ["left", "a"], "jump": ["space"]},
    )
    return InputMapper(Act, bindings)


def key(event_type: int, name: str) -> pygame.Event:
    return pygame.Event(event_type, key=pygame.key.key_code(name), mod=0)


def test_held_keys(mapper: InputMapper[Act]):
    mapper.handle(key(pygame.KEYDOWN, "a"))
    assert mapper.sample() == {Act.LEFT}
    assert mapper.sample() == {Act.LEFT}
    mapper.handle(key(pygame.KEYUP, "a"))
    assert mapper.sample() == frozenset()


def test_tap_within_one_frame_lasts_one_sample(mapper: InputMapper[Act]):
    mapper.handle(key(pygame.KEYDOWN, "space"))
    mapper.handle(key(pygame.KEYUP, "space"))
    assert mapper.sample() == {Act.JUMP}
    assert mapper.sample() == frozenset()


def test_two_keys_for_one_action(mapper: InputMapper[Act]):
    mapper.handle(key(pygame.KEYDOWN, "a"))
    mapper.handle(key(pygame.KEYDOWN, "left"))
    mapper.handle(key(pygame.KEYUP, "a"))
    assert mapper.sample() == {Act.LEFT}


def test_focus_loss_releases_everything(mapper: InputMapper[Act]):
    mapper.handle(key(pygame.KEYDOWN, "a"))
    mapper.sample()
    mapper.handle(pygame.Event(pygame.WINDOWFOCUSLOST))
    assert mapper.sample() == frozenset()


def test_unknown_bindings_are_skipped(caplog: pytest.LogCaptureFixture):
    pygame.init()
    InputMapper(Act, Bindings(keys={"fly": ["f"], "jump": ["nokey"]}))
    assert "unknown action 'fly'" in caplog.text
    assert "Unknown key 'nokey'" in caplog.text


def test_rebind(mapper: InputMapper[Act]):
    mapper.bind(Bindings(keys={"jump": ["z"]}))
    mapper.handle(key(pygame.KEYDOWN, "space"))
    mapper.handle(key(pygame.KEYDOWN, "z"))
    assert mapper.sample() == {Act.JUMP}
