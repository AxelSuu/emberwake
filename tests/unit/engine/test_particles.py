from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pytest

from emberwake.engine.core.serde import SerdeError
from emberwake.engine.render.particles import EmitterSpec, ParticleSystem, load_emitters
from emberwake.game import paths

if TYPE_CHECKING:
    from pathlib import Path

BLACK = pygame.Color("black")


def spec(  # noqa: PLR0917
    count: int = 4,
    speed: tuple[float, float] = (10.0, 10.0),
    angle: tuple[float, float] = (0.0, 0.0),
    life: tuple[float, float] = (1.0, 1.0),
    gravity: float = 0.0,
    drag: float = 0.0,
    size: int = 2,
    colors: list[str] | None = None,
) -> EmitterSpec:
    return EmitterSpec(count, speed, angle, life, gravity, drag, size, colors or ["#ffffff"])


def test_a_burst_launches_count_particles_that_move_and_expire():
    system = ParticleSystem()
    system.burst(spec(), 0, 0)
    assert system.count == 4
    system.update(0.5)
    assert system._x[0] == pytest.approx(5)
    system.update(0.6)
    assert system.count == 0


def test_gravity_pulls_down_and_drag_slows():
    system = ParticleSystem()
    system.burst(spec(count=1, gravity=100, drag=1.0), 0, 0)
    system.update(0.1)
    assert system._vy[0] == pytest.approx(10)
    assert system._vx[0] == pytest.approx(9)


def test_a_full_pool_drops_the_overflow():
    system = ParticleSystem(capacity=6)
    system.burst(spec(count=4), 0, 0)
    system.burst(spec(count=4), 0, 0)
    assert (system.count, system.dropped) == (6, 2)
    system.update(2.0)
    system.burst(spec(count=4), 0, 0)
    assert (system.count, system.dropped) == (4, 2)


def test_removing_keeps_the_survivors_intact():
    system = ParticleSystem()
    system.burst(spec(count=1, life=(0.1, 0.1), speed=(0.0, 0.0)), 1, 1)
    system.burst(spec(count=1, life=(1.0, 1.0), speed=(0.0, 0.0)), 7, 9)
    system.update(0.2)
    assert system.count == 1
    assert (system._x[0], system._y[0]) == (7, 9)


def test_same_seed_gives_the_same_burst():
    a, b = ParticleSystem(seed=3), ParticleSystem(seed=3)
    for system in (a, b):
        system.burst(spec(count=8, angle=(0.0, 360.0), speed=(10.0, 50.0)), 0, 0)
    assert a._x[:8] == b._x[:8]
    assert a._vy[:8] == b._vy[:8]


def test_color_steps_from_young_to_old_and_follows_the_camera():
    system = ParticleSystem()
    system.burst(
        spec(count=1, speed=(0.0, 0.0), life=(1.0, 1.0), size=2, colors=["#ff0000", "#0000ff"]),
        10,
        10,
    )
    target = pygame.Surface((20, 20))
    target.fill(BLACK)
    system.draw(target, (5, 5))
    assert target.get_at((5, 5)) == pygame.Color("#ff0000")
    assert target.get_at((7, 7)) == BLACK
    system.update(0.6)
    target.fill(BLACK)
    system.draw(target, (5, 5))
    assert target.get_at((5, 5)) == pygame.Color("#0000ff")


def test_loads_emitters_from_toml_with_defaults(tmp_path: Path):
    path = tmp_path / "p.toml"
    path.write_text('[puff]\ncount = 3\nangle = [250, 290]\ncolors = ["#ffffff", "#000000"]\n')
    emitters = load_emitters(path)
    assert emitters["puff"].count == 3
    assert emitters["puff"].angle == (250, 290)
    assert emitters["puff"].speed == (40.0, 130.0)
    path.write_text('[puff]\ncount = "many"\n')
    with pytest.raises(SerdeError):
        load_emitters(path)


def test_the_shipped_emitters_load():
    assert "beacon_burst" in load_emitters(paths.content("particles.toml"))
