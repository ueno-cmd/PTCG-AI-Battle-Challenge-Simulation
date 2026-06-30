from decks.cinderace_starmie_20260630 import DECK

ENERGY_IDS = {3, 17}  # Basic Water Energy, Ignition Energy


def test_deck_has_60_cards():
    assert sum(count for _, count in DECK) == 60


def test_no_non_energy_card_exceeds_4_copies():
    for card_id, count in DECK:
        if card_id not in ENERGY_IDS:
            assert count <= 4, f"Card {card_id} が {count} 枚（上限4枚）"


def test_key_pokemon_present():
    ids = {card_id for card_id, _ in DECK}
    assert 664  in ids, "Scorbunny が不在"
    assert 666  in ids, "Cinderace が不在"
    assert 1030 in ids, "Staryu が不在"
    assert 1031 in ids, "Mega Starmie ex が不在"


def test_energy_counts():
    water    = sum(c for i, c in DECK if i == 3)
    ignition = sum(c for i, c in DECK if i == 17)
    assert water    == 11
    assert ignition == 4
