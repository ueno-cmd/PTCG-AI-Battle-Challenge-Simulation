# ジャモライコ vs イオナサンプル 校正ノートブック Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ジャモライコが現行のイオナ/ナンジャモサンプルに対して勝率で上回るかを、Kaggle Notebook上の自己対戦（200試合）で確認するための、ノートブック生成スクリプトを実装する。

**Architecture:** 既存の`scripts/build_grimmsnarl_calibration_notebook.py`と同じビルド方式（参考ノートブックからcgランタイム起動セルをコピーし、エージェント本体・対戦ハーネス等のセルを合成）を踏襲する。2つのエージェント（`src/jamoraiko_agent/main.py`と既存イオナサンプル）は同名のグローバル変数（`agent`, `card_table`等）を持つため、`types.ModuleType`+`exec`で別々の名前空間に分離する。両デッキとも60枚のカードIDリストをノートブックに定数として直接埋め込む（Kaggleは1データセットしかアップロードできない制約のため）。

**Tech Stack:** Python 3.12 / uv / pytest（ビルドスクリプト自体のロジックのみテスト対象。生成されたノートブックはKaggle上の`cg`ライブラリでしか実行できないためpytest対象外）

## Global Constraints

- 生成物`src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`は`.gitignore`対象のためコミットしない
- 影武者カウント（`make_shadow_agent`等）は今回不要（同一ロジックのA/B比較ではないため）
- 負け試合の盤面ログ保存・質的分析は今回のスコープ外（勝率測定のみ）
- 試合数は200試合をデフォルトとする（`docs/superpowers/specs/2026-07-13-jamoraiko-vs-iono-calibration-design.md`参照）
- コードコメントは日本語（CLAUDE.md）

---

## 事前確認済みの事実

- イオナサンプルの`main.py`セルは`src/sample_notebook/a-sample-rule-based-agent-iono-s-deck.ipynb`の`cell id="4c4dd070"`（`source`は改行込みの単一文字列）。先頭行`%%writefile main.py`はJupyter magicでPythonとしてexec不可なため除去が必要
- イオナサンプルの決め打ちデッキ構成（60枚）：Iono_Voltorb(265)×3, Iono_Tadbulb(268)×3, Iono_Bellibolt_ex(269)×3, Iono_Wattrel(270)×3, Iono_Kilowattrel(271)×3, Buddy_Buddy_Poffin(1086)×3, Night_Stretcher(1097)×2, Max_Rod(1110)×1, Energy_Retrieval(1118)×1, Ultra_Ball(1121)×3, Poke_Pad(1152)×2, Lillie_Determination(1227)×4, Canari(1233)×4, Levincia(1254)×3, Boss_Orders(1182)×2, Basic_Lightning_Energy(4)×20
- ジャモライコのデッキは`decks/jamoraiko_20260713.py`の`DECK`（`(card_id, count)`タプルリスト、計60枚）

---

### Task 1: ビルドスクリプトの実装（名前空間分離・デッキ定数・単体テスト）

**Files:**
- Create: `scripts/build_jamoraiko_vs_iono_notebook.py`
- Test: `tests/test_jamoraiko_vs_iono_notebook_build.py`

**Interfaces:**
- Produces: `scripts/build_jamoraiko_vs_iono_notebook.py`の`main()`（`src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`を書き出す）、`load_agent_module(name, source) -> types.ModuleType`（モジュール文字列として公開、テストから直接execして検証する）、`IONO_DECK: list[int]`（60枚）、`_strip_writefile_magic(source: str) -> str`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_jamoraiko_vs_iono_notebook_build.py
"""ジャモライコ vs イオナサンプル校正ノートブック ビルドスクリプトの単体テスト

生成されるノートブックの実行(cg依存)はローカルでは検証できないため、
ビルドスクリプト自体の純粋なPythonロジック（名前空間分離・デッキ定数・
writefileマジック除去）のみをテストする。
"""
import importlib.util
import types
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_jamoraiko_vs_iono_notebook.py"
_spec = importlib.util.spec_from_file_location("build_jvi_nb", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # main()は __main__ ガードで走らない


class TestLoadAgentModule:
    def test_returns_module_with_agent_function(self):
        source = "def agent(obs_dict):\n    return [0]\n"
        mod = _mod.load_agent_module("fake_agent", source)
        assert isinstance(mod, types.ModuleType)
        assert mod.agent({"select": None}) == [0]

    def test_two_modules_with_colliding_globals_do_not_interfere(self):
        source_a = "card_table = {1: 'A'}\n\ndef agent(obs_dict):\n    return list(card_table.keys())\n"
        source_b = "card_table = {2: 'B'}\n\ndef agent(obs_dict):\n    return list(card_table.keys())\n"
        mod_a = _mod.load_agent_module("agent_a", source_a)
        mod_b = _mod.load_agent_module("agent_b", source_b)
        assert mod_a.agent(None) == [1]
        assert mod_b.agent(None) == [2]
        assert mod_a.card_table != mod_b.card_table


class TestStripWritefileMagic:
    def test_removes_leading_writefile_line(self):
        source = "%%writefile main.py\nimport os\nprint('hi')\n"
        result = _mod._strip_writefile_magic(source)
        assert result == "import os\nprint('hi')\n"

    def test_source_without_magic_is_unchanged(self):
        source = "import os\nprint('hi')\n"
        result = _mod._strip_writefile_magic(source)
        assert result == source


class TestIonoDeck:
    def test_deck_has_60_cards(self):
        assert len(_mod.IONO_DECK) == 60

    def test_expected_card_counts(self):
        counts = {}
        for card_id in _mod.IONO_DECK:
            counts[card_id] = counts.get(card_id, 0) + 1
        assert counts[265] == 3   # Iono's Voltorb
        assert counts[269] == 3   # Iono's Bellibolt ex
        assert counts[1227] == 4  # Lillie's Determination
        assert counts[4] == 20    # Basic {L} Energy


class TestJamoraikoDeckExpansion:
    def test_expanded_deck_has_60_cards(self):
        from decks.jamoraiko_20260713 import DECK
        expanded = _mod.expand_deck(DECK)
        assert len(expanded) == 60

    def test_expanded_deck_preserves_counts(self):
        from decks.jamoraiko_20260713 import DECK
        expanded = _mod.expand_deck(DECK)
        assert expanded.count(63) == 2  # タケルライコex
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_vs_iono_notebook_build.py -v`
Expected: FAIL（`FileNotFoundError` または `ModuleNotFoundError`：`scripts/build_jamoraiko_vs_iono_notebook.py`が存在しない）

- [ ] **Step 3: ビルドスクリプトを実装する**

```python
# scripts/build_jamoraiko_vs_iono_notebook.py
"""ジャモライコ vs イオナサンプル 校正ノートブックの生成スクリプト

src/jamoraiko_agent/main.py の全文と、既存イオナサンプルノートブックの
main.pyセル全文を、それぞれ別名前空間に読み込んで200試合自己対戦させる
Kaggle実行用ノートブックを生成する。main.py改修後はこのスクリプトを
再実行すればノートブックが追従する。

Usage: uv run python scripts/build_jamoraiko_vs_iono_notebook.py
"""
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

    sources_cell_src = (
        "# ==================== エージェントのソースコード（ビルド時に埋め込み） ====================\n"
        "# 手で編集せず、main.py改修後に scripts/build_jamoraiko_vs_iono_notebook.py を再実行すること。\n"
        f"JAMORAIKO_SOURCE = {jamoraiko_source!r}\n\n"
        f"IONO_SOURCE = {iono_source!r}\n"
    )

    load_helper_src = (
        "# ==================== 名前空間分離ヘルパー ====================\n"
        "import types\n\n\n"
        "def load_agent_module(name: str, source: str):\n"
        "    mod = types.ModuleType(name)\n"
        "    exec(compile(source, name, \"exec\"), mod.__dict__)\n"
        "    return mod\n"
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
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_vs_iono_notebook_build.py -v`
Expected: PASS（8テスト全て）

- [ ] **Step 5: リポジトリ全体の回帰確認**

Run: `uv run pytest -q`
Expected: 既存の全テスト＋本タスクで追加した8テストが全てPASS（408→416件）

- [ ] **Step 6: コミット**

```bash
git add scripts/build_jamoraiko_vs_iono_notebook.py tests/test_jamoraiko_vs_iono_notebook_build.py
git commit -m "feat: ジャモライコvsイオナサンプル校正ノートブックのビルドスクリプトを追加"
```

---

### Task 2: ノートブック生成・内容検証・実装サマリー作成

**Files:**
- Create（実行のみ、gitignore対象）: `src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`
- Create: `docs/implementations/20260713-jamoraiko-vs-iono-calibration.md`

**Interfaces:**
- Consumes: `scripts/build_jamoraiko_vs_iono_notebook.py`（Task 1）

- [ ] **Step 1: ビルドスクリプトを実行してノートブックを生成する**

Run: `uv run python scripts/build_jamoraiko_vs_iono_notebook.py`
Expected: `wrote src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb with 10 cells`

- [ ] **Step 2: 生成されたノートブックの内容を検証する**

```bash
uv run python -c "
import json
nb = json.loads(open('src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb').read())
print('cell count:', len(nb['cells']))
srcs = {c['id']: c['source'] for c in nb['cells'] if c['cell_type'] == 'code'}
assert 'JAMORAIKO_SOURCE' in srcs['agent-sources']
assert 'IONO_SOURCE' in srcs['agent-sources']
assert '%%writefile' not in srcs['agent-sources']
assert 'JAMORAIKO_DECK' in srcs['deck-load']
assert 'IONO_DECK' in srcs['deck-load']
assert 'load_agent_module' in srcs['load-helper']
assert 'battle_start' in srcs['battle-harness']
assert 'GAMES = 200' in srcs['calibration-run']
print('OK: all expected markers present')
"
```

Expected: `OK: all expected markers present`（エラーなく終了）

- [ ] **Step 3: 実装サマリーを作成する**

`docs/implementations/20260713-jamoraiko-vs-iono-calibration.md`に以下を記録する：
- 実装したファイル一覧（`scripts/build_jamoraiko_vs_iono_notebook.py`、テストファイル）
- テスト件数（Task 1で追加した8件、リポジトリ全体は408→416件）
- ノートブックの生成・検証結果（Step 1〜2の実行結果）
- Kaggle上での実行手順：Add Inputでジャモライコのdeck.csvデータセットのみアタッチすればよいこと（イオナサンプルはコード内蔵のため追加データセット不要）
- 次のステップ（Kaggle上での実行・勝率確認はユーザー判断で別途実施。設計書`docs/superpowers/specs/2026-07-13-jamoraiko-vs-iono-calibration-design.md`へのリンク）

- [ ] **Step 4: コミット**

```bash
git add docs/implementations/20260713-jamoraiko-vs-iono-calibration.md
git commit -m "docs: ジャモライコvsイオナサンプル校正ノートブックの実装サマリーを追加"
```

（`src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`は`.gitignore`対象のためコミット対象外）

---

## 未解決・次回以降の検討事項（設計書からの引き継ぎ）
- 負け試合の盤面ログ保存・質的分析（今回は勝率のみ。必要になれば別途追加）
- 実行後、実際の勝率次第でチューニング対象の洗い出しに進むかはユーザー判断
