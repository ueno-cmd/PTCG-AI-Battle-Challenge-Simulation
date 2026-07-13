"""ルカリオex 実挙動チェックノートブックの生成スクリプト

src/lucario_agent/main.py と src/grimmsnarl_agent/main.py の全文、および
両デッキ定義（decks/）をビルド時に埋め込み、Kaggle実行用の自己対戦ノートブックを生成する。

目的はバグ（クラッシュ）の実測検出：agent()が例外を投げた場面をトレースバック付きで
全件記録し（試合はフォールバックで続行）、ミラー戦＋対グリムスナール戦の2系列で
ルカリオエージェントの全経路を踏む。グリムスナールで実際に起きた
「シグネチャ追従漏れ→特定場面で毎回TypeError」型のバグがルカリオに無いかを確認する。
main.py を改修した後はこのスクリプトを再実行すればノートブックが追従する。

Usage: uv run python scripts/build_lucario_selfcheck_notebook.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "decks"))

REF_NB = ROOT / "src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb"
LUCARIO_PY = ROOT / "src/lucario_agent/main.py"
GRIMMSNARL_PY = ROOT / "src/grimmsnarl_agent/main.py"
DST = ROOT / "src/rl_experiments/lucario_selfcheck_experiment.ipynb"

# 参考ノートブックからコピーするセル（標準import / cgランタイム起動）
COPY_CELL_IDS = ["b6064b7f", "1a929ee3"]


def code_cell(cell_id: str, source: str) -> dict:
    return {
        "cell_type": "code", "id": cell_id, "metadata": {},
        "execution_count": None, "outputs": [], "source": source,
    }


def md_cell(cell_id: str, source: str) -> dict:
    return {"cell_type": "markdown", "id": cell_id, "metadata": {}, "source": source}


def load_deck_ids(module_name: str) -> list[int]:
    """decks/ の (card_id, count) 定義から60枚のIDリストを作る"""
    module = __import__(module_name)
    deck = [cid for cid, count in module.DECK for _ in range(count)]
    if len(deck) != 60:
        raise RuntimeError(f"{module_name}: expected 60 cards, got {len(deck)}")
    return deck


NOTE_MD = """# ルカリオex 実挙動チェック（クラッシュ検出・自己対戦）

**目的**: ルカリオexエージェント（`src/lucario_agent/main.py`）にクラッシュ型のバグが
無いかを実対戦で確認する。グリムスナールexエージェントでは「関数シグネチャ変更の
追従漏れ」により、自分のアクティブがきぜつして交代先を選ぶ場面で毎回TypeErrorが
発生するバグが実在した（2026-07-12発見・修正済み）。同型の事故を検出する。

- **系列1: ルカリオ ミラー戦**（1000試合）: 自コードの全経路を両側から踏む
- **系列2: ルカリオ vs グリムスナール**（1000試合）: 異なる対面（悪タイプ・
  ベンチ狙い技・Crustleなし）での経路確認。グリムスナール側（4修正ON）の
  クラッシュも同時に記録される
- agent()が例外を投げたら**トレースバック＋発生場面（context/turn）を全件記録**し、
  試合はフォールバック（全オプション昇順＝合法手）で続行する。
  クラッシュ0件なら「少なくとも自己対戦2000試合で踏んだ経路にクラッシュバグ無し」

**実行前の準備**: Add Input で cgライブラリを含む公式コンペデータをアタッチしておくこと
（デッキは埋め込み済みのため deck.csv のデータセットは不要）。
"""

DECK_CODE_TEMPLATE = """# ==================== デッキ（ビルド時に decks/ から埋め込み） ====================
# 手で編集せず、デッキ変更後は scripts/build_lucario_selfcheck_notebook.py を再実行すること
LUCARIO_DECK = {lucario_deck}

GRIMMSNARL_DECK = {grimmsnarl_deck}

assert len(LUCARIO_DECK) == 60 and len(GRIMMSNARL_DECK) == 60
print(f"lucario={{len(LUCARIO_DECK)}}枚 / grimmsnarl={{len(GRIMMSNARL_DECK)}}枚")"""

IMPORT_AGENTS_CODE = '''# ==================== エージェント読み込み＋クラッシュ記録ラッパー ====================
# 両main.pyはどちらも agent() を定義しているため、別モジュールとしてimportして分離する
import importlib
import traceback

lucario_main    = importlib.import_module("lucario_main")
grimmsnarl_main = importlib.import_module("grimmsnarl_main")

crash_records = []


def crash_logging_agent(fn, label):
    """agent()の例外をトレースバック付きで全件記録し、フォールバックで試合を続行する。
    クラッシュ検出用の計測ラッパー（本番の安全ネットではなく実験の観測装置）"""
    def _agent(obs):
        try:
            return fn(obs)
        except Exception:
            sel = obs.get("select") or {}
            crash_records.append({
                "label": label,
                "context": sel.get("context"),
                "turn": (obs.get("current") or {}).get("turn"),
                "traceback": traceback.format_exc(),
            })
            return list(range(len(sel.get("option") or [])))  # 全オプション昇順（合法手）
    return _agent


lucario_agent    = crash_logging_agent(lucario_main.agent, "lucario")
grimmsnarl_agent = crash_logging_agent(grimmsnarl_main.agent, "grimmsnarl")'''

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

RUN_CODE = '''# ==================== 自己対戦2系列（ミラー戦＋対グリムスナール戦） ====================
import time

GAMES = 1000  # 200試合では±7ptブレる実測があるため1000試合（±3pt精度）
CHECKPOINTS = [100, 200, 400, 600, 800, 1000]


def run_series(agent_a, agent_b, deck_a, deck_b, games, label):
    """agent_a側の視点で対戦を繰り返す。先手後手の偏りを消すため1試合ごとに座席を交代する"""
    results = []
    t0 = time.time()
    for i in range(games):
        if i % 2 == 0:
            r = play_game(agent_a, agent_b, deck_a, deck_b)
        else:
            r = -play_game(agent_b, agent_a, deck_b, deck_a)
        results.append(r)
        n = i + 1
        if n in CHECKPOINTS:
            wins = sum(1 for x in results if x > 0)
            losses = sum(1 for x in results if x < 0)
            print(f"[{label}] {n:>4}試合: 勝={wins:>4} 負={losses:>4} 引分={n - wins - losses:>4} "
                  f"勝率={wins / n:.3f} クラッシュ累計={len(crash_records)}")
    elapsed = time.time() - t0
    print(f"[{label}] 計{games}試合 {elapsed:.1f}秒（{elapsed / games * 1000:.0f}ms/試合）")
    return {"label": label, "results": results, "elapsed_sec": elapsed}


series_mirror = run_series(
    lucario_agent, lucario_agent, LUCARIO_DECK, LUCARIO_DECK,
    GAMES, "Lucario mirror",
)
series_cross = run_series(
    lucario_agent, grimmsnarl_agent, LUCARIO_DECK, GRIMMSNARL_DECK,
    GAMES, "Lucario vs Grimmsnarl",
)'''

CRASH_REPORT_CODE = '''# ==================== クラッシュ集計 ====================
# 同一バグは同じ末尾行（例外の種類＋メッセージ）に集約されるため、末尾行でグループ化する
from collections import Counter

print(f"クラッシュ総数: {len(crash_records)}件")
groups = Counter(
    (rec["label"], rec["traceback"].strip().splitlines()[-1]) for rec in crash_records
)
for (label, last_line), count in groups.most_common():
    print(f"\\n[{label}] {count}件: {last_line}")
    example = next(
        rec for rec in crash_records
        if rec["label"] == label and rec["traceback"].strip().splitlines()[-1] == last_line
    )
    print(f"  初出: turn={example['turn']} context={example['context']}")
    print("  " + example["traceback"].replace("\\n", "\\n  "))'''

SAVE_CODE = '''# ==================== 結果の保存 ====================
import json
from pathlib import Path

OUT_DIR = Path("/kaggle/working")
payload = {
    "series": [series_mirror, series_cross],
    "games": GAMES,
    "crash_count": len(crash_records),
    "crash_records": crash_records,
}
out_path = OUT_DIR / "lucario_selfcheck_results.json"
out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"saved: {out_path}")'''

PLOT_CODE = '''# ==================== 累積勝率の推移 ====================
# Kaggleではplotlyのグラフが表示されない実績があるため（2026-07-12実測）、
# matplotlib＋英語凡例で描画する（Kaggleに日本語フォントが無く日本語凡例は文字化けする）
import matplotlib.pyplot as plt

SERIES_STYLES = [
    (series_mirror, "Lucario mirror (expect ~50%)", "#8a8f98"),
    (series_cross, "Lucario vs Grimmsnarl", "#2a78d6"),
]

fig, ax = plt.subplots(figsize=(9, 5))
for series, label_en, color in SERIES_STYLES:
    results = series["results"]
    cum_rate = []
    wins = 0
    for i, r in enumerate(results, start=1):
        if r > 0:
            wins += 1
        cum_rate.append(wins / i)
    ax.plot(range(1, len(results) + 1), cum_rate, color=color, linewidth=2, label=label_en)
ax.axhline(0.5, color="#b0b4ba", linestyle="--", linewidth=1)
ax.set_title("Lucario self-check: cumulative win rate")
ax.set_xlabel("Games played")
ax.set_ylabel("Cumulative win rate")
ax.legend(loc="lower right")
ax.grid(True, color="#e6e8eb", linewidth=0.8)
ax.set_axisbelow(True)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)
plt.show()'''


def writefile_cell(cell_id: str, filename: str, agent_source: str, builder_note: str) -> dict:
    """main.py全文を %%writefile で別モジュールとして書き出すセルを作る"""
    source = (
        f"%%writefile {filename}\n"
        f"# {builder_note}\n"
        + agent_source
    )
    return code_cell(cell_id, source)


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

    lucario_source = LUCARIO_PY.read_text(encoding="utf-8")
    grimmsnarl_source = GRIMMSNARL_PY.read_text(encoding="utf-8")
    for name, source in [("lucario", lucario_source), ("grimmsnarl", grimmsnarl_source)]:
        if "def agent(" not in source:
            raise RuntimeError(f"{name} main.py に agent() がありません")

    deck_code = DECK_CODE_TEMPLATE.format(
        lucario_deck=load_deck_ids("lucario_20260621"),
        grimmsnarl_deck=load_deck_ids("grimmsnarl_20260701"),
    )

    builder_note = (
        "ビルド時に src/*/main.py の全文を埋め込んだもの。手で編集せず、"
        "main.py修正後に scripts/build_lucario_selfcheck_notebook.py を再実行すること。"
    )
    nb = {
        "cells": [
            md_cell("selfcheck-note", NOTE_MD),
            *copied,
            code_cell("deck-embed", deck_code),
            writefile_cell("lucario-main", "lucario_main.py", lucario_source, builder_note),
            writefile_cell("grimmsnarl-main", "grimmsnarl_main.py", grimmsnarl_source, builder_note),
            code_cell("import-agents", IMPORT_AGENTS_CODE),
            code_cell("battle-harness", HARNESS_CODE),
            code_cell("selfcheck-run", RUN_CODE),
            code_cell("crash-report", CRASH_REPORT_CODE),
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
