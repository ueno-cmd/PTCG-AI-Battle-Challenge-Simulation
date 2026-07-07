from decks.lucario_20260621 import DECK

ENERGY_IDS = {6}  # Basic {F} Energy
ACE_SPEC_IDS = {1159}  # Hero's Cape


def test_deck_has_60_cards():
    assert sum(count for _, count in DECK) == 60


def test_no_non_energy_card_exceeds_4_copies():
    for card_id, count in DECK:
        if card_id not in ENERGY_IDS:
            assert count <= 4, f"Card {card_id} が {count} 枚（上限4枚）"


def test_key_pokemon_present():
    ids = {card_id for card_id, _ in DECK}
    assert 677 in ids, "Riolu が不在"
    assert 678 in ids, "Mega Lucario ex が不在"
    assert 676 in ids, "Solrock が不在"
    assert 675 in ids, "Lunatone が不在"


def test_makuhita_hariyama_line_removed():
    ids = {card_id for card_id, _ in DECK}
    assert 673 not in ids, "Makuhita は今回の改修で削除されたはず"
    assert 674 not in ids, "Hariyama は今回の改修で削除されたはず"


def test_dusk_ball_and_carmine_and_switch_removed():
    ids = {card_id for card_id, _ in DECK}
    assert 1102 not in ids, "Dusk Ball は今回の改修で削除されたはず"
    assert 1192 not in ids, "Carmine は今回の改修で削除されたはず"
    assert 1123 not in ids, "Switch は今回の改修で削除されたはず"


def test_energy_count():
    fighting = sum(c for i, c in DECK if i == 6)
    assert fighting == 11


def test_ace_spec_does_not_exceed_1_copy():
    for card_id, count in DECK:
        if card_id in ACE_SPEC_IDS:
            assert count <= 1, f"ACE SPECカード {card_id} が {count} 枚（上限1枚）"


def test_no_duplicate_card_id_entries():
    ids = [card_id for card_id, _ in DECK]
    assert len(ids) == len(set(ids)), "同じcard_idが複数タプルに分かれている"


def test_new_cards_present_with_expected_counts():
    counts = dict(DECK)
    assert counts[1121] == 4  # Ultra Ball
    assert counts[1122] == 4  # Pokégear 3.0
    assert counts[1097] == 2  # Night Stretcher
    assert counts[1213] == 2  # Judge
    assert counts[1225] == 2  # Hilda
    assert counts[1229] == 1  # Wally's Compassion
    assert counts[1188] == 1  # Ciphermaniac's Codebreaking


def test_ogerpon_ex_present_with_1_copy():
    counts = dict(DECK)
    assert counts[117] == 1  # Cornerstone Mask Ogerpon ex


def test_solrock_reduced_to_3():
    counts = dict(DECK)
    assert counts[676] == 3  # Solrock 4→3（オーガポンex採用のため1枚減）
