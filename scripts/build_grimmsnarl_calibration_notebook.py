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
