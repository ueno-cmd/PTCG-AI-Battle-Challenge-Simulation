# デッキCSVビルダー 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** カード名と枚数を定義した Python ファイルから Kaggle 提出用 `deck.csv` を自動生成する CLI スクリプトを実装する

**Architecture:** `src/deck_builder/` に「カード名→ID 辞書構築」「デッキ定義ローダー」「CSV 書き出し」を責務ごとに分割したモジュールを置く。`scripts/build_deck.py` はこれらを呼び出す薄い CLI ラッパーとする。テストは `src/deck_builder/` の各関数を直接インポートして実行する。

**Tech Stack:** Python 3.12、uv、stdlib のみ（csv / pathlib / datetime / importlib / sys）

## Global Constraints

- `uv run pytest` でテスト実行
- テストには `data/EN_Card_Data.csv` を使用しない（tmp_path フィクスチャで代替）
- カード名は `EN_Card_Data.csv` の `Card Name` 列に合わせる（英語のみ、JP 不使用）
- 出力 CSV の行末は `\n`（1 行 1 カード ID、合計 60 行）
- コメントは日本語で書く

---

## ファイル構成

```
decks/                              # 新規作成（git 管理）
  lucario_20260621.py               # 新規作成（ルカリオデッキ定義）
output/                             # 新規作成（.gitignore 対象）
scripts/
  build_deck.py                     # 新規作成（CLI エントリポイント）
src/deck_builder/
  __init__.py                       # 新規作成（空）
  card_lookup.py                    # 新規作成：build_card_dict / find_card_id
  deck_loader.py                    # 新規作成：load_deck_def
  builder.py                        # 新規作成：write_deck_csv / 例外クラス
tests/
  test_deck_builder.py              # 新規作成（既存テストには触れない）
.gitignore                          # 修正：output/ を追加
```

---

### Task 1: ディレクトリ・設定・サンプルデッキ定義

**Files:**
- Create: `decks/lucario_20260621.py`
- Create: `src/deck_builder/__init__.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `decks/lucario_20260621.py` に `DECK: list[tuple[str, int]]` 定数

- [ ] **Step 1: `output/` を .gitignore に追加**

`.gitignore` の末尾に追記する（`Edit` ツールで既存ファイルを開いて末尾に追加）：

```
# 提出用 deck.csv 一時出力先
output/
```

- [ ] **Step 2: ディレクトリを作成する**

```bash
mkdir -p decks output src/deck_builder
touch src/deck_builder/__init__.py
```

- [ ] **Step 3: 既存 deck.csv からデッキ定義を逆引き生成する**

次のコマンドを実行し、出力をコピーして `decks/lucario_20260621.py` として保存する：

```bash
uv run python -c "
import csv
from collections import Counter
from pathlib import Path

ids = [int(x.strip()) for x in open('data/deck.csv') if x.strip()]
id_counts = Counter(ids)

name_map = {}
with open('data/EN_Card_Data.csv') as f:
    for row in csv.DictReader(f):
        name_map[int(row['Card ID'])] = row['Card Name']

print('DECK = [')
for card_id, count in sorted(id_counts.items(), key=lambda x: (x[1] == 6, x[0])):
    name = name_map.get(card_id, f'UNKNOWN_{card_id}')
    print(f'    (\"{name}\", {count}),')
print(']')
"
```

出力例（実際の値に従うこと）：
```python
DECK = [
    ("Lucario ex", 2),
    ("Mabosstiff ex", 2),
    ...
    ("Basic {F} Energy", 13),
]
```

- [ ] **Step 4: 合計 60 枚であることを確認する**

```bash
uv run python -c "
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location('d', 'decks/lucario_20260621.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
total = sum(c for _, c in m.DECK)
print(f'合計: {total} 枚')
assert total == 60, f'60枚ではありません: {total}'
"
```

期待される出力：`合計: 60 枚`

- [ ] **Step 5: コミット**

```bash
git add .gitignore decks/lucario_20260621.py src/deck_builder/__init__.py
git commit -m "chore: デッキビルダー用ディレクトリ構造・ルカリオデッキ定義を追加"
```

---

### Task 2: カード名→ID 検索モジュール（TDD）

**Files:**
- Create: `src/deck_builder/card_lookup.py`
- Create: `tests/test_deck_builder.py`

**Interfaces:**
- Produces:
  - `build_card_dict(csv_path: Path) -> dict[str, int]`
  - `find_card_id(name: str, card_dict: dict[str, int]) -> tuple[int | None, list[str]]`
    - 戻り値: `(card_id, candidates)` - 一致なし時は `(None, [候補名, ...])`

- [ ] **Step 1: テストを書く**

`tests/test_deck_builder.py` を作成：

```python
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
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_deck_builder.py -v
```

期待される出力：`ModuleNotFoundError: No module named 'deck_builder'`

- [ ] **Step 3: `src/deck_builder/card_lookup.py` を実装する**

```python
import csv
from pathlib import Path


def build_card_dict(csv_path: Path) -> dict[str, int]:
    """EN_Card_Data.csv を読み込み「カード名 → Card ID」辞書を返す"""
    card_dict: dict[str, int] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            card_dict[row["Card Name"]] = int(row["Card ID"])
    return card_dict


def _normalize(name: str) -> str:
    """大文字小文字・前後スペースを正規化する"""
    return name.lower().strip()


def find_card_id(name: str, card_dict: dict[str, int]) -> tuple[int | None, list[str]]:
    """
    カード名からIDを検索する。

    Returns:
        (card_id, candidates)
        - card_id: 一致したID。見つからなければ None
        - candidates: 部分一致候補のカード名リスト（card_id が None のときのみ意味を持つ）
    """
    # 完全一致
    if name in card_dict:
        return card_dict[name], []

    # 大文字小文字・スペース正規化後に一致
    norm = _normalize(name)
    for card_name, card_id in card_dict.items():
        if _normalize(card_name) == norm:
            return card_id, []

    # 部分一致候補
    candidates = [card_name for card_name in card_dict if norm in _normalize(card_name)]
    return None, candidates
```

- [ ] **Step 4: テストが全て通ることを確認する**

```bash
uv run pytest tests/test_deck_builder.py -v
```

期待される出力：`5 passed`

- [ ] **Step 5: コミット**

```bash
git add src/deck_builder/card_lookup.py tests/test_deck_builder.py
git commit -m "feat: カード名→ID検索モジュールを追加（TDD）"
```

---

### Task 3: デッキ定義ローダー・CSV 書き出し（TDD）

**Files:**
- Create: `src/deck_builder/deck_loader.py`
- Create: `src/deck_builder/builder.py`
- Modify: `tests/test_deck_builder.py`

**Interfaces:**
- Consumes: Task 2 の `build_card_dict`, `find_card_id`
- Produces:
  - `load_deck_def(file_path: Path) -> list[tuple[str, int]]`
  - `write_deck_csv(card_ids: list[int], output_dir: Path) -> Path`
  - `CardNotFoundError(Exception)` — 未解決カードがある場合に raise
  - `DeckSizeError(Exception)` — 合計が 60 枚でない場合に raise

- [ ] **Step 1: テストを `tests/test_deck_builder.py` に追記する**

ファイルの末尾に追加する：

```python
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
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_deck_builder.py::test_load_deck_def_returns_list tests/test_deck_builder.py::test_write_deck_csv_creates_file tests/test_deck_builder.py::test_write_deck_csv_filename_has_timestamp -v
```

期待される出力：`ModuleNotFoundError`

- [ ] **Step 3: `src/deck_builder/deck_loader.py` を実装する**

```python
import importlib.util
from pathlib import Path


def load_deck_def(file_path: Path) -> list[tuple[str, int]]:
    """デッキ定義ファイル (.py) の DECK リストを読み込む"""
    spec = importlib.util.spec_from_file_location("_deck_def", file_path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.DECK
```

- [ ] **Step 4: `src/deck_builder/builder.py` を実装する**

```python
from datetime import datetime
from pathlib import Path


class CardNotFoundError(Exception):
    """デッキ定義内のカード名が EN_Card_Data.csv で見つからなかった場合"""


class DeckSizeError(Exception):
    """デッキの合計枚数が 60 枚でない場合"""


def write_deck_csv(card_ids: list[int], output_dir: Path) -> Path:
    """カード ID リストをタイムスタンプ付き CSV に書き出す"""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"deck_{timestamp}.csv"
    with open(output_path, "w", encoding="utf-8") as f:
        for card_id in card_ids:
            f.write(f"{card_id}\n")
    return output_path
```

- [ ] **Step 5: テストが全て通ることを確認する**

```bash
uv run pytest tests/test_deck_builder.py -v
```

期待される出力：`8 passed`

- [ ] **Step 6: コミット**

```bash
git add src/deck_builder/deck_loader.py src/deck_builder/builder.py tests/test_deck_builder.py
git commit -m "feat: デッキ定義ローダー・CSV書き出しモジュールを追加（TDD）"
```

---

### Task 4: CLI スクリプト（`scripts/build_deck.py`）

**Files:**
- Create: `scripts/build_deck.py`

**Interfaces:**
- Consumes: Task 2 の `build_card_dict`, `find_card_id`; Task 3 の `load_deck_def`, `write_deck_csv`, `CardNotFoundError`, `DeckSizeError`

- [ ] **Step 1: `scripts/build_deck.py` を作成する**

```python
#!/usr/bin/env python3
"""デッキ定義ファイルから output/deck_YYYYMMDD_HHMMSS.csv を生成する

使い方:
    uv run python scripts/build_deck.py decks/lucario_20260621.py
"""

import sys
from pathlib import Path

# src/ をモジュール検索パスに追加（uv run 実行前提）
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from deck_builder.builder import CardNotFoundError, DeckSizeError, write_deck_csv
from deck_builder.card_lookup import build_card_dict, find_card_id
from deck_builder.deck_loader import load_deck_def

PROJECT_ROOT = Path(__file__).parent.parent
CARD_CSV = PROJECT_ROOT / "data" / "EN_Card_Data.csv"
OUTPUT_DIR = PROJECT_ROOT / "output"


def main() -> None:
    if len(sys.argv) < 2:
        print("使い方: uv run python scripts/build_deck.py <デッキ定義ファイル>")
        sys.exit(1)

    deck_def_path = Path(sys.argv[1])
    if not deck_def_path.exists():
        print(f"エラー: ファイルが見つかりません: {deck_def_path}")
        sys.exit(1)

    if not CARD_CSV.exists():
        print(f"エラー: カードデータが見つかりません: {CARD_CSV}")
        sys.exit(1)

    deck_def = load_deck_def(deck_def_path)
    card_dict = build_card_dict(CARD_CSV)

    card_ids: list[int] = []
    errors: list[str] = []

    for card_name, count in deck_def:
        card_id, candidates = find_card_id(card_name, card_dict)
        if card_id is not None:
            card_ids.extend([card_id] * count)
            print(f"✓ {card_name:<40} (ID: {card_id}) × {count}")
        else:
            if candidates:
                hint = ", ".join(f'{c} (ID: {card_dict[c]})' for c in candidates[:3])
                print(f'✗ "{card_name}" → 一致なし')
                print(f"  候補: {hint}")
            else:
                print(f'✗ "{card_name}" → 一致なし（候補もなし）')
            errors.append(card_name)

    if errors:
        print(f"\nエラー: {len(errors)} 件のカードが見つかりませんでした。")
        print("decks/ ファイルのカード名を修正して再実行してください。")
        sys.exit(1)

    if len(card_ids) != 60:
        print(f"\nエラー: 合計 {len(card_ids)} 枚（60 枚必要）")
        sys.exit(1)

    print(f"\n合計: {len(card_ids)} 枚")
    output_path = write_deck_csv(card_ids, OUTPUT_DIR)
    print(f"出力: {output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: ルカリオデッキで動作確認する**

```bash
uv run python scripts/build_deck.py decks/lucario_20260621.py
```

期待される出力（例）：
```
✓ Lucario ex                             (ID: 673) × 2
✓ Mabosstiff ex                          (ID: 674) × 2
...
合計: 60 枚
出力: output/deck_20260621_XXXXXX.csv
```

- [ ] **Step 3: 生成された CSV を既存の `data/deck.csv` と比較する**

```bash
sort output/deck_*.csv > /tmp/new_sorted.txt
sort data/deck.csv > /tmp/orig_sorted.txt
diff /tmp/orig_sorted.txt /tmp/new_sorted.txt
```

期待される出力：差分なし（空）

- [ ] **Step 4: 全テストが引き続き通ることを確認する**

```bash
uv run pytest -v
```

期待される出力：`8 passed`（既存テストを含む）

- [ ] **Step 5: コミット**

```bash
git add scripts/build_deck.py
git commit -m "feat: デッキCSVビルダー CLI スクリプトを追加"
```
