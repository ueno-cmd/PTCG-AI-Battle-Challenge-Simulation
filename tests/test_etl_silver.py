import csv
import json
from pathlib import Path

import pytest

from etl.silver import parse_to_silver


@pytest.fixture
def bronze_json(tmp_path: Path) -> Path:
    data = {
        "info": {
            "EpisodeId": 12345,
            "Agents": [{"Name": "Alice"}, {"Name": "Bob"}],
        },
        "rewards": [1, -1],
        "steps": [
            [
                {
                    "observation": {"step": 0, "logs": []},
                    "action": [],
                    "reward": 0,
                    "status": "ACTIVE",
                },
                {
                    "observation": {"step": 0, "logs": []},
                    "action": [],
                    "reward": 0,
                    "status": "ACTIVE",
                },
            ],
            [
                {
                    "observation": {"step": 1, "logs": [{"type": 4}]},
                    "action": [1, 2],
                    "reward": 1,
                    "status": "DONE",
                },
                {
                    "observation": {"step": 1, "logs": []},
                    "action": [],
                    "reward": -1,
                    "status": "DONE",
                },
            ],
        ],
    }
    p = tmp_path / "bronze_12345.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_parse_creates_summary_csv(bronze_json: Path, tmp_path: Path) -> None:
    catalog_dir = tmp_path / "unity-catalog"
    summary_path, _ = parse_to_silver(bronze_json, catalog_dir)
    assert summary_path.exists()
    assert summary_path.name == "silver_summary_12345.csv"


def test_parse_summary_content(bronze_json: Path, tmp_path: Path) -> None:
    catalog_dir = tmp_path / "unity-catalog"
    summary_path, _ = parse_to_silver(bronze_json, catalog_dir)
    with summary_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["episode_id"] == "12345"
    assert rows[0]["player0_name"] == "Alice"
    assert rows[0]["player1_name"] == "Bob"
    assert rows[0]["winner_index"] == "0"
    assert rows[0]["winner_name"] == "Alice"
    assert rows[0]["total_steps"] == "2"


def test_parse_creates_turns_csv(bronze_json: Path, tmp_path: Path) -> None:
    catalog_dir = tmp_path / "unity-catalog"
    _, turns_path = parse_to_silver(bronze_json, catalog_dir)
    assert turns_path.exists()
    assert turns_path.name == "silver_turns_12345.csv"


def test_parse_turns_row_count(bronze_json: Path, tmp_path: Path) -> None:
    catalog_dir = tmp_path / "unity-catalog"
    _, turns_path = parse_to_silver(bronze_json, catalog_dir)
    with turns_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4  # 2ステップ × 2エージェント


def test_parse_turns_content(bronze_json: Path, tmp_path: Path) -> None:
    catalog_dir = tmp_path / "unity-catalog"
    _, turns_path = parse_to_silver(bronze_json, catalog_dir)
    with turns_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # 3行目（step=1, agent=0）を確認
    assert rows[2]["step"] == "1"
    assert rows[2]["agent_index"] == "0"
    assert rows[2]["action"] == "[1, 2]"
    assert rows[2]["logs_count"] == "1"
    assert rows[2]["status"] == "DONE"


def test_parse_to_silver_handles_none_reward(tmp_path):
    """rewardsの片方がNone（タイムアウト等）でもクラッシュしないこと"""
    bronze_data = {
        "info": {
            "EpisodeId": 99999999,
            "Agents": [{"Name": "PlayerA"}, {"Name": "PlayerB"}],
        },
        "rewards": [1, None],
        "steps": [
            [
                {"observation": {"step": 0, "logs": []}, "action": None, "reward": 1, "status": "DONE"},
                {"observation": {"step": 0, "logs": []}, "action": None, "reward": None, "status": "DONE"},
            ]
        ],
    }
    bronze_path = tmp_path / "bronze_99999999.json"
    bronze_path.write_text(json.dumps(bronze_data), encoding="utf-8")
    catalog_dir = tmp_path / "catalog"

    summary_path, _ = parse_to_silver(bronze_path, catalog_dir)

    with summary_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["winner_index"] == "0"
    assert rows[0]["winner_name"] == "PlayerA"
