# tests/test_dragapult_deck.py
from decks.dragapult_20260721 import DECK

ACE_SPEC_IDS = {1080}  # Unfair Stamp（data/competition/EN_Card_Data.csv で Rule: ACE SPEC）


def test_deck_totals_60_cards():
    assert sum(count for _, count in DECK) == 60


def test_ace_spec_cards_limited_to_one_copy():
    for card_id, count in DECK:
        if card_id in ACE_SPEC_IDS:
            assert count == 1, f"ACE SPEC card {card_id} has {count} copies"


def test_no_duplicate_card_ids():
    ids = [card_id for card_id, _ in DECK]
    assert len(ids) == len(set(ids)), "同一カードIDが複数エントリに分かれている"
