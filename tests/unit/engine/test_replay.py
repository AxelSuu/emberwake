from __future__ import annotations

from enum import StrEnum

from hypothesis import given
from hypothesis import strategies as st

from emberwake.engine.input.replay import REPLAY_CODEC, Replay, ReplayPlayer, ReplayRecorder
from emberwake.engine.platform.documents import load_document, save_document
from emberwake.engine.platform.storage import MemoryStorage


class Act(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    JUMP = "jump"


frames_strategy = st.lists(st.frozensets(st.sampled_from(list(Act))), max_size=300)


def record(frames: list[frozenset[Act]]) -> Replay:
    recorder = ReplayRecorder[Act]("room", seed=7)
    for frame in frames:
        recorder.record(frame)
    return recorder.replay


def test_run_length_encoding():
    replay = record([frozenset({Act.RIGHT})] * 3 + [frozenset({Act.JUMP, Act.RIGHT})])
    assert replay.runs == [(3, ["right"]), (1, ["jump", "right"])]
    assert replay.ticks == 4


@given(frames_strategy)
def test_playback_reproduces_frames(frames: list[frozenset[Act]]):
    player = ReplayPlayer(record(frames), Act)
    assert [player.sample() for _ in frames] == frames
    assert not player.finished
    assert player.sample() == frozenset()
    assert player.finished


@given(frames_strategy)
def test_replay_document_round_trip(frames: list[frozenset[Act]]):
    storage = MemoryStorage()
    replay = record(frames)
    save_document(storage, "replays/a.json", REPLAY_CODEC, replay)
    assert load_document(storage, "replays/a.json", REPLAY_CODEC, Replay) == replay
