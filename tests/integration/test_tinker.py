"""The Tinker: talk to him, hear the returning greeting, and buy upgrades with embers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.game.combat import Health
from emberwake.game.data.save import load_slot
from emberwake.game.dialogue import Npc
from emberwake.game.light import Ember
from emberwake.game.scenes.dialogue import DialogueScene, ShopScene
from emberwake.game.scenes.gameplay import GameplayScene
from emberwake.game.shop import SPENT

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60


def key(scenes: SceneManager, code: int) -> None:
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=code))
    scenes.handle(pygame.event.Event(pygame.KEYUP, key=code))
    scenes.update(STEP)


def at_the_tinker(ctx: GameContext, room: str = "Enemy_Yard") -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx, room=room)
    scenes.push(game)
    scenes.update(STEP)
    for _, body, _npc in game.world.query(Body, Npc):
        game.body.x, game.body.y = body.x + 2, body.y - 4
    for _ in range(5):
        scenes.update(STEP)
    return scenes, game


def talk(scenes: SceneManager) -> DialogueScene:
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e))
    scenes.update(STEP)
    scenes.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_e))
    scenes.update(STEP)
    scenes.update(STEP)
    assert isinstance(scenes.top, DialogueScene)
    return scenes.top


def pick(scenes: SceneManager, text: str) -> None:
    scene = scenes.top
    assert isinstance(scene, DialogueScene | ShopScene)
    for _ in range(8):
        current = scene.ui.root.current
        if current is not None and current.text.startswith(text):
            key(scenes, pygame.K_RETURN)
            return
        key(scenes, pygame.K_DOWN)
    msg = f"no row {text!r}"
    raise AssertionError(msg)


def test_interacting_starts_a_conversation(ctx: GameContext) -> None:
    scenes, game = at_the_tinker(ctx)
    scene = talk(scenes)
    assert scene.runner.text == "dialogue.tinker.hello"
    pick(scenes, "Goodbye")
    assert scenes.top is game
    assert game.progress.data.flags["met_tinker"] == 1


def test_a_second_visit_greets_you_back(ctx: GameContext) -> None:
    scenes, _ = at_the_tinker(ctx)
    talk(scenes)
    pick(scenes, "Goodbye")
    scene = talk(scenes)
    assert scene.runner.text == "dialogue.tinker.welcome_back"


def test_the_story_choice_branches_and_continues(ctx: GameContext) -> None:
    scenes, game = at_the_tinker(ctx)
    talk(scenes)
    pick(scenes, "What happened")
    assert game.progress.data.flags["tinker_told_story"] == 1
    scene = scenes.top
    assert isinstance(scene, DialogueScene)
    assert scene.runner.text == "dialogue.tinker.city"
    key(scenes, pygame.K_RETURN)
    assert scene.runner.text == "dialogue.tinker.welcome_back"


def test_buying_a_health_upgrade_raises_the_maximum_at_once(ctx: GameContext) -> None:
    scenes, game = at_the_tinker(ctx)
    game.progress.data.stats.embers = 25
    base = game.world.get(game.player, Health).max
    talk(scenes)
    pick(scenes, "What do you sell")
    assert isinstance(scenes.top, ShopScene)
    pick(scenes, "Tougher cloak")
    assert game.progress.data.flags["up_hp"] == 1
    assert game.progress.data.flags[SPENT] == 10
    key(scenes, pygame.K_ESCAPE)
    key(scenes, pygame.K_ESCAPE)
    while scenes.top is not game:
        key(scenes, pygame.K_ESCAPE)
    health = game.world.get(game.player, Health)
    assert health.max == base + 1
    assert health.current == base + 1
    assert game.progress.data.flags["up_hp"] == 1


def test_an_oil_upgrade_raises_the_ember_capacity(ctx: GameContext) -> None:
    scenes, game = at_the_tinker(ctx)
    game.progress.data.stats.embers = 20
    talk(scenes)
    pick(scenes, "What do you sell")
    pick(scenes, "Lantern oil")
    while scenes.top is not game:
        key(scenes, pygame.K_ESCAPE)
    ember = game.world.get(game.player, Ember)
    assert ember.max == game.feel.light.ember_max + 25


def test_an_unaffordable_item_cannot_be_bought_and_purchases_are_saved(ctx: GameContext) -> None:
    scenes, game = at_the_tinker(ctx)
    game.progress.slot = ctx.slot
    game.progress.data.stats.embers = 9
    talk(scenes)
    pick(scenes, "What do you sell")
    shop = scenes.top
    assert isinstance(shop, ShopScene)
    assert not shop.buttons["hp"].enabled
    game.progress.data.stats.embers = 100
    shop._refresh()
    pick(scenes, "Tougher cloak")
    saved = load_slot(ctx.storage, ctx.slot)
    assert saved is not None
    assert saved.flags["up_hp"] == 1


def test_meeting_the_tinker_gives_flares_once(ctx: GameContext) -> None:
    scenes, game = at_the_tinker(ctx)
    assert not game.loadout.has("flare")
    talk(scenes)
    assert game.loadout.has("flare")
    assert game.toasts
    pick(scenes, "Goodbye")
    talk(scenes)
    assert game.progress.data.abilities.count("flare") == 1
