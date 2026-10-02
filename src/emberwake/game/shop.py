"""Shops (the Tinker's, Quill's): items bought with embers, remembered in the save."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from emberwake.engine.core.serde import from_data

if TYPE_CHECKING:
    from pathlib import Path

    from emberwake.game.data.save import SaveSlot

SPENT = "embers_spent"
HP_PER_UPGRADE = 1
EMBER_PER_UPGRADE = 25.0


@dataclass(slots=True)
class Item:
    """Something for sale: `price` for the first, rising by `step` for each later one."""

    price: int
    flag: str = ""
    step: int = 0
    max: int = 1
    grant: str = ""
    """A key of ``content/grants.toml``: bought into the inventory instead of counted in `flag`."""


@dataclass(slots=True)
class ShopData:
    items: dict[str, Item] = field(default_factory=dict)


def load_shops(path: Path) -> dict[str, ShopData]:
    """Parse the TOML file, one table per shop. Raises `tomllib.TOMLDecodeError` or `SerdeError`."""
    return from_data(dict[str, ShopData], tomllib.loads(path.read_text(encoding="utf-8")))


def wallet(save: SaveSlot) -> int:
    """Embers the player carries: collected, less spent or lost, less those in the Cinder."""
    dropped = save.cinder.embers if save.cinder is not None else 0
    return save.stats.embers - save.flags.get(SPENT, 0) - dropped


def owned(save: SaveSlot, item: Item) -> int:
    if item.grant:
        return save.inventory.get(item.grant, 0)
    return save.flags.get(item.flag, 0)


def price(save: SaveSlot, item: Item) -> int:
    """What the next one costs."""
    return item.price + item.step * owned(save, item)


def can_buy(save: SaveSlot, item: Item) -> bool:
    return owned(save, item) < item.max and wallet(save) >= price(save, item)


def buy(save: SaveSlot, item: Item) -> bool:
    """Spend embers on `item`; returns whether it was bought."""
    if not can_buy(save, item):
        return False
    save.flags[SPENT] = save.flags.get(SPENT, 0) + price(save, item)
    if item.grant:
        save.inventory[item.grant] = owned(save, item) + 1
    else:
        save.flags[item.flag] = owned(save, item) + 1
    return True
