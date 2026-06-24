# Unity Catalog ETL 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** バトルログJSONをメダリオンアーキテクチャ（bronze/silver）に変換するCLIスクリプトを作る

**Architecture:** `src/etl/` にロジックを置き、`scripts/etl_battle_log.py` がCLIとして呼び出す。bronze はファイルコピー、silver はJSON解析で summary/turns の2CSVを生成する。

**Tech Stack:** Python 3.12.13, pytest>=8.0, 標準ライブラリのみ（shutil, csv, json, pathlib）

## Global Constraints

- Python 3.12.13 を使用すること（`uv run` で実行）
- 外部ライブラリは追加しない（標準ライブラリのみ）
- テストは `tests/` に配置し、pytest で実行
- コードコメントは日本語で書く

---

## ファイル構成

```
src/
└── etl/
    ├── __init__.py          # 空ファイル（モジュール化）
    ├── bronze.py            # copy_to_bronze() 関数
    └── silver.py            # parse_to_silver() 関数
scripts/
└── etl_battle_log.py        # CLIエントリーポイント
tests/
├── test_etl_bronze.py       # bronze のテスト
└── test_etl_silver.py       # silver のテスト
data/
└── unity-catalog/           # 出力先（スクリプト実行時に自動作成）
```

---

### Task 1: Bronze コピー機能

**Files:**
- Create: `src/etl/__init__.py`
- Create: `src/etl/bronze.py`
- Create: `tests/test_etl_bronze.py`

**Interfaces:**
- Produces: `copy_to_bronze(src_path: Path, catalog_dir: Path) -> Path`
  - `src_path`: コピー元JSON（例: `data/battle_logs/81344455.json`）
  - `catalog_dir`: 出力先ディレクトリ（例: `data/unity-catalog/`）
  - 戻り値: 作成した bronze ファイルのパス（例: `data/unity-catalog/bronze_81344455.json`）

- [ ] **Step 1: テストファイルを作成して失敗させる**

`tests/test_etl_bronze.py` を作成：

```python
import json
from pathlib import Path

import pytest

from etl.bronze import copy_to_bronze


@pytest.fixture
def sample_json(tmp_path: Path) -> Path:
    p = tmp_path / "81344455.json"
    p.write_text(json.dumps({"id": "test"}), encoding="utf-8")
    return p


def test_copy_to_bronze_creates_file(sample_json: Path, tmp_path: Path) -> None:
    catalog_dir = tmp_path / "unity-catalog"
    result = copy_to_bronze(sample_json, catalog_dir)
    assert result.exists()
    assert result.name == "bronze_81344455.json"


def test_copy_to_bronze_creates_catalog_dir(sample_json: Path, tmp_path: Path) -> None:
    catalog_dir = tmp_path / "new-catalog"
    copy_to_bronze(sample_json, catalog_dir)
    assert catalog_dir.exists()


def test_copy_to_bronze_preserves_content(sample_json: Path, tmp_path: Path) -> None:
    catalog_dir = tmp_path / "unity-catalog"
    result = copy_to_bronze(sample_json, catalog_dir)
    assert result.read_text(encoding="utf-8") == sample_json.read_text(encoding="utf-8")
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_etl_bronze.py -v
```

期待: `ImportError: cannot import name 'copy_to_bronze' from 'etl.bronze'`

- [ ] **Step 3: `src/etl/__init__.py` を作成する**

```python
```
（空ファイル）

- [ ] **Step 4: `src/etl/bronze.py` を実装する**

```python
import shutil
from pathlib import Path


def copy_to_bronze(src_path: Path, catalog_dir: Path) -> Path:
    """バトルログJSONをunity-catalogのbronze層にコピーする"""
    catalog_dir.mkdir(parents=True, exist_ok=True)
    dest = catalog_dir / f"bronze_{src_path.name}"
    shutil.copy2(src_path, dest)
    return dest
```

- [ ] **Step 5: テストが通ることを確認する**

```bash
uv run pytest tests/test_etl_bronze.py -v
```

期待: 3件すべて PASS

- [ ] **Step 6: コミットする**

```bash
git add src/etl/__init__.py src/etl/bronze.py tests/test_etl_bronze.py
git commit -m "feat: bronze layer - バトルログJSONのコピー機能を追加"
```

---

### Task 2: Silver パース機能

**Files:**
- Create: `src/etl/silver.py`
- Create: `tests/test_etl_silver.py`

**Interfaces:**
- Consumes: なし（独立して動作）
- Produces: `parse_to_silver(bronze_path: Path, catalog_dir: Path) -> tuple[Path, Path]`
  - `bronze_path`: bronze JSONのパス（例: `data/unity-catalog/bronze_81344455.json`）
  - `catalog_dir`: 出力先ディレクトリ（例: `data/unity-catalog/`）
  - 戻り値: `(summary_path, turns_path)` のタプル

JSONの構造（参考）:
```
{
  "info": { "EpisodeId": 81344455, "Agents": [{"Name": "Alice"}, {"Name": "Bob"}] },
  "rewards": [1, -1],
  "steps": [
    [
      { "observation": {"step": 0, "logs": []}, "action": [], "reward": 0, "status": "ACTIVE" },
      { "observation": {"step": 0, "logs": []}, "action": [], "reward": 0, "status": "ACTIVE" }
    ],
    ...
  ]
}
```

- [ ] **Step 1: テストファイルを作成して失敗させる**

`tests/test_etl_silver.py` を作成：

```python
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
    rows = list(csv.DictReader(summary_path.open(encoding="utf-8")))
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
    rows = list(csv.DictReader(turns_path.open(encoding="utf-8")))
    assert len(rows) == 4  # 2ステップ × 2エージェント


def test_parse_turns_content(bronze_json: Path, tmp_path: Path) -> None:
    catalog_dir = tmp_path / "unity-catalog"
    _, turns_path = parse_to_silver(bronze_json, catalog_dir)
    rows = list(csv.DictReader(turns_path.open(encoding="utf-8")))
    # 3行目（step=1, agent=0）を確認
    assert rows[2]["step"] == "1"
    assert rows[2]["agent_index"] == "0"
    assert rows[2]["action"] == "[1, 2]"
    assert rows[2]["logs_count"] == "1"
    assert rows[2]["status"] == "DONE"
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_etl_silver.py -v
```

期待: `ImportError: cannot import name 'parse_to_silver' from 'etl.silver'`

- [ ] **Step 3: `src/etl/silver.py` を実装する**

```python
import csv
import json
from pathlib import Path


def parse_to_silver(bronze_path: Path, catalog_dir: Path) -> tuple[Path, Path]:
    """bronze JSONをパースしてsummaryとturnsのCSVを生成する"""
    data = json.loads(bronze_path.read_text(encoding="utf-8"))

    episode_id = data["info"]["EpisodeId"]
    agents = data["info"]["Agents"]
    rewards = data["rewards"]
    steps = data["steps"]

    winner_index = rewards.index(max(rewards))
    winner_name = agents[winner_index]["Name"]

    summary_path = catalog_dir / f"silver_summary_{episode_id}.csv"
    turns_path = catalog_dir / f"silver_turns_{episode_id}.csv"

    # サマリーCSV（1試合1行）
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "episode_id", "player0_name", "player1_name",
                "winner_index", "winner_name", "total_steps",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "episode_id": episode_id,
            "player0_name": agents[0]["Name"],
            "player1_name": agents[1]["Name"],
            "winner_index": winner_index,
            "winner_name": winner_name,
            "total_steps": len(steps),
        })

    # ターン詳細CSV（1ステップ × 2エージェント = 2行/step）
    with turns_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "episode_id", "step", "agent_index",
                "action", "reward", "status", "logs_count",
            ],
        )
        writer.writeheader()
        for step_list in steps:
            for agent_index, agent_step in enumerate(step_list):
                writer.writerow({
                    "episode_id": episode_id,
                    "step": agent_step["observation"]["step"],
                    "agent_index": agent_index,
                    "action": json.dumps(agent_step["action"]),
                    "reward": agent_step["reward"],
                    "status": agent_step["status"],
                    "logs_count": len(agent_step["observation"]["logs"]),
                })

    return summary_path, turns_path
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run pytest tests/test_etl_silver.py -v
```

期待: 5件すべて PASS

- [ ] **Step 5: コミットする**

```bash
git add src/etl/silver.py tests/test_etl_silver.py
git commit -m "feat: silver layer - バトルログのsummary/turns CSV生成を追加"
```

---

### Task 3: CLIエントリーポイント

**Files:**
- Create: `scripts/etl_battle_log.py`

**Interfaces:**
- Consumes:
  - `copy_to_bronze(src_path: Path, catalog_dir: Path) -> Path` （Task 1）
  - `parse_to_silver(bronze_path: Path, catalog_dir: Path) -> tuple[Path, Path]` （Task 2）
- Produces: CLIコマンド `python scripts/etl_battle_log.py <json_path>`

- [ ] **Step 1: `scripts/etl_battle_log.py` を作成する**

```python
import sys
from pathlib import Path

# src/ を import パスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from etl.bronze import copy_to_bronze
from etl.silver import parse_to_silver


def main() -> None:
    if len(sys.argv) != 2:
        print("使い方: python scripts/etl_battle_log.py <path_to_json>")
        sys.exit(1)

    src_path = Path(sys.argv[1])
    if not src_path.exists():
        print(f"エラー: {src_path} が見つかりません")
        sys.exit(1)

    catalog_dir = Path("data/unity-catalog")

    bronze_path = copy_to_bronze(src_path, catalog_dir)
    print(f"Bronze: {bronze_path}")

    summary_path, turns_path = parse_to_silver(bronze_path, catalog_dir)
    print(f"Silver summary: {summary_path}")
    print(f"Silver turns:   {turns_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 実際のバトルログで動作確認する**

```bash
uv run python scripts/etl_battle_log.py data/battle_logs/81344455.json
```

期待出力:
```
Bronze: data/unity-catalog/bronze_81344455.json
Silver summary: data/unity-catalog/silver_summary_81344455.csv
Silver turns:   data/unity-catalog/silver_turns_81344455.csv
```

- [ ] **Step 3: 生成されたファイルを目視確認する**

```bash
ls data/unity-catalog/
cat data/unity-catalog/silver_summary_81344455.csv
head -5 data/unity-catalog/silver_turns_81344455.csv
```

- [ ] **Step 4: 2つ目のログでも動作確認する**

```bash
uv run python scripts/etl_battle_log.py data/battle_logs/81350780.json
ls data/unity-catalog/
```

期待: 6ファイルが存在すること（bronze 2 + silver_summary 2 + silver_turns 2）

- [ ] **Step 5: 全テストが通ることを確認する**

```bash
uv run pytest tests/test_etl_bronze.py tests/test_etl_silver.py -v
```

期待: 8件すべて PASS

- [ ] **Step 6: コミットする**

```bash
git add scripts/etl_battle_log.py
git commit -m "feat: CLIエントリーポイント etl_battle_log.py を追加"
```
