"""Widgets and containers with focus navigation.

A `Container` keeps one focused child and moves it with up and down; left, right and accept go
to the focused child. Focus highlights ease in and out (`Widget.glow`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

import pygame

from emberwake.engine.core.mathx import approach, clamp
from emberwake.engine.input.mapper import BUTTONS
from emberwake.engine.ui.nav import Nav

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from emberwake.engine.ui.theme import Theme

BUTTON_NAMES = {code: name for name, code in BUTTONS.items()}
"""Gamepad button code -> the name bindings use."""


class Widget:
    """Base: a rect, focus state and the hooks containers call."""

    focusable = False
    text = ""
    extra = 0
    """Room beside the text for the widget's value, in px."""

    def __init__(self) -> None:
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.focused = False
        self.enabled = True
        self.glow = 0.0
        """0 to 1: how focused it looks right now."""

    @property
    def can_focus(self) -> bool:
        """Whether focus can land on it."""
        return self.focusable and self.enabled

    @property
    def capturing(self) -> bool:
        """Whether it wants raw events instead of navigation (see `KeybindField`)."""
        return False

    def preferred(self, theme: Theme) -> tuple[int, int]:
        """Width and height it would like."""
        return theme.render(self.text).get_width() + self.extra + 12, theme.row

    def update(self, dt: float, theme: Theme) -> None:
        """Ease the focus highlight."""
        self.glow = approach(self.glow, 1.0 if self.focused else 0.0, theme.tween * dt)

    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        """Draw within `rect`."""

    def navigate(self, nav: Nav) -> bool:
        """React to left, right or accept; return whether it did anything."""
        return False

    def capture(self, event: pygame.Event) -> bool:
        """Offer a raw event to a capturing widget; return whether it was used."""
        return False

    def _row(self, surface: pygame.Surface, theme: Theme) -> None:
        """The focus fill shared by interactive rows."""
        if self.glow > 0:
            fill = theme.color("panel").lerp(theme.color("focus"), self.glow)
            surface.fill(fill, self.rect)
            surface.fill(theme.color("accent"), (self.rect.x, self.rect.y, 2, self.rect.height))

    def _text(
        self,
        surface: pygame.Surface,
        theme: Theme,
        text: str,
        color: str,
        *,
        right: bool = False,
    ) -> None:
        image = theme.render(text, color if self.enabled else "dim")
        x = self.rect.right - image.get_width() - 4 if right else self.rect.x + 6
        surface.blit(image, (x, self.rect.centery - image.get_height() // 2))


class Label(Widget):
    """Static text."""

    def __init__(self, text: str, *, dim: bool = False) -> None:
        super().__init__()
        self.text, self.dim = text, dim

    @override
    def preferred(self, theme: Theme) -> tuple[int, int]:
        return theme.render(self.text).get_width() + 8, theme.row

    @override
    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        self._text(surface, theme, self.text, "dim" if self.dim else "text")


class Button(Widget):
    """Calls `on_press` when accepted."""

    focusable = True

    def __init__(self, text: str, on_press: Callable[[], None]) -> None:
        super().__init__()
        self.text, self.on_press = text, on_press

    @override
    def navigate(self, nav: Nav) -> bool:
        if nav is Nav.ACCEPT:
            self.on_press()
            return True
        return False

    @override
    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        self._row(surface, theme)
        self._text(surface, theme, self.text, "accent" if self.glow > 0.5 else "text")


class Toggle(Widget):
    """A boolean; accept, left or right flips it."""

    focusable = True
    extra = 36

    def __init__(
        self, text: str, value: bool = False, on_change: Callable[[bool], None] | None = None
    ) -> None:
        super().__init__()
        self.text, self.value, self.on_change = text, value, on_change

    @override
    def navigate(self, nav: Nav) -> bool:
        if nav not in (Nav.ACCEPT, Nav.LEFT, Nav.RIGHT):
            return False
        self.value = not self.value
        if self.on_change:
            self.on_change(self.value)
        return True

    @override
    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        self._row(surface, theme)
        self._text(surface, theme, self.text, "text")
        self._text(surface, theme, "on" if self.value else "off", "accent", right=True)


class Selector(Widget):
    """One of several options; left and right (or accept) step through them, wrapping."""

    focusable = True
    extra = 72

    def __init__(
        self,
        text: str,
        options: Sequence[str],
        index: int = 0,
        on_change: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__()
        self.text, self.options, self.index, self.on_change = text, list(options), index, on_change

    @property
    def value(self) -> str:
        """The chosen option."""
        return self.options[self.index]

    @override
    def navigate(self, nav: Nav) -> bool:
        step = {Nav.LEFT: -1, Nav.RIGHT: 1, Nav.ACCEPT: 1}.get(nav)
        if step is None or not self.options:
            return False
        self.index = (self.index + step) % len(self.options)
        if self.on_change:
            self.on_change(self.index)
        return True

    @override
    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        self._row(surface, theme)
        self._text(surface, theme, self.text, "text")
        self._text(surface, theme, f"< {self.value} >", "accent", right=True)


class Slider(Widget):
    """A number in a range; left and right step it by `step`."""

    focusable = True
    BAR = 40
    extra = BAR + 8

    def __init__(  # noqa: PLR0917
        self,
        text: str,
        value: float = 0.5,
        low: float = 0.0,
        high: float = 1.0,
        step: float = 0.1,
        on_change: Callable[[float], None] | None = None,
    ) -> None:
        super().__init__()
        self.text, self.low, self.high, self.step = text, low, high, step
        self.value, self.on_change = value, on_change

    @override
    def navigate(self, nav: Nav) -> bool:
        direction = {Nav.LEFT: -1, Nav.RIGHT: 1}.get(nav)
        if direction is None:
            return False
        stepped = round((self.value + direction * self.step) / self.step) * self.step
        new = clamp(stepped, self.low, self.high)
        if new != self.value:
            self.value = new
            if self.on_change:
                self.on_change(new)
        return True

    @override
    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        self._row(surface, theme)
        self._text(surface, theme, self.text, "text")
        bar = pygame.Rect(0, 0, self.BAR, 4)
        bar.midright = (self.rect.right - 6, self.rect.centery)
        pygame.draw.rect(surface, theme.color("border"), bar, 1)
        span = max(self.high - self.low, 1e-9)
        fill = round((bar.width - 2) * (self.value - self.low) / span)
        surface.fill(theme.color("accent"), (bar.x + 1, bar.y + 1, fill, bar.height - 2))


class KeybindField(Widget):
    """A binding shown as text; accept starts listening, and the next key or button replaces it."""

    focusable = True
    extra = 80

    def __init__(
        self, text: str, binding: str, on_bind: Callable[[str], None] | None = None
    ) -> None:
        super().__init__()
        self.text, self.binding, self.on_bind = text, binding, on_bind
        self.listening = False

    @property
    @override
    def capturing(self) -> bool:
        return self.listening

    @override
    def navigate(self, nav: Nav) -> bool:
        if nav is Nav.ACCEPT:
            self.listening = True
            return True
        return False

    @override
    def capture(self, event: pygame.Event) -> bool:
        if not self.listening:
            return False
        if event.type == pygame.KEYDOWN:
            self.listening = False
            if event.key != pygame.K_ESCAPE:
                self._bind(pygame.key.name(event.key))
            return True
        if event.type == pygame.CONTROLLERBUTTONDOWN:
            self.listening = False
            self._bind(BUTTON_NAMES.get(event.button, f"button {event.button}"))
            return True
        return False

    def _bind(self, name: str) -> None:
        self.binding = name
        if self.on_bind:
            self.on_bind(name)

    @override
    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        self._row(surface, theme)
        self._text(surface, theme, self.text, "text")
        shown, color = ("press a key", "accent") if self.listening else (self.binding, "text")
        self._text(surface, theme, shown, color, right=True)


class Container(Widget):
    """Children stacked top to bottom with one focused at a time."""

    def __init__(self, children: Sequence[Widget] = (), *, wrap: bool = True) -> None:
        super().__init__()
        self.children = list(children)
        self.wrap = wrap
        self.index = -1
        self.focus_first()

    @property
    @override
    def focusable(self) -> bool:  # type: ignore[override]
        return any(child.can_focus for child in self.children)

    @property
    def current(self) -> Widget | None:
        """The focused child, if any."""
        return self.children[self.index] if 0 <= self.index < len(self.children) else None

    @property
    @override
    def capturing(self) -> bool:
        return self.current is not None and self.current.capturing

    def add(self, child: Widget) -> None:
        """Append a child, focusing it if nothing else can be."""
        self.children.append(child)
        if self.current is None:
            self.focus_first()

    def focus_first(self) -> None:
        """Focus the first child that can take it."""
        self.index = next((i for i, c in enumerate(self.children) if c.can_focus), -1)

    @override
    def preferred(self, theme: Theme) -> tuple[int, int]:
        sizes = [child.preferred(theme) for child in self.children]
        width = max((w for w, _ in sizes), default=0)
        height = sum(h for _, h in sizes) + theme.gap * max(len(sizes) - 1, 0)
        return width + 2 * theme.pad, height + 2 * theme.pad

    def layout(self, rect: pygame.Rect, theme: Theme) -> None:
        """Place the children inside `rect`, padded."""
        self.rect = pygame.Rect(rect)
        y = rect.y + theme.pad
        for child in self.children:
            height = child.preferred(theme)[1]
            child.rect = pygame.Rect(rect.x + theme.pad, y, rect.width - 2 * theme.pad, height)
            if isinstance(child, Container):
                child.layout(child.rect, theme)
            y += height + theme.gap

    @override
    def update(self, dt: float, theme: Theme) -> None:
        super().update(dt, theme)
        for i, child in enumerate(self.children):
            child.focused = self.focused and i == self.index
            child.update(dt, theme)

    @override
    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        for child in self.children:
            child.draw(surface, theme)

    @override
    def navigate(self, nav: Nav) -> bool:
        if nav in (Nav.UP, Nav.DOWN):
            return self._move(-1 if nav is Nav.UP else 1)
        current = self.current
        return current is not None and current.navigate(nav)

    @override
    def capture(self, event: pygame.Event) -> bool:
        current = self.current
        return current is not None and current.capture(event)

    def _move(self, step: int) -> bool:
        current = self.current
        if isinstance(current, Container) and current.navigate(Nav.DOWN if step > 0 else Nav.UP):
            return True
        count = len(self.children)
        i = self.index
        for _ in range(count):
            i += step
            if not 0 <= i < count:
                if not self.wrap:
                    return False
                i %= count
            if self.children[i].can_focus:
                if i == self.index:
                    return False
                self.index = i
                return True
        return False


class Panel(Container):
    """A framed container, sized to fit its children."""

    @override
    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        surface.fill(theme.color("panel"), self.rect)
        pygame.draw.rect(surface, theme.color("border"), self.rect, 1)
        super().draw(surface, theme)


class ScrollList(Container):
    """A container showing `rows` of its children at a time, scrolling to keep focus visible."""

    def __init__(
        self, children: Sequence[Widget] = (), rows: int = 5, *, wrap: bool = False
    ) -> None:
        super().__init__(children, wrap=wrap)
        self.rows = rows
        self.top = 0.0
        """Scroll position in px, easing toward the focused child."""

    @override
    def preferred(self, theme: Theme) -> tuple[int, int]:
        width = max((child.preferred(theme)[0] for child in self.children), default=0)
        return width + 2 * theme.pad, self.rows * (theme.row + theme.gap) + 2 * theme.pad

    @override
    def layout(self, rect: pygame.Rect, theme: Theme) -> None:
        super().layout(rect, theme)
        self._base = [child.rect.copy() for child in self.children]

    @override
    def update(self, dt: float, theme: Theme) -> None:
        super().update(dt, theme)
        base = getattr(self, "_base", None)
        if not base:
            return
        view = self.rect.height - 2 * theme.pad
        if self.current is not None:
            item = base[self.index]
            origin = self.rect.y + theme.pad
            target = clamp(self.top, item.bottom - origin - view, item.y - origin)
            rate = max(abs(target - self.top), 1.0) * theme.tween
            self.top = approach(self.top, target, rate * dt)
        for child, rect in zip(self.children, base, strict=True):
            child.rect = rect.move(0, -round(self.top))

    @override
    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        clip = self.rect.inflate(-2 * theme.pad, -2 * theme.pad)
        previous = surface.get_clip()
        surface.set_clip(clip)
        for child in self.children:
            if child.rect.colliderect(clip):
                child.draw(surface, theme)
        surface.set_clip(previous)
