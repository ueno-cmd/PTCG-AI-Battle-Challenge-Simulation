from decks.grimmsnarl_20260701 import DECK

ENERGY_IDS = {7}  # Basic {D} Energy
ACE_SPEC_IDS = {1092}  # Secret Box（data/EN_Card_Data.csv で Rule: ACE SPEC）


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
    assert 112 in ids, "Munkidori が不在"
    assert 104 in ids, "Froslass が不在"
    assert 689 in ids, "Yveltal が不在"


def test_removed_pokemon_absent():
    ids = {card_id for card_id, _ in DECK}
    assert 649 not in ids, "Marnie's Morpeko は今回の改修で削除されたはず"
    assert 66 not in ids, "Dudunsparce は今回の改修で削除されたはず"
    assert 305 not in ids, "Dunsparce は今回の改修で削除されたはず"


def test_energy_count():
    darkness = sum(c for i, c in DECK if i == 7)
    assert darkness == 12


def test_ace_spec_does_not_exceed_1_copy():
    for card_id, count in DECK:
        if card_id in ACE_SPEC_IDS:
            assert count <= 1, f"ACE SPECカード {card_id} が {count} 枚（上限1枚）"


def test_ace_spec_card_is_secret_box():
    secret_box_count = sum(c for i, c in DECK if i == 1092)
    assert secret_box_count == 1, "Secret Box が1枚採用されているはず"
    hero_cape_count = sum(c for i, c in DECK if i == 1159)
    assert hero_cape_count == 0, "Hero's Cape は今回の改修で削除されたはず（ACE SPECをSecret Boxに統合）"


def test_no_duplicate_card_id_entries():
    ids = [card_id for card_id, _ in DECK]
    assert len(ids) == len(set(ids)), "同じcard_idが複数タプルに分かれている"


def test_boss_orders_count():
    count = sum(c for i, c in DECK if i == 1182)
    assert count == 3


def test_energy_recycler_removed():
    count = sum(c for i, c in DECK if i == 1139)
    assert count == 0, "Energy Recycler は今回の改修で削除されたはず"


def test_phase_b_removed_pokemon_absent():
    ids = {card_id for card_id, _ in DECK}
    assert 235 not in ids, "Budew(スボミー) はフェーズBで削除されたはず"
    assert 122 not in ids, "Tatsugiri(シャリタツ) はフェーズBで削除されたはず"
    assert 858 not in ids, "Psyduck(コダック) はフェーズBで削除されたはず"


def test_fezandipiti_ex_count():
    count = sum(c for i, c in DECK if i == 140)
    assert count == 2, "キチキギスex(140)は2枚採用のはず"


def test_yveltal_count_increased():
    count = sum(c for i, c in DECK if i == 689)
    assert count == 2, "イベルタル(689)はフェーズBで2枚に増量されたはず"
