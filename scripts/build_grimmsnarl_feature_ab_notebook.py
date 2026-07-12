"""グリムスナールex 新ルールA/B実験ノートブックの生成スクリプト

src/grimmsnarl_agent/main.py の全文と、参考ノートブックのcgランタイム起動セルを
組み合わせて、Kaggle実行用のA/B実験ノートブックを生成する。
FEATURE_FLAGS（attacker_promotion / boss_attack_gate / deck_safety）を
ON/OFFで比較し、Task 1-4で追加した新ルールが勝率を押し上げているかを検証する。
main.py を改修した後はこのスクリプトを再実行すればノートブックが追従する。

Usage: uv run python scripts/build_grimmsnarl_feature_ab_notebook.py
"""
import json
from pathlib import Path

REF_NB = Path("src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb")
AGENT_PY = Path("src/grimmsnarl_agent/main.py")
DST = Path("src/rl_experiments/grimmsnarl_feature_ab_experiment.ipynb")

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


NOTE_MD = """# グリムスナールex 新ルールA/B実験（FEATURE_FLAGS ON vs OFF）

**目的**: Task 1〜4（ブランチ `feature/grimmsnarl-promotion-deck-safety`）で追加した
4つの判断レイヤー修正（`attacker_promotion` / `boss_attack_gate` / `deck_safety` の
3フラグで有効化される新ルール）が、実際の勝率を押し上げているかを検証する。

- **系列A vs B**（設定A=新ルールON、設定B=新ルールOFF・旧挙動相当）を1000試合戦わせる。
  Aの勝率が50%+5pt（55%）以上で一貫して勝ち越すなら「新ルールに効果あり」と判定する。
- **系列A vs A**（ノイズ基準）は設定Aどうしを1000試合戦わせ、対戦自体が持つ揺らぎ
  （先手後手・カード引き運）の大きさを測る。A vs Bの差がこの揺らぎ幅に埋もれるなら
  「効果なし」と判断する。
- 7/12の校正実験の教訓（200試合では±7ptブレる）を踏まえ、1000試合（±3pt精度）で実施する。

**実行前の準備**: Notebook の Add Input で `deck_20260705_185905.csv` を含む
データセットと、cgライブラリを含む公式コンペデータをアタッチしておくこと。

設計書: docs/superpowers/specs/2026-07-12-grimmsnarl-promotion-deck-safety-design.md
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
from cg.game import battle_finish, battle_select, battle_start

MAX_STEPS_PER_GAME = 700


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

AB_CODE = '''# ==================== 新ルールA/B実験（FEATURE_FLAGS ON vs OFF） ====================
import time

GAMES = 1000  # 7/12の校正実験の教訓：200試合では±7ptブレる。1000試合で±3pt精度
CHECKPOINTS = [100, 200, 400, 600, 800, 1000]

FLAGS_ON  = {"attacker_promotion": True,  "boss_attack_gate": True,  "deck_safety": True}
FLAGS_OFF = {"attacker_promotion": False, "boss_attack_gate": False, "deck_safety": False}

DEFAULT_TUNABLE = dict(TUNABLE_WEIGHTS)


def make_flagged_agent(flags: dict):
    """FEATURE_FLAGS（モジュールグローバル）を対局のたびに差し替えるエージェントを作る。
    TUNABLE_WEIGHTSは両設定ともデフォルト値に固定し、フラグの効果だけを比較する"""
    def _agent(obs_dict):
        FEATURE_FLAGS.clear()
        FEATURE_FLAGS.update(flags)
        TUNABLE_WEIGHTS.clear()
        TUNABLE_WEIGHTS.update(DEFAULT_TUNABLE)
        return agent(obs_dict)
    return _agent


def run_series(agent_a, agent_b, games, label):
    """agent_a側の視点で対戦を繰り返す。先手後手の偏りを消すため1試合ごとに座席を交代する"""
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
            print(f"[{label}] {n:>4}試合: A勝={wins:>4} A負={losses:>4} 引分={n - wins - losses:>4} A勝率={wins / n:.3f}")
    elapsed = time.time() - t0
    print(f"[{label}] 計{games}試合 {elapsed:.1f}秒（{elapsed / games * 1000:.0f}ms/試合）")
    return {"label": label, "results": results, "elapsed_sec": elapsed}


series_ab = run_series(
    make_flagged_agent(FLAGS_ON), make_flagged_agent(FLAGS_OFF),
    GAMES, "A(新ルールON) vs B(OFF)",
)
series_aa = run_series(
    make_flagged_agent(FLAGS_ON), make_flagged_agent(FLAGS_ON),
    GAMES, "A vs A(ノイズ基準)",
)'''

SAVE_CODE = '''# ==================== 結果の保存 ====================
OUT_DIR = Path("/kaggle/working")
payload = {
    "series_ab": series_ab,
    "series_aa": series_aa,
    "games": GAMES,
    "flags_on": FLAGS_ON,
}
out_path = OUT_DIR / "feature_ab_results.json"
out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"saved: {out_path}")'''

PLOT_CODE = '''# ==================== 累積勝率の推移 ====================
# matplotlibはKaggle上で日本語フォントを持たず凡例が文字化けするため、
# ブラウザフォントで描画するplotly（Kaggle標準搭載）を使う
import plotly.graph_objects as go

fig = go.Figure()
for series in (series_ab, series_aa):
    results = series["results"]
    cum_rate = []
    wins = 0
    for i, r in enumerate(results, start=1):
        if r > 0:
            wins += 1
        cum_rate.append(wins / i)
    fig.add_trace(go.Scatter(
        x=list(range(1, len(results) + 1)), y=cum_rate,
        mode="lines", name=series["label"],
    ))
fig.add_hline(y=0.5, line_dash="dash", line_width=1)
fig.add_hline(y=0.55, line_dash="dot", line_width=1)
fig.update_layout(
    title="新ルールA/B実験：累積勝率の推移（点線=+5pt効果ありライン）",
    xaxis_title="試合数",
    yaxis_title="Aの累積勝率",
    legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    width=900, height=500,
)
fig.show()'''


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
        "# 手で編集せず、main.py修正後に scripts/build_grimmsnarl_feature_ab_notebook.py を再実行すること。\n"
        + agent_source
    )
    if "TUNABLE_WEIGHTS" not in agent_source:
        raise RuntimeError("main.py に TUNABLE_WEIGHTS がありません（Task 1が未完了？）")
    if "FEATURE_FLAGS" not in agent_source:
        raise RuntimeError("main.py に FEATURE_FLAGS がありません（Task 1が未完了？）")

    nb = {
        "cells": [
            md_cell("feature-ab-note", NOTE_MD),
            *copied,
            code_cell("deck-load", DECK_CODE),
            code_cell("agent-body", agent_cell_src),
            code_cell("battle-harness", HARNESS_CODE),
            code_cell("feature-ab-run", AB_CODE),
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
