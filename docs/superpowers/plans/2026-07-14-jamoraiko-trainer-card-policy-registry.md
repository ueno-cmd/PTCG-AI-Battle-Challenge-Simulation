# ジャモライコエージェント トレーナーズカード ポリシー登録制 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/superpowers/specs/2026-07-14-jamoraiko-trainer-card-policy-registry-design.md`に基づき、`_score_play_option`のif/elif連鎖11個を`TrainerCardPolicy`レジストリパターンに置き換える。振る舞いは一切変更しない（純粋なリファクタリング）。

**Architecture:** `PlayScoringContext`データクラスで既存の6引数をまとめ、`TrainerCardPolicy`抽象基底クラス（ABC）のサブクラスとして各カードの判断を独立したクラスに分離する。`{card_id: policy_instance}`の辞書（`TRAINER_CARD_POLICIES`）で登録し、`_score_play_option`はレジストリを引くだけの薄いディスパッチャに縮小する。

**Tech Stack:** Python 3.12 / pytest / dataclasses / abc（既存プロジェクト構成を継続、標準ライブラリの`abc`を新規使用）

## Global Constraints

- 全コード内コメント・ドキュメントは日本語で書く（CLAUDE.md ルール）
- 既存の499件のテストスイート全体が最後まで回帰なく通ること（`uv run pytest -q`）
- 振る舞いは一切変更しない。既存の`TestScorePlayOption`クラスの5件のテストは**変更せず**、レジストリ経由でも同じ結果を返すことの回帰確認として機能させる
- `POKEMON_LINES`同様、`TRAINER_CARD_POLICIES`もモジュールレベルの辞書として1度だけ構築する（遅延初期化は不要、依存する外部リソースが無いため）
- `data.cardType == CardType.POKEMON`のケース（進化ポケモン等）はカードID固有の判断ではなく型による判断のため、レジストリの対象外とし現状維持する
- カードID定数：`Lillie_Determination=1227`, `Boss_Orders=1182`, `Energy_Switch=1116`, `Buddy_Buddy_Poffin=1086`, `Ultra_Ball=1121`, `Night_Stretcher=1097`, `Energy_Retrieval=1118`, `Max_Rod=1110`, `Switch=1123`, `Canari=1233`, `Levincia=1254`（いずれも既存定義を流用、変更しない）

---

### Task 1: `TrainerCardPolicy`レジストリの実装

**Files:**
- Modify: `src/jamoraiko_agent/main.py`
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Produces: `PlayScoringContext`データクラス、`TrainerCardPolicy`（ABC）、`FixedScorePolicy`・`LillieDeterminationPolicy`・`BossOrdersPolicy`・`EnergySwitchPolicy`の4具象クラス、`TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy]`
- Consumes: 既存の`_deck_consumption`・`_safe_draws`・`ENERGY_POLICY`・`FieldState`・`AttackPlan`

- [ ] **Step 1: 失敗するテストを書く（新クラス群）**

`tests/test_jamoraiko_agent.py`の`class TestScorePlayOption:`（412行目付近）の直前に新規クラスを追加：

```python
class TestTrainerCardPolicies:
    def test_fixed_score_policy_returns_constant(self):
        policy = jm.FixedScorePolicy(1234)
        ctx = jm.PlayScoringContext(obs=None, o=None, my_index=0, fs=None, my_state=None, plan=None)
        assert policy.play_score(ctx) == 1234

    def test_lillie_determination_policy_blocked_when_deck_thin(self):
        my_state = make_player_state(deck_count=5, prize_count=6)  # safe_draws = -2
        fs = jm._collect_field_state(my_state)
        ctx = jm.PlayScoringContext(obs=None, o=None, my_index=0, fs=fs, my_state=my_state, plan=jm.AttackPlan())
        policy = jm.LillieDeterminationPolicy()
        assert policy.play_score(ctx) == -1

    def test_lillie_determination_policy_scores_high_when_safe(self):
        my_state = make_player_state(deck_count=40, prize_count=6)
        fs = jm._collect_field_state(my_state)
        ctx = jm.PlayScoringContext(obs=None, o=None, my_index=0, fs=fs, my_state=my_state, plan=jm.AttackPlan())
        policy = jm.LillieDeterminationPolicy()
        assert policy.play_score(ctx) == 3100

    def test_boss_orders_policy_scores_high_when_lethal(self):
        plan = jm.AttackPlan(attacker_id=jm.Iono_Voltorb, attack_id=1001, damage=300, is_lethal=True)
        ctx = jm.PlayScoringContext(obs=None, o=None, my_index=0, fs=None, my_state=None, plan=plan)
        policy = jm.BossOrdersPolicy()
        assert policy.play_score(ctx) == 8800

    def test_boss_orders_policy_scores_low_when_not_lethal(self):
        ctx = jm.PlayScoringContext(obs=None, o=None, my_index=0, fs=None, my_state=None, plan=jm.AttackPlan())
        policy = jm.BossOrdersPolicy()
        assert policy.play_score(ctx) == 500

    def test_energy_switch_policy_delegates_to_energy_policy(self):
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[6])  # 雷0闘1
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])  # 供給可能
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[bellibolt])
        ctx = jm.PlayScoringContext(obs=None, o=None, my_index=0, fs=None, my_state=my_state, plan=jm.AttackPlan())
        policy = jm.EnergySwitchPolicy()
        assert policy.play_score(ctx) == jm.ENERGY_POLICY.play_score(my_state)

    def test_trainer_card_policies_registers_all_expected_cards(self):
        expected_ids = {
            jm.Lillie_Determination, jm.Boss_Orders, jm.Energy_Switch,
            jm.Buddy_Buddy_Poffin, jm.Ultra_Ball, jm.Night_Stretcher,
            jm.Energy_Retrieval, jm.Max_Rod, jm.Switch, jm.Canari, jm.Levincia,
        }
        assert set(jm.TRAINER_CARD_POLICIES.keys()) == expected_ids
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k TestTrainerCardPolicies`
Expected: FAIL（`AttributeError: module 'jamoraiko_agent.main' has no attribute 'FixedScorePolicy'`）

- [ ] **Step 3: `abc`のimportを追加する**

`src/jamoraiko_agent/main.py`の先頭のimport群（1〜9行目）を変更：

変更前：
```python
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable
```

変更後：
```python
import os
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable
```

- [ ] **Step 4: `TrainerCardPolicy`レジストリを実装する**

`src/jamoraiko_agent/main.py`の`_score_play_option`関数（現在422〜459行目付近、`# ==================== PLAYオプションのスコアリング ====================`セクション見出し含む）の直前に、新しいセクションを挿入する：

```python
# ==================== PLAYスコアリングのポリシー登録制 ====================
@dataclass
class PlayScoringContext:
    """OptionType.PLAY のスコアリングに必要な情報をまとめる。
    将来カードが増えても、ポリシークラス側のシグネチャを変えずに済む"""
    obs: Observation
    o: "Option"
    my_index: int
    fs: FieldState
    my_state: "PlayerState"
    plan: AttackPlan


class TrainerCardPolicy(ABC):
    """1枚のトレーナーズカード（サポート/グッズ/スタジアム）のPLAY判断を表す"""
    @abstractmethod
    def play_score(self, ctx: PlayScoringContext) -> int: ...


class FixedScorePolicy(TrainerCardPolicy):
    """固定スコアを返すだけのカード用（ハイパーボール等、条件分岐が無いもの）"""
    def __init__(self, score: int):
        self._score = score

    def play_score(self, ctx: PlayScoringContext) -> int:
        return self._score


class LillieDeterminationPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        consumption = _deck_consumption(Lillie_Determination, ctx.my_state, ctx.fs.hand_counts)
        if consumption is not None and consumption > _safe_draws(ctx.my_state):
            return -1
        return 3100


class BossOrdersPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        return 8800 if ctx.plan.is_lethal else 500


class EnergySwitchPolicy(TrainerCardPolicy):
    """既存のENERGY_POLICYに委譲する（EnergyPolicy自体は変更しない）"""
    def play_score(self, ctx: PlayScoringContext) -> int:
        return ENERGY_POLICY.play_score(ctx.my_state)


TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {
    Lillie_Determination: LillieDeterminationPolicy(),
    Boss_Orders: BossOrdersPolicy(),
    Energy_Switch: EnergySwitchPolicy(),
    Buddy_Buddy_Poffin: FixedScorePolicy(8000),
    Ultra_Ball: FixedScorePolicy(6000),
    Night_Stretcher: FixedScorePolicy(4800),
    Energy_Retrieval: FixedScorePolicy(6100),
    Max_Rod: FixedScorePolicy(5500),
    Switch: FixedScorePolicy(2500),
    Canari: FixedScorePolicy(5900),
    Levincia: FixedScorePolicy(8500),
}
```

- [ ] **Step 5: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k TestTrainerCardPolicies`
Expected: PASS（7件）

- [ ] **Step 6: 失敗するテストを書く（未登録カードのフォールバック）**

`tests/test_jamoraiko_agent.py`の`class TestScorePlayOption:`の最後に追加：

```python
    def test_unregistered_card_defaults_to_1000(self, mock_card_table):
        mock_card_table[999999] = MockCardData(cardId=999999, cardType=CardType.ITEM)
        unknown = make_pokemon(id=999999)
        my_state = make_player_state(hand=[unknown], deck_count=40, prize_count=6)
        obs, o = self._make_obs_with_hand_card(999999, my_state)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_play_option(obs, o, my_index=0, fs=fs, my_state=my_state, plan=plan)
        assert score == 1000
```

- [ ] **Step 7: テストを実行する（この時点ではPASSするのが正しい）**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k test_unregistered_card_defaults_to_1000`
Expected: PASS。旧`_score_play_option`は末尾に`return 1000`のフォールバックを既に持っているため、この時点で既にPASSする。これはTDDのRED確認ではなく、Step 8のリファクタリング後も同じ振る舞い（未登録カードは1000）が保たれることを確認するための固定テストである。Step 9で再度実行し、変わらずPASSすることを確認する

- [ ] **Step 8: `_score_play_option`をレジストリ参照に書き換える**

`src/jamoraiko_agent/main.py`の`_score_play_option`関数全体（現在422〜459行目付近）を、以下に置き換える：

変更前：
```python
# ==================== PLAYオプションのスコアリング ====================
def _score_play_option(obs, o, my_index: int, fs: FieldState, my_state, plan: AttackPlan) -> int:
    """OptionType.PLAY のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    data = card_table[card.id]

    if card.id == Lillie_Determination:
        consumption = _deck_consumption(card.id, my_state, fs.hand_counts)
        if consumption is not None and consumption > _safe_draws(my_state):
            return -1
        return 3100

    if card.id == Boss_Orders:
        return 8800 if plan.is_lethal else 500

    if data.cardType == CardType.POKEMON:
        return 20000

    if card.id == Buddy_Buddy_Poffin:
        return 8000
    if card.id == Ultra_Ball:
        return 6000
    if card.id == Night_Stretcher:
        return 4800
    if card.id == Energy_Retrieval:
        return 6100
    if card.id == Energy_Switch:
        return ENERGY_POLICY.play_score(my_state)
    if card.id == Max_Rod:
        return 5500
    if card.id == Switch:
        return 2500
    if card.id == Canari:
        return 5900
    if card.id == Levincia:
        return 8500

    return 1000
```

変更後：
```python
# ==================== PLAYオプションのスコアリング ====================
def _score_play_option(obs, o, my_index: int, fs: FieldState, my_state, plan: AttackPlan) -> int:
    """OptionType.PLAY のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    data = card_table[card.id]

    if data.cardType == CardType.POKEMON:
        return 20000

    policy = TRAINER_CARD_POLICIES.get(card.id)
    if policy is None:
        return 1000

    ctx = PlayScoringContext(obs=obs, o=o, my_index=my_index, fs=fs, my_state=my_state, plan=plan)
    return policy.play_score(ctx)
```

- [ ] **Step 9: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v -k "TestScorePlayOption or TestTrainerCardPolicies"`
Expected: 全件PASS（`TestScorePlayOption`の既存5件が**変更なしのまま**PASSすることで、レジストリ経由でも振る舞いが変わっていないことを確認）

Run: `uv run pytest -q`
Expected: 全件PASS（499件から、新規8件追加で507件）

- [ ] **Step 10: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "refactor: _score_play_optionのif分岐をTrainerCardPolicyレジストリに置き換え（振る舞い変更なし）"
```

---

## 全タスク完了後の最終確認

- [ ] `uv run pytest -q`で全件PASSを確認（507件）
- [ ] `git log --oneline`でTask 1のコミットが積まれていることを確認
- [ ] 最終ブランチ全体レビュー（`superpowers:requesting-code-review`のcode-reviewer.mdテンプレート使用）を実施
- [ ] レビュー完了後、`docs/implementations/[日付]-jamoraiko-trainer-card-policy-registry.md`に実装サマリーを保存
- [ ] レビュー結果を`docs/reviews/[日付]-jamoraiko-trainer-card-policy-registry.md`に保存
- [ ] マージ後、ユーザーがKaggle上でノートブックを再実行し、振る舞いが変わっていないこと（勝率が今回の変更前後で大きく変動しないこと）を確認する
- [ ] 次回セッションで、フラッシュドロー依存の調整・`OptionType.ABILITY`分岐へのパターン展開・resilience調査のいずれに進むかを判断する
