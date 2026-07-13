from decks.jamoraiko_20260713 import DECK

ENERGY_IDS = {4, 6}  # Basic {L} Energy, Basic {F} Energy
ACE_SPEC_IDS = {1110}  # つりざおMAX


def test_deck_has_60_cards():
    assert sum(count for _, count in DECK) == 60


def test_no_non_energy_card_exceeds_4_copies():
    for card_id, count in DECK:
        if card_id not in ENERGY_IDS:
            assert count <= 4, f"Card {card_id} が {count} 枚（上限4枚）"


def test_ace_spec_does_not_exceed_1_copy():
    for card_id, count in DECK:
        if card_id in ACE_SPEC_IDS:
            assert count <= 1, f"ACE SPECカード {card_id} が {count} 枚（上限1枚）"


def test_no_duplicate_card_id_entries():
    ids = [card_id for card_id, _ in DECK]
    assert len(ids) == len(set(ids)), "同じcard_idが複数タプルに分かれている"


def test_key_pokemon_present_with_expected_counts():
    counts = dict(DECK)
    assert counts[63] == 2     # タケルライコex
    assert counts[268] == 3    # ズピカ
    assert counts[269] == 3    # ハラバリーex
    assert counts[270] == 3    # カイデン
    assert counts[271] == 3    # タイカイデン
    assert counts[265] == 1    # ビリリダマ


def test_trainer_counts():
    counts = dict(DECK)
    assert counts[1121] == 4   # ハイパーボール
    assert counts[1086] == 4   # なかよしポフィン
    assert counts[1118] == 2   # エネルギー回収
    assert counts[1097] == 3   # 夜のタンカ
    assert counts[1119] == 2   # エネルギー転送
    assert counts[1123] == 2   # ポケモンいれかえ
    assert counts[1110] == 1   # つりざおMAX
    assert counts[1227] == 3   # リーリエの決心
    assert counts[1233] == 4   # カナリィ
    assert counts[1182] == 2   # ボスの指令
    assert counts[1254] == 3   # ハッコウシティ


def test_energy_counts():
    counts = dict(DECK)
    assert counts[4] == 12  # 基本雷エネルギー
    assert counts[6] == 3   # 基本闘エネルギー
