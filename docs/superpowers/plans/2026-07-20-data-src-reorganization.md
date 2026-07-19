# data/・src/ フォルダ体系的整理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `data/`と`src/`に混在している「競技配布データ／ETL成果物／実験ログ／自前生成データ／提出物」「Pythonパッケージ／ノートブック資産」を用途別ディレクトリに再編成し、不要ファイルを削除し、`docs/steering/repo-structure.md`に実態を反映させる。

**Architecture:** 全作業はファイルシステム上の`mv`/`rm`とパス定数の追従修正のみ。新規ロジックは書かない。各タスクの最後に`uv run pytest`を実行し、パス変更ミスを機械的に検出する。`data/`配下と`src/**/*.ipynb`はGit非管理（`.gitignore`の`data/*`・`*.ipynb`）なので、移動・削除は`git mv`ではなく通常の`mv`/`rm`で行う。

**Tech Stack:** Python 3.12 / uv / pytest（既存構成のまま、変更なし）

## Global Constraints

- 全ての作業ディレクトリは絶対パスでなく `/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation` を起点とした相対パスで記述する
- 各タスクの最後に `uv run pytest -q` を実行し、ベースライン（541 passed / 0 failed）から件数が減らないことを確認する
- `data/battle_logs/`・`data/unity-catalog/`はディレクトリ名・場所とも変更しない（スコープ外、design docの「スコープ外」節参照）
- 削除タスク（Task 2）は破壊的操作のため、サブエージェントに委譲せずオーケストレーター自身が実行し、実行前にユーザーへ削除対象一覧を再提示して明示的な承認（y/n）を得ること（CLAUDE.mdルール6）
- 参照元の設計書: `docs/superpowers/specs/2026-07-20-data-src-reorganization-design.md`

---

## Task 1: 作業ブランチ作成とベースライン確認

**Files:** なし（Git操作とテスト実行のみ）

**Interfaces:**
- Produces: 作業ブランチ`chore/reorganize-data-src`、ベースラインのpytest結果（541 passed）

- [ ] **Step 1: 現在のブランチとworking treeがcleanであることを確認する**

Run: `git status`
Expected: `On branch main` / `nothing to commit, working tree clean`

- [ ] **Step 2: 作業ブランチを作成する**

Run: `git checkout -b chore/reorganize-data-src`
Expected: `Switched to a new branch 'chore/reorganize-data-src'`

- [ ] **Step 3: ベースラインとして全テストを実行する**

Run: `uv run pytest -q`
Expected: `541 passed` （failed 0件）。以降の各タスクはこの結果を基準に比較する。

---

## Task 2: 不要ファイルの削除（確認後）

**Files:**
- Delete: `data/cg/`
- Delete: `data/tmp_iono_analysis/`
- Delete: `data/deck.csv`
- Delete: `data/.DS_Store`
- Delete: `src/.DS_Store`
- Delete: 全`__pycache__`ディレクトリ

**Interfaces:**
- Consumes: なし
- Produces: 上記パスが存在しない状態（後続タスクはこれらのパスに触れない）

- [ ] **Step 1: 削除対象の一覧とサイズを表示する（ドライラン相当）**

Run:
```bash
du -sh data/cg data/tmp_iono_analysis data/deck.csv data/.DS_Store src/.DS_Store 2>/dev/null
find . -type d -name __pycache__ -not -path "./.venv/*"
```
Expected: 設計書に記載した6種類のパスが表示される。`data/tmp_iono_analysis`が約94MB、`data/cg`が約1.4MBであることを確認する。

- [ ] **Step 2: ユーザーに削除対象一覧を提示し、明示的な承認を得る**

上記Step 1の出力をそのままユーザーに提示し、「これらを削除してよいか（y/n）」を確認する。承認が得られるまで次のStepに進まない。

- [ ] **Step 3: 承認後に削除を実行する**

Run:
```bash
rm -rf data/cg data/tmp_iono_analysis data/deck.csv data/.DS_Store src/.DS_Store
find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} +
```
Expected: コマンドがエラーなく終了する

- [ ] **Step 4: 削除完了を確認する**

Run: `ls data/cg data/tmp_iono_analysis data/deck.csv 2>&1; find . -type d -name __pycache__ -not -path "./.venv/*"`
Expected: 全て `No such file or directory`（または該当なし）

- [ ] **Step 5: テストを実行し影響がないことを確認する**

Run: `uv run pytest -q`
Expected: `541 passed`（削除対象はいずれもコード未参照のため、件数は変化しない）

- [ ] **Step 6: コミット**

このタスクは`data/`・`__pycache__`いずれも`.gitignore`対象のため、`git status`に変化がないことを確認するのみでコミット不要。

Run: `git status`
Expected: `nothing to commit, working tree clean`

---

## Task 3: data/ 新構成への移動とコード追従修正

**Files:**
- Move: `data/JP_Card_Data.csv` → `data/competition/JP_Card_Data.csv`
- Move: `data/EN_Card_Data.csv` → `data/competition/EN_Card_Data.csv`
- Move: `data/Card_ID List_JP.pdf` → `data/competition/Card_ID List_JP.pdf`
- Move: `data/Card_ID List_EN.pdf` → `data/competition/Card_ID List_EN.pdf`
- Move: `data/sample_submission/` → `data/competition/sample_submission/`
- Move: `data/card_data_merged.csv` → `data/derived/card_data_merged.csv`
- Move: `data/top10_meta_targets.csv` → `data/derived/top10_meta_targets.csv`
- Move: `data/jamoraiko_vs_iono_results.json` → `data/experiments/jamoraiko_vs_iono/results.json`
- Move: `data/jamoraiko_vs_iono_turn_log.json` → `data/experiments/jamoraiko_vs_iono/turn_log.json`
- Modify: `pyproject.toml`
- Modify: `scripts/analyze_grimmsnarl_stall_metrics.py`
- Modify: `scripts/build_deck.py`
- Modify: `scripts/merge_card_data.py`
- Modify: `scripts/analyze_top10_meta.py`
- Modify: `tests/test_analyze_top10_meta.py`
- Modify: `tests/test_etl_gold.py`

**Interfaces:**
- Consumes: Task 2完了後の`data/`（不要ファイル削除済み）
- Produces: `data/competition/`・`data/derived/`・`data/experiments/jamoraiko_vs_iono/`ディレクトリと、それらを参照するパス定数

- [ ] **Step 1: ディレクトリを作成しファイルを移動する**

Run:
```bash
mkdir -p data/competition data/derived data/experiments/jamoraiko_vs_iono
mv data/JP_Card_Data.csv data/competition/
mv data/EN_Card_Data.csv data/competition/
mv "data/Card_ID List_JP.pdf" data/competition/
mv "data/Card_ID List_EN.pdf" data/competition/
mv data/sample_submission data/competition/sample_submission
mv data/card_data_merged.csv data/derived/
mv data/top10_meta_targets.csv data/derived/
mv data/jamoraiko_vs_iono_results.json data/experiments/jamoraiko_vs_iono/results.json
mv data/jamoraiko_vs_iono_turn_log.json data/experiments/jamoraiko_vs_iono/turn_log.json
```
Expected: エラーなく終了する

- [ ] **Step 2: 移動結果を確認する**

Run: `find data -maxdepth 2 -type d | sort && ls data/competition data/derived data/experiments/jamoraiko_vs_iono`
Expected: `data/competition`・`data/derived`・`data/experiments/jamoraiko_vs_iono`が存在し、それぞれ想定ファイルが入っている

- [ ] **Step 3: `pyproject.toml`のpythonpathを更新する**

`pyproject.toml`の該当箇所:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = [
    "src",
    "data/sample_submission",
]
```
を次のように変更する:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = [
    "src",
    "data/competition/sample_submission",
]
```

- [ ] **Step 4: `scripts/analyze_grimmsnarl_stall_metrics.py`のsys.pathを更新する**

該当箇所:
```python
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "data" / "sample_submission"))
```
を次のように変更する:
```python
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "data" / "competition" / "sample_submission"))
```

- [ ] **Step 5: `scripts/build_deck.py`の`CARD_CSV`を更新する**

該当箇所:
```python
PROJECT_ROOT = Path(__file__).parent.parent
CARD_CSV = PROJECT_ROOT / "data" / "EN_Card_Data.csv"
```
を次のように変更する:
```python
PROJECT_ROOT = Path(__file__).parent.parent
CARD_CSV = PROJECT_ROOT / "data" / "competition" / "EN_Card_Data.csv"
```

- [ ] **Step 6: `scripts/merge_card_data.py`のパスを更新する**

該当箇所:
```python
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

EN_CSV = DATA_DIR / "EN_Card_Data.csv"
JP_CSV = DATA_DIR / "JP_Card_Data.csv"
OUT_CSV = DATA_DIR / "card_data_merged.csv"
```
を次のように変更する:
```python
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

EN_CSV = DATA_DIR / "competition" / "EN_Card_Data.csv"
JP_CSV = DATA_DIR / "competition" / "JP_Card_Data.csv"
OUT_CSV = DATA_DIR / "derived" / "card_data_merged.csv"
```

- [ ] **Step 7: `scripts/analyze_top10_meta.py`のデフォルトパスを更新する**

該当箇所:
```python
def main() -> None:
    targets_csv = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/top10_meta_targets.csv")
    repo_root = Path(__file__).parent.parent
    report = build_report(
        targets_csv=targets_csv,
        battle_logs_dir=repo_root / "data" / "battle_logs",
        card_data_csv=repo_root / "data" / "EN_Card_Data.csv",
        catalog_dir=repo_root / "data" / "unity-catalog",
    )
```
を次のように変更する:
```python
def main() -> None:
    targets_csv = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/derived/top10_meta_targets.csv")
    repo_root = Path(__file__).parent.parent
    report = build_report(
        targets_csv=targets_csv,
        battle_logs_dir=repo_root / "data" / "battle_logs",
        card_data_csv=repo_root / "data" / "competition" / "EN_Card_Data.csv",
        catalog_dir=repo_root / "data" / "unity-catalog",
    )
```

ファイル冒頭のdocstringも更新する。該当箇所:
```python
"""TOP10メタ分析CLI。data/top10_meta_targets.csvを読み、対象バトルログを
デッキ分布・意思決定パターンの2観点で集約したMarkdownレポートを生成する。

使い方: uv run python scripts/analyze_top10_meta.py [targets_csv]
（省略時は data/top10_meta_targets.csv を使う）
"""
```
を次のように変更する:
```python
"""TOP10メタ分析CLI。data/derived/top10_meta_targets.csvを読み、対象バトルログを
デッキ分布・意思決定パターンの2観点で集約したMarkdownレポートを生成する。

使い方: uv run python scripts/analyze_top10_meta.py [targets_csv]
（省略時は data/derived/top10_meta_targets.csv を使う）
"""
```

- [ ] **Step 8: `tests/test_analyze_top10_meta.py`のパスを更新する**

該当箇所（3箇所とも同一パターン、`DATA_DIR / "EN_Card_Data.csv"`を検索して置換）:
```python
        card_data_csv=DATA_DIR / "EN_Card_Data.csv",
```
を次のように変更する（3箇所とも）:
```python
        card_data_csv=DATA_DIR / "competition" / "EN_Card_Data.csv",
```

- [ ] **Step 9: `tests/test_etl_gold.py`のパスを更新する**

該当箇所:
```python
FIXTURE_PATH = Path(__file__).parent.parent / "data" / "battle_logs" / "84580427.json"
CARD_DATA_PATH = Path(__file__).parent.parent / "data" / "EN_Card_Data.csv"
```
を次のように変更する:
```python
FIXTURE_PATH = Path(__file__).parent.parent / "data" / "battle_logs" / "84580427.json"
CARD_DATA_PATH = Path(__file__).parent.parent / "data" / "competition" / "EN_Card_Data.csv"
```

- [ ] **Step 10: テストを実行し全てパスすることを確認する**

Run: `uv run pytest -q`
Expected: `541 passed`（Task 1のベースラインと同じ件数）

- [ ] **Step 11: コミット**

```bash
git add data pyproject.toml scripts/analyze_grimmsnarl_stall_metrics.py scripts/build_deck.py scripts/merge_card_data.py scripts/analyze_top10_meta.py tests/test_analyze_top10_meta.py tests/test_etl_gold.py
git status
```
`data/`配下は`.gitignore`対象のため`git add data`は実質何もステージしないが、念のため実行して`git status`で意図通り（コード変更ファイルのみステージ）であることを確認してからコミットする。

```bash
git commit -m "$(cat <<'EOF'
refactor(data): data/を用途別ディレクトリ(competition/derived/experiments)に再編成

競技配布データ・自前生成の派生データ・実験ログがdata/直下にフラットに
混在していたため、用途別サブディレクトリに集約し、参照コードのパスを追従させた。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: src/ → notebooks/ の移動とスクリプト追従修正

**Files:**
- Move: `src/rl_references/` → `notebooks/references/`
- Move: `src/rl_experiments/` → `notebooks/experiments/`
- Move: `src/sample_notebook/` → `notebooks/samples/`
- Modify: `scripts/build_lucario_selfcheck_notebook.py`
- Modify: `scripts/build_grimmsnarl_feature_ab_notebook.py`
- Modify: `scripts/build_grimmsnarl_calibration_notebook.py`
- Modify: `scripts/build_jamoraiko_vs_iono_notebook.py`

**Interfaces:**
- Consumes: Task 3完了後のリポジトリ状態
- Produces: `notebooks/references/`・`notebooks/experiments/`・`notebooks/samples/`ディレクトリと、それらを参照するパス定数

- [ ] **Step 1: ディレクトリを移動する**

Run:
```bash
mkdir -p notebooks
mv src/rl_references notebooks/references
mv src/rl_experiments notebooks/experiments
mv src/sample_notebook notebooks/samples
```
Expected: エラーなく終了する

- [ ] **Step 2: 移動結果を確認する**

Run: `ls notebooks/references notebooks/experiments notebooks/samples && find src -maxdepth 1 -type d`
Expected: `notebooks/`配下に3ディレクトリがあり、`src`配下にノートブックディレクトリが存在しない（Pythonパッケージのディレクトリのみ残る）

- [ ] **Step 3: `scripts/build_lucario_selfcheck_notebook.py`のパスを更新する**

該当箇所:
```python
REF_NB = ROOT / "src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb"
LUCARIO_PY = ROOT / "src/lucario_agent/main.py"
GRIMMSNARL_PY = ROOT / "src/grimmsnarl_agent/main.py"
DST = ROOT / "src/rl_experiments/lucario_selfcheck_experiment.ipynb"
```
を次のように変更する（`LUCARIO_PY`・`GRIMMSNARL_PY`は`src/`のまま変更しない）:
```python
REF_NB = ROOT / "notebooks/references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb"
LUCARIO_PY = ROOT / "src/lucario_agent/main.py"
GRIMMSNARL_PY = ROOT / "src/grimmsnarl_agent/main.py"
DST = ROOT / "notebooks/experiments/lucario_selfcheck_experiment.ipynb"
```

- [ ] **Step 4: `scripts/build_grimmsnarl_feature_ab_notebook.py`のパスを更新する**

該当箇所:
```python
REF_NB = Path("src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb")
AGENT_PY = Path("src/grimmsnarl_agent/main.py")
DST = Path("src/rl_experiments/grimmsnarl_feature_ab_experiment.ipynb")
```
を次のように変更する（`AGENT_PY`は変更しない）:
```python
REF_NB = Path("notebooks/references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb")
AGENT_PY = Path("src/grimmsnarl_agent/main.py")
DST = Path("notebooks/experiments/grimmsnarl_feature_ab_experiment.ipynb")
```

- [ ] **Step 5: `scripts/build_grimmsnarl_calibration_notebook.py`のパスを更新する**

該当箇所:
```python
REF_NB = Path("src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb")
AGENT_PY = Path("src/grimmsnarl_agent/main.py")
DST = Path("src/rl_experiments/grimmsnarl_calibration_experiment.ipynb")
```
を次のように変更する（`AGENT_PY`は変更しない）:
```python
REF_NB = Path("notebooks/references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb")
AGENT_PY = Path("src/grimmsnarl_agent/main.py")
DST = Path("notebooks/experiments/grimmsnarl_calibration_experiment.ipynb")
```

同ファイル内のコメント`（\`data/experiments/20260712_grimmsnarl_calibration.json\`）`は`data/experiments/`のまま変更不要（Task 3で`data/experiments/`自体は移動していないため）。

- [ ] **Step 6: `scripts/build_jamoraiko_vs_iono_notebook.py`のパスとコメントを更新する**

該当箇所（パス定数）:
```python
REF_NB = Path("src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb")
JAMORAIKO_PY = Path("src/jamoraiko_agent/main.py")
IONO_NB = Path("src/sample_notebook/a-sample-rule-based-agent-iono-s-deck.ipynb")
IONO_CELL_ID = "4c4dd070"
DST = Path("src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb")
```
を次のように変更する（`JAMORAIKO_PY`は変更しない）:
```python
REF_NB = Path("notebooks/references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb")
JAMORAIKO_PY = Path("src/jamoraiko_agent/main.py")
IONO_NB = Path("notebooks/samples/a-sample-rule-based-agent-iono-s-deck.ipynb")
IONO_CELL_ID = "4c4dd070"
DST = Path("notebooks/experiments/jamoraiko_vs_iono_experiment.ipynb")
```

該当箇所（コメント、IONO_DECK_TUPLES手前）:
```python
# イオナサンプルの決め打ちデッキ構成（60枚）。
# src/sample_notebook/a-sample-rule-based-agent-iono-s-deck.ipynb のDecklistコメントと一致
```
を次のように変更する:
```python
# イオナサンプルの決め打ちデッキ構成（60枚）。
# notebooks/samples/a-sample-rule-based-agent-iono-s-deck.ipynb のDecklistコメントと一致
```

該当箇所（RuntimeErrorメッセージ）:
```python
        raise RuntimeError(
            "イオナサンプルのデッキ読み込みコードが想定と異なります。"
            "src/sample_notebook/a-sample-rule-based-agent-iono-s-deck.ipynb の内容が"
            "変更された可能性があります。ソースを確認してください。"
        )
```
を次のように変更する:
```python
        raise RuntimeError(
            "イオナサンプルのデッキ読み込みコードが想定と異なります。"
            "notebooks/samples/a-sample-rule-based-agent-iono-s-deck.ipynb の内容が"
            "変更された可能性があります。ソースを確認してください。"
        )
```

- [ ] **Step 7: テストを実行し全てパスすることを確認する**

Run: `uv run pytest -q`
Expected: `541 passed`（`tests/test_jamoraiko_vs_iono_notebook_build.py`・`tests/test_shadow_count_cell.py`は`_mod.DST`等スクリプト側の定数を参照する実装のため、Step 3-6の修正が正しければ自動的に追従する）

- [ ] **Step 8: コミット**

```bash
git add notebooks src/rl_references src/rl_experiments src/sample_notebook scripts/build_lucario_selfcheck_notebook.py scripts/build_grimmsnarl_feature_ab_notebook.py scripts/build_grimmsnarl_calibration_notebook.py scripts/build_jamoraiko_vs_iono_notebook.py
git status
```
`notebooks/`配下は`*.ipynb`が`.gitignore`対象のため実質ステージされないが、スクリプト側の変更が正しくステージされていることを確認する。

```bash
git commit -m "$(cat <<'EOF'
refactor(src): ノートブック資産をsrc/からnotebooks/へ分離

src/がPythonパッケージとGit非管理のノートブック群（参考資料・実験・
サンプル）で混在していたため、notebooks/配下に切り出し、生成スクリプトの
出力先パスを追従させた。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: ステアリングファイル（repo-structure.md）の更新

**Files:**
- Modify: `docs/steering/repo-structure.md`

**Interfaces:**
- Consumes: Task 3・Task 4完了後の最終ディレクトリ構成
- Produces: なし（ドキュメントのみ）

- [ ] **Step 1: `docs/steering/repo-structure.md`を以下の内容で上書きする**

```markdown
# ディレクトリ構成・ファイル責務

> このファイルは `/starter` コマンドで自動生成・上書きされます。
> 2026-07-20: data/・src/フォルダ再編成に伴い手動更新。

---

## 構成概要

コンペ提出用のポケモンカードゲームAIエージェント開発リポジトリ。
`src/`は実行可能なPythonパッケージのみ、`data/`は用途別に分けたデータ資産、
`notebooks/`はGit非管理のノートブック資産を置く。

---

## ディレクトリ構成

```
src/                        # Pythonパッケージ（Git管理・pythonpath対象）
├── <agent>_agent/          # 各対戦AIエージェント（main.pyにAgentクラス）
├── deck_builder/           # デッキ定義からdeck.csvを生成
└── etl/                    # バトルログの bronze/silver/gold 変換

decks/                      # デッキ定義（カードIDタプルのリスト）
scripts/                    # CLIツール（デッキ生成・ETL実行・分析・ノートブック生成）
tests/                      # pytestテストスイート

notebooks/                  # Git非管理のノートブック資産（*.ipynb）
├── references/             # 競技提供の参考ノートブック
├── experiments/            # 自前生成の実験ノートブック（scripts/build_*.pyが生成）
└── samples/                # 競技提供のサンプルノートブック

data/                       # Git非管理（.gitignoreのdata/*）。コンペ配布データ含むため再配布不可
├── competition/            # 競技配布データ（不変）
│   ├── JP_Card_Data.csv / EN_Card_Data.csv / Card_ID List_*.pdf
│   └── sample_submission/  # 競技公式サンプル（cgシミュレータ本体含む）
├── battle_logs/            # ダウンロードした生バトルログ（JSON）
├── unity-catalog/          # ETLパイプライン成果物（bronze/silver層）
├── experiments/            # 実験ログ・キャリブレーション結果
├── derived/                # スクリプトで再生成可能な自前生成データ
└── submission.tar.gz       # 提出物アーカイブ

output/                     # 実行時生成物（deck.csv出力など、Git非管理）
docs/                       # ドキュメント（要件・実装サマリ・レビュー・steering）
```

---

## 主要ファイル責務

- `src/<agent>_agent/main.py`: 各対戦AIエージェントの意思決定ロジック（`cg`ランタイムから呼ばれる`agent()`関数を実装）
- `src/deck_builder/`: `decks/*.py`のデッキ定義（カード名 or IDのタプル列）から提出用`deck.csv`を生成
- `src/etl/`: `data/battle_logs/`の生JSONを`data/unity-catalog/`のbronze（コピー）→silver（パース済みCSV）→gold（分析用集計）に変換
- `scripts/build_deck.py`: `decks/*.py`を読み`output/`にdeck.csvを出力
- `scripts/etl_battle_log.py`: 単一バトルログをbronze/silverに変換するCLI
- `scripts/merge_card_data.py`: `data/competition/`のEN/JP Card DataをJOINして`data/derived/card_data_merged.csv`を生成
- `scripts/analyze_top10_meta.py`: `data/derived/top10_meta_targets.csv`を読み、対象バトルログを分析してレポートを`output/`に出力
- `scripts/build_*_notebook.py`: `notebooks/references/`の参考ノートブックを元に`notebooks/experiments/`へ実験用ノートブックを生成
- `data/competition/`: 競技運営から配布されたデータ一式。改変しない
- `data/unity-catalog/`: ETLパイプラインの成果物置き場（medallion architecture命名）
```

- [ ] **Step 2: 変更内容を確認する**

Run: `git diff docs/steering/repo-structure.md`
Expected: テンプレートから上記内容への差分が表示される

- [ ] **Step 3: コミット**

```bash
git add docs/steering/repo-structure.md
git commit -m "$(cat <<'EOF'
docs(steering): repo-structure.mdをdata/src再編成後の実態に更新

テンプレートのまま放置されていたため、data/・src/・notebooks/の
新しいディレクトリ構成と各ファイルの責務を反映した。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: 最終検証

**Files:** なし（検証のみ）

**Interfaces:**
- Consumes: Task 1〜5の全成果物
- Produces: 完了報告

- [ ] **Step 1: 全テストを再実行する**

Run: `uv run pytest -q`
Expected: `541 passed`（Task 1のベースラインと同数）

- [ ] **Step 2: ディレクトリツリーを目視確認する**

Run:
```bash
find data -maxdepth 2 -type d | sort
find src -maxdepth 1 -type d | sort
find notebooks -maxdepth 2 -type d | sort
```
Expected: design docの「新しいディレクトリ構成」節と一致する

- [ ] **Step 3: git logで一連のコミットを確認する**

Run: `git log --oneline main..HEAD`
Expected: Task 3〜5で作成した3つのコミットが表示される

- [ ] **Step 4: ユーザーに完了を報告し、次の統合方法（マージ/PR）を確認する**

`superpowers:finishing-a-development-branch`スキルを使い、マージ・PR作成・そのまま保持のいずれにするかユーザーに確認する。
