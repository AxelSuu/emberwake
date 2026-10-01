"""Assist options, game speed and cosmetics, applied in a real room and from the settings screen."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pygame

from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.engine.ui import ScrollList, Selector, Toggle
from emberwake.game.combat import Health
from emberwake.game.data.settings import SETTINGS_KEY
from emberwake.game.enemies import Brain
from emberwake.game.light import Ember
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.scenes.settings import SettingsScene

if TYPE_CHECKING:
    from collections.abc import Callable

    from emberwake.game.context import GameContext

STEP = 1 / 60


def start(ctx: GameContext, room: str = "Test_Room") -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx, room=room)
    scenes.push(game)
    scenes.update(STEP)
    return scenes, game


def test_invulnerable_ignores_enemy_contact(ctx: GameContext) -> None:
    ctx.settings.assist.invulnerable = True
    scenes, game = start(ctx, "Enemy_Yard")
    for _, body, brain in game.world.query(Body, Brain):
        if brain.kind == "clockrat":
            game.body.x, game.body.y = body.x + 3, body.y - 4
    for _ in range(30):
        scenes.update(STEP)
    assert game.world.get(game.player, Health).current == game.feel.enemies.player_hp


def test_without_the_option_contact_hurts(ctx: GameContext) -> None:
    scenes, game = start(ctx, "Enemy_Yard")
    for _, body, brain in game.world.query(Body, Brain):
        if brain.kind == "clockrat":
            game.body.x, game.body.y = body.x + 3, body.y - 4
    for _ in range(30):
        scenes.update(STEP)
    assert game.world.get(game.player, Health).current < game.feel.enemies.player_hp


def test_no_ember_drain_keeps_the_ember_full(ctx: GameContext) -> None:
    ctx.settings.assist.no_ember_drain = True
    scenes, game = start(ctx)
    for _ in range(300):
        scenes.update(STEP)
    assert game.world.get(game.player, Ember).current > game.feel.light.ember_max - 1


def test_infinite_dashes_refill_after_a_dash(ctx: GameContext) -> None:
    ctx.settings.assist.infinite_dashes = True
    scenes, game = start(ctx)
    game.motor.dash_charges = 0
    scenes.update(STEP)
    assert game.motor.dash_charges >= 1


def test_half_speed_halves_the_simulation(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    before = game.clock
    for _ in range(60):
        scenes.update(STEP)
    full = game.clock - before
    ctx.settings.assist.game_speed = 0.5
    game.on_resume()
    before = game.clock
    for _ in range(60):
        scenes.update(STEP)
    assert abs((game.clock - before) - full / 2) < 0.05


def test_a_skin_and_lantern_color_reach_the_game(ctx: GameContext) -> None:
    ctx.settings.cosmetics.skin = "moss"
    ctx.settings.cosmetics.lantern = "mint"
    _, game = start(ctx)
    assert game.glow == (0x30, 0xE1, 0xB9)
    image = game.sprite.image(1, 1.0, 1.0)
    assert tuple(image.get_at((4, 18)))[:3] == (0x23, 0x90, 0x63)


def change(widget: Toggle | Selector, value: int) -> None:
    callback: Callable[[Any], None] | None = widget.on_change
    assert callback is not None
    callback(value)


def test_the_settings_screen_changes_and_saves_assist_and_cosmetics(ctx: GameContext) -> None:
    scenes = SceneManager()
    scene = SettingsScene(ctx)
    scenes.push(scene)
    scenes.update(STEP)
    inner = scene.ui.root.children[1]
    assert isinstance(inner, ScrollList)
    toggles = {r.text: r for r in inner.children if isinstance(r, Toggle)}
    selectors = {r.text: r for r in inner.children if isinstance(r, Selector)}
    assert "Enemies cannot hurt you" in toggles
    assert "Skin" in selectors
    change(toggles["Enemies cannot hurt you"], True)
    change(selectors["Skin"], 2)
    change(selectors["Game speed"], 2)
    change(selectors["Lantern color"], 3)
    assert ctx.settings.assist.invulnerable
    assert ctx.settings.assist.game_speed == 0.5
    assert ctx.settings.cosmetics.skin == "moss"
    assert ctx.settings.cosmetics.lantern == "violet"
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    scenes.update(STEP)
    saved = json.loads(ctx.storage.read(SETTINGS_KEY) or "{}")["data"]
    assert saved["assist"]["game_speed"] == 0.5
    assert saved["cosmetics"]["skin"] == "moss"
