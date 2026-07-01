from decks.grimmsnarl_20260701 import DECK

ENERGY_IDS = {7}  # Basic {D} Energy
ACE_SPEC_IDS = {1159}  # Hero's Cape（data/EN_Card_Data.csv で Rule: ACE SPEC）


def test_deck_has_60_cards():
    assert sum(count for _, count in DECK) == 60


def test_no_non_energy_card_exceeds_4_copies():
    for card_id, count in DECK:
        if card_id not in ENERGY_IDS:
            assert count <= 4, f"Card {card_id} が {count} 枚（上限4枚）"


def test_key_pokemon_present():
    ids = {card_id for card_id, _ in DECK}
    assert 646 in ids, "Marnie's Impidimp が不在"
    assert 647 in ids, "Marnie's Morgrem が不在"
    assert 648 in ids, "Marnie's Grimmsnarl ex が不在"
    assert 649 in ids, "Marnie's Morpeko が不在"
    assert 112 in ids, "Munkidori が不在"
    assert 66  in ids, "Dudunsparce が不在"
    assert 305 in ids, "Dunsparce が不在"


def test_energy_count():
    darkness = sum(c for i, c in DECK if i == 7)
    assert darkness == 12


def test_ace_spec_does_not_exceed_1_copy():
    for card_id, count in DECK:
        if card_id in ACE_SPEC_IDS:
            assert count <= 1, f"ACE SPECカード {card_id} が {count} 枚（上限1枚）"


def test_no_duplicate_card_id_entries():
    ids = [card_id for card_id, _ in DECK]
    assert len(ids) == len(set(ids)), "同じcard_idが複数タプルに分かれている"
