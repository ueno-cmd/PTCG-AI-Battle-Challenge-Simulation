# グリムスナールex ハイブリッドチューニング ステップ0（校正実験）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 設計書 `docs/superpowers/specs/2026-07-12-grimmsnarl-hybrid-tuning-design.md` のステップ0を実装する。①`src/grimmsnarl_agent/main.py` のエネルギー配分数字8個を `TUNABLE_WEIGHTS` 辞書に集約し（挙動不変）、②その辞書を差し替えた2設定を自己対戦させて評価試合数を校正するKaggle実行用ノートブックを生成する。

**Architecture:** main.py はスコアラー内の数値リテラルを辞書参照に置き換えるだけの等価リファクタリング。ノートブックは生成スクリプト（`scripts/build_grimmsnarl_calibration_notebook.py`、git管理）が組み立てる：cgランタイム起動セルは参考ノートブックから機械的にコピーし、エージェント本体セルは main.py の実ファイル内容をビルド時に埋め込む（手動転記によるズレを排除。main.py改修後はスクリプト再実行で追従できる）。

**Tech Stack:** Python 3.12 / uv / pytest / nbformat 4.5 相当のJSON直組み / jq（検証）

## Global Constraints

- `TUNABLE_WEIGHTS` のキーは設計書の8個ちょうど：`grimmsnarl_base` / `grimmsnarl_slope` / `grimmsnarl_surplus_base` / `grimmsnarl_surplus_slope` / `fezandipiti_base` / `fezandipiti_slope` / `morpeko_base` / `morpeko_slope`。デフォルト値は現行の手書き値（9000/1000/3500/100/5000/500/4500/200）
- `_score_attach` の場合分け構造（ゲート条件・閾値2エネ/3エネ）・エネルギー以外のスコアは一切変更しない
- 既存テスト全件（リポジトリ全体292件）がPASSし続けること
- ノートブックのファイル名は `src/rl_experiments/grimmsnarl_calibration_experiment.ipynb`（命名規則 `{デッキ名}_{手法タグ}_experiment.ipynb`）。`*.ipynb` は .gitignore 対象のためコミットされない（生成スクリプトの方をコミットする）
- デッキ読み込みは既存実験と同じglobパターン `/kaggle/input/datasets/**/deck_20260705_185905.csv`
- 校正の試合数は A vs B 200試合 ＋ A vs A 200試合。チェックポイントは 10/20/40/80/120/160/200
- Kaggle上での実行はユーザーが行う。本計画のスコープはノートブック生成と静的検証まで

---

### Task 1: `TUNABLE_WEIGHTS` 辞書化（等価リファクタリング、TDD）

**Files:**
- Modify: `src/grimmsnarl_agent/main.py`（定数セクションに辞書追加、`_score_attach` の数値リテラルを辞書参照へ）
- Test: `tests/test_grimmsnarl_agent.py`（`TestScoreAttach` クラスの後に新クラス追加）

**Interfaces:**
- Consumes: 既存の `gm.FieldState` / `make_pokemon(id=..., energies=[...])` テストヘルパー（`tests/test_grimmsnarl_agent.py` 冒頭で定義済み）
- Produces: `gm.TUNABLE_WEIGHTS: dict[str, int]`（モジュール直下）。Task 2 のノートブックがこの辞書を `clear()`＋`update()` で差し替えて2設定のエージェントを作る

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_grimmsnarl_agent.py` の `TestScoreAttach` クラスの直後に追加：

```python
# ==================== TUNABLE_WEIGHTS ====================
class TestTunableWeights:
    """TUNABLE_WEIGHTS辞書（進化探索のチューニング対象、エネルギー配分8個）の検証"""

    EXPECTED_KEYS = {
        "grimmsnarl_base", "grimmsnarl_slope",
        "grimmsnarl_surplus_base", "grimmsnarl_surplus_slope",
        "fezandipiti_base", "fezandipiti_slope",
        "morpeko_base", "morpeko_slope",
    }

    def _make_fs(self):
        return gm.FieldState(
            field_counts=defaultdict(int, {gm.Grimmsnarl_ex: 1}), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), grimmsnarl_active=True,
            grimmsnarl_energy_count=0, impidimp_bench_idx=-1,
            morpeko_bench_idx=-1, morpeko_energy_count=0, rare_candy_in_hand=False,
            my_active_hp=200, my_active_id=0, op_active_hp=200, op_active_id=0, op_bench_hp=[],
        )

    def test_tunable_weights_has_exactly_energy_allocation_keys(self):
        """チューニング対象は設計書の8キーちょうど（増減したら設計書と不整合）"""
        assert set(gm.TUNABLE_WEIGHTS) == self.EXPECTED_KEYS

    def test_tunable_weights_defaults_match_handwritten_values(self):
        """デフォルト値＝手書きの現行値（挙動不変の根拠）"""
        assert gm.TUNABLE_WEIGHTS == {
            "grimmsnarl_base": 9000, "grimmsnarl_slope": 1000,
            "grimmsnarl_surplus_base": 3500, "grimmsnarl_surplus_slope": 100,
            "fezandipiti_base": 5000, "fezandipiti_slope": 500,
            "morpeko_base": 4500, "morpeko_slope": 200,
        }

    def test_score_attach_reflects_overridden_weights(self):
        """辞書を差し替えるとスコアが変わること（ノートブックからの差し替え運用の担保）"""
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, energies=[])
        fs = self._make_fs()
        saved = dict(gm.TUNABLE_WEIGHTS)
        try:
            gm.TUNABLE_WEIGHTS["grimmsnarl_base"] = 12000
            score = gm._score_attach(grimmsnarl, AreaType.ACTIVE, gm.Basic_D_Energy, fs)
            assert score == 12000
        finally:
            gm.TUNABLE_WEIGHTS.clear()
            gm.TUNABLE_WEIGHTS.update(saved)
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py::TestTunableWeights -v`
Expected: 3件FAIL（`AttributeError: module ... has no attribute 'TUNABLE_WEIGHTS'`）

- [ ] **Step 3: 最小実装を書く**

`src/grimmsnarl_agent/main.py` の `EPSILON` / `_rng` 定義ブロックの直後（「アタックID」セクションの前）に追加：

```python
# ==================== エネルギー配分のチューニング対象 ====================
# 進化探索（ハイブリッドチューニング）で調整する数字。デフォルト値は手書きの現行値。
# 実験ノートブック側からこの辞書を clear()+update() で差し替えて学習する。
# 場合分けの構造（ゲート条件・閾値）は _score_attach 側に固定で残す。
# 設計書: docs/superpowers/specs/2026-07-12-grimmsnarl-hybrid-tuning-design.md
TUNABLE_WEIGHTS = {
    "grimmsnarl_base":          9000,  # オーロンゲ2エネ未満の基礎点
    "grimmsnarl_slope":         1000,  # 同・エネ1枚ごとの減点
    "grimmsnarl_surplus_base":  3500,  # オーロンゲ2エネ確保後の基礎点
    "grimmsnarl_surplus_slope":  100,  # 同・エネ1枚ごとの減点
    "fezandipiti_base":         5000,  # キチキギスの基礎点
    "fezandipiti_slope":         500,  # 同・エネ1枚ごとの減点
    "morpeko_base":             4500,  # モルペコの基礎点
    "morpeko_slope":             200,  # 同・エネ1枚ごとの減点
}
```

`_score_attach` の該当3分岐を辞書参照に置き換える（コメントは現状のまま残す）：

```python
        if pokemon.id == Grimmsnarl_ex:
            if energy_count < 2:
                return TUNABLE_WEIGHTS["grimmsnarl_base"] - energy_count * TUNABLE_WEIGHTS["grimmsnarl_slope"]
            # シャドーバレット（悪悪=2エネ）は追加投資しても威力が変わらないため、
            # 確保後はキチキギスex・モルペコへの配分を優先する
            return TUNABLE_WEIGHTS["grimmsnarl_surplus_base"] - energy_count * TUNABLE_WEIGHTS["grimmsnarl_surplus_slope"]
        if pokemon.id == Fezandipiti_ex and energy_count < 3 and grimmsnarl_ready_or_absent:
            # クルーエルアローの実際のコストは無色3（本デッキは全て悪エネルギーのため
            # 悪3枚で支払える）
            return TUNABLE_WEIGHTS["fezandipiti_base"] - energy_count * TUNABLE_WEIGHTS["fezandipiti_slope"]
        if pokemon.id == Marnie_Morpeko and grimmsnarl_ready_or_absent:
            # スパイキーホイールは装着した悪エネルギー数に比例して際限なくダメージが伸びる
            # （20+悪エネルギー×40）ため上限を設けず、グリムスナールexの攻撃分確保後は
            # 積極的に投資する
            return TUNABLE_WEIGHTS["morpeko_base"] - energy_count * TUNABLE_WEIGHTS["morpeko_slope"]
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -q`
Expected: `91 passed`（既存88件＋新規3件、失敗0件）

- [ ] **Step 5: リポジトリ全体の回帰確認**

Run: `uv run pytest -q`
Expected: `295 passed`（292件＋新規3件）

- [ ] **Step 6: コミット**

```bash
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "refactor: エネルギー配分の数字8個をTUNABLE_WEIGHTS辞書に集約

ハイブリッドチューニング（ルールベース方策×進化探索）の土台。
デフォルト値は手書きの現行値のままで挙動不変（既存テスト88件で担保）。
実験ノートブックから辞書を差し替えて2設定の自己対戦を行えるようにする。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 校正実験ノートブックの生成スクリプト

**Files:**
- Create: `scripts/build_grimmsnarl_calibration_notebook.py`
- Create（生成物、git管理外）: `src/rl_experiments/grimmsnarl_calibration_experiment.ipynb`
- Reference (read-only): `src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb`（セルid `b6064b7f`=標準import、`1a929ee3`=cgランタイム起動 の2セルをビルド時にコピーする）
- Reference (read-only): `src/grimmsnarl_agent/main.py`（全文をビルド時にエージェントセルへ埋め込む）

**Interfaces:**
- Consumes: Task 1 の `TUNABLE_WEIGHTS`（main.py全文埋め込み経由でノートブック名前空間に入る）
- Produces: 実行可能ノートブック。セル構成は「①実験ノートmd ②標準import（コピー） ③cgランタイム起動（コピー） ④デッキ読み込み ⑤エージェント本体（main.py全文） ⑥対戦ハーネス ⑦校正実験ループ ⑧結果保存 ⑨学習曲線プロット」の9セル

- [ ] **Step 1: 生成スクリプトを書く**

`scripts/build_grimmsnarl_calibration_notebook.py` を以下の内容で作成する：

```python
"""グリムスナールex 校正実験ノートブックの生成スクリプト

src/grimmsnarl_agent/main.py の全文と、参考ノートブックのcgランタイム起動セルを
組み合わせて、Kaggle実行用の校正実験ノートブックを生成する。
main.py を改修した後はこのスクリプトを再実行すればノートブックが追従する。

Usage: uv run python scripts/build_grimmsnarl_calibration_notebook.py
"""
import json
from pathlib import Path

REF_NB = Path("src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb")
AGENT_PY = Path("src/grimmsnarl_agent/main.py")
DST = Path("src/rl_experiments/grimmsnarl_calibration_experiment.ipynb")

DECK_CSV_GLOB = "/kaggle/input/datasets/**/deck_20260705_185905.csv"

# 参考ノートブックからコピーするセル（標準import / cgランタイム起動）
COPY_CELL_IDS = ["b6064b7f", "1a929ee3"]


def code_cell(cell_id: str, source: str) -> dict:
    return {
        "cell_type": "code", "id": cell_id, "metadata": {},
        "execution_count": None, "outputs": [], "source": source,
    }


def md_cell(cell_id: str, source: str) -> dict:
    return {"cell_type": "markdown", "id": cell_id, "metadata": {}, "source": source}


NOTE_MD = """# グリムスナールex 校正実験（ハイブリッドチューニング ステップ0）

**目的**: 進化探索を回す前に「強い設定と弱い設定を何試合戦わせれば、強い方が
安定して勝ち越して見えるか」を実測する。2026-07-11のevo_search失敗
（4試合評価がノイズに支配され学習が成立しなかった）の再発防止。

- 設定A（強いはず）: `TUNABLE_WEIGHTS` のデフォルト値（手書きの現行値）
- 設定B（弱いはず）: `grimmsnarl_base` と `morpeko_base` を入れ替えた値
  （オーロンゲの攻撃準備より先にモルペコへエネルギーを注ぐ、明らかに悪い方針）

**実行前の準備**: Notebook の Add Input で `deck_20260705_185905.csv` を含む
データセットと、cgライブラリを含む公式コンペデータをアタッチしておくこと。

**見方**: A vs B の勝率がある試合数N以降一貫して60%を超えるなら、そのNが
ステップ1（本番チューニング）の1候補あたり評価試合数になる。
200試合で差が見えなければ、エネルギー配分は勝敗を左右していないという
持ち帰り（チューニング対象の再選定）になる。

設計書: docs/superpowers/specs/2026-07-12-grimmsnarl-hybrid-tuning-design.md
"""

DECK_CODE = f'''# 既存の提出ノートブック群と同じglobパターンで、アップロード済みの
# Kaggleデータセットから現行グリムスナールexデッキのdeck.csvを読み込む
DECK_CSV_GLOB = "{DECK_CSV_GLOB}"


def load_grimmsnarl_deck() -> list[int]:
    matches = glob.glob(DECK_CSV_GLOB, recursive=True)
    if not matches:
        raise FileNotFoundError(
            f"deck.csv not found via glob pattern: {{DECK_CSV_GLOB}}. "
            "Kaggle Notebookの Add Input で該当データセットをアタッチしてください。"
        )
    cards = [int(line.strip()) for line in Path(matches[0]).read_text().splitlines() if line.strip()]
    if len(cards) != 60:
        raise ValueError(f"expected 60 cards, got {{len(cards)}} from {{matches[0]}}")
    return cards


DECK = load_grimmsnarl_deck()
print(f"deck length={{len(DECK)}}")
print(DECK[:12], "...")'''

HARNESS_CODE = '''# ==================== 対戦ハーネス ====================
# make_weighted_agent: TUNABLE_WEIGHTS（モジュールグローバル）を対局のたびに
# 差し替えてから agent() を呼ぶラッパー。agent()は1手ごとに呼ばれるため、
# 2つの設定が同じ盤面計算ロジックを共有していても混線しない。
from cg.game import battle_finish, battle_select, battle_start

MAX_STEPS_PER_GAME = 700

DEFAULT_TUNABLE = dict(TUNABLE_WEIGHTS)


def make_weighted_agent(weights: dict):
    def _agent(obs_dict):
        TUNABLE_WEIGHTS.clear()
        TUNABLE_WEIGHTS.update(weights)
        return agent(obs_dict)
    return _agent


def play_game(agent_a, agent_b, deck_a, deck_b, max_steps=MAX_STEPS_PER_GAME) -> int:
    """1試合対戦する。agent_a勝ち=+1 / 負け=-1 / 引き分け・打ち切り=0"""
    obs, start_data = battle_start(deck_a, deck_b)
    if getattr(start_data, "errorPlayer", -1) >= 0:
        raise ValueError(f"deck error: player={start_data.errorPlayer}, type={start_data.errorType}")
    steps = 0
    try:
        while obs["current"]["result"] < 0 and steps < max_steps:
            your_index = obs["current"]["yourIndex"]
            selected = agent_a(obs) if your_index == 0 else agent_b(obs)
            obs = battle_select(selected)
            steps += 1
        result = obs["current"]["result"]
    finally:
        battle_finish()
    if result == 0:
        return 1
    if result == 1:
        return -1
    return 0'''

CALIBRATION_CODE = '''# ==================== 校正実験 ====================
import time

GAMES = 200
CHECKPOINTS = [10, 20, 40, 80, 120, 160, 200]

# 設定B: エネルギー配分の優先順位をわざと壊す（オーロンゲ⇔モルペコの基礎点を入れ替え）
BROKEN_WEIGHTS = dict(DEFAULT_TUNABLE)
BROKEN_WEIGHTS["grimmsnarl_base"], BROKEN_WEIGHTS["morpeko_base"] = (
    BROKEN_WEIGHTS["morpeko_base"], BROKEN_WEIGHTS["grimmsnarl_base"],
)
print("設定B（壊した設定）:", BROKEN_WEIGHTS)


def run_series(weights_a, weights_b, games, label):
    """weights_a側の視点で対戦を繰り返す。先手後手の偏りを消すため1試合ごとに座席を交代する"""
    agent_a = make_weighted_agent(weights_a)
    agent_b = make_weighted_agent(weights_b)
    results = []
    t0 = time.time()
    for i in range(games):
        if i % 2 == 0:
            r = play_game(agent_a, agent_b, DECK, DECK)
        else:
            r = -play_game(agent_b, agent_a, DECK, DECK)
        results.append(r)
        n = i + 1
        if n in CHECKPOINTS:
            wins = sum(1 for x in results if x > 0)
            losses = sum(1 for x in results if x < 0)
            print(f"[{label}] {n:>3}試合: A勝={wins:>3} A負={losses:>3} 引分={n - wins - losses:>3} A勝率={wins / n:.3f}")
    elapsed = time.time() - t0
    print(f"[{label}] 計{games}試合 {elapsed:.1f}秒（{elapsed / games * 1000:.0f}ms/試合）")
    return {"label": label, "results": results, "elapsed_sec": elapsed}


series_ab = run_series(DEFAULT_TUNABLE, BROKEN_WEIGHTS, GAMES, "A(手書き) vs B(壊した設定)")
series_aa = run_series(DEFAULT_TUNABLE, DEFAULT_TUNABLE, GAMES, "A vs A (ノイズ基準線)")'''

SAVE_CODE = '''# ==================== 結果の保存 ====================
OUT_DIR = Path("/kaggle/working")
payload = {
    "default_tunable": DEFAULT_TUNABLE,
    "broken_weights": BROKEN_WEIGHTS,
    "games": GAMES,
    "series": [series_ab, series_aa],
}
out_path = OUT_DIR / "calibration_results.json"
out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"saved: {out_path}")'''

PLOT_CODE = '''# ==================== 累積勝率の推移 ====================
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(9, 5))
for series in (series_ab, series_aa):
    results = series["results"]
    cum_rate = []
    wins = 0
    for i, r in enumerate(results, start=1):
        if r > 0:
            wins += 1
        cum_rate.append(wins / i)
    ax.plot(range(1, len(results) + 1), cum_rate, label=series["label"])
ax.axhline(0.5, linestyle="--", linewidth=1)
ax.axhline(0.6, linestyle=":", linewidth=1)
ax.set_xlabel("games")
ax.set_ylabel("cumulative win rate of A")
ax.set_title("Calibration: how many games until the stronger setting is visible?")
ax.legend()
ax.grid(True, alpha=0.3)
plt.show()'''


def main() -> None:
    ref = json.loads(REF_NB.read_text(encoding="utf-8"))
    ref_cells = {c.get("id"): c for c in ref["cells"]}
    copied = []
    for cid in COPY_CELL_IDS:
        if cid not in ref_cells:
            raise RuntimeError(f"reference cell not found: {cid}")
        cell = json.loads(json.dumps(ref_cells[cid]))  # deep copy
        cell["outputs"] = []
        cell["execution_count"] = None
        copied.append(cell)

    agent_source = AGENT_PY.read_text(encoding="utf-8")
    agent_cell_src = (
        "# ==================== エージェント本体 ====================\n"
        "# src/grimmsnarl_agent/main.py の全文をビルド時に埋め込んだもの。\n"
        "# 手で編集せず、main.py修正後に scripts/build_grimmsnarl_calibration_notebook.py を再実行すること。\n"
        + agent_source
    )
    if "TUNABLE_WEIGHTS" not in agent_source:
        raise RuntimeError("main.py に TUNABLE_WEIGHTS がありません（Task 1が未完了？）")

    nb = {
        "cells": [
            md_cell("calibration-note", NOTE_MD),
            *copied,
            code_cell("deck-load", DECK_CODE),
            code_cell("agent-body", agent_cell_src),
            code_cell("battle-harness", HARNESS_CODE),
            code_cell("calibration-run", CALIBRATION_CODE),
            code_cell("save-results", SAVE_CODE),
            code_cell("plot-curve", PLOT_CODE),
        ],
        "metadata": ref.get("metadata", {}),
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {DST} with {len(nb['cells'])} cells")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: スクリプトを実行してノートブックを生成する**

Run: `uv run python scripts/build_grimmsnarl_calibration_notebook.py`
Expected: `wrote src/rl_experiments/grimmsnarl_calibration_experiment.ipynb with 9 cells`

- [ ] **Step 3: 静的検証（JSON構文・セル数・Python構文・キー要素の存在）**

Run:
```bash
jq empty src/rl_experiments/grimmsnarl_calibration_experiment.ipynb && echo "JSON_OK"
jq '.cells | length' src/rl_experiments/grimmsnarl_calibration_experiment.ipynb
jq -r '.cells[] | select(.cell_type=="code") | (.source | if type=="array" then join("") else . end) + "\n#---CELL-BREAK---\n"' \
  src/rl_experiments/grimmsnarl_calibration_experiment.ipynb > /tmp/calibration_cells.py
python3 -c "
import ast
src = open('/tmp/calibration_cells.py').read()
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
rm /tmp/calibration_cells.py
grep -c 'TUNABLE_WEIGHTS' <(jq -r '.cells[].source | if type=="array" then join("") else . end' src/rl_experiments/grimmsnarl_calibration_experiment.ipynb)
jq -r '.cells[] | select(.id=="deck-load") | .source' src/rl_experiments/grimmsnarl_calibration_experiment.ipynb | grep -F '/kaggle/input/datasets/**/deck_20260705_185905.csv'
```
Expected: `JSON_OK` / `9` / `ALL_CELLS_SYNTAX_OK` / TUNABLE_WEIGHTSの出現数が1以上 / globパターン行が出力される

- [ ] **Step 4: gitignoreの確認（ノートブックが追跡されないこと）**

Run: `git status --short src/rl_experiments/`
Expected: 出力が空（`*.ipynb` はgitignore対象）

- [ ] **Step 5: 生成スクリプトをコミット**

```bash
git add scripts/build_grimmsnarl_calibration_notebook.py
git commit -m "feat: グリムスナールex校正実験ノートブックの生成スクリプトを追加

TUNABLE_WEIGHTSのデフォルト値（手書き）vs わざと壊した値を各200試合
自己対戦させ、何試合で実力差が見えるかを測るKaggle実行用ノートブックを
生成する。main.py全文はビルド時に埋め込むため手動転記が不要。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

このタスクが完了したら、ユーザーに次のように伝えて完了報告する：「`src/rl_experiments/grimmsnarl_calibration_experiment.ipynb` をKaggleにアップロードし、`deck_20260705_185905.csv` を含むデータセットと公式コンペデータをAdd Inputでアタッチして実行してください。見るポイントは①A vs Bの勝率が何試合目から一貫して60%を超えるか、②A vs Aが50%付近に収束しているか、③1試合あたりの実行時間、の3点です。結果（`calibration_results.json` と実行ログ）を持ち帰っていただければ、ステップ1（本番チューニング）の試合数・世代数を決めます」
