"""ジャモライコ vs イオナサンプル 校正ノートブックの生成スクリプト

src/jamoraiko_agent/main.py の全文と、既存イオナサンプルノートブックの
main.pyセル全文を、それぞれ別名前空間に読み込んで200試合自己対戦させる
Kaggle実行用ノートブックを生成する。main.py改修後はこのスクリプトを
再実行すればノートブックが追従する。

Usage: uv run python scripts/build_jamoraiko_vs_iono_notebook.py
"""
import inspect
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # decksパッケージをimportするため
from decks.jamoraiko_20260713 import DECK as JAMORAIKO_DECK_TUPLES  # noqa: E402

REF_NB = Path("src/rl_references/ptcg-tiny-rl-to-submission-baseline-guide.ipynb")
JAMORAIKO_PY = Path("src/jamoraiko_agent/main.py")
IONO_NB = Path("src/sample_notebook/a-sample-rule-based-agent-iono-s-deck.ipynb")
IONO_CELL_ID = "4c4dd070"
DST = Path("src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb")

# 参考ノートブックからコピーするセル（標準import / cgランタイム起動）
COPY_CELL_IDS = ["b6064b7f", "1a929ee3"]

# イオナサンプルの決め打ちデッキ構成（60枚）。
# src/sample_notebook/a-sample-rule-based-agent-iono-s-deck.ipynb のDecklistコメントと一致
IONO_DECK_TUPLES = [
    (265, 3),   # Iono's Voltorb
    (268, 3),   # Iono's Tadbulb
    (269, 3),   # Iono's Bellibolt ex
    (270, 3),   # Iono's Wattrel
    (271, 3),   # Iono's Kilowattrel
    (1086, 3),  # Buddy-Buddy Poffin
    (1097, 2),  # Night Stretcher
    (1110, 1),  # Max Rod
    (1118, 1),  # Energy Retrieval
    (1121, 3),  # Ultra Ball
    (1152, 2),  # Poké Pad
    (1227, 4),  # Lillie's Determination
    (1233, 4),  # Canari
    (1254, 3),  # Levincia
    (1182, 2),  # Boss's Orders
    (4, 20),    # Basic {L} Energy
]


def expand_deck(deck_tuples: list[tuple[int, int]]) -> list[int]:
    """(card_id, count)タプルリストを60枚のカードIDリストに展開する"""
    return [card_id for card_id, count in deck_tuples for _ in range(count)]


IONO_DECK = expand_deck(IONO_DECK_TUPLES)


def load_agent_module(name: str, source: str) -> types.ModuleType:
    """ソースコードを別名前空間のモジュールとしてロードする
    （複数エージェントが同名のグローバル変数(agent, card_table等)を持っていても衝突しない）"""
    mod = types.ModuleType(name)
    exec(compile(source, name, "exec"), mod.__dict__)
    return mod


def _strip_writefile_magic(source: str) -> str:
    """先頭行が%%writefileマジックならその行を取り除く（execできないため）"""
    lines = source.split("\n")
    if lines and lines[0].startswith("%%writefile"):
        return "\n".join(lines[1:])
    return source


# イオナサンプルのデッキ読み込みブロック（原文）。
# モジュールレベルでtry/exceptなしにopen()するため、Kaggle対話セッション等で
# deck.csvが存在しないと exec() 実行時点で FileNotFoundError となりノートブック
# 全体がクラッシュする（Critical指摘）。ビルド時にこの文字列を検索して安全な
# フォールバック付きバージョンに書き換える。
_IONO_DECK_LOAD_ORIGINAL = '''file_path = "deck.csv"
if not os.path.exists(file_path):
    file_path = "/kaggle_simulations/agent/" + file_path
with open(file_path, "r") as file:
    csv = file.read().split("\\n")
my_deck = []
for i in range(60):
    my_deck.append(int(csv[i]))'''


def _patch_iono_deck_load(iono_source: str, iono_deck: list[int]) -> str:
    """イオナサンプルのモジュールレベルデッキ読み込みコードを、
    try/except FileNotFoundError + ビルド時埋め込み定数へのフォールバック付き
    バージョンに書き換える。

    元コードと完全一致しない場合（サンプルノートブックの実装が変更された等）は
    無言でフォールバックせず RuntimeError を送出する。
    """
    if _IONO_DECK_LOAD_ORIGINAL not in iono_source:
        raise RuntimeError(
            "イオナサンプルのデッキ読み込みコードが想定と異なります。"
            "src/sample_notebook/a-sample-rule-based-agent-iono-s-deck.ipynb の内容が"
            "変更された可能性があります。ソースを確認してください。"
        )

    patched_block = f'''file_path = "deck.csv"
if not os.path.exists(file_path):
    file_path = "/kaggle_simulations/agent/" + file_path
try:
    with open(file_path, "r") as file:
        csv = file.read().split("\\n")
    my_deck = []
    for i in range(60):
        my_deck.append(int(csv[i]))
except FileNotFoundError:
    # Kaggle対話セッションではdeck.csvが存在しないため、ビルド時埋め込みのIONO_DECKにフォールバックする
    my_deck = {iono_deck!r}'''

    return iono_source.replace(_IONO_DECK_LOAD_ORIGINAL, patched_block)


def code_cell(cell_id: str, source: str) -> dict:
    return {
        "cell_type": "code", "id": cell_id, "metadata": {},
        "execution_count": None, "outputs": [], "source": source,
    }


def md_cell(cell_id: str, source: str) -> dict:
    return {"cell_type": "markdown", "id": cell_id, "metadata": {}, "source": source}


NOTE_MD = """# ジャモライコ vs イオナサンプル 校正実験

**目的**: ジャモライコエージェント（タケルライコex軸）が、現行のイオナ/ナンジャモ
サンプル（Kaggle LB 600〜877）に対して勝率で上回るかを、Kaggle上の自己対戦
200試合で確認する。macOSでは`libcg.so`が動かずローカル対戦できないための代替。

グリムスナールの校正実験（重みA/Bの差を検出するのに必要な試合数の検証）とは
目的が異なり、今回は**別デッキ同士の勝率そのもの**を測る。

両デッキとも60枚のカードIDリストをノートブックに定数として直接埋め込んでいる
（Kaggleは1データセットしかアップロードできない制約のため、ジャモライコの
`output/deck_jamoraiko_20260713.csv`データセットのみをAdd Inputすればよい。
イオナサンプル側はコード内蔵のため追加データセット不要）。

設計書: docs/superpowers/specs/2026-07-13-jamoraiko-vs-iono-calibration-design.md
"""

DECK_CODE = f'''# ジャモライコのデッキ（decks/jamoraiko_20260713.py の DECK をビルド時に展開）
JAMORAIKO_DECK = {expand_deck(JAMORAIKO_DECK_TUPLES)!r}

# イオナサンプルの決め打ちデッキ（60枚、ビルド時に埋め込み）
IONO_DECK = {IONO_DECK!r}

print(f"jamoraiko deck length={{len(JAMORAIKO_DECK)}}")
print(f"iono deck length={{len(IONO_DECK)}}")'''

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

AGENT_LOAD_CODE = '''# ==================== エージェント本体（名前空間分離） ====================
# jamoraiko_agent/main.py と イオナサンプルnotebookのmain.pyセルは同名の
# グローバル変数(agent, card_table等)を持つため、別モジュール名前空間に分離する
jamoraiko_mod = load_agent_module("jamoraiko_agent_module", JAMORAIKO_SOURCE)
iono_mod = load_agent_module("iono_agent_module", IONO_SOURCE)
print("jamoraiko agent loaded:", jamoraiko_mod.agent)
print("iono agent loaded:", iono_mod.agent)'''

CALIBRATION_CODE = '''# ==================== 校正実験（勝率測定） ====================
import time

GAMES = 200
CHECKPOINTS = [10, 20, 40, 80, 120, 160, 200]


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
            print(f"[{label}] {n:>3}試合: A勝={wins:>3} A負={losses:>3} 引分={n - wins - losses:>3} A勝率={wins / n:.3f}")
    elapsed = time.time() - t0
    print(f"[{label}] 計{games}試合 {elapsed:.1f}秒（{elapsed / games * 1000:.0f}ms/試合）")
    return {"label": label, "results": results, "elapsed_sec": elapsed}


series = run_series(
    jamoraiko_mod.agent, iono_mod.agent,
    JAMORAIKO_DECK, IONO_DECK,
    GAMES, "Jamoraiko vs Iono Sample",
)'''

SAVE_CODE = '''# ==================== 結果の保存 ====================
from pathlib import Path

OUT_DIR = Path("/kaggle/working")
payload = {"games": GAMES, "series": series}
out_path = OUT_DIR / "jamoraiko_vs_iono_results.json"
out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"saved: {out_path}")'''

PLOT_CODE = '''# ==================== 累積勝率の推移 ====================
# Kaggleではplotlyのグラフが表示されない実績があるため、matplotlib＋英語凡例で描画する
import matplotlib.pyplot as plt

results = series["results"]
cum_rate = []
wins = 0
for i, r in enumerate(results, start=1):
    if r > 0:
        wins += 1
    cum_rate.append(wins / i)

fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(range(1, len(results) + 1), cum_rate, color="#2a78d6", linewidth=2, label="Jamoraiko win rate vs Iono Sample")
ax.axhline(0.5, color="#b0b4ba", linestyle="--", linewidth=1)
ax.set_title("Jamoraiko vs Iono Sample: cumulative win rate")
ax.set_xlabel("Games played")
ax.set_ylabel("Cumulative win rate of Jamoraiko")
ax.legend(loc="lower right")
ax.grid(True, color="#e6e8eb", linewidth=0.8)
ax.set_axisbelow(True)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)
plt.show()
print(f"final win rate: {cum_rate[-1]:.3f}")'''


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

    jamoraiko_source = JAMORAIKO_PY.read_text(encoding="utf-8")

    iono_nb = json.loads(IONO_NB.read_text(encoding="utf-8"))
    iono_cells = {c.get("id"): c for c in iono_nb["cells"]}
    if IONO_CELL_ID not in iono_cells:
        raise RuntimeError(f"iono sample cell not found: {IONO_CELL_ID}")
    iono_source = _strip_writefile_magic(iono_cells[IONO_CELL_ID]["source"])
    iono_source = _patch_iono_deck_load(iono_source, IONO_DECK)

    sources_cell_src = (
        "# ==================== エージェントのソースコード（ビルド時に埋め込み） ====================\n"
        "# 手で編集せず、main.py改修後に scripts/build_jamoraiko_vs_iono_notebook.py を再実行すること。\n"
        f"JAMORAIKO_SOURCE = {jamoraiko_source!r}\n\n"
        f"IONO_SOURCE = {iono_source!r}\n"
    )

    load_helper_src = (
        "# ==================== 名前空間分離ヘルパー ====================\n"
        "import types\n\n\n"
        + inspect.getsource(load_agent_module)
    )

    nb = {
        "cells": [
            md_cell("calibration-note", NOTE_MD),
            *copied,
            code_cell("deck-load", DECK_CODE),
            code_cell("agent-sources", sources_cell_src),
            code_cell("load-helper", load_helper_src),
            code_cell("agent-load", AGENT_LOAD_CODE),
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
