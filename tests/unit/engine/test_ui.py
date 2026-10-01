from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pygame
import pytest

from emberwake.engine.ui import (
    Button,
    Container,
    KeybindField,
    Label,
    Nav,
    Navigator,
    Panel,
    ScrollList,
    Selector,
    Slider,
    Theme,
    Toggle,
    UiRoot,
    load_theme,
)
from emberwake.engine.ui.nav import DELAY, INTERVAL

THEME = Theme()


@pytest.fixture(autouse=True, scope="module")
def fonts():
    pygame.font.init()


def key(code: int, kind: int = pygame.KEYDOWN) -> pygame.Event:
    return pygame.event.Event(kind, key=code)


def button(code: int, kind: int = pygame.CONTROLLERBUTTONDOWN) -> pygame.Event:
    return pygame.event.Event(kind, button=code)


class Menu(NamedTuple):
    panel: Panel
    play: Button
    shake: Slider
    crt: Toggle
    lang: Selector
    pressed: list[str]


def menu() -> Menu:
    pressed: list[str] = []
    play = Button("Play", lambda: pressed.append("play"))
    shake, crt, lang = Slider("Shake", 0.5), Toggle("CRT"), Selector("Language", ["en", "sv"])
    quit_ = Button("Quit", lambda: pressed.append("quit"))
    panel = Panel([Label("Settings"), play, shake, crt, lang, quit_])
    return Menu(panel, play, shake, crt, lang, pressed)


def test_focus_starts_on_the_first_focusable_and_skips_labels_and_disabled():
    m = menu()
    assert m.panel.current is m.play
    m.shake.enabled = False
    m.panel.navigate(Nav.DOWN)
    assert m.panel.current is m.crt
    m.panel.navigate(Nav.UP)
    assert m.panel.current is m.play


def test_up_and_down_wrap_unless_told_not_to():
    panel = menu().panel
    panel.navigate(Nav.UP)
    assert panel.current is panel.children[-1]
    panel.navigate(Nav.DOWN)
    assert panel.current is panel.children[1]
    flat = Panel([Button("a", print), Button("b", print)], wrap=False)
    assert not flat.navigate(Nav.UP)
    assert flat.navigate(Nav.DOWN)
    assert not flat.navigate(Nav.DOWN)


def test_widgets_react_to_left_right_and_accept():
    m = menu()
    panel = m.panel
    panel.navigate(Nav.ACCEPT)
    assert m.pressed == ["play"]
    panel.navigate(Nav.DOWN)
    panel.navigate(Nav.RIGHT)
    panel.navigate(Nav.RIGHT)
    assert m.shake.value == pytest.approx(0.7)
    for _ in range(10):
        panel.navigate(Nav.RIGHT)
    assert m.shake.value == 1.0
    panel.navigate(Nav.DOWN)
    panel.navigate(Nav.ACCEPT)
    assert m.crt.value is True
    panel.navigate(Nav.DOWN)
    panel.navigate(Nav.LEFT)
    assert m.lang.value == "sv"


def test_callbacks_fire_with_the_new_value():
    seen: list[object] = []
    panel = Panel(
        [Toggle("t", on_change=seen.append), Selector("s", ["a", "b"], on_change=seen.append)]
    )
    panel.navigate(Nav.ACCEPT)
    panel.navigate(Nav.DOWN)
    panel.navigate(Nav.RIGHT)
    assert seen == [True, 1]


def test_nested_containers_pass_up_and_down_through_before_leaving():
    inner = Container([Button("a", print), Button("b", print)], wrap=False)
    outer = Panel([Button("top", print), inner, Button("bottom", print)])
    outer.navigate(Nav.DOWN)
    assert outer.current is inner
    assert inner.index == 0
    outer.navigate(Nav.DOWN)
    assert inner.index == 1
    outer.navigate(Nav.DOWN)
    assert outer.current is not inner


def test_focus_glow_eases_in_and_out():
    m = menu()
    root = UiRoot(m.panel, THEME)
    root.update(0.01)
    assert 0 < m.play.glow < 1
    root.update(1.0)
    assert m.play.glow == 1.0
    root.press(Nav.DOWN)
    root.update(0.01)
    assert 0 < m.play.glow < 1
    assert m.shake.glow > 0


def test_keybind_field_captures_the_next_key_and_escape_cancels():
    bound: list[str] = []
    field = KeybindField("Jump", "space", bound.append)
    root = UiRoot(Panel([field, Button("ok", print)]), THEME)
    root.handle(key(pygame.K_RETURN))
    assert field.listening
    root.handle(key(pygame.K_DOWN))
    assert bound == ["down"]
    assert field.binding == "down"
    assert not field.listening
    root.handle(key(pygame.K_RETURN))
    root.handle(key(pygame.K_ESCAPE))
    assert (field.binding, field.listening) == ("down", False)
    root.handle(key(pygame.K_RETURN))
    root.handle(button(pygame.CONTROLLER_BUTTON_Y))
    assert field.binding == "y"


def test_root_routes_events_and_back():
    backs: list[int] = []
    m = menu()
    root = UiRoot(m.panel, THEME, lambda: backs.append(1))
    root.handle(key(pygame.K_RETURN))
    root.handle(button(pygame.CONTROLLER_BUTTON_DPAD_DOWN))
    root.handle(key(pygame.K_ESCAPE))
    root.handle(button(pygame.CONTROLLER_BUTTON_B))
    assert m.pressed == ["play"]
    assert m.panel.current is m.shake
    assert len(backs) == 2


def test_navigator_repeats_a_held_direction_and_stops_on_release():
    nav = Navigator()
    assert nav.handle(key(pygame.K_DOWN)) is Nav.DOWN
    assert nav.update(DELAY / 2) is None
    assert nav.update(DELAY / 2) is Nav.DOWN
    assert nav.update(INTERVAL) is Nav.DOWN
    nav.handle(key(pygame.K_DOWN, pygame.KEYUP))
    assert nav.update(1.0) is None
    assert nav.handle(key(pygame.K_RETURN)) is Nav.ACCEPT
    assert nav.update(1.0) is None
    assert nav.handle(key(pygame.K_F1)) is None


def test_navigator_treats_the_stick_like_a_dpad_with_hysteresis():
    nav = Navigator()
    axis = pygame.CONTROLLER_AXIS_LEFTY

    def tilt(value: float) -> Nav | None:
        return nav.handle(pygame.event.Event(pygame.CONTROLLERAXISMOTION, axis=axis, value=value))

    assert tilt(0.4) is None
    assert tilt(0.8) is Nav.DOWN
    assert tilt(0.9) is None
    assert tilt(0.0) is None
    assert tilt(-0.8) is Nav.UP


def test_scroll_list_keeps_the_focused_row_in_view():
    rows = [Button(f"item {i}", print) for i in range(12)]
    lst = ScrollList(rows, rows=3)
    root = UiRoot(Panel([lst]), THEME)
    root.center((320, 180))
    for _ in range(8):
        root.press(Nav.DOWN)
    for _ in range(60):
        root.update(1 / 60)
    view = lst.rect.inflate(-2 * THEME.pad, -2 * THEME.pad)
    assert lst.index == 8
    assert view.contains(rows[8].rect)
    assert not view.colliderect(rows[0].rect)


def test_layout_stacks_children_and_draws_without_error():
    panel = menu().panel
    root = UiRoot(panel, THEME)
    root.center((320, 180))
    ys = [child.rect.y for child in panel.children]
    assert ys == sorted(ys)
    assert panel.rect.center == (160, 90)
    canvas = pygame.Surface((320, 180))
    canvas.fill("black")
    root.update(1.0)
    root.draw(canvas)
    assert canvas.get_at(panel.rect.center) != pygame.Color("black")


def test_theme_loads_from_toml_and_the_shipped_one_parses(tmp_path: Path):
    path = tmp_path / "ui.toml"
    path.write_text('accent = "#ff0000"\nrow = 20\n')
    theme = load_theme(path)
    assert (theme.color("accent"), theme.row, theme.pad) == (pygame.Color("#ff0000"), 20, 6)
    assert load_theme(Path("content/ui.toml")) == Theme()
