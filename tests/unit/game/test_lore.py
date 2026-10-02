from __future__ import annotations

from emberwake.engine.core.i18n import load_tables
from emberwake.engine.ecs import World
from emberwake.engine.physics import Body
from emberwake.engine.world.ldtk import load_project
from emberwake.game import paths
from emberwake.game.actions import Action, default_bindings
from emberwake.game.lore import EchoPlay, Recording, Sign, load_echo, sign_text, speeches
from emberwake.game.player.controller import Motor
from emberwake.game.rebind import key_name, labels, rebind
from emberwake.game.strings import load_strings

STRINGS = load_strings("en")
TABLES = load_tables(paths.content("strings"))


def world_with_sign(player_x: float) -> World:
    world = World()
    world.spawn(Body(100, 100, 16, 16), Sign("lore_move"))
    world.spawn(Body(player_x, 100, 10, 20), Motor())
    world.flush()
    return world


def test_a_sign_speaks_only_while_the_player_is_near():
    keys = default_bindings().keys
    assert speeches(world_with_sign(120), STRINGS.t, keys)[0].x == 108
    assert speeches(world_with_sign(200), STRINGS.t, keys) == []


def test_a_dead_player_reads_nothing():
    world = world_with_sign(110)
    for _, motor in world.query(Motor):
        motor.dead = True
    assert speeches(world, STRINGS.t, default_bindings().keys) == []


def test_sign_text_shows_the_first_key_of_each_action():
    keys = default_bindings().keys
    text = sign_text(STRINGS.t, Sign("lore_move"), keys)
    assert "[Left]" in text
    assert "[Right]" in text
    assert "[Space]" in text


def test_sign_text_follows_rebinding():
    keys = default_bindings().keys
    rebind(keys, Action.JUMP, "j")
    assert "[J]" in sign_text(STRINGS.t, Sign("lore_move"), keys)


def test_labels_name_an_unbound_action_with_a_dash():
    keys = default_bindings().keys
    keys["jump"] = []
    assert labels(keys)["jump"] == "-"
    assert key_name("left shift") == "Left Shift"


def test_a_missing_replay_loads_as_none():
    assert load_echo("no_such_echo") is None


def test_an_echo_without_a_replay_still_speaks():
    world = World()
    world.spawn(Body(100, 100, 16, 16), Recording("lore_hall"), EchoPlay(None, 3.0))
    world.flush()
    (speech,) = speeches(world, STRINGS.t, default_bindings().keys)
    assert speech.text == STRINGS.t("echo.lore_hall")


def test_every_sign_and_echo_in_the_world_has_its_content():
    problems = []
    for level in load_project(paths.levels("world.ldtk")).all_levels:
        for entity in level.entities():
            ident = entity.field("Id") or entity.field("Text")
            if entity.identifier == "Echo":
                if load_echo(ident) is None:
                    problems.append(f"{level.identifier}: no replay {ident}")
                key = f"echo.{ident}"
            elif entity.identifier == "Signpost":
                key = f"sign.{ident}"
            else:
                continue
            problems += [
                f"{level.identifier}: no {language} string {key}"
                for language, table in TABLES.items()
                if key not in table
            ]
    assert problems == []
