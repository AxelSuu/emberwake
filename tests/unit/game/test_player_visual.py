from __future__ import annotations

from emberwake.game.player.controller import Motor, PlayerState
from emberwake.game.player.kindle import Kindle
from emberwake.game.player.swing import Direction, Swing
from emberwake.game.player.visual import PlayerVisual, anim_state

STEP = 1 / 60


def test_the_lantern_lags_behind_a_start_and_settles() -> None:
    visual, motor = PlayerVisual(), Motor(grounded=True)
    motor.vx = 180.0
    visual.animate(motor, STEP)
    for _ in range(3):
        visual.animate(motor, STEP)
    assert visual.lantern_angle < 0
    for _ in range(600):
        visual.animate(motor, STEP)
    assert abs(visual.lantern_angle) < 0.02


def test_running_takes_steps_and_bobs_standing_breathes() -> None:
    visual, motor = PlayerVisual(), Motor(grounded=True, vx=180.0)
    events = [e for _ in range(60) for e in visual.animate(motor, STEP)]
    assert events.count("step") >= 4
    assert visual.breath == 0
    motor.vx = 0.0
    for _ in range(20):
        visual.animate(motor, STEP)
    assert visual.bob == 0
    assert visual.breath != 0


def test_wall_slides_scrape() -> None:
    visual, motor = PlayerVisual(), Motor(state=PlayerState.WALL_SLIDE)
    events = [e for _ in range(30) for e in visual.animate(motor, STEP)]
    assert "scrape" in events


def test_the_animation_state_follows_what_the_player_does() -> None:
    motor = Motor(grounded=True)
    assert anim_state(motor) == "idle"
    motor.vx = 100
    assert anim_state(motor) == "run"
    motor.grounded, motor.vy = False, -50
    assert anim_state(motor) == "jump"
    motor.vy = 50
    assert anim_state(motor) == "fall"
    assert anim_state(motor, Swing(tick=3, direction=Direction.DOWN)) == "swing_down"
    grounded = Motor(grounded=True)
    assert anim_state(grounded, None, Kindle(ticks=5)) == "kindle"
    assert anim_state(Motor(dead=True)) == "death"
