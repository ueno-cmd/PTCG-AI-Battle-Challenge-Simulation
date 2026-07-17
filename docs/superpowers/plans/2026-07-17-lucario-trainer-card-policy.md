# ルカリオexエージェント TrainerCardPolicy化＋2件のロジック修正 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/lucario_agent/main.py`の`_score_play_option`（トレーナーズカードのif/elif連鎖）を、ジャモライコと同じ`TrainerCardPolicy`レジストリパターンでクラス化し、その過程で実ログで確認済みの2つのロジックミス（リーリエの決意の手札無視・ハイパーボールの歯止め欠如）と、`SETUP_ACTIVE_POKEMON`のオーガポンex優先度欠如を修正する。

**Architecture:** `PlayScoringContext`データクラスに既存の`_score_play_option`引数をまとめ、`TrainerCardPolicy`（ABC）のカードID→ポリシーオブジェクト辞書（`TRAINER_CARD_POLICIES`）に置き換える。山札温存ガード（`_deck_consumption`/`_safe_draws`）は現行構造通り`_score_play_option`のラッパー側に残す（ジャモライコとは意図的に異なる設計判断）。

**Tech Stack:** Python 3.12 / uv / pytest（既存の`tests/test_lucario_agent.py`のテストヘルパーを流用）

**参照設計書:** `docs/superpowers/specs/2026-07-17-lucario-trainer-card-policy-design.md`

## Global Constraints

- 既存の`tests/test_lucario_agent.py`のテストは、Task 3・Task 4・Task 5で明示的に新しい振る舞いを追加する箇所を除き、**無改修のまま全てPASSし続けること**（振る舞い変更なしのリファクタリングであるため）
- `_score_play_option`の外部シグネチャ（引数名・順序・戻り値の型）は変更しないこと。呼び出し元（`_score_option`内の呼び出し、既存テストの直接呼び出し）を壊さないため
- **重要な落とし穴の回避**：dataclassのフィールドに文字列（クォート付き）の型注釈を使い、かつその型名が実際にはインポートされていない場合、Kaggleノートブックのexec()実行方式でクラッシュする既知の問題がある（過去のジャモライコ実装で発生済み）。今回`PlayScoringContext`で使う`Option`・`PlayerState`は必ず`cg.api`から実インポートし、クォート無しの型注釈として使うこと（Task 1で対応）
- 各タスックの最後に`uv run pytest -q`でリポジトリ全体を実行し、全件PASSであることを確認してからコミットすること。本計画作成時点のベースラインは**495件全PASS**

---

## Task 1: `PlayScoringContext`・`TrainerCardPolicy`・`FixedScorePolicy`のスキャフォールディング

まだ`_score_play_option`には配線しない。土台となるクラスを追加し、単体で正しく動くことをテストで確認する。

**Files:**
- Modify: `src/lucario_agent/main.py:1-9`（import文にABC・Option・PlayerStateを追加）
- Modify: `src/lucario_agent/main.py:458-460`（`_deck_consumption`の直後、`_score_play_option`の直前に新セクションを挿入）
- Test: `tests/test_lucario_agent.py:543`（`_hand_counts`の直後に新テストクラスを追加）

**Interfaces:**
- Produces: `PlayScoringContext`（dataclass）, `TrainerCardPolicy`（ABC、`play_score(ctx) -> int`）, `FixedScorePolicy(score: int)`（後続タスクで使用）

- [ ] **Step 1: importを修正する**

`src/lucario_agent/main.py`の1-9行目を以下に置き換える：

```python
import os
import random
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass

from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, Option, PlayerState, all_card_data, to_observation_class,
)
```

- [ ] **Step 2: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`_hand_counts`関数（543行目付近）の直後に以下を追加する：

```python
class TestPlayScoringContextScaffolding:
    """TrainerCardPolicyパターンの土台（まだ_score_play_optionには未配線）"""

    def test_fixed_score_policy_returns_constant(self):
        policy = lm.FixedScorePolicy(1234)
        ctx = lm.PlayScoringContext(
            obs=MagicMock(), o=Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=False,
            state=_make_state(), my_state=make_player_state(),
            hand_counts=defaultdict(int), field_counts=defaultdict(int), stadium_id=0,
        )
        assert policy.play_score(ctx) == 1234

    def test_trainer_card_policy_is_abstract(self):
        with pytest.raises(TypeError):
            lm.TrainerCardPolicy()
```

- [ ] **Step 3: テストが失敗することを確認する**

Run: `uv run pytest tests/test_lucario_agent.py -k TestPlayScoringContextScaffolding -v`
Expected: FAIL（`AttributeError: module 'lucario_agent.main' has no attribute 'FixedScorePolicy'`）

- [ ] **Step 4: 最小実装を書く**

`src/lucario_agent/main.py`の`_deck_consumption`関数（458行目付近）の直後、`_score_play_option`関数の直前に以下を挿入する：

```python
# ==================== PLAYスコアリングのポリシー登録制 ====================
@dataclass
class PlayScoringContext:
    """OptionType.PLAY のスコアリングに必要な情報をまとめる（_score_play_optionの既存引数を集約）"""
    obs: Observation
    o: Option
    my_index: int
    current_plan: AttackPlan
    can_attack: bool
    state: PlayerState
    my_state: PlayerState
    hand_counts: defaultdict
    field_counts: defaultdict
    stadium_id: int
    attacker1: bool = False
    rng: "random.Random | None" = None


class TrainerCardPolicy(ABC):
    """1枚のトレーナーズカード（サポート/グッズ/スタジアム）のPLAY判断を表す"""
    @abstractmethod
    def play_score(self, ctx: PlayScoringContext) -> int: ...


class FixedScorePolicy(TrainerCardPolicy):
    """固定スコアのみを返すカード用"""
    def __init__(self, score: int):
        self._score = score

    def play_score(self, ctx: PlayScoringContext) -> int:
        return self._score
```

- [ ] **Step 5: テストが通ることを確認する**

Run: `uv run pytest tests/test_lucario_agent.py -k TestPlayScoringContextScaffolding -v`
Expected: PASS（2 passed）

- [ ] **Step 6: リポジトリ全体の回帰確認**

Run: `uv run pytest -q`
Expected: `497 passed`（既存495件 + 新規2件、まだ配線していないため既存の挙動は一切変わらない）

- [ ] **Step 7: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat(lucario): add TrainerCardPolicy scaffolding (PlayScoringContext/ABC/FixedScorePolicy)"
```

---

## Task 2: 全トレーナーズカードをポリシークラスへ移行する（振る舞い変更なし）

`_score_play_option`のif/elif連鎖11個を、Task 1の土台を使って完全にレジストリ化する。**この時点ではLillie_DeterminationとUltra_Ballの挙動は現状のまま変更しない**（修正はTask 3・4で行う）。純粋なリファクタリングなので、新しい失敗するテストではなく「既存テストが全て変わらずPASSすること」を検証基準にする。

**Files:**
- Modify: `src/lucario_agent/main.py`（Task 1で挿入した`FixedScorePolicy`の直後に具象ポリシークラスを追加、`_score_play_option`本体を置き換え）

**Interfaces:**
- Consumes: `PlayScoringContext`, `TrainerCardPolicy`, `FixedScorePolicy`（Task 1で定義）
- Produces: `PremiumPowerProPolicy`, `BossOrdersPolicy`, `LillieDeterminationPolicy`（現状維持版）, `UltraBallPolicy`（現状維持版）, `JudgePolicy`, `WallyCompassionPolicy`, `GravityMountainPolicy`, `TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy]`

- [ ] **Step 1: 現状のテスト結果を記録する（基準値）**

Run: `uv run pytest -q`
Expected: `497 passed`（Task 1完了後の状態）

- [ ] **Step 2: 具象ポリシークラスを追加する**

`FixedScorePolicy`クラスの直後に以下を追加する（既存の`_score_play_option`内if/elif連鎖のロジックを1対1でそのまま移植、挙動変更なし。Task 1でコードを挿入した分、行番号は本計画作成時点からずれているため、`if card.id == Premium_Power_Pro:`等のテキストで検索して該当箇所を特定すること）：

```python
class PremiumPowerProPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        confirmed_ko_already_secured = ctx.state.supporterPlayed and ctx.current_plan.remain_hp <= 0
        if confirmed_ko_already_secured:
            return -1
        if ctx.can_attack:
            return 5000
        other_supporter_in_hand = ctx.hand_counts[Boss_Orders] >= 1 or ctx.hand_counts[Lillie_Determination] >= 1
        if not ctx.state.supporterPlayed and not other_supporter_in_hand:
            return 3050
        return -1


class BossOrdersPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        if ctx.current_plan.target < 1:
            return -1  # 対象不在なら温存
        if ctx.current_plan.remain_hp <= 0:
            return 8800  # 即使用（確定KO）
        active_rng = ctx.rng if ctx.rng is not None else _rng
        if active_rng.random() < EPSILON:
            return 6000  # 探索的先出し
        return -1  # 温存


class LillieDeterminationPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        return 3100


class UltraBallPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        already_found = (
            ctx.field_counts[Riolu] + ctx.field_counts[Mega_Lucario_ex] + ctx.field_counts[Ogerpon_ex]
            + ctx.hand_counts[Riolu] + ctx.hand_counts[Mega_Lucario_ex] + ctx.hand_counts[Ogerpon_ex]
        )
        return 6000 if already_found == 0 else 5500


class JudgePolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        return 7000 if ctx.hand_counts[Basic_Fighting_Energy] == 0 and not ctx.attacker1 else -1


class WallyCompassionPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        my_lucario = next(
            (p for p in ([ctx.my_state.active[0]] if ctx.my_state.active else []) + list(ctx.my_state.bench)
             if p is not None and p.id == Mega_Lucario_ex),
            None,
        )
        if my_lucario is not None and my_lucario.hp < my_lucario.maxHp:
            return 6800
        return -1


class GravityMountainPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        return -1 if ctx.stadium_id == 0 else 10000


TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {
    Premium_Power_Pro: PremiumPowerProPolicy(),
    Boss_Orders: BossOrdersPolicy(),
    Lillie_Determination: LillieDeterminationPolicy(),
    Ultra_Ball: UltraBallPolicy(),
    Pokegear: FixedScorePolicy(5200),
    Night_Stretcher: FixedScorePolicy(4800),
    Judge: JudgePolicy(),
    Hilda: FixedScorePolicy(5300),
    Ciphermaniac_Codebreaking: FixedScorePolicy(5100),
    Wally_Compassion: WallyCompassionPolicy(),
    Gravity_Mountain: GravityMountainPolicy(),
}
```

- [ ] **Step 3: `_score_play_option`本体をレジストリ経由に置き換える**

既存の`_score_play_option`関数全体（`def _score_play_option(obs, o, my_index, current_plan, can_attack,`という行から、その関数の最後の`    return 10000`という行まで。Step 2でクラスを挿入した分、行番号は本計画作成時点からずれているため、この関数シグネチャの文字列で検索して特定すること）を丸ごと以下に置き換える：

```python
def _score_play_option(obs, o, my_index, current_plan, can_attack,
                       state, my_state, hand_counts, field_counts, stadium_id,
                       attacker1: bool = False,
                       rng: "random.Random | None" = None) -> int:
    """OptionType.PLAY のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    data = card_table[card.id]
    consumption = _deck_consumption(card.id, my_state, hand_counts)
    if consumption is not None and consumption > _safe_draws(my_state):
        return -1  # 山札温存
    if data.cardType == CardType.POKEMON:
        if card.id in (Lunatone, Solrock):
            return -1 if field_counts[card.id] >= 1 else 20000
        if card.id == Riolu:
            return -1 if field_counts[Riolu] + field_counts[Mega_Lucario_ex] >= 2 else 20000
        return 20000

    policy = TRAINER_CARD_POLICIES.get(card.id)
    if policy is None:
        return 10000

    ctx = PlayScoringContext(
        obs=obs, o=o, my_index=my_index, current_plan=current_plan, can_attack=can_attack,
        state=state, my_state=my_state, hand_counts=hand_counts, field_counts=field_counts,
        stadium_id=stadium_id, attacker1=attacker1, rng=rng,
    )
    return policy.play_score(ctx)
```

- [ ] **Step 4: 既存テストが全てそのままPASSすることを確認する**

Run: `uv run pytest -q`
Expected: `497 passed`（Task 1完了時と完全に同じ件数。振る舞いを一切変えていないため）

もし1件でも失敗した場合、`_score_play_option`の移植ミス（既存if/elif分岐の条件・戻り値の写し間違い）を疑い、該当するテストの`assert`と見比べて特定すること。

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py
git commit -m "refactor(lucario): migrate _score_play_option to TrainerCardPolicy registry (behavior-preserving)"
```

---

## Task 3: リーリエの決意に手札質ガードを追加する（ロジックミス修正①）

**Files:**
- Modify: `src/lucario_agent/main.py`（`LillieDeterminationPolicy`のみ）
- Test: `tests/test_lucario_agent.py`（`TestUltraBallAlreadyFoundIncludesOgerponEx`クラスの直後に新テストクラスを追加）

**Interfaces:**
- Consumes: `PlayScoringContext.hand_counts`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の末尾（`TestUltraBallAlreadyFoundIncludesOgerponEx`クラスの後）に以下を追加する：

```python
class TestLillieDeterminationHandQualityGuard:
    """★修正：手札に主要ポケモンがあれば温存する。
    実ログ86363073, 86197001, 86241854, 86295193, 86295949等で、有用な手札を
    持ちながら山札に戻していたロジックミスの修正"""

    def _score(self, extra_hand_cards):
        lillie = Card(id=lm.Lillie_Determination, serial=1, playerIndex=0)
        cards = [lillie] + extra_hand_cards
        obs, my_state = _obs_with_hand(cards, deck_count=20)
        o = Option(type=OptionType.PLAY, index=0)
        return lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts(cards), field_counts=defaultdict(int),
            stadium_id=0,
        )

    def test_suppressed_when_riolu_in_hand(self):
        score = self._score([Card(id=lm.Riolu, serial=2, playerIndex=0)])
        assert score == -1

    def test_suppressed_when_mega_lucario_ex_in_hand(self):
        score = self._score([Card(id=lm.Mega_Lucario_ex, serial=2, playerIndex=0)])
        assert score == -1

    def test_suppressed_when_ogerpon_ex_in_hand(self):
        score = self._score([Card(id=lm.Ogerpon_ex, serial=2, playerIndex=0)])
        assert score == -1

    def test_suppressed_when_solrock_in_hand(self):
        score = self._score([Card(id=lm.Solrock, serial=2, playerIndex=0)])
        assert score == -1

    def test_suppressed_when_lunatone_in_hand(self):
        score = self._score([Card(id=lm.Lunatone, serial=2, playerIndex=0)])
        assert score == -1

    def test_scores_normally_when_no_key_pokemon_in_hand(self):
        score = self._score([Card(id=lm.Pokegear, serial=2, playerIndex=0)])
        assert score == 3100
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_lucario_agent.py -k TestLillieDeterminationHandQualityGuard -v`
Expected: FAIL（`test_suppressed_when_*`の5件が`assert 3100 == -1`で失敗。`test_scores_normally_when_no_key_pokemon_in_hand`はこの時点でもPASSする）

- [ ] **Step 3: 最小実装を書く**

`LillieDeterminationPolicy`クラス全体を以下に置き換える：

```python
class LillieDeterminationPolicy(TrainerCardPolicy):
    """手札に主要ポケモンがあれば温存する（86363073, 86197001, 86241854, 86295193,
    86295949等の実ログで、有用な手札を持ちながら山札に戻していたロジックミスの修正）"""
    KEY_POKEMON_IDS = (Riolu, Mega_Lucario_ex, Ogerpon_ex, Solrock, Lunatone)

    def play_score(self, ctx: PlayScoringContext) -> int:
        if any(ctx.hand_counts[pid] >= 1 for pid in self.KEY_POKEMON_IDS):
            return -1
        return 3100
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_lucario_agent.py -k TestLillieDeterminationHandQualityGuard -v`
Expected: PASS（6 passed）

- [ ] **Step 5: リポジトリ全体の回帰確認**

Run: `uv run pytest -q`
Expected: `503 passed`（497 + 新規6件）。特に`TestDeckSafetyGate`の`test_lillie_determination_scores_normally_when_deck_healthy`等（手札にリーリエの決意単体しか無いケース）が引き続きPASSすることを確認する

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "fix(lucario): suppress Lillie's Determination when hand already has a key Pokemon"
```

---

## Task 4: ハイパーボールに確保済み抑制ロジックを追加する（ロジックミス修正②）

**Files:**
- Modify: `src/lucario_agent/main.py`（`UltraBallPolicy`のみ）
- Test: `tests/test_lucario_agent.py`（Task 3で追加したクラスの直後に新テストクラスを追加）

**Interfaces:**
- Consumes: `PlayScoringContext.field_counts`, `PlayScoringContext.hand_counts`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の末尾に以下を追加する：

```python
class TestUltraBallAlreadyFoundSuppression:
    """★修正：主要ポケモンを十分確保済み（already_found>=3）ならスコアを大幅に下げる。
    実ログ86197001で、手札がボスの指令とメガルカリオexの2枚しかない状況でもハイパー
    ボールを撃ち両方とも巻き込んで捨てていたロジックミスの修正"""

    def _score(self, field_counts=None, hand_counts=None):
        my_ps = make_player_state(hand=[Card(id=lm.Ultra_Ball, serial=1, playerIndex=0)])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        return lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=False,
            state=_make_state(), my_state=my_ps,
            hand_counts=hand_counts or defaultdict(int),
            field_counts=field_counts or defaultdict(int), stadium_id=0,
        )

    def test_still_high_priority_when_already_found_is_2(self):
        fc = defaultdict(int, {lm.Riolu: 1, lm.Mega_Lucario_ex: 1})
        assert self._score(field_counts=fc) == 5500

    def test_suppressed_when_already_found_is_3(self):
        fc = defaultdict(int, {lm.Riolu: 1, lm.Mega_Lucario_ex: 1, lm.Ogerpon_ex: 1})
        assert self._score(field_counts=fc) == 100

    def test_suppressed_when_already_found_exceeds_3(self):
        fc = defaultdict(int, {lm.Riolu: 2, lm.Mega_Lucario_ex: 1, lm.Ogerpon_ex: 1})
        assert self._score(field_counts=fc) == 100
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_lucario_agent.py -k TestUltraBallAlreadyFoundSuppression -v`
Expected: FAIL（`test_suppressed_when_already_found_is_3`と`test_suppressed_when_already_found_exceeds_3`が`assert 5500 == 100`で失敗。`test_still_high_priority_when_already_found_is_2`はこの時点でもPASSする）

- [ ] **Step 3: 最小実装を書く**

`UltraBallPolicy`クラス全体を以下に置き換える：

```python
class UltraBallPolicy(TrainerCardPolicy):
    """主要ポケモンを十分確保済み（already_found>=3）ならスコアを大幅に下げる
    （86197001の実ログで、手札がボスの指令とメガルカリオexの2枚しかない状況でも
    ハイパーボールを撃ち両方とも巻き込んで捨てていたロジックミスの修正）"""
    ALREADY_FOUND_SUPPRESS_THRESHOLD = 3

    def play_score(self, ctx: PlayScoringContext) -> int:
        already_found = (
            ctx.field_counts[Riolu] + ctx.field_counts[Mega_Lucario_ex] + ctx.field_counts[Ogerpon_ex]
            + ctx.hand_counts[Riolu] + ctx.hand_counts[Mega_Lucario_ex] + ctx.hand_counts[Ogerpon_ex]
        )
        if already_found >= self.ALREADY_FOUND_SUPPRESS_THRESHOLD:
            return 100
        return 6000 if already_found == 0 else 5500
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_lucario_agent.py -k TestUltraBallAlreadyFoundSuppression -v`
Expected: PASS（3 passed）

- [ ] **Step 5: リポジトリ全体の回帰確認**

Run: `uv run pytest -q`
Expected: `506 passed`（503 + 新規3件）。特に`TestNewCardScoring.test_ultra_ball_prioritised_when_riolu_not_found`（already_found=0→6000）、`test_ultra_ball_still_positive_when_riolu_present`（already_found=1→5500）、`TestUltraBallAlreadyFoundIncludesOgerponEx`の2件（already_found=1→5500）が引き続きPASSすることを確認する

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "fix(lucario): suppress Ultra Ball once key Pokemon are already secured"
```

---

## Task 5: SETUP_ACTIVE_POKEMONにオーガポンexの優先度を追加する（ロジックミス修正③）

**Files:**
- Modify: `src/lucario_agent/main.py`（`_score_card_option`内の`SelectContext.SETUP_ACTIVE_POKEMON`ケース。これまでのタスクでのコード追加により行番号は本計画作成時点からずれているため、`case SelectContext.SETUP_ACTIVE_POKEMON:`のテキストで検索して特定すること）
- Test: `tests/test_lucario_agent.py`（Task 4で追加したクラスの直後に新テストクラスを追加）

**Interfaces:**
- Consumes: `_score_card_option`の既存引数（変更なし）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の末尾に以下を追加する：

```python
class TestSetupActivePokemonOgerponPriority:
    """SelectContext.SETUP_ACTIVE_POKEMONでのオーガポンex優先度テスト。
    実ログ86197001：開幕手札にRiolu/Solrockが無く、Lunatone(攻撃不可)とOgerpon_ex
    (3エネで攻撃可能)が両方あった場面で同点(0)によりLunatoneが選ばれ、以後
    エネルギー無しで自力退場できず20ターン無攻撃のまま敗北していたロジックミスの修正"""

    def _score(self, card_id):
        card = Card(id=card_id, serial=1, playerIndex=0)
        obs = MagicMock()
        obs.select.deck = [card]
        return lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.DECK, index=0, playerIndex=0),
            context=lm.SelectContext.SETUP_ACTIVE_POKEMON, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )

    def test_ogerpon_ex_score_is_1(self):
        assert self._score(lm.Ogerpon_ex) == 1

    def test_lunatone_score_unchanged_at_0(self):
        assert self._score(lm.Lunatone) == 0

    def test_ogerpon_ex_beats_lunatone_reproducing_log_86197001(self):
        assert self._score(lm.Ogerpon_ex) > self._score(lm.Lunatone)

    def test_riolu_still_takes_priority_over_ogerpon_ex(self):
        assert self._score(lm.Riolu) > self._score(lm.Ogerpon_ex)

    def test_solrock_still_takes_priority_over_ogerpon_ex(self):
        assert self._score(lm.Solrock) > self._score(lm.Ogerpon_ex)
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_lucario_agent.py -k TestSetupActivePokemonOgerponPriority -v`
Expected: FAIL（`test_ogerpon_ex_score_is_1`が`assert 0 == 1`、`test_ogerpon_ex_beats_lunatone_reproducing_log_86197001`が`assert 0 > 0`で失敗。他3件はこの時点でもPASSする）

- [ ] **Step 3: 最小実装を書く**

`_score_card_option`内の`SelectContext.SETUP_ACTIVE_POKEMON`ケースを以下に置き換える：

```python
        case SelectContext.SETUP_ACTIVE_POKEMON:
            if card.id == Solrock:
                return 4 if state.firstPlayer != my_index else 2
            if card.id == Riolu:
                return 3
            if card.id == Ogerpon_ex:
                return 1  # ルナトーン(0点)より優先。Riolu/Solrockには劣後させたまま
            return 0
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_lucario_agent.py -k TestSetupActivePokemonOgerponPriority -v`
Expected: PASS（5 passed）

- [ ] **Step 5: リポジトリ全体の回帰確認**

Run: `uv run pytest -q`
Expected: `511 passed`（506 + 新規5件）

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "fix(lucario): prioritize Ogerpon ex over Lunatone in SETUP_ACTIVE_POKEMON"
```

---

## Task 6: 対象外箇所へのコメント追記＋最終回帰確認

設計書の「対象外だが目を通す箇所」に基づき、機能変更はせずコメントのみ残す。

**Files:**
- Modify: `src/lucario_agent/main.py`（`_score_card_option`のSWITCH/TO_ACTIVEケース、`calc_attack_plan`関数のdocstring。これまでのタスクでのコード追加により行番号は本計画作成時点からずれているため、テキストで検索して特定すること）

**Interfaces:**
- Consumes: なし（コメント追加のみ、既存コードの動作は一切変更しない）

- [ ] **Step 1: SWITCH/TO_ACTIVEケースにコメントを追加する**

`_score_card_option`内の`case SelectContext.SWITCH | SelectContext.TO_ACTIVE:`の直後（`if o.playerIndex == my_index:`という行の直前）に以下のコメントを追加する：

```python
        case SelectContext.SWITCH | SelectContext.TO_ACTIVE:
            # 【メモ・2026-07-17】current_plan(グローバルplan)はSelectContext.MAIN かつ
            # turn>=2 のタイミングでのみ再計算される。それ以外のタイミング（相手の
            # ボスの指令等で強制的にこのコンテキストへ入った場合）は直前のMAIN計算
            # 時点の古いattacker/targetを参照し続けるため、盤面が変わった後もスコアが
            # ズレる可能性がある。2026-07-17時点ではこれが直接の敗因になったケースは
            # 未確認（実ログ86197001の敗因はSETUP_ACTIVE_POKEMON側だった）が、
            # 潜在リスクとして次回検討の余地がある
            if o.playerIndex == my_index:
```

- [ ] **Step 2: `calc_attack_plan`にコメントを追加する**

`calc_attack_plan`関数のdocstring（`"""最適な攻撃プランを計算して返す"""`）を以下に置き換える：

```python
    """最適な攻撃プランを計算して返す。

    【メモ・2026-07-17】Mega_Lucario_ex/Solrock/Ogerpon_exのアタッカー候補は
    if/elif連鎖で判定している。2026-07-07にテーブル化リファクタリング
    （アタッカー定義をdataclassのリストに切り出す案）が検討されたが、
    ブレスト中にスコープ確定直後で中断されたまま未着手。今回のTrainerCardPolicy化とは
    別スコープのため対象外とする
    """
```

- [ ] **Step 3: 構文エラーが無いことを確認する**

Run: `uv run python -c "import lucario_agent.main"`
Expected: エラーなく終了（何も出力されない）

- [ ] **Step 4: リポジトリ全体の最終回帰確認**

Run: `uv run pytest -q`
Expected: `511 passed`（コメント追加のみのため件数は変わらない）

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py
git commit -m "docs(lucario): annotate SWITCH/TO_ACTIVE staleness risk and calc_attack_plan table-ization backlog"
```

---

## 実装完了後（このセッションではやらないこと）

- デッキCSV再生成・Kaggle再提出でスコア変化を確認する（ユーザー側で別途実施、要明示確認）
- ジャモライコ側`LillieDeterminationPolicy`の同種バグ修正（次回セッション）
- Alakazam系対策・RETREAT未実装への対応（次回セッション）
- `docs/implementations/20260717-lucario-trainer-card-policy.md`への実装サマリー作成（全タスク完了後、CLAUDE.mdフェーズ4の手順に従い作成すること）
