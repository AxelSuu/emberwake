from __future__ import annotations

from tests.unit.game.test_strings import TABLES

from emberwake.engine.core.dialogue import load_dialogues
from emberwake.game import paths
from emberwake.game.data.save import SaveSlot
from emberwake.game.shop import SPENT, buy, can_buy, load_shop, owned, price, wallet

SHOP = load_shop(paths.content("shop.toml"))
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
