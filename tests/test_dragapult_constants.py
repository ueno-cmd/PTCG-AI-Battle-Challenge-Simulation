# tests/test_dragapult_constants.py
from decks.dragapult_20260721 import DECK
from dragapult_agent import constants as c


def test_all_deck_card_ids_have_a_named_constant():
    """DECK内の全カードIDが、constants.py内のいずれかの定数値と一致することを確認する
    （constants.pyのタイポでデッキ内カードと不整合が起きるのを防ぐ）"""
    deck_ids = {card_id for card_id, _ in DECK}
    constant_values = {
        v for k, v in vars(c).items()
        if not k.startswith("_") and isinstance(v, int)
    }
    assert deck_ids <= constant_values, deck_ids - constant_values


def test_boss_orders_id_matches_known_value():
    assert c.Boss_Orders == 1182


def test_dragapult_ex_id_matches_known_value():
    assert c.Dragapult_ex == 121
