# ドラパルトexデッキ MVP開発 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kaggle公式サンプルのドラパルトexエージェントを`src/dragapult_agent/`へ移植し、ボスの指令の使用条件をルカリオex実証済みパターンで改善したMVPを、既存デッキと同じテスト・デッキビルド慣習の上に構築する。

**Architecture:** サンプルの855行の手続き型ロジックはほぼそのまま`src/dragapult_agent/main.py`へ移植する（`combat.py`分離はしない）。カードID定数のみ`src/dragapult_agent/constants.py`へ切り出す。デッキ定義は`decks/dragapult_20260721.py`（既存デッキと同じ`DECK = [(id, count), ...]`形式）。

**Tech Stack:** Python 3.12 / pytest / 既存の`cg.api`（`data/competition/sample_submission/cg`、pytestの`pythonpath`設定で解決済み）/ `uv run`

## Global Constraints

- デッキは合計60枚、ACE SPEC（1枚制限）カードは1種類につき1枚まで（このデッキでは`Unfair_Stamp`=1080のみ該当）
- 実装対象の設計根拠は`docs/superpowers/specs/2026-07-21-dragapult-ex-mvp-design.md`（承認済み）。本プランはそこからの逸脱を含まない
- コードコメントは日本語で書く（変数名・関数名は英語）
- 既存テストスイート（`uv run pytest -q`）は各タスック完了時点で全件PASSを維持する
- 進化ルートの改修・アンフェアスタンプの使いどころの精緻化は本プランのスコープ外（設計書「今回やらないこと」参照）

---

### Task 1: デッキ定義ファイルとACE SPECテスト

**Files:**
- Create: `decks/dragapult_20260721.py`
- Test: `tests/test_dragapult_deck.py`

**Interfaces:**
- Produces: `decks.dragapult_20260721.DECK`（`list[tuple[int, int]]`、`(card_id, count)`のリスト、合計60枚）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_dragapult_deck.py`:

```python
# tests/test_dragapult_deck.py
from decks.dragapult_20260721 import DECK

ACE_SPEC_IDS = {1080}  # Unfair Stamp（data/competition/EN_Card_Data.csv で Rule: ACE SPEC）


def test_deck_totals_60_cards():
    assert sum(count for _, count in DECK) == 60


def test_ace_spec_cards_limited_to_one_copy():
    for card_id, count in DECK:
        if card_id in ACE_SPEC_IDS:
            assert count == 1, f"ACE SPEC card {card_id} has {count} copies"


def test_no_duplicate_card_ids():
    ids = [card_id for card_id, _ in DECK]
    assert len(ids) == len(set(ids)), "同一カードIDが複数エントリに分かれている"
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_dragapult_deck.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'decks.dragapult_20260721'`）

- [ ] **Step 3: デッキ定義ファイルを作成する**

`decks/dragapult_20260721.py`:

```python
# ドラパルトexデッキ定義（2026-07-21 MVP開発）
# Kaggle公式サンプルエージェント（notebooks/samples/a-sample-rule-based-agent-dragapult-ex-deck.ipynb）
# と実戦バトルログ34戦中12戦で完全一致した60枚構成をそのまま採用（docs/superpowers/specs/2026-07-21-dragapult-ex-mvp-design.md参照）

DECK = [
    (2, 4),      # Basic {R} Energy
    (5, 4),      # Basic {P} Energy
    (119, 4),    # Dreepy
    (120, 4),    # Drakloak
    (121, 3),    # Dragapult ex
    (140, 1),    # Fezandipiti ex
    (184, 1),    # Latias ex
    (235, 2),    # Budew
    (1071, 1),   # Meowth ex
    (1079, 2),   # Rare Candy
    (1080, 1),   # Unfair Stamp (ACE SPEC)
    (1086, 4),   # Buddy-Buddy Poffin
    (1097, 2),   # Night Stretcher
    (1120, 4),   # Crushing Hammer
    (1121, 4),   # Ultra Ball
    (1152, 3),   # Poké Pad
    (1156, 1),   # Lucky Helmet
    (1182, 3),   # Boss's Orders
    (1198, 4),   # Crispin
    (1210, 2),   # Brock's Scouting
    (1227, 4),   # Lillie's Determination
    (1256, 2),   # Team Rocket's Watchtower
]
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_dragapult_deck.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: コミット**

```bash
git add decks/dragapult_20260721.py tests/test_dragapult_deck.py
git commit -m "feat(dragapult): デッキ定義とACE SPECテストを追加"
```

---

### Task 2: カードID定数モジュール

**Files:**
- Create: `src/dragapult_agent/__init__.py`（空ファイル、`lucario_agent/__init__.py`と同じ慣習）
- Create: `src/dragapult_agent/constants.py`
- Test: `tests/test_dragapult_constants.py`

**Interfaces:**
- Consumes: `decks.dragapult_20260721.DECK`（Task 1の成果物、テストでの突き合わせに使用）
- Produces: `dragapult_agent.constants`モジュール内の22個のカードID定数（`Dreepy`, `Drakloak`, `Dragapult_ex`, `Fezandipiti_ex`, `Latias_ex`, `Budew`, `Meowth_ex`, `Rare_Candy`, `Unfair_Stamp`, `Buddy_Buddy_Poffin`, `Night_Stretcher`, `Crushing_Hammer`, `Ultra_Ball`, `Poke_Pad`, `Lucky_Helmet`, `Boss_Orders`, `Crispin`, `Brock_Scouting`, `Lillie_Determination`, `Team_Rocket_Watchtower`, `Basic_Fire_Energy`, `Basic_Psychic_Energy`）。Task 3・Task 4で`from dragapult_agent.constants import (...)`として使う

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_dragapult_constants.py`:

```python
# tests/test_dragapult_constants.py
from decks.dragapult_20260721 import DECK
from dragapult_agent import constants as c


def test_all_deck_card_ids_have_a_named_constant():
    """DECK内の全カードIDが、constants.py内のいずれかの定数値と一致することを確認する
    （constants.pyのタイポでデッキ内カードと不整合が起きるのを防ぐ）"""
    deck_ids = {card_id for card_id, _ in DECK}
    constant_values = {
        v for k, v in vars(c).items()
        if not k.startswith("_") and isinstance(v, int)
    }
    assert deck_ids <= constant_values, deck_ids - constant_values


def test_boss_orders_id_matches_known_value():
    assert c.Boss_Orders == 1182


def test_dragapult_ex_id_matches_known_value():
    assert c.Dragapult_ex == 121
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_dragapult_constants.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'dragapult_agent'`）

- [ ] **Step 3: パッケージ初期化ファイルと定数モジュールを作成する**

`src/dragapult_agent/__init__.py`:（空ファイル）

`src/dragapult_agent/constants.py`:

```python
# ==================== カードID定数 ====================
# Kaggle公式サンプルエージェント（notebooks/samples/a-sample-rule-based-agent-dragapult-ex-deck.ipynb）
# の main.py 内にインラインで定義されていたものを切り出したもの
Dreepy                  = 119
Drakloak                = 120
Dragapult_ex            = 121
Fezandipiti_ex          = 140  # キチキギスex（JP名）
Latias_ex               = 184
Budew                   = 235
Meowth_ex               = 1071
Rare_Candy              = 1079
Unfair_Stamp            = 1080  # ACE SPEC
Buddy_Buddy_Poffin      = 1086
Night_Stretcher         = 1097
Crushing_Hammer         = 1120
Ultra_Ball              = 1121
Poke_Pad                = 1152
Lucky_Helmet            = 1156
Boss_Orders             = 1182
Crispin                 = 1198  # アカマツ（JP名）
Brock_Scouting          = 1210  # タケシのスカウト（JP名）
Lillie_Determination    = 1227
Team_Rocket_Watchtower  = 1256
Basic_Fire_Energy       = 2
Basic_Psychic_Energy    = 5
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_dragapult_constants.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/__init__.py src/dragapult_agent/constants.py tests/test_dragapult_constants.py
git commit -m "feat(dragapult): カードID定数モジュールを追加"
```

---

### Task 3: サンプルエージェントの移植（deck.csv遅延読み込み化を含む）

**Files:**
- Create: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent_import.py`

**Interfaces:**
- Produces: `dragapult_agent.main.agent(obs_dict: dict) -> list[int]`（Kaggleエージェントのエントリーポイント、既存の`lucario_agent.main.agent`と同じシグネチャ）。Task 4・Task 5がこのモジュールを編集する

**背景:** サンプルのオリジナルコードは、モジュールのトップレベル（import直後）で`deck.csv`をファイルから読み込む（`notebooks/samples/a-sample-rule-based-agent-dragapult-ex-deck.ipynb`のcell3、14〜22行目）。このままだと`import dragapult_agent.main`した瞬間にファイルI/Oが発生し、`deck.csv`が存在しないテスト環境で`FileNotFoundError`になる。このタスクでは移植と同時に、読み込みを`set_card_counts()`内で初回のみ実行する遅延初期化に変更し、importだけなら安全に完了するようにする（ロジックの意味・実行結果は変えない。実際にKaggle環境で対局が始まれば`set_card_counts`は毎ターン呼ばれるため、遅延させても実質的な初回タイミングは変わらない）。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_dragapult_agent_import.py`:

```python
# tests/test_dragapult_agent_import.py
def test_module_imports_without_deck_csv_on_disk():
    """deck.csvがカレントディレクトリに存在しない状態でも import できること
    （Kaggle実行時は同ディレクトリにdeck.csvが配置されるが、pytest実行時は存在しない）"""
    import dragapult_agent.main as dm
    assert callable(dm.agent)


def test_my_deck_is_empty_immediately_after_import():
    """import直後はdeck.csvの読み込みが走っておらず、my_deckが空のままであること"""
    import dragapult_agent.main as dm
    assert dm.my_deck == []
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_dragapult_agent_import.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'dragapult_agent.main'`）

- [ ] **Step 3: ノートブックからソースを抽出する**

Run:
```bash
uv run python3 -c "
import json
from pathlib import Path

nb = json.load(open('notebooks/samples/a-sample-rule-based-agent-dragapult-ex-deck.ipynb'))
source = ''.join(nb['cells'][3]['source'])
lines = source.split('\n')
assert lines[0] == '%%writefile main.py', lines[0]
Path('src/dragapult_agent/main.py').write_text('\n'.join(lines[1:]) + '\n')
print('wrote', len(lines) - 1, 'lines')
"
```
Expected: `wrote 854 lines`（`%%writefile main.py`の1行を除いた行数）

- [ ] **Step 4: deck.csv読み込みを遅延初期化に変更する**

`src/dragapult_agent/main.py`の先頭付近、現状：

```python
# Load deck.csv in the dataset
file_path = "deck.csv"
if not os.path.exists(file_path):
    file_path = "/kaggle_simulations/agent/" + file_path
with open(file_path, "r") as file:
    csv = file.read().split("\n")
my_deck = []
for i in range(60):
    my_deck.append(int(csv[i]))
```

修正後：

```python
my_deck: list[int] = []


def _load_deck() -> list[int]:
    """deck.csvを初回のみ読み込む（importタイミングでのファイルI/Oを避けるための遅延初期化）"""
    global my_deck
    if my_deck:
        return my_deck
    file_path = "deck.csv"
    if not os.path.exists(file_path):
        file_path = "/kaggle_simulations/agent/" + file_path
    with open(file_path, "r") as file:
        csv = file.read().split("\n")
    my_deck = [int(csv[i]) for i in range(60)]
    return my_deck
```

そして`set_card_counts`関数（`for id in my_deck:`を含む関数）の先頭に読み込み呼び出しを追加する。現状：

```python
def set_card_counts(obs: Observation, my_index: int):
    card_counts.clear()
    serial_set.clear()
    for id in my_deck:
        card_counts[id] += 1
```

修正後：

```python
def set_card_counts(obs: Observation, my_index: int):
    _load_deck()
    card_counts.clear()
    serial_set.clear()
    for id in my_deck:
        card_counts[id] += 1
```

- [ ] **Step 5: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_dragapult_agent_import.py -v`
Expected: 2 tests PASS

- [ ] **Step 6: 既存テストスイート全体の回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS（新規5件＋既存567件、失敗0件）

- [ ] **Step 7: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent_import.py
git commit -m "feat(dragapult): Kaggle公式サンプルを移植（deck.csv読み込みを遅延初期化）"
```

---

### Task 4: インライン定数をconstants.pyからのimportに置き換え

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent_import.py`（既存テストの再実行のみ、新規テストは追加しない）

**Interfaces:**
- Consumes: `dragapult_agent.constants`（Task 2の成果物）
- Produces: 変更なし（`dragapult_agent.main.agent`のシグネチャ・挙動は不変）

- [ ] **Step 1: 現状の重複定義を確認する**

`src/dragapult_agent/main.py`内、`from cg.api import ...`の下に以下のブロックが存在する（Task 3で移植したまま）：

```python
# Decklist
Dreepy = 119  # ×4
Drakloak = 120  # ×4
Dragapult_ex = 121  # ×3
Fezandipiti_ex = 140  # ×1
Latias_ex = 184  # ×1
Budew = 235  # ×2
Meowth_ex = 1071  # ×1
Rare_Candy = 1079  # ×2
Unfair_Stamp = 1080  # ×1
Buddy_Buddy_Poffin = 1086  # ×4
Night_Stretcher = 1097  # ×2
Crushing_Hammer = 1120  # ×4
Ultra_Ball = 1121  # ×4
Poke_Pad = 1152  # x3
Lucky_Helmet = 1156  # ×1
Boss_Orders = 1182  # ×3
Crispin = 1198  # ×4
Brock_Scouting = 1210  # ×2
Lillie_Determination = 1227  # ×4
Team_Rocket_Watchtower = 1256  # ×2
Basic_Fire_Energy = 2  # ×4
Basic_Psychic_Energy = 5  # ×4
```

- [ ] **Step 2: このブロックをconstants.pyからのimportに置き換える**

`from cg.api import AreaType, ...`の行の直後に追記：

```python
from dragapult_agent.constants import (
    Dreepy, Drakloak, Dragapult_ex, Fezandipiti_ex, Latias_ex, Budew,
    Meowth_ex, Rare_Candy, Unfair_Stamp, Buddy_Buddy_Poffin, Night_Stretcher,
    Crushing_Hammer, Ultra_Ball, Poke_Pad, Lucky_Helmet, Boss_Orders, Crispin,
    Brock_Scouting, Lillie_Determination, Team_Rocket_Watchtower,
    Basic_Fire_Energy, Basic_Psychic_Energy,
)
```

そして上記Step 1に示した`# Decklist`コメントから`Basic_Psychic_Energy = 5  # ×4`までの22行のブロックを削除する。

- [ ] **Step 3: テストを実行して回帰がないことを確認する**

Run: `uv run pytest tests/test_dragapult_agent_import.py tests/test_dragapult_constants.py -v`
Expected: 5 tests PASS（importが変わらず成功すること、定数の値が変わっていないこと）

- [ ] **Step 4: 既存テストスイート全体の回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/main.py
git commit -m "refactor(dragapult): main.py内のカードID定数をconstants.pyからのimportに置き換え"
```

---

### Task 5: ボスの指令の探索的先出しロジック（TDD）

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: なし（純粋関数として独立実装）
- Produces: `dragapult_agent.main._boss_orders_score(has_pull_target: bool, explore_roll: float, epsilon: float) -> int`

**設計根拠:** `docs/superpowers/specs/2026-07-21-dragapult-ex-mvp-design.md`「設計1：ボスの指令の探索的先出し」。`src/lucario_agent/main.py`の`BossOrdersPolicy`（323〜332行目）と同じ3段階（確定的な引き剥がし先あり／確率的に探索的先出し／温存）の考え方を、サンプルの手続き型コードに適用する。`hand_score`関数は`agent()`内のネストされたクロージャのため、判定ロジックだけを独立したモジュールレベルの純粋関数`_boss_orders_score`へ切り出し、`obs_dict`を組み立てずに単体テストできるようにする。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_dragapult_agent.py`:

```python
# tests/test_dragapult_agent.py
import dragapult_agent.main as dm


def test_boss_orders_score_confirmed_pull_target():
    """確定的な引き剥がし先がある場合は最優先スコア"""
    assert dm._boss_orders_score(has_pull_target=True, explore_roll=0.99, epsilon=0.28) == 60000


def test_boss_orders_score_exploratory_use_within_epsilon():
    """確定的な引き剥がし先が無くても、乱数がepsilon未満なら探索的に先出しする"""
    assert dm._boss_orders_score(has_pull_target=False, explore_roll=0.1, epsilon=0.28) == 30000


def test_boss_orders_score_conserve_outside_epsilon():
    """確定的な引き剥がし先が無く、乱数もepsilon以上なら温存（0点）"""
    assert dm._boss_orders_score(has_pull_target=False, explore_roll=0.5, epsilon=0.28) == 0


def test_boss_orders_score_boundary_is_exclusive():
    """explore_roll == epsilon ちょうどは温存側（lucario_agentのrng.random() < EPSILONと同じ境界）"""
    assert dm._boss_orders_score(has_pull_target=False, explore_roll=0.28, epsilon=0.28) == 0
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: FAIL（`AttributeError: module 'dragapult_agent.main' has no attribute '_boss_orders_score'`）

- [ ] **Step 3: 純粋関数を追加する**

`src/dragapult_agent/main.py`の`UNNECESSARY = -10000000`の直後に追加：

```python
BOSS_ORDERS_EXPLORE_EPSILON = 0.28  # ルカリオexのEPSILON（src/lucario_agent/combat.py:13）と同値を初期値として踏襲
_dragapult_rng = random.Random()  # 本番用の実乱数。テストでは_boss_orders_scoreを直接呼び乱数を注入する


def _boss_orders_score(has_pull_target: bool, explore_roll: float, epsilon: float) -> int:
    """ボスの指令のスコアを返す。
    has_pull_target: 現在のベスト攻撃プランがベンチの相手を狙っているか（plan_a.attack > 0）
    explore_roll: 探索的先出し判定用の乱数値（0.0以上1.0未満）
    epsilon: 探索的先出しを行う確率の閾値
    """
    if has_pull_target:
        return 60000  # ベストプランがベンチ狙いを示している：即使用
    if explore_roll < epsilon:
        return 30000  # 確定的な引き剥がし先がなくても、一定確率で探索的に先出しする
    return 0  # 温存
```

ファイル冒頭のimport群（`import os` / `import sys`の並び）に`import random`を追加する。

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: `hand_score`内のボスの指令の分岐を`_boss_orders_score`呼び出しに置き換える**

現状（`hand_score`関数内）：

```python
        elif id == Boss_Orders:
            if plan_a.attack > 0:
                score = 60000
```

修正後：

```python
        elif id == Boss_Orders:
            score = _boss_orders_score(plan_a.attack > 0, _dragapult_rng.random(), BOSS_ORDERS_EXPLORE_EPSILON)
```

- [ ] **Step 6: 既存テストスイート全体の回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS（新規4件を含め全件成功、失敗0件）

- [ ] **Step 7: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "feat(dragapult): ボスの指令に探索的先出しロジックを追加"
```

---

### Task 6: 最終回帰確認・実装サマリー作成

**Files:**
- Create: `docs/implementations/20260721-dragapult-ex-mvp.md`
- No code changes

**Interfaces:**
- Consumes: Task 1〜5の全成果物
- Produces: なし（ドキュメントのみ）

- [ ] **Step 1: 全体テストスイートを実行する**

Run: `uv run pytest -q`
Expected: 全件PASS（既存567件＋新規約12件、失敗0件）

- [ ] **Step 2: デッキビルドスクリプトで実際にdeck.csvを生成できることを確認する**

Run: `uv run python scripts/build_deck.py decks/dragapult_20260721.py`
Expected: `合計: 60 枚` と `出力: output/deck_<timestamp>.csv` が表示される（エラー終了しないこと）

- [ ] **Step 3: 実装サマリーを作成する**

`docs/implementations/20260721-dragapult-ex-mvp.md`に以下を含めて記録する（CLAUDE.mdフェーズ4の慣習）：
- 実装した内容（Task 1〜5の要約）
- テスト結果（Step 1・Step 2の実行結果）
- 設計書（`docs/superpowers/specs/2026-07-21-dragapult-ex-mvp-design.md`）との対応関係
- 未着手のまま残した項目（進化ルートの検証、アンフェアスタンプの使いどころ精緻化 — 提出後の実測データを見てから判断する方針であることを明記）
- 次のステップ（Kaggle提出、[[project_battle_log_parser]]の手法での検証計画）

- [ ] **Step 4: コミット**

```bash
git add docs/implementations/20260721-dragapult-ex-mvp.md
git commit -m "docs(dragapult): MVP実装サマリーを追加"
```

---

## Self-Review Notes

- **Spec coverage**：設計書の「今回やること」1〜6項目は Task 1（デッキ）・Task 2〜4（main.py移植＋constants.py分離）・Task 5（ボスの指令）・Task 1（ACE SPECテスト）でそれぞれ対応済み。「今回やらないこと」（進化ルート改修・アンフェアスタンプ精緻化・combat.py分離）はどのタスクにも含めていない
- **Placeholder scan**：TBD/TODO等のプレースホルダーなし。全ステップに具体的なコード・コマンド・期待結果を記載
- **Type consistency**：`_boss_orders_score(has_pull_target: bool, explore_roll: float, epsilon: float) -> int`はTask 5内のテスト（Step1）と実装（Step3・Step5の呼び出し側）で一貫。`DECK: list[tuple[int, int]]`の形もTask 1〜2で一貫
- **既知のリスク**：Task 3のノートブック抽出コマンドは`nb['cells'][3]`のインデックス依存。ノートブックの構成が変わっていた場合は`assert lines[0] == '%%writefile main.py'`で早期に失敗するため、サイレントに誤った内容を書き込むことはない
