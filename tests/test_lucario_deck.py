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


def test_dusk_ball_and_carmine_removed():
    ids = {card_id for card_id, _ in DECK}
    assert 1102 not in ids, "Dusk Ball は今回の改修で削除されたはず"
    assert 1192 not in ids, "Carmine は今回の改修で削除されたはず"


def test_energy_count():
    basic = sum(c for i, c in DECK if i == 6)
    rock = sum(c for i, c in DECK if i == 20)
    assert basic == 7
    assert rock == 4
    assert basic + rock == 11


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
    assert counts[1213] == 3  # Judge（2026-07-25: 2→3、Alakazam対面のJudge資源枯渇対策）


def test_ogerpon_ex_present_with_2_copies():
    counts = dict(DECK)
    assert counts[117] == 2  # Cornerstone Mask Ogerpon ex（1→2に増量）


def test_solrock_reduced_to_2():
    counts = dict(DECK)
    assert counts[676] == 2  # Solrock 3→2（オーガポンex増量のため1枚減）


def test_hilda_wally_ciphermaniac_removed():
    """2026-07-25: 資源制約に効果の薄い単発サポート3種を削り、
    Judge増量・Switch・Air Balloonの採用枠に充てた"""
    ids = {card_id for card_id, _ in DECK}
    assert 1225 not in ids, "Hilda（トウコ）は今回の改修で削除されたはず"
    assert 1229 not in ids, "Wally's Compassion（ミツルの思いやり）は今回の改修で削除されたはず"
    assert 1188 not in ids, "Ciphermaniac's Codebreaking（暗号マニアの解読）は今回の改修で削除されたはず"


def test_switch_and_air_balloon_newly_adopted():
    """2026-07-25: 自発的な交代手段が無い構造的ギャップへの対応として新規採用"""
    counts = dict(DECK)
    assert counts[1123] == 1  # ポケモンいれかえ（Switch）
    assert counts[1174] == 2  # ふうせん（Air Balloon）
