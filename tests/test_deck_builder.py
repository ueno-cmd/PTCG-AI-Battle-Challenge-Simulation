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


from deck_builder.deck_loader import load_deck_def
from deck_builder.builder import CardNotFoundError, DeckSizeError, write_deck_csv


def test_load_deck_def_returns_list(tmp_path: Path) -> None:
    deck_file = tmp_path / "deck.py"
    deck_file.write_text('DECK = [("Lucario ex", 2), ("Basic {F} Energy", 58)]')
    result = load_deck_def(deck_file)
    assert result == [("Lucario ex", 2), ("Basic {F} Energy", 58)]


def test_write_deck_csv_creates_file(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    path = write_deck_csv([673, 6, 6], out_dir)
    assert path.exists()
    lines = path.read_text().strip().split("\n")
    assert lines == ["673", "6", "6"]


def test_write_deck_csv_filename_has_timestamp(tmp_path: Path) -> None:
    path = write_deck_csv([1], tmp_path)
    assert path.name.startswith("deck_")
    assert path.suffix == ".csv"


def test_build_card_dict_keeps_first_on_duplicate(tmp_path: Path) -> None:
    """同名カードが複数ある場合、最初のエントリのIDを保持する"""
    p = tmp_path / "dup.csv"
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
        writer.writerow({"Card ID": "333", "Card Name": "Riolu", **{k: "" for k in ["Expansion", "Collection No.", "Stage (Pokémon)/Type (Energy and Trainer)", "Rule", "Category", "Previous stage", "HP", "Type", "Weakness", "Resistance (Type)", "Retreat", "Move Name", "Cost", "Damage", "Effect Explanation"]}})
        writer.writerow({"Card ID": "677", "Card Name": "Riolu", **{k: "" for k in ["Expansion", "Collection No.", "Stage (Pokémon)/Type (Energy and Trainer)", "Rule", "Category", "Previous stage", "HP", "Type", "Weakness", "Resistance (Type)", "Retreat", "Move Name", "Cost", "Damage", "Effect Explanation"]}})
    result = build_card_dict(p)
    assert result["Riolu"] == 333  # 最初のエントリを保持
