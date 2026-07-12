# 影武者カウント計測（校正実験v2）実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 校正実験で「A（手書き）vs B（壊した設定）が200試合で勝率50.0%＝差が出ない」となった原因を1回のKaggle実験で切り分けるため、校正ノートブックに「設定Aで実戦しながら、毎手番『設定Bなら何を選んだか』を裏で数える」計測（影武者カウント）を追加する。

**Architecture:** チューニング対象の8定数はすべて `_score_attach()` 内でのみ参照されるため、`_score_attach` をグローバル名の付け替えで記録ラッパーに差し替え、`agent()` をA/B両方の重みで二重に呼んで選択と付与スコアを比較する。ε探索（`Boss_Orders` の乱数）による偽の差分は、`_rng` の状態を保存・復元して両呼び出しに同じ乱数系列を見せることで排除する。すべてノートブック側（ビルドスクリプトのセル定数）の変更で、`src/grimmsnarl_agent/main.py` は変更しない。

**Tech Stack:** Python 3 / uv / pytest / Jupyter notebook（ビルドスクリプト生成）/ Kaggle（libcg実行環境）

## 背景（実測データ）

`data/experiments/20260712_grimmsnarl_calibration.json` より：
- A vs B: 200試合で100勝100敗（勝率50.0%）。60%を超えた区間なし
- A vs A: 勝率43.0%（ノイズ基準線）
- 1試合約92ms

区別できていない3つの仮説：
1. **反映バグ**：`TUNABLE_WEIGHTS` の差し替えが実際のスコア計算に効いていない
2. **競合場面なし**：オーロンゲとモルペコがエネ付与先として同時に候補に並ぶ場面がほぼない
3. **意思決定は変わるが勝敗に効かない**：どちらに付けても勝率が変わらない

影武者カウントの `shadow_stats` で判定する：

| カウンタ | 意味 | 判定 |
|---|---|---|
| `attach_score_diff` | 同じ候補の付与スコアがAとBで異なった手番数 | 0かつ付与場面あり → 仮説1（バグ） |
| `grimmsnarl_morpeko_both` | 基本悪エネの付与先候補にオーロンゲとモルペコが同時に並んだ手番数 | ≈0 → 仮説2 |
| `select_diff` / `attach_top_diff` | 最終選択／付与先トップがAとBで変わった手番数 | 多いのに勝率50% → 仮説3 |

## Global Constraints

- コメント・ドキュメント・コミットメッセージは日本語（変数名・関数名は英語）
- `src/grimmsnarl_agent/main.py` は**変更しない**（計測はノートブック側のみ）
- ノートブックは手編集禁止。`scripts/build_grimmsnarl_calibration_notebook.py` の再実行で生成し、生成は冪等（同一入力→バイト一致）であること
- `*.ipynb` はgitignore対象なのでコミットしない（ビルドスクリプトとテストのみコミット）
- テストは `uv run pytest` で実行。既存テスト（295件）を壊さない
- 作業ブランチ: `feature/grimmsnarl-hybrid-step0`（校正実験v1と同じブランチで継続）
- libcg（対戦エンジン）はローカルmacOSで動かないため、対戦を伴う検証はKaggleでユーザーが実施する

## 前提知識（実装者向け）

- `scripts/build_grimmsnarl_calibration_notebook.py` は、セルのソースをモジュールレベルの文字列定数（`NOTE_MD`, `HARNESS_CODE`, `CALIBRATION_CODE`, `SAVE_CODE`, `PLOT_CODE`）として持ち、`main()` でノートブックJSONを組み立てて `src/rl_experiments/grimmsnarl_calibration_experiment.ipynb` に書き出す
- 生成されるノートブックでは `main.py` の全文が1つのセルとして埋め込まれるため、`agent`, `_score_attach`, `_rng`, `TUNABLE_WEIGHTS`, `Basic_D_Energy`, `Grimmsnarl_ex`, `Marnie_Morpeko` などはすべて**ノートブックのグローバル名前空間**に存在する
- `agent()`（main.py:425）はグローバル名 `_score_attach` を参照して付与候補をスコアリングする（main.py:473）ため、グローバル名を記録ラッパーに再束縛すれば呼び出しを傍受できる
- `agent()` は `_score_play()` の `Boss_Orders` 分岐（main.py:277）でモジュールグローバル `_rng` を消費することがある。同じ盤面でも2回呼ぶと乱数系列がずれて選択が変わりうるため、A/B比較時は `_rng.getstate()/setstate()` で系列を揃える
- 既存の `make_weighted_agent(weights)`（HARNESS_CODE内）は呼び出しごとに `TUNABLE_WEIGHTS.clear(); TUNABLE_WEIGHTS.update(weights)` してから `agent()` を呼ぶ

---

### Task 1: 影武者カウントセルの追加とユニットテスト

**Files:**
- Modify: `scripts/build_grimmsnarl_calibration_notebook.py`
- Test: `tests/test_shadow_count_cell.py`（新規）

**Interfaces:**
- Produces: ビルドスクリプトのモジュール定数 `SHADOW_CODE: str`（セルソース）。その中に `make_shadow_agent(weights_main: dict, weights_shadow: dict, stats: dict = SHADOW_STATS) -> Callable[[dict], list[int]]` と `SHADOW_STATS: dict`（キー: `calls`, `select_diff`, `attach_calls`, `attach_score_diff`, `attach_top_diff`, `grimmsnarl_morpeko_both`）を定義する
- Consumes: ノートブック名前空間の `agent`, `_score_attach`, `_rng`, `TUNABLE_WEIGHTS`, `Basic_D_Energy`, `Grimmsnarl_ex`, `Marnie_Morpeko`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_shadow_count_cell.py` を新規作成する。セルソースをスタブと同じ名前空間で `exec` して計測ロジックだけを検証する（libcg不要でローカル実行できる）。

```python
"""影武者カウントセル（SHADOW_CODE）の単体テスト

ビルドスクリプトがノートブックに埋め込むセルのソースを、スタブの
agent / _score_attach / _rng と同じ名前空間でexecし、計測ロジックを検証する。
実際の対戦エンジン（libcg）はローカルで動かないため使わない。
"""
import importlib.util
import random
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_grimmsnarl_calibration_notebook.py"
_spec = importlib.util.spec_from_file_location("build_calib_nb", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # main()は __main__ ガードで走らない
SHADOW_CODE = _mod.SHADOW_CODE

# 本物のカードID定数の代わりに使う適当な値（名前空間に同名で注入する）
GRIMMSNARL_ID = 101
MORPEKO_ID = 102
ENERGY_ID = 900

WEIGHTS_A = {"grimmsnarl_base": 9000, "morpeko_base": 4500}
WEIGHTS_B = {"grimmsnarl_base": 4500, "morpeko_base": 9000}

# 本物のagent()を模したスタブ。乱数を1回消費し、候補ごとにグローバル名
# _score_attach を呼んで最高点の候補インデックスを返す（本物と同じ参照経路）
STUB_SRC = '''
class FakePokemon:
    def __init__(self, pid):
        self.id = pid
        self.energies = []


def _score_attach(pokemon, area, card_id, fs):
    if pokemon.id == Grimmsnarl_ex:
        return TUNABLE_WEIGHTS["grimmsnarl_base"]
    return TUNABLE_WEIGHTS["morpeko_base"]


def agent(obs_dict):
    _rng.random()  # 本物のε探索に相当する乱数消費
    candidates = obs_dict["candidates"]
    if not candidates:
        return [0]
    scores = [_score_attach(p, None, Basic_D_Energy, None) for p in candidates]
    return [max(range(len(scores)), key=scores.__getitem__)]
'''


def make_ns(seed: int = 0) -> dict:
    """スタブ→SHADOW_CODEの順で同一名前空間にexecし、その名前空間を返す"""
    ns = {
        "TUNABLE_WEIGHTS": dict(WEIGHTS_A),
        "_rng": random.Random(seed),
        "Basic_D_Energy": ENERGY_ID,
        "Grimmsnarl_ex": GRIMMSNARL_ID,
        "Marnie_Morpeko": MORPEKO_ID,
    }
    exec(STUB_SRC, ns)
    exec(SHADOW_CODE, ns)
    return ns


def make_obs(ns: dict, pokemon_ids: list[int]) -> dict:
    fake = ns["FakePokemon"]
    return {"candidates": [fake(pid) for pid in pokemon_ids]}


class TestShadowAgent:
    def test_returns_main_selection(self):
        # AとBで選択が割れる盤面でも、返すのは必ずA（本線）の選択
        ns = make_ns()
        shadow = ns["make_shadow_agent"](WEIGHTS_A, WEIGHTS_B)
        obs = make_obs(ns, [GRIMMSNARL_ID, MORPEKO_ID])
        assert shadow(obs) == [0]  # Aではオーロンゲ（index 0）が最高点

    def test_counts_all_diffs_when_weights_flip_choice(self):
        ns = make_ns()
        shadow = ns["make_shadow_agent"](WEIGHTS_A, WEIGHTS_B)
        shadow(make_obs(ns, [GRIMMSNARL_ID, MORPEKO_ID]))
        stats = ns["SHADOW_STATS"]
        assert stats["calls"] == 1
        assert stats["select_diff"] == 1
        assert stats["attach_calls"] == 1
        assert stats["attach_score_diff"] == 1
        assert stats["attach_top_diff"] == 1
        assert stats["grimmsnarl_morpeko_both"] == 1

    def test_no_diffs_when_shadow_uses_same_weights(self):
        ns = make_ns()
        shadow = ns["make_shadow_agent"](WEIGHTS_A, dict(WEIGHTS_A))
        shadow(make_obs(ns, [GRIMMSNARL_ID, MORPEKO_ID]))
        stats = ns["SHADOW_STATS"]
        assert stats["calls"] == 1
        assert stats["select_diff"] == 0
        assert stats["attach_score_diff"] == 0
        assert stats["attach_top_diff"] == 0
        assert stats["grimmsnarl_morpeko_both"] == 1  # 競合場面自体は数える

    def test_no_competition_count_with_single_candidate(self):
        ns = make_ns()
        shadow = ns["make_shadow_agent"](WEIGHTS_A, WEIGHTS_B)
        shadow(make_obs(ns, [GRIMMSNARL_ID]))
        stats = ns["SHADOW_STATS"]
        assert stats["attach_calls"] == 1
        assert stats["grimmsnarl_morpeko_both"] == 0
        assert stats["select_diff"] == 0  # 候補1体ならどちらの重みでも同じ選択

    def test_attach_calls_not_counted_without_candidates(self):
        ns = make_ns()
        shadow = ns["make_shadow_agent"](WEIGHTS_A, WEIGHTS_B)
        shadow(make_obs(ns, []))
        stats = ns["SHADOW_STATS"]
        assert stats["calls"] == 1
        assert stats["attach_calls"] == 0

    def test_mainline_rng_advances_exactly_once_per_call(self):
        # 影武者（B側）の呼び出しが本線の乱数系列を乱さないこと：
        # 1回のshadow呼び出し後の_rngは「random()を1回消費したRandom(0)」と一致する
        ns = make_ns(seed=0)
        shadow = ns["make_shadow_agent"](WEIGHTS_A, WEIGHTS_B)
        shadow(make_obs(ns, [GRIMMSNARL_ID, MORPEKO_ID]))
        reference = random.Random(0)
        reference.random()
        assert ns["_rng"].getstate() == reference.getstate()

    def test_tunable_weights_restored_to_main_after_call(self):
        ns = make_ns()
        shadow = ns["make_shadow_agent"](WEIGHTS_A, WEIGHTS_B)
        shadow(make_obs(ns, [GRIMMSNARL_ID, MORPEKO_ID]))
        assert ns["TUNABLE_WEIGHTS"] == WEIGHTS_A

    def test_stats_accumulate_across_calls(self):
        ns = make_ns()
        shadow = ns["make_shadow_agent"](WEIGHTS_A, WEIGHTS_B)
        shadow(make_obs(ns, [GRIMMSNARL_ID, MORPEKO_ID]))
        shadow(make_obs(ns, [GRIMMSNARL_ID]))
        stats = ns["SHADOW_STATS"]
        assert stats["calls"] == 2
        assert stats["select_diff"] == 1
        assert stats["grimmsnarl_morpeko_both"] == 1
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_shadow_count_cell.py -v`
Expected: FAIL（`AttributeError: module 'build_calib_nb' has no attribute 'SHADOW_CODE'`）

- [ ] **Step 3: `SHADOW_CODE` 定数をビルドスクリプトに追加する**

`scripts/build_grimmsnarl_calibration_notebook.py` の `HARNESS_CODE` と `CALIBRATION_CODE` の間に、以下のモジュール定数を追加する：

```python
SHADOW_CODE = '''# ==================== 影武者カウント計測 ====================
# 設定Aで実戦しながら、毎手番「設定Bなら何を選んだか」を裏で計算して数える。
# 判定したいこと：
#   1. attach_score_diff > 0         → 重みの差し替えはスコアに反映されている（バグではない）
#   2. grimmsnarl_morpeko_both       → オーロンゲとモルペコがエネ付与先として競合する頻度
#   3. select_diff / attach_top_diff → 8定数が実際の意思決定を変えているか
# 裏の計算後に乱数状態と重みを復元するため、ゲーム進行には影響しない。

SHADOW_STATS = {
    "calls": 0,                    # 計測エージェントの呼び出し総数（=手番数）
    "select_diff": 0,              # AとBで最終選択が変わった手番数
    "attach_calls": 0,             # 付与スコア計算が発生した手番数
    "attach_score_diff": 0,        # 同じ候補の付与スコアがAとBで異なった手番数
    "attach_top_diff": 0,          # 付与先トップ候補がAとBで変わった手番数
    "grimmsnarl_morpeko_both": 0,  # 基本悪エネの付与先候補にオーロンゲとモルペコが同時に並んだ手番数
}

_ATTACH_LOG = []  # 直近のagent()呼び出し中に記録した (pokemon_id, card_id, score)
_orig_score_attach = _score_attach


def _recording_score_attach(pokemon, area, card_id, fs):
    score = _orig_score_attach(pokemon, area, card_id, fs)
    _ATTACH_LOG.append((pokemon.id, card_id, score))
    return score


# agent() はグローバル名 _score_attach を参照するため、名前の付け替えで記録が効く
_score_attach = _recording_score_attach


def _call_with_weights(weights, obs_dict):
    """重みを差し替えてagent()を1回呼び、(選択結果, 付与スコアのログ) を返す"""
    TUNABLE_WEIGHTS.clear()
    TUNABLE_WEIGHTS.update(weights)
    _ATTACH_LOG.clear()
    selected = agent(obs_dict)
    return selected, list(_ATTACH_LOG)


def make_shadow_agent(weights_main, weights_shadow, stats=SHADOW_STATS):
    """weights_mainで実戦しつつ、weights_shadowでの選択を裏で計測するエージェント"""
    def _agent(obs_dict):
        rng_state = _rng.getstate()
        sel_main, log_main = _call_with_weights(weights_main, obs_dict)
        rng_after_main = _rng.getstate()
        _rng.setstate(rng_state)  # 影武者にも本線と同じ乱数系列を見せる（ε探索の差を消す）
        sel_shadow, log_shadow = _call_with_weights(weights_shadow, obs_dict)
        _rng.setstate(rng_after_main)  # 本線の乱数消費はA側の1回分だけにする
        TUNABLE_WEIGHTS.clear()
        TUNABLE_WEIGHTS.update(weights_main)

        stats["calls"] += 1
        if sel_main != sel_shadow:
            stats["select_diff"] += 1
        if log_main:
            stats["attach_calls"] += 1
            if [s for (_, _, s) in log_main] != [s for (_, _, s) in log_shadow]:
                stats["attach_score_diff"] += 1
            top_main = max(range(len(log_main)), key=lambda i: log_main[i][2])
            top_shadow = max(range(len(log_shadow)), key=lambda i: log_shadow[i][2])
            if log_main[top_main][:2] != log_shadow[top_shadow][:2]:
                stats["attach_top_diff"] += 1
            energy_targets = {pid for (pid, cid, _) in log_main if cid == Basic_D_Energy}
            if Grimmsnarl_ex in energy_targets and Marnie_Morpeko in energy_targets:
                stats["grimmsnarl_morpeko_both"] += 1
        return sel_main
    return _agent'''
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_shadow_count_cell.py -v`
Expected: PASS（8件）

- [ ] **Step 5: `CALIBRATION_CODE` / `SAVE_CODE` / `NOTE_MD` / `main()` を更新する**

同ファイル内で以下4箇所を変更する。

(a) `CALIBRATION_CODE` を全置換（`run_series` が重み辞書ではなくエージェント関数を受け取るように変更し、A vs B側に影武者エージェントを使う）：

```python
CALIBRATION_CODE = '''# ==================== 校正実験（影武者カウント付き） ====================
import time

GAMES = 200
CHECKPOINTS = [10, 20, 40, 80, 120, 160, 200]

# 設定B: エネルギー配分の優先順位をわざと壊す（オーロンゲ⇔モルペコの基礎点を入れ替え）
BROKEN_WEIGHTS = dict(DEFAULT_TUNABLE)
BROKEN_WEIGHTS["grimmsnarl_base"], BROKEN_WEIGHTS["morpeko_base"] = (
    BROKEN_WEIGHTS["morpeko_base"], BROKEN_WEIGHTS["grimmsnarl_base"],
)
print("設定B（壊した設定）:", BROKEN_WEIGHTS)


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
            print(f"[{label}] {n:>3}試合: A勝={wins:>3} A負={losses:>3} 引分={n - wins - losses:>3} A勝率={wins / n:.3f}")
    elapsed = time.time() - t0
    print(f"[{label}] 計{games}試合 {elapsed:.1f}秒（{elapsed / games * 1000:.0f}ms/試合）")
    return {"label": label, "results": results, "elapsed_sec": elapsed}


series_ab = run_series(
    make_shadow_agent(DEFAULT_TUNABLE, BROKEN_WEIGHTS),
    make_weighted_agent(BROKEN_WEIGHTS),
    GAMES, "A(手書き・影武者計測) vs B(壊した設定)",
)
shadow_stats_ab = dict(SHADOW_STATS)  # A vs Bシリーズ分のスナップショット
print("影武者カウント（A vs B）:", shadow_stats_ab)

series_aa = run_series(
    make_weighted_agent(DEFAULT_TUNABLE), make_weighted_agent(DEFAULT_TUNABLE),
    GAMES, "A vs A (ノイズ基準線)",
)'''
```

(b) `SAVE_CODE` を全置換（`shadow_stats` を追加し、出力ファイル名をv2用に変更）：

```python
SAVE_CODE = '''# ==================== 結果の保存 ====================
OUT_DIR = Path("/kaggle/working")
payload = {
    "default_tunable": DEFAULT_TUNABLE,
    "broken_weights": BROKEN_WEIGHTS,
    "games": GAMES,
    "series": [series_ab, series_aa],
    "shadow_stats": shadow_stats_ab,
}
out_path = OUT_DIR / "calibration_shadow_results.json"
out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"saved: {out_path}")'''
```

(c) `NOTE_MD` の末尾（`設計書: docs/superpowers/specs/...` の行の後）に以下を追記：

```python
# NOTE_MD の文字列末尾に追記する内容
"""
## v2追記（2026-07-12・影武者カウント）

初回実行の結果はA vs Bが200試合で勝率50.0%（差なし）だった
（`data/experiments/20260712_grimmsnarl_calibration.json`）。原因を切り分けるため、
設定Aで実戦しながら毎手番「設定Bなら何を選んだか」を裏で数える計測を追加した。

`shadow_stats` の見方：
- `attach_score_diff = 0` なのに `attach_calls > 0` → 重みの差し替えが効いていない（バグ）
- `grimmsnarl_morpeko_both ≈ 0` → 競合場面がそもそもない（8定数は意思決定に無関係）
- `select_diff` が多いのに勝率50% → 選択は変わるが勝敗に効かない（ダイヤルとして無価値）
いずれの場合もステップ1のチューニング対象は選び直しになる。
"""
```

（実装上は `NOTE_MD = """...既存本文..."""` の閉じ引用符の直前に上記本文を足す形でよい）

(d) `main()` のセルリストに影武者セルを追加（`battle-harness` と `calibration-run` の間）：

```python
        code_cell("battle-harness", HARNESS_CODE),
        code_cell("shadow-agent", SHADOW_CODE),
        code_cell("calibration-run", CALIBRATION_CODE),
```

- [ ] **Step 6: 全テストが通ることを確認する**

Run: `uv run pytest -q`
Expected: 303 passed（既存295件＋新規8件）

- [ ] **Step 7: コミット**

```bash
git add scripts/build_grimmsnarl_calibration_notebook.py tests/test_shadow_count_cell.py
git commit -m "feat: 校正ノートブックに影武者カウント計測を追加（勝率差なしの原因切り分け用）"
```

---

### Task 2: ノートブック再生成と構造検証

**Files:**
- 生成: `src/rl_experiments/grimmsnarl_calibration_experiment.ipynb`（gitignore対象、コミットしない）

**Interfaces:**
- Consumes: Task 1で更新した `scripts/build_grimmsnarl_calibration_notebook.py`

- [ ] **Step 1: ノートブックを再生成する**

Run: `uv run python scripts/build_grimmsnarl_calibration_notebook.py`
Expected: `wrote src/rl_experiments/grimmsnarl_calibration_experiment.ipynb with 10 cells`

- [ ] **Step 2: セル構成と埋め込み内容を検証する**

```bash
uv run python - <<'EOF'
import json
nb = json.load(open("src/rl_experiments/grimmsnarl_calibration_experiment.ipynb"))
ids = [c["id"] for c in nb["cells"]]
print(ids)
assert ids == ["calibration-note", "b6064b7f", "1a929ee3", "deck-load", "agent-body",
               "battle-harness", "shadow-agent", "calibration-run", "save-results", "plot-curve"], ids
src = {c["id"]: "".join(c["source"]) if isinstance(c["source"], list) else c["source"] for c in nb["cells"]}
assert "make_shadow_agent" in src["shadow-agent"]
assert "make_shadow_agent(DEFAULT_TUNABLE, BROKEN_WEIGHTS)" in src["calibration-run"]
assert "shadow_stats" in src["save-results"]
assert "calibration_shadow_results.json" in src["save-results"]
assert "影武者カウント" in src["calibration-note"]
print("structure OK")
EOF
```

Expected: `structure OK`（全10セル。`shadow-agent` が `battle-harness` の直後にあること）

- [ ] **Step 3: 生成の冪等性を確認する**

```bash
shasum src/rl_experiments/grimmsnarl_calibration_experiment.ipynb
uv run python scripts/build_grimmsnarl_calibration_notebook.py
shasum src/rl_experiments/grimmsnarl_calibration_experiment.ipynb
```

Expected: 2回のハッシュが一致

- [ ] **Step 4: 全テストを最終確認する**

Run: `uv run pytest -q`
Expected: 303 passed

- [ ] **Step 5: 完了報告（コミットなし）**

ノートブックはgitignore対象のためコミットは発生しない。ユーザーへの完了報告に以下を含める：
「`src/rl_experiments/grimmsnarl_calibration_experiment.ipynb` を再度Kaggleにアップロードし、前回と同じ入力（`deck_20260705_185905.csv` を含むデータセット＋公式コンペデータ）で実行してください。持ち帰るのは `calibration_shadow_results.json` です。`shadow_stats` の6つの数字で、①重みが反映されているか（`attach_score_diff`）、②競合場面があるか（`grimmsnarl_morpeko_both`）、③意思決定が変わるか（`select_diff`/`attach_top_diff`）が確定します」

---

## 検証まとめ

| 検証項目 | 方法 | 実施場所 |
|---|---|---|
| 影武者エージェントの計測ロジック | `tests/test_shadow_count_cell.py`（スタブexec、8件） | ローカル |
| 本線への非干渉（RNG・重みの復元） | 同上（`test_mainline_rng_advances_exactly_once_per_call` 等） | ローカル |
| 既存機能の非破壊 | `uv run pytest -q` 303件 | ローカル |
| ノートブック生成の冪等性・セル構成 | Task 2 Step 2-3 | ローカル |
| 実対戦での計測値取得 | ノートブック実行（200試合×2系列、約40秒） | Kaggle（ユーザー） |
