"""combat.pyのcalc_attack_planが使う手打ちのエネルギー要求・ダメージ値を、
data/competition/EN_Card_Data.csvのカード原文と突き合わせるテスト。

libcg.so（macOSで動作しない）を経由せず、手元のCSVだけで検証できる。
このテストは今回の修正の正しさを保証するものではなく、将来
all_attack()/CSVベースのテーブル化に着手する際、新実装が現行の
手打ち値と同じ結果を再現できているかの回帰テストとして転用することを狙いとする。
"""
import csv
from pathlib import Path

import pytest

CSV_PATH = Path(__file__).parent.parent / "data" / "competition" / "EN_Card_Data.csv"


def _count_energy_symbols(cost: str) -> int:
    """Cost文字列（例: "{F}●●"）内のエネルギー記号数を数える。
    "{X}"ブロック1つ・"●"1文字がそれぞれ1エネルギーに相当する"""
    return cost.count("{") + cost.count("●")


def _load_moves() -> dict:
    """(Card ID, Move Name) -> {"energy": int, "damage": int} の辞書を作る。
    [Ability]/[Tera]接頭辞の行（技ではなく特性等）は除外する"""
    moves = {}
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            move_name = row["Move Name"]
            cost = row["Cost"]
            if move_name in ("n/a", "") or cost in ("n/a", ""):
                continue
            if move_name.startswith("[Ability]") or move_name.startswith("[Tera]"):
                continue
            damage_str = row["Damage"]
            if damage_str in ("n/a", ""):
                damage = 0
            else:
                try:
                    damage = int(damage_str)
                except ValueError:
                    # 可変ダメージ（例: "30×"）はスキップ
                    continue
            moves[(int(row["Card ID"]), move_name)] = {
                "energy": _count_energy_symbols(cost),
                "damage": damage,
            }
    return moves


MOVES = _load_moves()


@pytest.mark.parametrize("card_id,move_name,expected_energy,expected_damage", [
    (678, "Aura Jab", 1, 130),    # Mega Lucario ex 通常技（combat.py: energy_required=1, base_damage=130）
    (678, "Mega Brave", 2, 270),  # Mega Lucario ex メガブレイブ（combat.py: energy_required=2, base_damage=270）
    (676, "Cosmic Beam", 1, 70),  # Solrock（combat.py: energy_required=1, base_damage=70）
    (117, "Demolish", 3, 140),    # Cornerstone Mask Ogerpon ex（combat.py: energy_required=3, base_damage=140）
])
def test_calc_attack_plan_hardcoded_values_match_card_data(card_id, move_name, expected_energy, expected_damage):
    move = MOVES[(card_id, move_name)]
    assert move["energy"] == expected_energy, (
        f"{move_name}(ID{card_id}): combat.pyの手打ちエネルギー要求={expected_energy} "
        f"だがEN_Card_Data.csvの実際の値は{move['energy']}"
    )
    assert move["damage"] == expected_damage, (
        f"{move_name}(ID{card_id}): combat.pyの手打ちダメージ={expected_damage} "
        f"だがEN_Card_Data.csvの実際の値は{move['damage']}"
    )
