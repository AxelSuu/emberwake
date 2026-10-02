"""Lore_Hall: a signpost, an Echo, a Lost Light and a Trial door."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from emberwake.engine.physics import Body
from emberwake.engine.scene import SceneManager
from emberwake.engine.world.ldtk import load_project
from emberwake.game import paths
from emberwake.game.areas import LightCensus, load_areas
from emberwake.game.lore import Echo, EchoPlay, Sign, speeches
from emberwake.game.scenes.gameplay import GameplayScene

if TYPE_CHECKING:
    from emberwake.game.context import GameContext

STEP = 1 / 60
ROOM = "Lore_Hall"


def start(ctx: GameContext) -> tuple[SceneManager, GameplayScene]:
    scenes = SceneManager()
    game = GameplayScene(ctx, room=ROOM)
    scenes.push(game)
    scenes.update(STEP)
    return scenes, game


def settle(scenes: SceneManager, ticks: int = 3) -> None:
    for _ in range(ticks):
        scenes.update(STEP)


def stand_at(game: GameplayScene, component: type) -> None:
    for _, body, _ in game.world.query(Body, component):
        game.body.x, game.body.y = body.x, body.y + body.height - game.body.height
        return
    raise AssertionError(component)


def said(game: GameplayScene) -> list[str]:
    return [s.text for s in speeches(game.world, game.ctx.t, game.ctx.settings.controls.keys)]


def test_the_signpost_reads_out_the_current_keys_when_near(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    assert said(game) == []
    stand_at(game, Sign)
    settle(scenes)
    (text,) = said(game)
    assert "[Space]" in text
    game.ctx.settings.controls.keys["jump"] = ["j"]
    assert "[J]" in said(game)[0]


def test_the_speech_bubble_is_drawn_over_the_world(ctx: GameContext) -> None:
    scenes, game = start(ctx)
    stand_at(game, Sign)
    settle(scenes)
    canvas = pygame.Surface(ctx.canvas_size)
    game.draw(canvas, 1.0)
    before = pygame.image.tobytes(canvas, "RGB")
    game.bubbles.draw(canvas, "hello", (100, 100))
    assert pygame.image.tobytes(canvas, "RGB") != before


def use(scenes: SceneManager, key: int = pygame.K_e) -> None:
    scenes.handle(pygame.event.Event(pygame.KEYDOWN, key=key))
    settle(scenes, 2)
    scenes.handle(pygame.event.Event(pygame.KEYUP, key=key))
    settle(scenes, 2)


def plays(game: GameplayScene) -> list[EchoPlay]:
    return [play for _, play in game.world.query(EchoPlay)]


def hear_the_echo(ctx: GameContext) -> tuple[SceneManager, GameplayScene]:
    scenes, game = start(ctx)
    stand_at(game, Echo)
    settle(scenes)
    use(scenes)
    return scenes, game


def test_using_an_echo_plays_its_ghost_and_shows_its_line(ctx: GameContext) -> None:
    scenes, game = hear_the_echo(ctx)
    (play,) = plays(game)
    assert play.ghost is not None
    start_x = play.ghost.body.x
    assert said(game) == [ctx.t("echo.lore_hall")]
    settle(scenes, 60)
    assert play.ghost.body.x > start_x + 20
    game.draw(pygame.Surface(ctx.canvas_size), 1.0)


def test_the_ghost_ends_and_the_line_fades_after_the_hold(ctx: GameContext) -> None:
    scenes, game = hear_the_echo(ctx)
    settle(scenes, 200)
    (play,) = plays(game)
    assert play.ghost is not None
    assert play.ghost.finished
    assert said(game) == [ctx.t("echo.lore_hall")]
    settle(scenes, 200)
    assert plays(game) == []
    assert said(game) == []


def test_an_echo_counts_once_however_often_it_is_heard(ctx: GameContext) -> None:
    scenes, game = hear_the_echo(ctx)
    flags = game.progress.data.flags
    assert flags["echo_lore_hall"] == flags["echoes"] == 1
    assert len(game.toasts) == 1
    settle(scenes, 400)
    use(scenes)
    assert plays(game)
    assert flags["echoes"] == 1
    assert len(game.toasts) <= 1


def test_a_heard_echo_is_saved_and_counts_toward_the_light(ctx: GameContext) -> None:
    _, game = start(ctx)
    levels = load_project(game.world_path).all_levels
    areas = load_areas(paths.content("areas.toml"))
    census = LightCensus(levels, game.spawner.prefabs, areas.light)
    before = census.count(game.progress.data.world)["lab"]
    _, game = hear_the_echo(ctx)
    game.spawner.snapshot_all()
    after = census.count(game.progress.data.world)["lab"]
    assert (after.lit, after.total) == (before.lit + 1, before.total)
