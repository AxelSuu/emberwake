from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pytest

from emberwake.engine.render.rig import (
    Bone,
    Key,
    Part,
    Rig,
    RigClip,
    RotSpriteCache,
    load_rig,
    rotsprite,
)

if TYPE_CHECKING:
    from pathlib import Path


def arm() -> Rig:
    return Rig(
        [
            Bone("torso", offset=(50, 50)),
            Bone("upper", "torso", offset=(10, 0)),
            Bone("lower", "upper", offset=(10, 0)),
        ]
    )


def test_rest_pose_stacks_offsets() -> None:
    t = arm().solve()
    assert (t["torso"].x, t["torso"].y) == (50, 50)
    assert (t["lower"].x, t["lower"].y, t["lower"].angle) == (70, 50, 0)


def test_rotating_a_parent_swings_its_children_clockwise_on_screen() -> None:
    t = arm().solve({"torso": 90})
    assert (round(t["upper"].x), round(t["upper"].y)) == (50, 60)
    assert (round(t["lower"].x), round(t["lower"].y)) == (50, 70)
    assert t["lower"].angle == 90


def test_angles_add_down_the_chain() -> None:
    t = arm().solve({"torso": 90, "upper": -90})
    assert t["lower"].angle == 0
    assert (round(t["lower"].x), round(t["lower"].y)) == (60, 60)


def test_rig_validation() -> None:
    with pytest.raises(ValueError, match="parent"):
        Rig([Bone("a", "b"), Bone("b")])
    with pytest.raises(ValueError, match="duplicate"):
        Rig([Bone("a"), Bone("a")])
    with pytest.raises(ValueError, match="unknown bone"):
        Rig([Bone("a")], [Part("x", "img")])


def test_clip_interpolates_and_loops() -> None:
    clip = RigClip(1.0, {"arm": [Key(0, 0), Key(0.5, 40), Key(1.0, 0)]})
    assert clip.sample(0.25)["arm"] == pytest.approx(20)
    assert clip.sample(0.5)["arm"] == pytest.approx(40)
    assert clip.sample(1.25)["arm"] == pytest.approx(20)


def test_clip_without_loop_holds_the_end() -> None:
    clip = RigClip(1.0, {"a": [Key(0, 0), Key(1, 90)]}, loop=False)
    assert clip.sample(5)["a"] == 90
    assert clip.sample(-1)["a"] == 0


def test_interpolation_takes_the_short_way_round() -> None:
    clip = RigClip(1.0, {"a": [Key(0, 350), Key(1, 10)]}, loop=False)
    assert clip.sample(0.5)["a"] == pytest.approx(360)


def test_clip_validation() -> None:
    with pytest.raises(ValueError, match="duration"):
        RigClip(0)
    with pytest.raises(ValueError, match="sorted"):
        RigClip(1, {"a": [Key(1, 0), Key(0, 0)]})


def sprite() -> pygame.Surface:
    surface = pygame.Surface((8, 4), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))
    surface.fill((255, 0, 0, 255), (0, 0, 4, 4))
    surface.fill((0, 255, 0, 255), (4, 0, 4, 4))
    return surface


def colors(surface: pygame.Surface) -> set[tuple[int, ...]]:
    w, h = surface.get_size()
    seen = {tuple(surface.get_at((x, y))) for x in range(w) for y in range(h)}
    return {c for c in seen if c[3] > 0}


def test_rotsprite_keeps_a_hard_palette() -> None:
    out = rotsprite(sprite(), 30)
    assert colors(out) <= {(255, 0, 0, 255), (0, 255, 0, 255)}
    assert out.get_height() > 4


def test_rotsprite_quarter_turn_is_exact() -> None:
    out = rotsprite(sprite(), 90)
    assert out.get_size() == (4, 8)
    assert tuple(out.get_at((1, 1))) == (255, 0, 0, 255)
    assert tuple(out.get_at((1, 6))) == (0, 255, 0, 255)


def test_rotsprite_zero_returns_the_image() -> None:
    image = sprite()
    assert rotsprite(image, 0) is image


def test_cache_quantizes_and_counts_hits() -> None:
    cache = RotSpriteCache(step=10)
    image = sprite()
    first = cache.rotate("s", image, 31)
    assert cache.rotate("s", image, 34) is first
    assert (cache.hits, cache.misses) == (1, 1)
    assert cache.rotate("s", image, 50) is not first
    assert cache.quantize(195) == -160


def test_cache_evicts_least_recently_used() -> None:
    cache = RotSpriteCache(step=10, capacity=2)
    image = sprite()
    cache.rotate("s", image, 10)
    cache.rotate("s", image, 20)
    cache.rotate("s", image, 10)
    cache.rotate("s", image, 30)
    assert len(cache) == 2
    cache.misses = 0
    cache.rotate("s", image, 10)
    assert cache.misses == 0
    cache.rotate("s", image, 20)
    assert cache.misses == 1


def test_a_part_lands_on_its_bone_whatever_the_rotation() -> None:
    marker = pygame.Surface((9, 9), pygame.SRCALPHA)
    marker.fill((0, 0, 0, 0))
    marker.fill((255, 255, 255, 255), (8, 4, 1, 1))
    rig = Rig([Bone("root", offset=(20, 20))], [Part("root", "m", pivot=(4, 4))])
    cache = RotSpriteCache(step=90)
    for angle in (0, 90, 180, -90):
        canvas = pygame.Surface((40, 40), pygame.SRCALPHA)
        canvas.fill((0, 0, 0, 0))
        rig.draw(canvas, {"m": marker}, (0, 0), {"root": angle}, cache)
        lit = [(x, y) for x in range(40) for y in range(40) if canvas.get_at((x, y)).a > 0]
        expect = {0: (24, 20), 90: (20, 24), 180: (16, 20), -90: (20, 16)}[angle]
        assert expect in lit, (angle, lit)


def test_parts_draw_back_to_front() -> None:
    red = pygame.Surface((4, 4))
    red.fill((255, 0, 0))
    blue = pygame.Surface((4, 4))
    blue.fill((0, 0, 255))
    rig = Rig(
        [Bone("root", offset=(10, 10))],
        [Part("root", "front", z=1, pivot=(2, 2)), Part("root", "back", z=0, pivot=(2, 2))],
    )
    canvas = pygame.Surface((20, 20))
    rig.draw(canvas, {"front": red, "back": blue}, (0, 0))
    assert tuple(canvas.get_at((10, 10)))[:3] == (255, 0, 0)


def test_load_rig_from_toml(tmp_path: Path) -> None:
    path = tmp_path / "boss.toml"
    path.write_text(
        """
[[bones]]
name = "body"
offset = [10, 10]

[[bones]]
name = "leg"
parent = "body"
offset = [0, 4]

[[parts]]
bone = "leg"
image = "leg"
pivot = [1, 0]

[clips.walk]
duration = 0.8

[clips.walk.tracks]
leg = [{ time = 0.0, angle = -20 }, { time = 0.4, angle = 20 }, { time = 0.8, angle = -20 }]
"""
    )
    rig, clips = load_rig(path)
    assert [b.name for b in rig.bones] == ["body", "leg"]
    assert rig.parts[0].pivot == (1, 0)
    assert clips["walk"].sample(0.2)["leg"] == pytest.approx(0)
