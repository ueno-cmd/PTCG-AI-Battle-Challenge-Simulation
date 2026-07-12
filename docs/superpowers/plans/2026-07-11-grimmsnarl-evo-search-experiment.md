# グリムスナールex 進化的方策探索(evo_search)実験ノートブック作成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb`（進化的方策探索によるRL学習→提出パッケージングまでの参考ノートブック）を土台に、現行のグリムスナールex（オーロンゲ）デッキに対して同じ手法を試す実験ノートブック `src/rl_experiments/grimmsnarl_evo_search_experiment.ipynb` を作成する。

**Architecture:** 参考ノートブックのJSON構造をそのまま複製し、「デッキ読み込み」セル1箇所のみを、Kaggle公式サンプルデッキ読み込みから、ユーザーが既存のグリムスナールex提出ノートブック群で使っている glob パターン（`/kaggle/input/datasets/**/deck_20260705_185905.csv`）で既存Kaggleデータセットの`deck.csv`を検索・読み込む方式に置き換える。あわせて実験の目的・出典を明記する説明セルを1つ追加する。学習量パラメータ・評価ロジック・提出パッケージングロジックは変更しない。

**Tech Stack:** Jupyter Notebook (nbformat 4.5) / Python 3.12 / jq（JSON検証）。実行はcgライブラリ依存・Kaggleデータセットアタッチ依存のためKaggle上でのみ可能（macOSローカルでは不可）。

## Global Constraints

- 実験ノートブックのファイル名は `src/rl_experiments/grimmsnarl_evo_search_experiment.ipynb`（個人名を含めない、手法タグ`evo_search`を使う命名規則。ユーザー承認済み）
- `*.ipynb`は`.gitignore`のプロジェクト全体ルールで既に追跡対象外なので、この作業でコミットは発生しない
- 学習量パラメータ（`GENERATIONS=4`、`POPULATION=8`、`GAMES_PER_CANDIDATE=4`、`FINAL_EVAL_GAMES=20`、`MUTATION_SCALE=0.35`、`MAX_STEPS_PER_GAME=700`）は変更しない
- 評価ロジック（`evaluate_weights`が学習方策とDEFAULT_WEIGHTS方策を同じデッキで自己対戦させる）は変更しない
- デッキ読み込み方式は、ユーザーが既存の提出ノートブックで使っているのと同じglobパターン
  `glob.glob('/kaggle/input/datasets/**/deck_20260705_185905.csv', recursive=True)[0]` を使う
  （`deck_20260705_185905.csv`は`decks/grimmsnarl_20260701.py`の現行DECKと60枚完全一致することをこのセッション内で確認済み）
- 実行はcgライブラリとKaggleデータセットのアタッチに依存するため、Kaggle上でユーザーが行う。このタスクの範囲はノートブックファイルの作成までで、Kaggle実行結果の確認・次のステップ判断はこのタスクの範囲外

---

## Task 1: 実験ノートブックの作成

**Files:**
- Create: `src/rl_experiments/grimmsnarl_evo_search_experiment.ipynb`
- Reference (read-only, 変更しない): `src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb`

**Interfaces:**
- Consumes: なし（このプロジェクトで最初のタスク）
- Produces: `src/rl_experiments/grimmsnarl_evo_search_experiment.ipynb`（nbformat 4.5、24セル構成のJupyterノートブック、うちセルid `0c6580fb` が新しいデッキ読み込みロジックを持つ）。Task 2の検証ステップがこのファイルパスと `0c6580fb` のセル内容を直接検証する

- [ ] **Step 1: ディレクトリを作成する**

Run: `mkdir -p src/rl_experiments`
Expected: コマンドがエラーなく終了する（既存でも問題ない）

- [ ] **Step 2: 変換スクリプトを作成する**

以下の内容で `/tmp/build_grimmsnarl_evo_search_experiment.py` を作成する（一時ファイル。Task完了後に削除してよい）。

```python
import json
from pathlib import Path

SRC = Path("src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb")
DST = Path("src/rl_experiments/grimmsnarl_evo_search_experiment.ipynb")

DECK_CSV_GLOB = "/kaggle/input/datasets/**/deck_20260705_185905.csv"

nb = json.loads(SRC.read_text(encoding="utf-8"))

NEW_DECK_MD = """## Deck

**2026-07-11実験版の変更点**: 公式サンプルデッキの代わりに、現行のグリムスナールex（オーロンゲ）デッキを使う。
既存のグリムスナールex提出ノートブック群と同じ glob パターンで、Kaggleにアップロード済みの
データセットから `deck_20260705_185905.csv` を検索して読み込む。Kaggle上でこのノートブックを実行する際は、
その`deck_20260705_185905.csv`を含むデータセットを Notebook の Add Input でアタッチしておくこと。

目的は、MakiMakiAi型（進化的方策探索）のRL手法が既存デッキに対して学習・収束するか、
学習後の重みや勝率がどう変化するかを小さく試すこと。

A valid `deck.csv` has exactly 60 lines. Each line is a card ID. The agent returns this list when
`obs.select is None`, which means the game is asking for the deck before the first turn."""

NEW_DECK_CODE = '''# 2026-07-11実験: 公式サンプルデッキではなく、現行グリムスナールex（オーロンゲ）デッキを使う。
# 既存の提出ノートブック群と同じ glob パターンで、アップロード済みのKaggleデータセットから
# deck.csv を検索する（tar.add(glob.glob("/kaggle/input/datasets/**/deck_20260705_185905.csv",
# recursive=True)[0], arcname="deck.csv") と同じ探索方式。glob は先頭セルで import 済み）。
DECK_CSV_GLOB = "''' + DECK_CSV_GLOB + '''"


def load_grimmsnarl_deck() -> list[int]:
    matches = glob.glob(DECK_CSV_GLOB, recursive=True)
    if not matches:
        raise FileNotFoundError(
            f"deck.csv not found via glob pattern: {DECK_CSV_GLOB}. "
            "Kaggle Notebookの Add Input で該当データセットをアタッチしてください。"
        )
    cards = [int(line.strip()) for line in Path(matches[0]).read_text().splitlines() if line.strip()]
    if len(cards) != 60:
        raise ValueError(f"expected 60 cards, got {len(cards)} from {matches[0]}")
    return cards


DECK = load_grimmsnarl_deck()
print(f"deck length={len(DECK)}")
print(DECK[:12], "...")'''

EXPERIMENT_NOTE_MD = """## 実験ノート（2026-07-11）

このノートブックは `src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb`
（進化的方策探索によるRL学習→`main.py`書き出し→`submission.tar.gz`パッケージングまでの参考実装）を
そのまま複製し、「デッキ」セルのみを現行のグリムスナールex（オーロンゲ）デッキに差し替えたものです。

目的：MakiMakiAi型（進化的方策探索）の手法を、新しいドラパルトex軸デッキではなく、
まず手元にある実績のあるデッキに小さく試し、世代を追うごとに報酬・勝率が変化するか、
学習後の重みがDEFAULT_WEIGHTSからどう変わるかを観察する。
学習量パラメータ・評価ロジック・提出パッケージングロジックは元のノートブックから変更していない。"""

target_ids = {"28b262d2", "0c6580fb"}
found = set()
for cell in nb["cells"]:
    cid = cell.get("id")
    if cid == "28b262d2":
        cell["source"] = NEW_DECK_MD
        found.add(cid)
    elif cid == "0c6580fb":
        cell["source"] = NEW_DECK_CODE
        cell["outputs"] = []
        cell["execution_count"] = None
        found.add(cid)
    if cell.get("cell_type") == "code":
        cell["outputs"] = []
        cell["execution_count"] = None

missing = target_ids - found
if missing:
    raise RuntimeError(f"target cell ids not found: {missing}")

note_cell = {
    "cell_type": "markdown",
    "id": "grimmsnarl-evo-search-note",
    "metadata": {},
    "source": EXPERIMENT_NOTE_MD,
}
nb["cells"].insert(1, note_cell)

DST.parent.mkdir(parents=True, exist_ok=True)
DST.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"wrote {DST} with {len(nb['cells'])} cells")
```

- [ ] **Step 3: 変換スクリプトを実行する**

Run: `python3 /tmp/build_grimmsnarl_evo_search_experiment.py`
Expected: 標準出力に `wrote src/rl_experiments/grimmsnarl_evo_search_experiment.ipynb with 24 cells` と表示され、エラーなく終了する

- [ ] **Step 4: 一時スクリプトを削除する**

Run: `rm /tmp/build_grimmsnarl_evo_search_experiment.py`
Expected: エラーなく終了する

- [ ] **Step 5: コミット**

`*.ipynb`は`.gitignore`で追跡対象外のため、`git add`/`git commit`は不要（`git status`で新規ファイルが表示されないことを確認するのみでよい）。

Run: `git status --short src/rl_experiments/`
Expected: 出力が空（何も表示されない＝gitignoreにより無視されている）

---

## Task 2: ノートブックの静的検証

**Files:**
- Verify: `src/rl_experiments/grimmsnarl_evo_search_experiment.ipynb`

**Interfaces:**
- Consumes: Task 1が作成した `src/rl_experiments/grimmsnarl_evo_search_experiment.ipynb`
- Produces: なし（検証のみ。Kaggle上での実行確認・データセットアタッチ確認はこのタスクの範囲外）

実行環境（macOS）では`cg`ライブラリが無く、`/kaggle/input/`も存在しないため、このノートブックをローカルで実行・glob解決することはできない。代わりに以下の静的チェックで正当性を確認する。

- [ ] **Step 1: JSON構文を検証する**

Run: `jq empty src/rl_experiments/grimmsnarl_evo_search_experiment.ipynb && echo "JSON_OK"`
Expected: `JSON_OK` が出力される（jqがパースエラーを出さない）

- [ ] **Step 2: セル数を確認する**

Run: `jq '.cells | length' src/rl_experiments/grimmsnarl_evo_search_experiment.ipynb`
Expected: `24`（元の23セル + 実験ノートmdセル1つ）

- [ ] **Step 3: 全コードセルがPythonとして構文的に有効か確認する**

Run:
```bash
jq -r '.cells[] | select(.cell_type=="code") | (.source | if type=="array" then join("") else . end) + "\n#---CELL-BREAK---\n"' \
  src/rl_experiments/grimmsnarl_evo_search_experiment.ipynb > /tmp/grimmsnarl_evo_search_cells.py
python3 -c "
import ast
src = open('/tmp/grimmsnarl_evo_search_cells.py').read()
for i, block in enumerate(src.split('#---CELL-BREAK---')):
    block = block.strip()
    if not block:
        continue
    try:
        ast.parse(block)
    except SyntaxError as e:
        raise SystemExit(f'cell block {i} has a syntax error: {e}')
print('ALL_CELLS_SYNTAX_OK')
"
rm /tmp/grimmsnarl_evo_search_cells.py
```
Expected: `ALL_CELLS_SYNTAX_OK` が出力される（構文エラーが無い）

- [ ] **Step 4: デッキ読み込みセルのglobパターンが正しいか確認する**

Run:
```bash
jq -r '.cells[] | select(.id=="0c6580fb") | .source' src/rl_experiments/grimmsnarl_evo_search_experiment.ipynb | grep -F '/kaggle/input/datasets/**/deck_20260705_185905.csv'
```
Expected: 該当行がそのまま出力される（globパターン文字列がセル内に存在することの確認）

- [ ] **Step 5: 参考ノートブック本体が変更されていないことを確認する**

Run: `diff <(jq -S . src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb) <(git show HEAD:src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb 2>/dev/null | jq -S . 2>/dev/null) || echo "SKIP: ipynb is gitignored, compare by eye if needed"`
Expected: `*.ipynb`はgit管理外のため多くの場合`SKIP`が出力される。実質的な確認は「Task 1のStep 2で参照(Reference)としてのみ扱い、書き込み対象に含めていないこと」で担保されている

このタスクが完了したら、ユーザーに次のように伝えて完了報告する：「`src/rl_experiments/grimmsnarl_evo_search_experiment.ipynb`をKaggleにアップロードし、`deck_20260705_185905.csv`を含むデータセットをNotebookのAdd Inputでアタッチしてから実行してください。確認したいのは①世代ごとの報酬・勝率の推移、②学習後の重みがDEFAULT_WEIGHTSからどう変化したか、の2点です」。
