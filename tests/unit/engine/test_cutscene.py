from __future__ import annotations

import pytest

from emberwake.engine.core.cutscene import (
    Cutscene,
    CutscenePlayer,
    Script,
    together,
    until,
    wait,
)

STEP = 1 / 60


def delay(seconds: float) -> Script:
    yield wait(seconds)


def run(scene: Cutscene, seconds: float) -> None:
    for _ in range(round(seconds / STEP)):
        scene.update(STEP)


def test_waits_pace_a_script() -> None:
    log: list[str] = []

    def script() -> Script:
        log.append("a")
        yield wait(0.5)
        log.append("b")
        yield wait(0.25)
        log.append("c")

    scene = Cutscene(script())
    scene.update(0.0)
    assert log == ["a"]
    run(scene, 0.4)
    assert log == ["a"]
    run(scene, 0.15)
    assert log == ["a", "b"]
    run(scene, 0.3)
    assert log == ["a", "b", "c"]
    assert scene.finished


def test_back_to_back_waits_do_not_drift() -> None:
    times: list[int] = []
    ticks = 0

    def script() -> Script:
        for _ in range(10):
            yield wait(0.1)
            times.append(ticks)

    scene = Cutscene(script())
    scene.update(0.0)
    for _ in range(61):
        ticks += 1
        scene.update(STEP)
    assert scene.finished
    assert times[-1] == 60


def test_until_polls_a_condition() -> None:
    flag = {"on": False}

    def script() -> Script:
        yield until(lambda: flag["on"])
        flag["done"] = True  # type: ignore[assignment]

    scene = Cutscene(script())
    run(scene, 1.0)
    assert not scene.finished
    flag["on"] = True
    scene.update(STEP)
    assert scene.finished
    assert flag.get("done")


def test_none_waits_one_step() -> None:
    count = {"n": 0}

    def script() -> Script:
        for _ in range(3):
            count["n"] += 1
            yield None

    scene = Cutscene(script())
    scene.update(0.0)
    assert count["n"] == 1
    scene.update(STEP)
    scene.update(STEP)
    assert count["n"] == 3
    scene.update(STEP)
    assert scene.finished


def test_yield_from_composes_scripts() -> None:
    log: list[str] = []

    def line(text: str) -> Script:
        log.append(text)
        yield wait(0.2)

    def script() -> Script:
        yield from line("hi")
        yield from line("bye")

    scene = Cutscene(script())
    scene.update(0.0)
    run(scene, 0.25)
    assert log == ["hi", "bye"]


def test_together_waits_for_the_slowest() -> None:
    log: list[str] = []

    def short() -> Script:
        yield wait(0.1)
        log.append("short")

    def long() -> Script:
        yield wait(0.4)
        log.append("long")

    def script() -> Script:
        yield together(short(), long())
        log.append("after")

    scene = Cutscene(script())
    scene.update(0.0)
    run(scene, 0.2)
    assert log == ["short"]
    run(scene, 0.3)
    assert log == ["short", "long", "after"]


def test_skip_runs_the_script_to_its_end() -> None:
    log: list[str] = []

    def script() -> Script:
        log.append("start")
        yield wait(100)
        log.append("middle")
        yield until(lambda: False)
        yield together(delay(5), delay(6))
        log.append("end")

    scene = Cutscene(script())
    scene.update(0.0)
    scene.skip()
    assert scene.finished
    assert log == ["start", "middle", "end"]


def test_skip_gives_up_on_a_script_that_never_ends() -> None:
    def forever() -> Script:
        while True:
            yield None

    scene = Cutscene(forever())
    scene.skip()
    assert scene.finished


def test_player_tracks_activity_and_calls_back() -> None:
    done: list[int] = []

    def script() -> Script:
        yield wait(0.2)

    player = CutscenePlayer()
    assert not player.active
    player.play(script(), lambda: done.append(1))
    assert player.active
    for _ in range(12):
        player.update(STEP)
    assert not player.active
    assert done == [1]


def test_player_skip_ends_everything() -> None:
    done: list[int] = []

    def script() -> Script:
        yield wait(50)

    player = CutscenePlayer()
    player.play(script(), lambda: done.append(1))
    player.play(script(), lambda: done.append(2))
    player.skip()
    assert not player.active
    assert done == [1, 2]


def test_a_script_that_ends_at_once_never_becomes_active() -> None:
    def script() -> Script:
        return
        yield

    player = CutscenePlayer()
    player.play(script())
    assert not player.active


def test_error_in_script_propagates() -> None:
    def script() -> Script:
        yield wait(0.1)
        raise ValueError("boom")

    scene = Cutscene(script())
    scene.update(0.0)
    with pytest.raises(ValueError, match="boom"):
        run(scene, 0.2)
