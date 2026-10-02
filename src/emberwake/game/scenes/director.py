"""The gameplay scene's side of a story script: where things are, flags, lamps and credits."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from emberwake.engine.core.events import EventBus
from emberwake.engine.physics import Body
from emberwake.engine.world.spawning import Identity
from emberwake.game.areas import area_of
from emberwake.game.lamps import Lamp, LampLit
from emberwake.game.story import Stage

if TYPE_CHECKING:
    from emberwake.game.scenes.gameplay import GameplayScene


class SceneDirector:
    """Carries out what a `Script` asks of the running game."""

    def __init__(self, scene: GameplayScene) -> None:
        self.scene = scene
        self.stage = Stage()

    def locate(self, prefab: str) -> tuple[float, float] | None:
        for _, identity, body in self.scene.world.query(Identity, Body):
            if identity.prefab == prefab:
                return body.center_x, body.y + body.height / 2
        return None

    def set_flag(self, name: str, value: int) -> None:
        self.scene.facts.flags[name] = value

    def area_lamps(self) -> list[str]:
        scene = self.scene
        area = area_of(scene.rooms.graph.levels[scene.room])
        x, y = self.stage.focus or (scene.body.center_x, scene.body.y)
        found = []
        for level in scene.rooms.graph.levels.values():
            if area_of(level) != area:
                continue
            for lamp in level.entities("Lamp"):
                lx, ly = level.world_x + lamp.px[0], level.world_y + lamp.px[1]
                found.append((math.hypot(lx - x, ly - y), lamp.iid))
        return [iid for _, iid in sorted(found)]

    def light_lamp(self, iid: str) -> None:
        scene = self.scene
        eid = scene.spawner.resolve(iid)
        lamp = scene.world.find(eid, Lamp) if eid is not None else None
        if eid is None or lamp is None:
            saved = scene.spawner.state.entities.setdefault(iid, {})
            saved["Lamp"] = {"lit": True, "protected": True}
            return
        was = lamp.lit
        lamp.lit = lamp.protected = True
        if not was:
            body = scene.world.get(eid, Body)
            event = LampLit(iid, body.center_x, body.y + body.height / 2)
            scene.world.resource(EventBus).publish(event)

    def flash(self) -> None:
        self.scene.flash.start(self.scene.feel.juice.beacon_flash)

    def recount(self) -> None:
        self.scene.recount_light()

    def credits(self) -> None:
        from emberwake.game.scenes.credits import CreditsScene  # noqa: PLC0415

        self.scene.manager.push(CreditsScene(self.scene.ctx))
