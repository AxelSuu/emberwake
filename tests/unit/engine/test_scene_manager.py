from __future__ import annotations

import pygame
import pytest

from emberwake.engine.scene import Scene, SceneManager


class Recorder(Scene):
    def __init__(self, name: str, log: list[str]) -> None:
        self.name = name
        self.log = log

    def on_enter(self) -> None:
        self.log.append(f"{self.name}.enter")

    def on_exit(self) -> None:
        self.log.append(f"{self.name}.exit")

    def on_pause(self) -> None:
        self.log.append(f"{self.name}.pause")

    def on_resume(self) -> None:
        self.log.append(f"{self.name}.resume")

    def handle(self, event: pygame.Event) -> None:
        self.log.append(f"{self.name}.handle")

    def update(self, dt: float) -> None:
        self.log.append(f"{self.name}.update")

    def draw(self, canvas: pygame.Surface, alpha: float) -> None:
        self.log.append(f"{self.name}.draw")


class Overlay(Recorder):
    blocks_update = False
    blocks_draw = False


@pytest.fixture
def log() -> list[str]:
    return []


def test_changes_apply_on_next_update(log: list[str]):
    manager = SceneManager()
    manager.push(Recorder("a", log))
    assert manager.top is None
    assert manager
    manager.update(0.0)
    assert log == ["a.enter", "a.update"]


def test_push_pop_lifecycle(log: list[str]):
    manager = SceneManager()
    a, b = Recorder("a", log), Recorder("b", log)
    manager.push(a)
    manager.push(b)
    manager.apply_pending()
    assert manager.scenes == (a, b)
    assert a.manager is manager
    manager.pop()
    manager.apply_pending()
    assert log == ["a.enter", "a.pause", "b.enter", "b.exit", "a.resume"]
    assert manager.top is a


def test_replace_does_not_resume_scene_below(log: list[str]):
    manager = SceneManager()
    manager.push(Recorder("a", log))
    manager.push(Recorder("b", log))
    manager.apply_pending()
    log.clear()
    manager.replace(Recorder("c", log))
    manager.apply_pending()
    assert log == ["b.exit", "a.pause", "c.enter"]


def test_switch_clears_stack(log: list[str]):
    manager = SceneManager()
    manager.push(Recorder("a", log))
    manager.push(Recorder("b", log))
    manager.apply_pending()
    log.clear()
    c = Recorder("c", log)
    manager.switch(c)
    manager.apply_pending()
    assert log == ["b.exit", "a.exit", "c.enter"]
    assert manager.scenes == (c,)


def test_pop_on_empty_stack_is_harmless():
    manager = SceneManager()
    manager.pop()
    manager.apply_pending()
    assert not manager


def test_overlay_lets_scene_below_update_and_draw(log: list[str]):
    manager = SceneManager()
    manager.push(Recorder("game", log))
    manager.push(Overlay("pause", log))
    manager.apply_pending()
    log.clear()
    manager.update(0.0)
    manager.draw(pygame.Surface((1, 1)), 0.0)
    manager.handle(pygame.Event(pygame.KEYDOWN))
    assert log == ["pause.update", "game.update", "game.draw", "pause.draw", "pause.handle"]


def test_blocking_scene_hides_scenes_below(log: list[str]):
    manager = SceneManager()
    manager.push(Recorder("game", log))
    manager.push(Recorder("menu", log))
    manager.apply_pending()
    log.clear()
    manager.update(0.0)
    manager.draw(pygame.Surface((1, 1)), 0.0)
    assert log == ["menu.update", "menu.draw"]


def test_scene_can_request_changes_during_update(log: list[str]):
    class Launcher(Recorder):
        def update(self, dt: float) -> None:
            super().update(dt)
            self.manager.replace(Recorder("next", self.log))

    manager = SceneManager()
    manager.push(Launcher("launcher", log))
    manager.update(0.0)
    manager.update(0.0)
    assert log == [
        "launcher.enter",
        "launcher.update",
        "launcher.exit",
        "next.enter",
        "next.update",
    ]


def test_close_exits_every_scene_top_first(log: list[str]):
    manager = SceneManager()
    manager.push(Recorder("a", log))
    manager.push(Recorder("b", log))
    manager.apply_pending()
    manager.push(Recorder("c", log))
    log.clear()
    manager.close()
    assert log == ["b.exit", "a.exit"]
    assert not manager
