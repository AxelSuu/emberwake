from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from emberwake.engine.render.animation import Animator, Clip, load_clips
from emberwake.game import paths

if TYPE_CHECKING:
    from pathlib import Path

RUN = Clip(frames=[10, 11, 12, 13], ms=100, events={1: "footstep", 3: "footstep"})
ONCE = Clip(frames=[0, 1, 2], ms=50, loop=False, events={2: "done"})


def animator() -> Animator:
    return Animator({"run": RUN, "once": ONCE})


def test_frames_advance_on_time_and_loop() -> None:
    a = animator()
    a.play("run")
    assert a.frame == 10
    a.update(0.05)
    assert a.frame == 10
    a.update(0.06)
    assert a.frame == 11
    a.update(0.3)
    assert a.frame == 10


def test_events_fire_once_per_entry() -> None:
    a = animator()
    a.play("run")
    assert [e.name for e in a.update(0.11)] == ["footstep"]
    assert a.update(0.05) == []
    assert [e.frame for e in a.update(0.1)] == []
    assert [e.frame for e in a.update(0.1)] == [3]


def test_a_long_step_reports_every_skipped_event() -> None:
    a = animator()
    a.play("run")
    assert [e.frame for e in a.update(0.35)] == [1, 3]


def test_a_one_shot_holds_its_last_frame_and_finishes() -> None:
    a = animator()
    a.play("once")
    events = a.update(1.0)
    assert [e.name for e in events] == ["done"]
    assert a.finished
    assert a.frame == 2
    assert a.update(1.0) == []


def test_replaying_the_same_clip_does_not_restart_it() -> None:
    a = animator()
    a.play("run")
    a.update(0.15)
    a.play("run")
    assert a.frame == 11
    a.play("run", restart=True)
    assert a.frame == 10


def test_first_frame_events_fire_on_play() -> None:
    clip = Clip(frames=[0, 1], events={0: "swing"})
    a = Animator({"hit": clip})
    a.play("hit")
    assert [e.name for e in a.update(0.0)] == ["swing"]


def test_hitboxes_follow_the_frame() -> None:
    clip = Clip(frames=[0, 1, 2], ms=10, hitboxes={1: [(0, 0, 8, 8)]})
    a = Animator({"swing": clip})
    a.play("swing")
    assert a.hitboxes == []
    a.update(0.011)
    assert a.hitboxes == [(0, 0, 8, 8)]
    a.update(0.01)
    assert a.hitboxes == []


def test_unknown_clip_and_bad_clips() -> None:
    with pytest.raises(KeyError):
        animator().play("nope")
    with pytest.raises(ValueError, match="at least one"):
        Clip(frames=[])
    with pytest.raises(ValueError, match="positive"):
        Clip(frames=[0], ms=0)


def test_shipped_clips_load() -> None:
    clips = load_clips(paths.content("animations.toml"))
    assert clips["player_run"].events == {1: "footstep", 3: "footstep"}
    assert clips["player_dash"].hitboxes[0] == [(0, 4, 20, 10)]
    assert not clips["player_dash"].loop


def test_load_clips_from_text(tmp_path: Path) -> None:
    path = tmp_path / "a.toml"
    path.write_text('[x]\nframes = [3, 4]\nms = 40\nevents = { 0 = "go" }\n')
    assert load_clips(path)["x"].events == {0: "go"}
