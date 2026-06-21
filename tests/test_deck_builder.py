import csv
import pytest
from pathlib import Path
from deck_builder.card_lookup import build_card_dict, find_card_id


@pytest.fixture
def card_csv(tmp_path: Path) -> Path:
    """テスト用カードデータ CSV を作成する"""
    p = tmp_path / "cards.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["Card ID", "Card Name", "Expansion", "Collection No.",
                        "Stage (Pokémon)/Type (Energy and Trainer)", "Rule",
                        "Category", "Previous stage", "HP", "Type", "Weakness",
                        "Resistance (Type)", "Retreat", "Move Name", "Cost",
                        "Damage", "Effect Explanation"],
        )
        writer.writeheader()
        writer.writerow({"Card ID": "673", "Card Name": "Lucario ex", **{k: "" for k in ["Expansion", "Collection No.", "Stage (Pokémon)/Type (Energy and Trainer)", "Rule", "Category", "Previous stage", "HP", "Type", "Weakness", "Resistance (Type)", "Retreat", "Move Name", "Cost", "Damage", "Effect Explanation"]}})
        writer.writerow({"Card ID": "6", "Card Name": "Basic {F} Energy", **{k: "" for k in ["Expansion", "Collection No.", "Stage (Pokémon)/Type (Energy and Trainer)", "Rule", "Category", "Previous stage", "HP", "Type", "Weakness", "Resistance (Type)", "Retreat", "Move Name", "Cost", "Damage", "Effect Explanation"]}})
        writer.writerow({"Card ID": "1227", "Card Name": "Ultra Ball", **{k: "" for k in ["Expansion", "Collection No.", "Stage (Pokémon)/Type (Energy and Trainer)", "Rule", "Category", "Previous stage", "HP", "Type", "Weakness", "Resistance (Type)", "Retreat", "Move Name", "Cost", "Damage", "Effect Explanation"]}})
    return p


def test_build_card_dict_maps_name_to_id(card_csv: Path) -> None:
    result = build_card_dict(card_csv)
    assert result["Lucario ex"] == 673
    assert result["Basic {F} Energy"] == 6
    assert result["Ultra Ball"] == 1227


def test_find_card_id_exact_match(card_csv: Path) -> None:
    card_dict = build_card_dict(card_csv)
    card_id, candidates = find_card_id("Lucario ex", card_dict)
    assert card_id == 673
    assert candidates == []


def test_find_card_id_case_insensitive(card_csv: Path) -> None:
    card_dict = build_card_dict(card_csv)
    card_id, candidates = find_card_id("lucario EX", card_dict)
    assert card_id == 673
    assert candidates == []


def test_find_card_id_partial_match_returns_candidates(card_csv: Path) -> None:
    card_dict = build_card_dict(card_csv)
    card_id, candidates = find_card_id("Lucario", card_dict)
    assert card_id is None
    assert "Lucario ex" in candidates


def test_find_card_id_no_match_returns_empty_candidates(card_csv: Path) -> None:
    card_dict = build_card_dict(card_csv)
    card_id, candidates = find_card_id("Pikachu", card_dict)
    assert card_id is None
    assert candidates == []
