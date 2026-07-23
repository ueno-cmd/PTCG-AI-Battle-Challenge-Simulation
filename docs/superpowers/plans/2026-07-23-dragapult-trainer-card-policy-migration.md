# ドラパルトex PLAY分岐 TrainerCardPolicy移植 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/dragapult_agent/main.py`の`agent()`内`OptionType.PLAY`分岐にある12枚のトレーナーズカード（グッズ/サポート/スタジアム）のif/elif連鎖を、`src/lucario_agent/main.py`で実運用中の`TrainerCardPolicy`パターン（ABC＋登録辞書）へ、現行の判定を一切変えずに移植する。

**Architecture:** `PlayTrainerCardContext`（dataclass）に必要な変数を集約し、`TrainerCardPolicy`（ABC）のサブクラス群を`TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy]`に登録する。`_score_play_trainer_card(card_id, ctx)`という新規関数が辞書引きしてスコアを返し、`agent()`のPLAY分岐からはポケモンカード（Dreepy/Fezandipiti_ex/Latias_ex/Budew/Meowth_ex、対象外）のif/elifチェーンの`else`節としてこの関数を呼ぶだけにする。

**Tech Stack:** Python 3.12 / pytest / 既存の`cg.api`型（`State`, `Card`）

## Global Constraints

- 対象は`agent()`内`OptionType.PLAY`のトレーナーズカード分岐（12カードID）のみ。ポケモンカード分岐（Dreepy/Fezandipiti_ex/Latias_ex/Budew/Meowth_ex）と`hand_score()`関数は対象外（別セッション）
- 全てのタスクで現行の数値・条件を一切変更しない「振る舞い保存」を厳守する（`docs/superpowers/specs/2026-07-23-dragapult-trainer-card-policy-migration-design.md`参照）
- テストは既存の`tests/test_dragapult_agent.py`にフラットな関数として追加する（クラス化しない。既存ファイルのスタイルに合わせる）
- 各タスク完了時に`uv run pytest -q`でリポジトリ全体を実行し、既存テストに回帰が無いことを確認してからコミットする
- コミットメッセージ・コードコメントは日本語（CLAUDE.md）
- 通常のfeatureブランチで作業する（git worktreeは使わない）

---

### Task 1: スキャフォールディング（PlayTrainerCardContext・TrainerCardPolicy ABC・FixedScorePolicy・ディスパッチャ）

**Files:**
- Modify: `src/dragapult_agent/main.py`（先頭のimport、および`_crispin_score`関数の直後・`class AttackPlan:`の直前）
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Produces: `PlayTrainerCardContext`（dataclass、フィールド：`card_id: int`, `card_score: int`, `state: State`, `stadium_id: int`, `deck_counts: defaultdict`, `negative_hand_count: int`, `no_draw: bool`, `use_support: int`, `no_more_dex: bool`）、`TrainerCardPolicy`（ABC、`play_score(ctx) -> int`）、`FixedScorePolicy(score: int)`、`TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy]`（空辞書）、`_score_play_trainer_card(card_id: int, ctx: PlayTrainerCardContext) -> int`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_dragapult_agent.py`の先頭のimportを以下に変更する（`pytest`と`State`を追加）：

```python
# tests/test_dragapult_agent.py
import pytest
from collections import defaultdict
from dataclasses import dataclass, field as dc_field

from cg.api import CardType, State

import dragapult_agent.main as dm
```

ファイル末尾に以下を追記する：

```python
def _make_state(turn: int = 3, supporter_played: bool = False) -> State:
    return State(
        turn=turn, turnActionCount=0, yourIndex=0, firstPlayer=0,
        supporterPlayed=supporter_played, stadiumPlayed=False,
        energyAttached=False, retreated=False, result=-1,
        stadium=[], looking=None, players=[],
    )


def _make_ctx(**overrides) -> dm.PlayTrainerCardContext:
    defaults = dict(
        card_id=0, card_score=0, state=_make_state(), stadium_id=0,
        deck_counts=defaultdict(int), negative_hand_count=0,
        no_draw=False, use_support=0, no_more_dex=False,
    )
    defaults.update(overrides)
    return dm.PlayTrainerCardContext(**defaults)


def test_trainer_card_policy_is_abstract():
    with pytest.raises(TypeError):
        dm.TrainerCardPolicy()


def test_fixed_score_policy_returns_constant():
    policy = dm.FixedScorePolicy(1234)
    assert policy.play_score(_make_ctx()) == 1234


def test_score_play_trainer_card_returns_zero_for_unregistered_card():
    """未登録カードは現行のif/elif連鎖がどれにも一致しない場合のデフォルト値0と一致させる
    （main.py:712の`score = 0  # The default and baseline score is 0.`と同じ）"""
    assert dm._score_play_trainer_card(999999, _make_ctx()) == 0
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "trainer_card_policy_is_abstract or fixed_score_policy_returns_constant or score_play_trainer_card_returns_zero"`
Expected: FAIL（`AttributeError: module 'dragapult_agent.main' has no attribute 'PlayTrainerCardContext'`等）

- [ ] **Step 3: 最小実装を書く**

`src/dragapult_agent/main.py`の先頭のimportを以下に変更する：

```python
import os
import random
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass

from cg.api import AreaType, CardType, Log, LogType, Observation, SelectContext, OptionType, Card, Pokemon, State, all_card_data, to_observation_class
```

`_crispin_score`関数の末尾（`return 25000`の行）と`class AttackPlan:`の間に、以下を挿入する：

```python
    if not can_main_attack and not bench_attacker and field_counts[Dragapult_ex] >= 1:
        return 55000
    return 25000


# ==================== PLAYスコアリングのポリシー登録制（トレーナーズカードのみ） ====================
@dataclass
class PlayTrainerCardContext:
    """OptionType.PLAY のトレーナーズカードのスコアリングに必要な情報をまとめる。
    ポケモンカード分岐(Dreepy/Fezandipiti_ex/Latias_ex/Budew/Meowth_ex)はagent()側に
    残すため含まない"""
    card_id: int
    card_score: int          # hand_scores[o.index]
    state: State
    stadium_id: int
    deck_counts: defaultdict
    negative_hand_count: int
    no_draw: bool
    use_support: int
    no_more_dex: bool


class TrainerCardPolicy(ABC):
    """1枚のトレーナーズカード（サポート/グッズ/スタジアム）のPLAY判断を表す"""
    @abstractmethod
    def play_score(self, ctx: PlayTrainerCardContext) -> int: ...


class FixedScorePolicy(TrainerCardPolicy):
    """固定スコアのみを返すカード用"""
    def __init__(self, score: int):
        self._score = score

    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        return self._score


TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {}


def _score_play_trainer_card(card_id: int, ctx: PlayTrainerCardContext) -> int:
    """OptionType.PLAY のトレーナーズカード分岐のスコアを返す。
    未登録カードは現行のif/elif連鎖がどれにも一致しない場合と同じく0を返す"""
    policy = TRAINER_CARD_POLICIES.get(card_id)
    return policy.play_score(ctx) if policy is not None else 0


class AttackPlan:
```

- [ ] **Step 4: テストを実行し成功を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: PASS（既存14件＋新規3件＝17件）

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "$(cat <<'EOF'
feat(dragapult): PLAY分岐TrainerCardPolicyの土台を追加

ルカリオexと同型のPlayTrainerCardContext/TrainerCardPolicy ABC/
FixedScorePolicy/_score_play_trainer_cardディスパッチャを追加。
まだagent()には未配線（次タスク以降で1枚ずつ移植する）。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: 固定スコアカードの移植（Unfair_Stamp・Crushing_Hammer）

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: Task 1の`FixedScorePolicy`, `TRAINER_CARD_POLICIES`, `_score_play_trainer_card`, `_make_ctx`
- Produces: `TRAINER_CARD_POLICIES`に`Unfair_Stamp`・`Crushing_Hammer`のエントリを追加

現行コード（`main.py`のPLAY分岐、移植元）：
```python
elif card.id == Unfair_Stamp:
    score = 15000
...
elif card.id == Crushing_Hammer:
    score = 40000
```

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_dragapult_agent.py`に追記：

```python
def test_unfair_stamp_and_crushing_hammer_registered():
    assert dm._score_play_trainer_card(dm.Unfair_Stamp, _make_ctx()) == 15000
    assert dm._score_play_trainer_card(dm.Crushing_Hammer, _make_ctx()) == 40000
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k test_unfair_stamp_and_crushing_hammer_registered`
Expected: FAIL（両方とも`0`が返り`15000`/`40000`と不一致）

- [ ] **Step 3: 実装する**

`main.py`の`TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {}`を以下に変更：

```python
TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {
    Unfair_Stamp: FixedScorePolicy(15000),
    Crushing_Hammer: FixedScorePolicy(40000),
}
```

- [ ] **Step 4: テストを実行し成功を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: PASS（18件）

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "$(cat <<'EOF'
feat(dragapult): Unfair_Stamp/Crushing_HammerをTrainerCardPolicyへ移植

固定スコアのみのカード2枚をFixedScorePolicyで登録辞書に追加。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: SupporterSelectedPolicy + Boss_Orders・Lillie_Determination

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: Task 1の`TrainerCardPolicy`, `PlayTrainerCardContext`, `_make_ctx`
- Produces: `SupporterSelectedPolicy(score: int, *, no_draw_gate: bool = False)`（`no_draw_gate`はTask 6でCrispin/Brock_Scoutingに使うが、クラス自体はここで完成させる）。`TRAINER_CARD_POLICIES`に`Boss_Orders`・`Lillie_Determination`を追加

現行コード（移植元）：
```python
elif card.id == Boss_Orders:
    if card.id == use_support:
        score = 35000
    else:
        score = -1
elif card.id == Lillie_Determination:
    if card.id == use_support:
        score = 14000
    else:
        score = -1
```

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_supporter_selected_policy_scores_when_selected_as_use_support():
    policy = dm.SupporterSelectedPolicy(35000)
    ctx = _make_ctx(card_id=dm.Boss_Orders, use_support=dm.Boss_Orders)
    assert policy.play_score(ctx) == 35000


def test_supporter_selected_policy_returns_minus_one_when_not_selected():
    policy = dm.SupporterSelectedPolicy(35000)
    ctx = _make_ctx(card_id=dm.Boss_Orders, use_support=dm.Lillie_Determination)
    assert policy.play_score(ctx) == -1


def test_supporter_selected_policy_no_draw_gate_suppresses_even_when_selected():
    """no_draw_gate=Trueの場合、use_supportと一致していてもno_draw中は-1
    （現行のelif no_draw連鎖でCrispin/Brock_Scoutingが受けている暗黙の副作用を明示化）"""
    policy = dm.SupporterSelectedPolicy(35000, no_draw_gate=True)
    ctx = _make_ctx(card_id=dm.Crispin, use_support=dm.Crispin, no_draw=True)
    assert policy.play_score(ctx) == -1


def test_supporter_selected_policy_without_gate_ignores_no_draw():
    policy = dm.SupporterSelectedPolicy(35000)
    ctx = _make_ctx(card_id=dm.Boss_Orders, use_support=dm.Boss_Orders, no_draw=True)
    assert policy.play_score(ctx) == 35000


def test_boss_orders_and_lillie_determination_registered():
    assert dm._score_play_trainer_card(
        dm.Boss_Orders, _make_ctx(card_id=dm.Boss_Orders, use_support=dm.Boss_Orders)
    ) == 35000
    assert dm._score_play_trainer_card(
        dm.Lillie_Determination, _make_ctx(card_id=dm.Lillie_Determination, use_support=dm.Lillie_Determination)
    ) == 14000
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "supporter_selected_policy or boss_orders_and_lillie"`
Expected: FAIL（`AttributeError: ... no attribute 'SupporterSelectedPolicy'`）

- [ ] **Step 3: 実装する**

`FixedScorePolicy`クラスの直後（`TRAINER_CARD_POLICIES`定義の前）に追加：

```python
class SupporterSelectedPolicy(TrainerCardPolicy):
    """このターンの最強サポート(use_support)と一致すれば固定スコア、そうでなければ-1。
    no_draw_gate=Trueの場合、山札残り僅少(no_draw)ならuse_supportとの一致に関わらず-1にする
    （現行のelif no_draw連鎖で、この分岐より後ろに書かれているカードだけが受ける
    暗黙の副作用を明示化したもの。Boss_Orders/Lillie_Determinationはno_drawの影響を
    受けないため no_draw_gate=False のまま使う）"""
    def __init__(self, score: int, *, no_draw_gate: bool = False):
        self._score = score
        self._no_draw_gate = no_draw_gate

    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        if self._no_draw_gate and ctx.no_draw:
            return -1
        return self._score if ctx.card_id == ctx.use_support else -1
```

`TRAINER_CARD_POLICIES`辞書に2エントリ追加：

```python
TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {
    Unfair_Stamp: FixedScorePolicy(15000),
    Crushing_Hammer: FixedScorePolicy(40000),
    Boss_Orders: SupporterSelectedPolicy(35000),
    Lillie_Determination: SupporterSelectedPolicy(14000),
}
```

- [ ] **Step 4: テストを実行し成功を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: PASS（23件）

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "$(cat <<'EOF'
feat(dragapult): Boss_Orders/Lillie_DeterminationをTrainerCardPolicyへ移植

use_support一致判定を共通化したSupporterSelectedPolicyを追加。
no_draw_gateパラメータはCrispin/Brock_Scouting移植(Task 6)向けに
先行実装するが、今回登録する2枚はゲート無しで使用する。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: RareCandyPolicy・TeamRocketWatchtowerPolicy

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: Task 1の`TrainerCardPolicy`, `PlayTrainerCardContext`, `_make_ctx`, `_make_state`
- Produces: `RareCandyPolicy`, `TeamRocketWatchtowerPolicy`。`TRAINER_CARD_POLICIES`に`Rare_Candy`・`Team_Rocket_Watchtower`を追加

現行コード（移植元）：
```python
elif card.id == Rare_Candy:
    if no_more_dex:
        score = -1
    else:
        score = 75000
...
elif card.id == Team_Rocket_Watchtower:
    if stadium_id > 0 or state.turn == 1:
        score = 80000
    else:
        score = -1
```

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_rare_candy_policy_unnecessary_when_no_more_dex():
    policy = dm.RareCandyPolicy()
    assert policy.play_score(_make_ctx(no_more_dex=True)) == -1


def test_rare_candy_policy_high_priority_otherwise():
    policy = dm.RareCandyPolicy()
    assert policy.play_score(_make_ctx(no_more_dex=False)) == 75000


def test_team_rocket_watchtower_policy_plays_when_stadium_already_set():
    policy = dm.TeamRocketWatchtowerPolicy()
    ctx = _make_ctx(stadium_id=dm.Team_Rocket_Watchtower, state=_make_state(turn=5))
    assert policy.play_score(ctx) == 80000


def test_team_rocket_watchtower_policy_plays_on_turn_one_even_without_stadium():
    policy = dm.TeamRocketWatchtowerPolicy()
    ctx = _make_ctx(stadium_id=0, state=_make_state(turn=1))
    assert policy.play_score(ctx) == 80000


def test_team_rocket_watchtower_policy_holds_otherwise():
    policy = dm.TeamRocketWatchtowerPolicy()
    ctx = _make_ctx(stadium_id=0, state=_make_state(turn=5))
    assert policy.play_score(ctx) == -1


def test_rare_candy_and_team_rocket_watchtower_registered():
    assert dm._score_play_trainer_card(dm.Rare_Candy, _make_ctx(no_more_dex=False)) == 75000
    assert dm._score_play_trainer_card(
        dm.Team_Rocket_Watchtower, _make_ctx(stadium_id=0, state=_make_state(turn=1))
    ) == 80000
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "rare_candy_policy or team_rocket_watchtower_policy or rare_candy_and_team_rocket"`
Expected: FAIL

- [ ] **Step 3: 実装する**

`SupporterSelectedPolicy`クラスの直後に追加：

```python
class RareCandyPolicy(TrainerCardPolicy):
    """no_more_dex(プライズ枚数から見てドラパルトexの数が既に十分)ならもう不要"""
    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        return -1 if ctx.no_more_dex else 75000


class TeamRocketWatchtowerPolicy(TrainerCardPolicy):
    """スタジアムが既に何か設置済み、または1ターン目なら設置する"""
    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        if ctx.stadium_id > 0 or ctx.state.turn == 1:
            return 80000
        return -1
```

辞書に追加：

```python
TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {
    Unfair_Stamp: FixedScorePolicy(15000),
    Crushing_Hammer: FixedScorePolicy(40000),
    Boss_Orders: SupporterSelectedPolicy(35000),
    Lillie_Determination: SupporterSelectedPolicy(14000),
    Rare_Candy: RareCandyPolicy(),
    Team_Rocket_Watchtower: TeamRocketWatchtowerPolicy(),
}
```

- [ ] **Step 4: テストを実行し成功を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: PASS（29件）

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "$(cat <<'EOF'
feat(dragapult): Rare_Candy/Team_Rocket_WatchtowerをTrainerCardPolicyへ移植

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: NightStretcherPolicy

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: Task 1の`TrainerCardPolicy`, `PlayTrainerCardContext`, `_make_ctx`
- Produces: `NightStretcherPolicy`。`TRAINER_CARD_POLICIES`に`Night_Stretcher`を追加

現行コード（移植元）：
```python
elif card.id == Night_Stretcher:
    if card_score >= 18000:
        score = 42000
    else:
        score = -1
```

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_night_stretcher_policy_plays_when_card_score_meets_threshold():
    policy = dm.NightStretcherPolicy()
    assert policy.play_score(_make_ctx(card_score=18000)) == 42000


def test_night_stretcher_policy_holds_below_threshold():
    policy = dm.NightStretcherPolicy()
    assert policy.play_score(_make_ctx(card_score=17999)) == -1


def test_night_stretcher_registered():
    assert dm._score_play_trainer_card(dm.Night_Stretcher, _make_ctx(card_score=20000)) == 42000
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k night_stretcher`
Expected: FAIL

- [ ] **Step 3: 実装する**

`TeamRocketWatchtowerPolicy`クラスの直後に追加：

```python
class NightStretcherPolicy(TrainerCardPolicy):
    """手札評価(card_score)が閾値以上(=有用なカードを回収できる)場合のみ使用"""
    CARD_SCORE_THRESHOLD = 18000

    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        return 42000 if ctx.card_score >= self.CARD_SCORE_THRESHOLD else -1
```

辞書に追加：

```python
TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {
    Unfair_Stamp: FixedScorePolicy(15000),
    Crushing_Hammer: FixedScorePolicy(40000),
    Boss_Orders: SupporterSelectedPolicy(35000),
    Lillie_Determination: SupporterSelectedPolicy(14000),
    Rare_Candy: RareCandyPolicy(),
    Team_Rocket_Watchtower: TeamRocketWatchtowerPolicy(),
    Night_Stretcher: NightStretcherPolicy(),
}
```

- [ ] **Step 4: テストを実行し成功を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: PASS（32件）

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "$(cat <<'EOF'
feat(dragapult): Night_StretcherをTrainerCardPolicyへ移植

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: no_drawゲート付きカード（Buddy_Buddy_Poffin・Ultra_Ball・Poke_Pad・Crispin・Brock_Scouting）

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: Task 1の`TrainerCardPolicy`, `PlayTrainerCardContext`, `_make_ctx`。Task 3の`SupporterSelectedPolicy(score, *, no_draw_gate=True)`
- Produces: `BuddyBuddyPoffinPolicy`, `UltraBallPolicy`, `PokePadPolicy`。`TRAINER_CARD_POLICIES`に`Buddy_Buddy_Poffin`・`Ultra_Ball`・`Poke_Pad`・`Crispin`・`Brock_Scouting`を追加

現行コード（移植元。`elif no_draw: score = -1`という無条件分岐が、この5枚だけに掛かっている点に注意）：
```python
elif no_draw:
    score = -1
elif card.id == Buddy_Buddy_Poffin:
    if deck_counts[Dreepy] > 0:
        score = 46000
    else:
        score = -1
elif card.id == Ultra_Ball:
    if negative_hand_count >= 2:
        score = 44000
    else:
        score = -1
elif card.id == Poke_Pad:
    if deck_counts[Dreepy] + deck_counts[Drakloak] > 0:
        score = 45000
    else:
        score = -1
elif card.id == Crispin or card.id == Brock_Scouting:
    if card.id == use_support:
        score = 35000
    else:
        score = -1
```

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_buddy_buddy_poffin_policy_plays_when_dreepy_in_deck():
    policy = dm.BuddyBuddyPoffinPolicy()
    ctx = _make_ctx(deck_counts=defaultdict(int, {dm.Dreepy: 1}))
    assert policy.play_score(ctx) == 46000


def test_buddy_buddy_poffin_policy_holds_when_no_dreepy_in_deck():
    policy = dm.BuddyBuddyPoffinPolicy()
    ctx = _make_ctx(deck_counts=defaultdict(int))
    assert policy.play_score(ctx) == -1


def test_buddy_buddy_poffin_policy_suppressed_by_no_draw():
    policy = dm.BuddyBuddyPoffinPolicy()
    ctx = _make_ctx(deck_counts=defaultdict(int, {dm.Dreepy: 1}), no_draw=True)
    assert policy.play_score(ctx) == -1


def test_ultra_ball_policy_plays_when_two_or_more_negative_cards():
    policy = dm.UltraBallPolicy()
    assert policy.play_score(_make_ctx(negative_hand_count=2)) == 44000


def test_ultra_ball_policy_holds_below_threshold():
    policy = dm.UltraBallPolicy()
    assert policy.play_score(_make_ctx(negative_hand_count=1)) == -1


def test_ultra_ball_policy_suppressed_by_no_draw():
    policy = dm.UltraBallPolicy()
    assert policy.play_score(_make_ctx(negative_hand_count=2, no_draw=True)) == -1


def test_poke_pad_policy_plays_when_dreepy_or_drakloak_in_deck():
    policy = dm.PokePadPolicy()
    ctx = _make_ctx(deck_counts=defaultdict(int, {dm.Drakloak: 1}))
    assert policy.play_score(ctx) == 45000


def test_poke_pad_policy_holds_when_neither_in_deck():
    policy = dm.PokePadPolicy()
    ctx = _make_ctx(deck_counts=defaultdict(int))
    assert policy.play_score(ctx) == -1


def test_poke_pad_policy_suppressed_by_no_draw():
    policy = dm.PokePadPolicy()
    ctx = _make_ctx(deck_counts=defaultdict(int, {dm.Dreepy: 1}), no_draw=True)
    assert policy.play_score(ctx) == -1


def test_no_draw_gated_cards_registered():
    assert dm._score_play_trainer_card(
        dm.Buddy_Buddy_Poffin, _make_ctx(deck_counts=defaultdict(int, {dm.Dreepy: 1}))
    ) == 46000
    assert dm._score_play_trainer_card(
        dm.Ultra_Ball, _make_ctx(negative_hand_count=2)
    ) == 44000
    assert dm._score_play_trainer_card(
        dm.Poke_Pad, _make_ctx(deck_counts=defaultdict(int, {dm.Drakloak: 1}))
    ) == 45000
    assert dm._score_play_trainer_card(
        dm.Crispin, _make_ctx(card_id=dm.Crispin, use_support=dm.Crispin)
    ) == 35000
    assert dm._score_play_trainer_card(
        dm.Brock_Scouting, _make_ctx(card_id=dm.Brock_Scouting, use_support=dm.Brock_Scouting)
    ) == 35000
    # no_drawが真なら、use_supportと一致していてもCrispin/Brock_Scoutingは-1
    assert dm._score_play_trainer_card(
        dm.Crispin, _make_ctx(card_id=dm.Crispin, use_support=dm.Crispin, no_draw=True)
    ) == -1
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "buddy_buddy_poffin_policy or ultra_ball_policy or poke_pad_policy or no_draw_gated_cards_registered"`
Expected: FAIL

- [ ] **Step 3: 実装する**

`NightStretcherPolicy`クラスの直後に追加：

```python
class BuddyBuddyPoffinPolicy(TrainerCardPolicy):
    """山札にドロディー(Dreepy)が残っている場合のみ使用。山札残り僅少(no_draw)なら使わない"""
    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        if ctx.no_draw:
            return -1
        return 46000 if ctx.deck_counts[Dreepy] > 0 else -1


class UltraBallPolicy(TrainerCardPolicy):
    """手札に低評価カードが2枚以上ある(=捨てても惜しくない)場合のみ使用。
    山札残り僅少(no_draw)なら使わない"""
    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        if ctx.no_draw:
            return -1
        return 44000 if ctx.negative_hand_count >= 2 else -1


class PokePadPolicy(TrainerCardPolicy):
    """山札にドロディー(Dreepy)かイダテヌキ(Drakloak)が残っている場合のみ使用。
    山札残り僅少(no_draw)なら使わない"""
    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        if ctx.no_draw:
            return -1
        return 45000 if ctx.deck_counts[Dreepy] + ctx.deck_counts[Drakloak] > 0 else -1
```

辞書に追加（Crispin/Brock_Scoutingは`SupporterSelectedPolicy`を`no_draw_gate=True`で使い回す）：

```python
TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {
    Unfair_Stamp: FixedScorePolicy(15000),
    Crushing_Hammer: FixedScorePolicy(40000),
    Boss_Orders: SupporterSelectedPolicy(35000),
    Lillie_Determination: SupporterSelectedPolicy(14000),
    Rare_Candy: RareCandyPolicy(),
    Team_Rocket_Watchtower: TeamRocketWatchtowerPolicy(),
    Night_Stretcher: NightStretcherPolicy(),
    Buddy_Buddy_Poffin: BuddyBuddyPoffinPolicy(),
    Ultra_Ball: UltraBallPolicy(),
    Poke_Pad: PokePadPolicy(),
    Crispin: SupporterSelectedPolicy(35000, no_draw_gate=True),
    Brock_Scouting: SupporterSelectedPolicy(35000, no_draw_gate=True),
}
```

- [ ] **Step 4: テストを実行し成功を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: PASS（43件）

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "$(cat <<'EOF'
feat(dragapult): no_drawゲート付き5枚をTrainerCardPolicyへ移植

Buddy_Buddy_Poffin/Ultra_Ball/Poke_Padは専用クラスで、
Crispin/Brock_ScoutingはSupporterSelectedPolicy(no_draw_gate=True)で
それぞれ現行のelif no_draw暗黙ゲートを明示化して再現する。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: カバレッジ回帰テスト（12カード漏れ無し確認）

**Files:**
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: Task 1〜6で完成した`TRAINER_CARD_POLICIES`

[[feedback_agent_dispatch_coverage]]の教訓（ジャモライコで`OptionType.CARD`の分岐漏れが実戦で勝率0.015という致命傷になった）に従い、移植対象の12カードが過不足なく登録されていることを機械的に保証する。

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_trainer_card_policies_cover_exactly_the_migrated_card_set():
    """現行if/elif連鎖でトレーナーズカードとして扱われている12枚と過不足なく一致することを保証する"""
    expected = {
        dm.Rare_Candy, dm.Unfair_Stamp, dm.Night_Stretcher, dm.Crushing_Hammer,
        dm.Boss_Orders, dm.Lillie_Determination, dm.Team_Rocket_Watchtower,
        dm.Buddy_Buddy_Poffin, dm.Ultra_Ball, dm.Poke_Pad, dm.Crispin, dm.Brock_Scouting,
    }
    assert set(dm.TRAINER_CARD_POLICIES.keys()) == expected
```

- [ ] **Step 2: テストを実行する**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k test_trainer_card_policies_cover_exactly_the_migrated_card_set`
Expected: PASS（Task 1〜6で既に12枚全て登録済みのため、このテストは書いた時点で通る想定。もしFAILする場合はTask 1〜6のいずれかで登録漏れがあるため、辞書登録部分を見直すこと）

- [ ] **Step 3: コミット**

```bash
git add tests/test_dragapult_agent.py
git commit -m "$(cat <<'EOF'
test(dragapult): TrainerCardPolicies登録漏れが無いことを保証する回帰テストを追加

feedback_agent_dispatch_coverageの教訓（ジャモライコのOptionType.CARD
未実装事故）に従い、移植対象12枚が過不足なく登録されていることを
機械的に固定する。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: agent()のPLAY分岐へ配線し、旧if/elifチェーンを削除する

**Files:**
- Modify: `src/dragapult_agent/main.py`（`agent()`関数内、`OptionType.PLAY`分岐）

**Interfaces:**
- Consumes: Task 1〜6の`PlayTrainerCardContext`, `_score_play_trainer_card`

現行の`agent()`内`OptionType.PLAY`分岐（`elif o.type == OptionType.PLAY:`から次の`elif o.type == OptionType.ATTACH:`の直前まで）を、以下のように置き換える。

- [ ] **Step 1: 配線前の状態を確認する（ベースライン）**

Run: `uv run pytest -q`
Expected: PASS（このリポジトリの既存テスト全件。dragapult_agent以外のテストも含め、このタスク開始時点で何件PASSしているかを記録しておく）

- [ ] **Step 2: agent()のPLAY分岐を書き換える**

`src/dragapult_agent/main.py`内の以下のブロックを検索する（`elif o.type == OptionType.PLAY:`で始まり、次の`elif o.type == OptionType.ATTACH:`の直前で終わる）：

```python
        elif o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            card_score = hand_scores[o.index]
            if card.id == Dreepy:
                score = 51000
            elif card.id == Fezandipiti_ex:
                if card_score > 0:
                    score = 53000
                else:
                    score = -1
            elif card.id == Latias_ex:
                if active_id != Drakloak and active_id != Dragapult_ex:
                    score = 51000
                else:
                    score = -1
            elif card.id == Budew:
                if field_counts[Budew] == 0 and field_counts[Dragapult_ex] == 0:
                    score = 52000
                else:
                    score = -1
            elif card.id == Meowth_ex:
                if state.supporterPlayed or stadium_id == Team_Rocket_Watchtower:
                    score = -1
                elif support_count == 0:
                    score = 50000
                elif support_count == hand_counts[Boss_Orders] and not plan_a.attack <= 0:
                    score = 50000
                else:
                    score = -1
            elif card.id == Rare_Candy:
                if no_more_dex:
                    score = -1
                else:
                    score = 75000
            elif card.id == Unfair_Stamp:
                score = 15000
            elif card.id == Night_Stretcher:
                if card_score >= 18000:
                    score = 42000
                else:
                    score = -1
            elif card.id == Crushing_Hammer:
                score = 40000
            elif card.id == Boss_Orders:
                if card.id == use_support:
                    score = 35000
                else:
                    score = -1
            elif card.id == Lillie_Determination:
                if card.id == use_support:
                    score = 14000
                else:
                    score = -1
            elif card.id == Team_Rocket_Watchtower:
                if stadium_id > 0 or state.turn == 1:
                    score = 80000
                else:
                    score = -1
            elif no_draw:
                score = -1
            elif card.id == Buddy_Buddy_Poffin:
                if deck_counts[Dreepy] > 0:
                    score = 46000
                else:
                    score = -1
            elif card.id == Ultra_Ball:
                if negative_hand_count >= 2:
                    score = 44000
                else:
                    score = -1
            elif card.id == Poke_Pad:
                if deck_counts[Dreepy] + deck_counts[Drakloak] > 0:
                    score = 45000
                else:
                    score = -1
            elif card.id == Crispin or card.id == Brock_Scouting:
                if card.id == use_support:
                    score = 35000
                else:
                    score = -1
```

これを以下に置き換える（ポケモンカード5分岐はそのまま維持し、トレーナーズカード分岐だけを`else`節でのディスパッチに置き換える）：

```python
        elif o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            card_score = hand_scores[o.index]
            if card.id == Dreepy:
                score = 51000
            elif card.id == Fezandipiti_ex:
                if card_score > 0:
                    score = 53000
                else:
                    score = -1
            elif card.id == Latias_ex:
                if active_id != Drakloak and active_id != Dragapult_ex:
                    score = 51000
                else:
                    score = -1
            elif card.id == Budew:
                if field_counts[Budew] == 0 and field_counts[Dragapult_ex] == 0:
                    score = 52000
                else:
                    score = -1
            elif card.id == Meowth_ex:
                if state.supporterPlayed or stadium_id == Team_Rocket_Watchtower:
                    score = -1
                elif support_count == 0:
                    score = 50000
                elif support_count == hand_counts[Boss_Orders] and not plan_a.attack <= 0:
                    score = 50000
                else:
                    score = -1
            else:
                # トレーナーズカード(グッズ/サポート/スタジアム)はTrainerCardPolicyへ委譲
                # (docs/superpowers/plans/2026-07-23-dragapult-trainer-card-policy-migration.md)
                ctx = PlayTrainerCardContext(
                    card_id=card.id, card_score=card_score, state=state, stadium_id=stadium_id,
                    deck_counts=deck_counts, negative_hand_count=negative_hand_count,
                    no_draw=no_draw, use_support=use_support, no_more_dex=no_more_dex,
                )
                score = _score_play_trainer_card(card.id, ctx)
```

- [ ] **Step 3: 全体テストを実行し回帰が無いことを確認する**

Run: `uv run pytest -q`
Expected: PASS件数がStep 1のベースラインと完全に一致すること（新規追加した`test_dragapult_agent.py`のテストは既にTask 1〜7でカウント済みのため、このステップで新規に増減しない）。1件でも新規に失敗する場合は、旧elifチェーンと新しい`TRAINER_CARD_POLICIES`のいずれかに条件の写し間違いがあるため、該当カードのポリシークラスを見直すこと（推測で直さず、現行コードの該当行と1行ずつ突き合わせる）

- [ ] **Step 4: dragapult_agentのテストを個別にも確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: PASS（Task 1〜7で追加した全テスト＋既存14件が通る）

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/main.py
git commit -m "$(cat <<'EOF'
refactor(dragapult): agent()のPLAY分岐をTrainerCardPolicyディスパッチへ配線

トレーナーズカード12枚のif/elif連鎖をTRAINER_CARD_POLICIES経由の
ディスパッチに置き換え、if/elif乱立を解消した。ポケモンカード分岐
(Dreepy/Fezandipiti_ex/Latias_ex/Budew/Meowth_ex)は今回スコープ外
のためそのまま維持。振る舞いは一切変更していない
(docs/superpowers/specs/2026-07-23-dragapult-trainer-card-policy-migration-design.md)。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review チェック結果

- **spec網羅性**：設計書の「アーキテクチャ」「no_drawゲートの明示化」「未登録カードのフォールバック」「テスト方針」の全項目に対応するタスクが存在する（Task 1=フォールバック含む土台、Task 3/6=no_drawゲート、Task 7=カバレッジ回帰）
- **プレースホルダー無し**：全ステップに実コードを記載済み
- **型の一貫性**：`PlayTrainerCardContext`のフィールド名・`TRAINER_CARD_POLICIES`のキー・`_score_play_trainer_card`のシグネチャは全タスクで統一
- **スコープ外の明記**：`hand_score()`移植・RL調査・no_draw/no_more_dexの妥当性検証は対象外のまま据え置き（設計書と一致）
