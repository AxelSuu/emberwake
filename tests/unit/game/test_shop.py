from __future__ import annotations

from tests.unit.game.test_strings import TABLES

from emberwake.engine.core.dialogue import load_dialogues
from emberwake.game import paths
from emberwake.game.data.save import SaveSlot
from emberwake.game.grants import load_grants
from emberwake.game.shop import SPENT, buy, can_buy, load_shops, owned, price, wallet

SHOPS = load_shops(paths.content("shop.toml"))
SHOP = SHOPS["tinker"]
HP = SHOP.items["hp"]


def save(embers: int) -> SaveSlot:
    slot = SaveSlot(room="Test_Room")
    slot.stats.embers = embers
    return slot


def test_the_wallet_is_embers_minus_what_was_spent() -> None:
    slot = save(30)
    assert wallet(slot) == 30
    slot.flags[SPENT] = 12
    assert wallet(slot) == 18


def test_buying_spends_embers_and_counts_the_item() -> None:
    slot = save(30)
    assert buy(slot, HP)
    assert wallet(slot) == 30 - HP.price
    assert owned(slot, HP) == 1


def test_each_purchase_costs_more() -> None:
    slot = save(1000)
    first = price(slot, HP)
    buy(slot, HP)
    assert price(slot, HP) == first + HP.step


def test_you_cannot_buy_what_you_cannot_afford_or_past_the_limit() -> None:
    poor = save(HP.price - 1)
    assert not can_buy(poor, HP)
    assert not buy(poor, HP)
    assert owned(poor, HP) == 0
    rich = save(10_000)
    for _ in range(HP.max):
        assert buy(rich, HP)
    assert not buy(rich, HP)
    assert owned(rich, HP) == HP.max


def test_every_item_has_a_name_in_every_language() -> None:
    for language, table in TABLES.items():
        for ident in SHOP.items:
            assert table[f"shop.{ident}.name"], (language, ident)


def test_dialogue_scripts_only_use_strings_that_exist() -> None:
    graphs = load_dialogues(paths.content("dialogue.toml"))
    assert "tinker" in graphs
    for graph in graphs.values():
        for node in graph.values():
            keys = [node.text, *(choice.text for choice in node.choices)]
            for language, table in TABLES.items():
                for key in filter(None, keys):
                    assert key in table, (language, key)


def test_quill_sells_the_map_into_the_inventory() -> None:
    item = SHOPS["quill"].items["map.quarter"]
    slot = save(100)
    assert buy(slot, item)
    assert slot.inventory["map.quarter"] == 1
    assert wallet(slot) == 100 - item.price
    assert not can_buy(slot, item)
    assert not buy(slot, item)
    assert slot.inventory["map.quarter"] == 1


def test_every_shop_has_a_title_and_every_grant_item_exists() -> None:
    grants = load_grants(paths.content("grants.toml"))
    for language, table in TABLES.items():
        for name in SHOPS:
            assert table[f"shop.title.{name}"], (language, name)
    for shop in SHOPS.values():
        for item in shop.items.values():
            assert bool(item.flag) != bool(item.grant)
            assert not item.grant or item.grant in grants
