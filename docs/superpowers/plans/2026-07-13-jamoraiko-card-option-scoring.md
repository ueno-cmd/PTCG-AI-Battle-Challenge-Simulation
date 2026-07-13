# ジャモライコ OptionType.CARD スコアリング追加 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/jamoraiko_agent/main.py`の`_score_option`に`OptionType.CARD`のスコアリングを追加し、校正実験で判明した勝率0.015（イオナサンプル相手）の壊滅的な結果の原因を解消する。

**Architecture:** 既存の`ATTACKERS`テーブルと同じデータ駆動スタイルで、ポケモンごとの優先度情報を`POKEMON_LINES`辞書にまとめる。`SelectContext`ごとに専用の小さなスコアリング関数（`_score_setup_active`/`_score_switch_target`/`_score_search_candidate`/`_score_discard_candidate`）を用意し、新設する`_score_card_option`ディスパッチャがこれらを呼び分ける。`_score_option`の`match`文に`case OptionType.CARD:`を追加してディスパッチャに接続する。

**Tech Stack:** Python 3.12 / pytest / `cg.api`（Kaggle専用ライブラリ、テストは`tests/conftest.py`のモックヘルパー経由）

## Global Constraints

- 対象コンテキストは`SETUP_ACTIVE_POKEMON`/`SWITCH`/`TO_ACTIVE`/`TO_HAND`/`TO_BENCH`/`DISCARD`の6つのみ（設計書の合意事項）。`SETUP_BENCH_POKEMON`と`ATTACH_FROM`はスコープ外
- 実装スタイルはデータ駆動型（テーブル）。`if/elif`の連鎖を作らない（CLAUDE.mdのif文設計ガイドライン：ネスト2階層まで）
- 全タスクで`uv run pytest -q`が全件PASSすることを確認してからコミットする
- コミットメッセージ・コードコメントは日本語

---

## 事前準備：ファイル構成の確認

このタスクでは既存の`src/jamoraiko_agent/main.py`のみを編集する（新規ファイル作成なし）。編集箇所は3つのセクションに分かれる：

1. `ATTACKERS`テーブル定義の直後（141行目付近）に`PokemonLine`/`POKEMON_LINES`を追加
2. `_score_play_option`関数の直後（354行目付近）に新セクション「CARDオプションのスコアリング」を追加し、`_score_setup_active`/`_is_attack_ready`/`_score_switch_target`/`_score_search_candidate`/`_score_discard_candidate`/`_score_card_option`を実装
3. `_score_option`関数（357行目付近）の`match o.type:`に`case OptionType.CARD:`を追加

テストは全て`tests/test_jamoraiko_agent.py`に追加する（新規テストファイルは作らない。既存ファイルの末尾に新しいテストクラスを追記していく）。

---

### Task 1: PokemonLineテーブル + SETUP_ACTIVE_POKEMONスコアリング

**Files:**
- Modify: `src/jamoraiko_agent/main.py`（ATTACKERSテーブル直後に挿入）
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Produces: `PokemonLine`（frozen dataclass、フィールド`id: int`, `pre_evo_id: int | None`, `max_field_copies: int`, `setup_active_priority: int`）、`POKEMON_LINES: dict[int, PokemonLine]`、`_score_setup_active(card_id: int) -> int`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_jamoraiko_agent.py`の末尾に追記：

```python
class TestScoreSetupActive:
    def test_voltorb_outranks_raging_bolt_ex(self):
        assert jm._score_setup_active(jm.Iono_Voltorb) > jm._score_setup_active(jm.Raging_Bolt_ex)

    def test_raging_bolt_ex_outranks_tadbulb(self):
        assert jm._score_setup_active(jm.Raging_Bolt_ex) > jm._score_setup_active(jm.Iono_Tadbulb)

    def test_unknown_card_defaults_to_zero(self):
        assert jm._score_setup_active(999999) == 0
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestScoreSetupActive -v`
Expected: FAIL（`AttributeError: module 'jamoraiko_agent.main' has no attribute '_score_setup_active'`）

- [ ] **Step 3: 最小実装を書く**

`src/jamoraiko_agent/main.py`の`ATTACKERS: list[Attacker] = [...]`の閉じ`]`の直後（142行目付近、`# ==================== 攻撃プラン計算 ====================`の直前）に挿入：

```python
# ==================== ポケモンライン優先度テーブル ====================
@dataclass(frozen=True)
class PokemonLine:
    id: int
    pre_evo_id: "int | None" = None   # 進化前のID（自身が進化ポケモンの場合）
    max_field_copies: int = 1         # 場+手札に置きたい上限（これ以上のサーチ優先度は下げる）
    setup_active_priority: int = 0    # 初期アクティブ選択時の基礎優先度


POKEMON_LINES: dict[int, PokemonLine] = {
    Iono_Voltorb:      PokemonLine(id=Iono_Voltorb, max_field_copies=2, setup_active_priority=300),
    Iono_Tadbulb:      PokemonLine(id=Iono_Tadbulb, max_field_copies=1, setup_active_priority=50),
    Iono_Bellibolt_ex: PokemonLine(id=Iono_Bellibolt_ex, pre_evo_id=Iono_Tadbulb, max_field_copies=1),
    Iono_Wattrel:      PokemonLine(id=Iono_Wattrel, max_field_copies=1, setup_active_priority=50),
    Iono_Kilowattrel:  PokemonLine(id=Iono_Kilowattrel, pre_evo_id=Iono_Wattrel, max_field_copies=1),
    Raging_Bolt_ex:    PokemonLine(id=Raging_Bolt_ex, max_field_copies=1, setup_active_priority=200),
}
```

`_score_play_option`関数（354行目付近、`return 1000`の直後）の直後に新セクションを追加：

```python
# ==================== CARDオプションのスコアリング ====================
def _score_setup_active(card_id: int) -> int:
    """OptionType.CARD / SelectContext.SETUP_ACTIVE_POKEMON のスコアを返す"""
    line = POKEMON_LINES.get(card_id)
    return line.setup_active_priority if line else 0
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestScoreSetupActive -v`
Expected: PASS（3件）

- [ ] **Step 5: 全体回帰確認**

Run: `uv run pytest -q`
Expected: 既存の全テストが引き続きPASS（新規3件追加）

- [ ] **Step 6: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "feat: PokemonLineテーブルとSETUP_ACTIVE_POKEMONスコアリングを追加"
```

---

### Task 2: SWITCH/TO_ACTIVEスコアリング

**Files:**
- Modify: `src/jamoraiko_agent/main.py`（Task 1で追加した「CARDオプションのスコアリング」セクションに追記）
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: `ATTACKERS`（既存、`main.py`定義済み）、`AttackPlan`（既存dataclass、フィールド`attacker_id: int`, `attack_id: int`, `damage: int`, `is_lethal: bool`）
- Produces: `_is_attack_ready(card_id: int, energy_count: int, fighting_count: int) -> bool`、`_score_switch_target(card, o, my_index: int, plan: AttackPlan) -> int`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_jamoraiko_agent.py`の末尾に追記：

```python
class TestIsAttackReady:
    def test_voltorb_ready_with_2_energy(self):
        assert jm._is_attack_ready(jm.Iono_Voltorb, energy_count=2, fighting_count=0) is True

    def test_voltorb_not_ready_with_1_energy(self):
        assert jm._is_attack_ready(jm.Iono_Voltorb, energy_count=1, fighting_count=0) is False

    def test_raging_bolt_ex_not_ready_without_fighting_energy(self):
        # きょくらいごうは闘エネ必須。はじけるほうこうはis_utilityのため候補から除外される
        assert jm._is_attack_ready(jm.Raging_Bolt_ex, energy_count=2, fighting_count=0) is False

    def test_raging_bolt_ex_ready_with_fighting_energy(self):
        assert jm._is_attack_ready(jm.Raging_Bolt_ex, energy_count=2, fighting_count=1) is True

    def test_unknown_card_is_never_ready(self):
        assert jm._is_attack_ready(999999, energy_count=10, fighting_count=10) is False


class TestScoreSwitchTarget:
    def test_opponent_bench_lethal_gets_large_bonus(self):
        from cg.api import Option

        target = make_pokemon(id=999, hp=50)
        o = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=1)
        plan = jm.AttackPlan(attacker_id=jm.Iono_Voltorb, attack_id=1001, damage=60, is_lethal=False)
        score = jm._score_switch_target(target, o, my_index=0, plan=plan)
        # スコアは -hp + 100000（このケースでは99950）。HPは最大でも数百程度なので
        # 90000以上であれば確実に確定KOボーナス分岐が適用されたことを検証できる
        assert score >= 90000

    def test_opponent_bench_prefers_lower_hp_when_not_lethal(self):
        from cg.api import Option

        low_hp = make_pokemon(id=999, hp=50)
        high_hp = make_pokemon(id=999, hp=200)
        o = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=1)
        plan = jm.AttackPlan(attacker_id=jm.Iono_Voltorb, attack_id=1001, damage=10, is_lethal=False)
        score_low = jm._score_switch_target(low_hp, o, my_index=0, plan=plan)
        score_high = jm._score_switch_target(high_hp, o, my_index=0, plan=plan)
        assert score_low > score_high

    def test_own_pokemon_ready_to_attack_outranks_not_ready(self):
        from cg.api import Option

        ready = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])       # 2エネ=攻撃可能
        not_ready = make_pokemon(id=jm.Iono_Voltorb, energies=[4])      # 1エネ=攻撃不可
        o = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        plan = jm.AttackPlan()
        score_ready = jm._score_switch_target(ready, o, my_index=0, plan=plan)
        score_not_ready = jm._score_switch_target(not_ready, o, my_index=0, plan=plan)
        assert score_ready > score_not_ready
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestIsAttackReady tests/test_jamoraiko_agent.py::TestScoreSwitchTarget -v`
Expected: FAIL（`_is_attack_ready`/`_score_switch_target`が未定義）

- [ ] **Step 3: 最小実装を書く**

`src/jamoraiko_agent/main.py`の「CARDオプションのスコアリング」セクション、`_score_setup_active`関数の直後に追記：

```python
def _is_attack_ready(card_id: int, energy_count: int, fighting_count: int) -> bool:
    """このポケモンが今すぐ攻撃可能な技を持つか（ATTACKERSテーブルの再利用）"""
    for atk in ATTACKERS:
        if atk.id != card_id or atk.is_utility:
            continue
        if energy_count < atk.energy_required:
            continue
        if atk.requires_fighting and fighting_count < 1:
            continue
        return True
    return False


def _score_switch_target(card, o, my_index: int, plan: AttackPlan) -> int:
    """OptionType.CARD / SelectContext.SWITCH・TO_ACTIVE のスコアを返す"""
    if o.playerIndex != my_index:
        # ボスの指令：現在の攻撃プラン(plan.damage)で確定KOできるベンチを最優先、次に低HP
        score = -card.hp
        if plan.attacker_id != -1 and plan.damage >= card.hp:
            score += 100000
        return score
    # 自分の交代先／強制昇格先
    energy_count = len(card.energies)
    fighting_count = card.energies.count(EnergyType.FIGHTING)
    score = energy_count * 10
    if _is_attack_ready(card.id, energy_count, fighting_count):
        score += 5000
    return score
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestIsAttackReady tests/test_jamoraiko_agent.py::TestScoreSwitchTarget -v`
Expected: PASS（8件）

- [ ] **Step 5: 全体回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "feat: SWITCH/TO_ACTIVEスコアリング(_is_attack_ready/_score_switch_target)を追加"
```

---

### Task 3: TO_HAND/TO_BENCHスコアリング

**Files:**
- Modify: `src/jamoraiko_agent/main.py`（「CARDオプションのスコアリング」セクションに追記）
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: `FieldState`（既存dataclass、`field_counts`/`hand_counts`はどちらも`defaultdict(int)`）、`POKEMON_LINES`（Task 1）
- Produces: `_score_search_candidate(card_id: int, fs: FieldState) -> int`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_jamoraiko_agent.py`の末尾に追記：

```python
class TestScoreSearchCandidate:
    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            own_board_basic_energy_total=0, active_energy_count=0,
            active_fighting_energy_count=0,
        )
        base.update(overrides)
        return jm.FieldState(**base)

    def test_pokemon_below_cap_scores_positive(self):
        fs = self._fs()
        assert jm._score_search_candidate(jm.Iono_Voltorb, fs) > 0

    def test_pokemon_at_cap_is_deprioritised(self):
        fs = self._fs(field_counts=defaultdict(int, {jm.Iono_Voltorb: 2}))
        assert jm._score_search_candidate(jm.Iono_Voltorb, fs) < 0

    def test_evolution_deprioritised_when_pre_evo_absent(self):
        fs_no_pre_evo = self._fs()
        fs_with_pre_evo = self._fs(field_counts=defaultdict(int, {jm.Iono_Tadbulb: 1}))
        score_absent = jm._score_search_candidate(jm.Iono_Bellibolt_ex, fs_no_pre_evo)
        score_present = jm._score_search_candidate(jm.Iono_Bellibolt_ex, fs_with_pre_evo)
        assert score_present > score_absent

    def test_lightning_energy_has_base_priority(self):
        fs = self._fs()
        assert jm._score_search_candidate(jm.Basic_Lightning_Energy, fs) == 150

    def test_fighting_energy_prioritised_when_raging_bolt_ex_needs_it(self):
        fs_needs = self._fs(
            field_counts=defaultdict(int, {jm.Raging_Bolt_ex: 1}),
            active_fighting_energy_count=0,
        )
        fs_not_needed = self._fs()
        score_needs = jm._score_search_candidate(jm.Basic_Fighting_Energy, fs_needs)
        score_not_needed = jm._score_search_candidate(jm.Basic_Fighting_Energy, fs_not_needed)
        assert score_needs > score_not_needed

    def test_unknown_card_defaults_to_zero(self):
        fs = self._fs()
        assert jm._score_search_candidate(999999, fs) == 0
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestScoreSearchCandidate -v`
Expected: FAIL（`_score_search_candidate`が未定義）

- [ ] **Step 3: 最小実装を書く**

`src/jamoraiko_agent/main.py`の「CARDオプションのスコアリング」セクション、`_score_switch_target`関数の直後に追記：

```python
def _score_search_candidate(card_id: int, fs: FieldState) -> int:
    """OptionType.CARD / SelectContext.TO_HAND・TO_BENCH のスコアを返す"""
    line = POKEMON_LINES.get(card_id)
    if line is not None:
        owned = fs.field_counts[card_id] + fs.hand_counts[card_id]
        if owned >= line.max_field_copies:
            return -1000  # もう十分
        score = 300
        if line.pre_evo_id is not None and fs.field_counts[line.pre_evo_id] == 0:
            score -= 200  # 進化前が場にいないなら優先度を下げる
        return score
    if card_id == Basic_Lightning_Energy:
        return 150
    if card_id == Basic_Fighting_Energy:
        raging_needs_fighting = (
            fs.field_counts[Raging_Bolt_ex] > 0
            and fs.active_fighting_energy_count < 1
        )
        return 180 if raging_needs_fighting else 20
    return 0
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestScoreSearchCandidate -v`
Expected: PASS（6件）

- [ ] **Step 5: 全体回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "feat: TO_HAND/TO_BENCHスコアリング(_score_search_candidate)を追加"
```

---

### Task 4: DISCARDスコアリング

**Files:**
- Modify: `src/jamoraiko_agent/main.py`（「CARDオプションのスコアリング」セクションに追記）
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: `FieldState`、`POKEMON_LINES`（Task 1）
- Produces: `_score_discard_candidate(card_id: int, fs: FieldState) -> int`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_jamoraiko_agent.py`の末尾に追記：

```python
class TestScoreDiscardCandidate:
    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            own_board_basic_energy_total=0, active_energy_count=0,
            active_fighting_energy_count=0,
        )
        base.update(overrides)
        return jm.FieldState(**base)

    def test_surplus_pokemon_is_safe_to_discard(self):
        fs = self._fs(hand_counts=defaultdict(int, {jm.Iono_Voltorb: 3}))  # 上限2を超過
        assert jm._score_discard_candidate(jm.Iono_Voltorb, fs) > 0

    def test_needed_pokemon_is_protected(self):
        fs = self._fs()
        assert jm._score_discard_candidate(jm.Iono_Voltorb, fs) < 0

    def test_key_supporter_is_protected(self):
        fs = self._fs()
        assert jm._score_discard_candidate(jm.Boss_Orders, fs) < 0

    def test_fighting_energy_is_protected(self):
        fs = self._fs()
        assert jm._score_discard_candidate(jm.Basic_Fighting_Energy, fs) < 0

    def test_surplus_lightning_energy_is_safe_to_discard(self):
        fs = self._fs(hand_counts=defaultdict(int, {jm.Basic_Lightning_Energy: 3}))
        assert jm._score_discard_candidate(jm.Basic_Lightning_Energy, fs) > 0

    def test_generic_card_gets_small_positive_score(self):
        fs = self._fs()
        assert jm._score_discard_candidate(999999, fs) == 10
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestScoreDiscardCandidate -v`
Expected: FAIL（`_score_discard_candidate`が未定義）

- [ ] **Step 3: 最小実装を書く**

`src/jamoraiko_agent/main.py`の「CARDオプションのスコアリング」セクション、`_score_search_candidate`関数の直後に追記：

```python
def _score_discard_candidate(card_id: int, fs: FieldState) -> int:
    """OptionType.CARD / SelectContext.DISCARD のスコアを返す"""
    line = POKEMON_LINES.get(card_id)
    if line is not None:
        owned = fs.field_counts[card_id] + fs.hand_counts[card_id]
        return 50 if owned > line.max_field_copies else -300
    if card_id == Basic_Lightning_Energy:
        return 30 if fs.hand_counts[Basic_Lightning_Energy] >= 3 else -50
    if card_id == Basic_Fighting_Energy:
        return -100  # 希少なので温存
    if card_id in (Boss_Orders, Lillie_Determination, Max_Rod):
        return -200  # キーカード・ACE SPECは温存
    return 10
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestScoreDiscardCandidate -v`
Expected: PASS（6件）

- [ ] **Step 5: 全体回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "feat: DISCARDスコアリング(_score_discard_candidate)を追加"
```

---

### Task 5: _score_card_optionディスパッチャの新設 + _score_optionへの統合

**Files:**
- Modify: `src/jamoraiko_agent/main.py`（「CARDオプションのスコアリング」セクション末尾に`_score_card_option`を追加、`_score_option`の`match`文を変更）
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: Task 1〜4の全関数（`_score_setup_active`/`_score_switch_target`/`_score_search_candidate`/`_score_discard_candidate`）、`get_card`（既存）
- Produces: `_score_card_option(obs, o, context, my_index: int, fs: FieldState, plan: AttackPlan) -> int`。`_score_option`が`OptionType.CARD`をこの関数にディスパッチするようになる

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_jamoraiko_agent.py`の末尾に追記：

```python
class TestScoreCardOptionDispatch:
    def test_dispatches_setup_active_pokemon(self):
        from cg.api import Option, SelectContext

        voltorb = make_pokemon(id=jm.Iono_Voltorb)
        my_state = make_player_state(hand=[voltorb], deck_count=40, prize_count=6)
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.CARD, area=AreaType.HAND, index=0, playerIndex=0)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_card_option(obs, o, SelectContext.SETUP_ACTIVE_POKEMON, my_index=0, fs=fs, plan=plan)
        assert score == jm._score_setup_active(jm.Iono_Voltorb)

    def test_dispatches_switch_context(self):
        from cg.api import Option, SelectContext

        target = make_pokemon(id=999, hp=50)
        op_state = make_player_state(active_pokemon=None, bench=[target])
        obs = MagicMock()
        obs.current.players = [make_player_state(), op_state]
        o = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=1)
        fs = jm._collect_field_state(make_player_state())
        plan = jm.AttackPlan(attacker_id=jm.Iono_Voltorb, attack_id=1001, damage=60, is_lethal=False)
        score = jm._score_card_option(obs, o, SelectContext.SWITCH, my_index=0, fs=fs, plan=plan)
        assert score == jm._score_switch_target(target, o, my_index=0, plan=plan)

    def test_dispatches_to_hand_and_to_bench_identically(self):
        from cg.api import Option, SelectContext

        voltorb = make_pokemon(id=jm.Iono_Voltorb)
        my_state = make_player_state(deck_count=40, prize_count=6)
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.CARD, area=AreaType.DECK, index=0, playerIndex=0)
        obs.select.deck = [voltorb]
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score_hand = jm._score_card_option(obs, o, SelectContext.TO_HAND, my_index=0, fs=fs, plan=plan)
        score_bench = jm._score_card_option(obs, o, SelectContext.TO_BENCH, my_index=0, fs=fs, plan=plan)
        assert score_hand == score_bench == jm._score_search_candidate(jm.Iono_Voltorb, fs)

    def test_returns_zero_when_card_is_none(self):
        from cg.api import Option, SelectContext

        my_state = make_player_state()
        my_state.active = [None]
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.CARD, area=AreaType.ACTIVE, index=0, playerIndex=0)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_card_option(obs, o, SelectContext.SWITCH, my_index=0, fs=fs, plan=plan)
        assert score == 0

    def test_score_option_routes_card_type_through_dispatcher(self, mock_card_table):
        from cg.api import Option, SelectContext

        voltorb = make_pokemon(id=jm.Iono_Voltorb)
        my_state = make_player_state(hand=[voltorb], deck_count=40, prize_count=6)
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.CARD, area=AreaType.HAND, index=0, playerIndex=0)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_option(
            obs, o, SelectContext.SETUP_ACTIVE_POKEMON, my_index=0,
            state=None, my_state=my_state, fs=fs, plan=plan,
        )
        assert score == jm._score_setup_active(jm.Iono_Voltorb)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestScoreCardOptionDispatch -v`
Expected: FAIL（`_score_card_option`が未定義。最後のテストは`_score_option`が`OptionType.CARD`で`0`を返し`_score_setup_active`の値と不一致でFAIL）

- [ ] **Step 3: 最小実装を書く**

`src/jamoraiko_agent/main.py`の「CARDオプションのスコアリング」セクション、`_score_discard_candidate`関数の直後に追記：

```python
def _score_card_option(obs, o, context, my_index: int, fs: FieldState, plan: AttackPlan) -> int:
    """OptionType.CARD のスコアをコンテキスト別に返す"""
    card = get_card(obs, o.area, o.index, o.playerIndex)
    if card is None:
        return 0
    match context:
        case SelectContext.SETUP_ACTIVE_POKEMON:
            return _score_setup_active(card.id)
        case SelectContext.SWITCH | SelectContext.TO_ACTIVE:
            return _score_switch_target(card, o, my_index, plan)
        case SelectContext.TO_HAND | SelectContext.TO_BENCH:
            return _score_search_candidate(card.id, fs)
        case SelectContext.DISCARD:
            return _score_discard_candidate(card.id, fs)
        case _:
            return 0
```

`_score_option`関数（357行目付近）の`match o.type:`ブロックを次のように変更（`case OptionType.YES:`の直後に`case OptionType.CARD:`を追加）：

```python
    match o.type:
        case OptionType.NUMBER:
            return o.number
        case OptionType.YES:
            return 1
        case OptionType.CARD:
            return _score_card_option(obs, o, context, my_index, fs, plan)
        case OptionType.PLAY:
            return _score_play_option(obs, o, my_index, fs, my_state, plan)
        case OptionType.ATTACH:
            return _score_attach_option(obs, o, my_index)
        case OptionType.EVOLVE:
            return 9000
        case OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if card.id == Iono_Bellibolt_ex:
                return 9500  # エレキストリーマーは常に高優先
            if card.id == Iono_Kilowattrel:
                consumption = _flashing_draw_consumption(my_state, fs.hand_counts)
                return 8000 if consumption <= _safe_draws(my_state) else -1
            return -1
        case OptionType.RETREAT:
            return -1
        case OptionType.ATTACK:
            return 10000 if o.attackId == plan.attack_id else 100
        case _:
            return 0
```

（`NUMBER`/`YES`/`PLAY`以降/`ATTACH`〜`ATTACK`/`case _:`は既存コードのまま。変更点は`case OptionType.CARD:`の1ブロック追加のみ）

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestScoreCardOptionDispatch -v`
Expected: PASS（5件）

- [ ] **Step 5: 全体回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "feat: _score_card_optionディスパッチャを新設し_score_optionのOptionType.CARDを実装"
```

---

### Task 6: 校正ノートブック再ビルド・実装サマリー作成

**Files:**
- Modify: `src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`（ビルドスクリプト実行で再生成、gitignore対象のためコミット不要）
- Create: `docs/implementations/20260713-jamoraiko-card-option-scoring.md`

**Interfaces:**
- Consumes: Task 1〜5で完成した`src/jamoraiko_agent/main.py`、既存の`scripts/build_jamoraiko_vs_iono_notebook.py`

- [ ] **Step 1: リポジトリ全体のテストを実行**

Run: `uv run pytest -q`
Expected: 全件PASS（Task 1〜5で追加した28件のテストを含む）

- [ ] **Step 2: 校正ノートブックを再ビルド**

Run: `uv run python scripts/build_jamoraiko_vs_iono_notebook.py`
Expected: `src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`が今回のmain.py全文（`OptionType.CARD`実装込み）で再生成される旨のログが出力される

- [ ] **Step 3: 再ビルドされたノートブックにOptionType.CARD実装が反映されていることを確認**

Run:
```bash
uv run python -c "
import json
nb = json.load(open('src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb'))
src = ''.join(nb['cells'][0]['source'])
assert 'POKEMON_LINES' in src
assert '_score_card_option' in src
assert 'case OptionType.CARD:' in src
print('OK: main.py embedded with CARD scoring')
"
```
Expected: `OK: main.py embedded with CARD scoring`が出力される

- [ ] **Step 4: 実装サマリーを作成**

`docs/implementations/20260713-jamoraiko-card-option-scoring.md`を作成：

```markdown
# ジャモライコ OptionType.CARD スコアリング追加 実装サマリー

- 日付: 2026-07-13
- 設計書: `docs/superpowers/specs/2026-07-13-jamoraiko-card-option-scoring-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-13-jamoraiko-card-option-scoring.md`

## 背景

校正実験（`jamoraiko_vs_iono_experiment.ipynb`、200試合）でジャモライコの勝率が0.015という
壊滅的な結果になった。原因は`src/jamoraiko_agent/main.py`の`_score_option`に
`OptionType.CARD`のケースが一つも実装されておらず、`SETUP_ACTIVE_POKEMON`/`SWITCH`/
`TO_ACTIVE`/`TO_HAND`/`TO_BENCH`/`DISCARD`という多くの重要な意思決定が全て
「エンジンが提示した順番の先頭を機械的に選ぶだけ」になっていたこと。

## 実装内容

データ駆動型（`POKEMON_LINES`テーブル）で6コンテキスト分のスコアリングを新規実装：

- `PokemonLine`/`POKEMON_LINES`：ポケモンごとの優先度データ（進化前ID・場に置きたい上限・
  初期アクティブ優先度）
- `_score_setup_active`：初期アクティブ選択（ビリリダマ＞タケルライコex＞ズピカ/カイデン）
- `_is_attack_ready`/`_score_switch_target`：交代先選択（自分側は攻撃可能なポケモンを優先、
  相手側＝ボスの指令は現在の攻撃プランで確定KOできるベンチを最優先）
- `_score_search_candidate`：TO_HAND/TO_BENCH共通のサーチ優先度（上限超過は減点、
  進化ポケモンは進化前不在なら減点）
- `_score_discard_candidate`：DISCARD（ハイパーボール・カナリィのコスト）。余剰札は気軽に
  切り、キーカード・ACE SPECは温存
- `_score_card_option`：上記をコンテキストで振り分けるディスパッチャ。`_score_option`の
  `match`文に`case OptionType.CARD:`を追加して接続

## テスト

`tests/test_jamoraiko_agent.py`に28件のテストクラス（`TestScoreSetupActive`/
`TestIsAttackReady`/`TestScoreSwitchTarget`/`TestScoreSearchCandidate`/
`TestScoreDiscardCandidate`/`TestScoreCardOptionDispatch`）を追加。
リポジトリ全体`uv run pytest -q`で全件PASS。

## 未検証（次回以降）

- `POKEMON_LINES`の優先度の具体的な数値（300/200/150/180等）は初期値であり、微調整の余地がある
- 校正ノートブックの再実行はユーザーがKaggle上で実施し、勝率が0.015からどこまで改善したかを確認する
```

- [ ] **Step 5: 実装サマリーをコミット**

```bash
git add docs/implementations/20260713-jamoraiko-card-option-scoring.md
git commit -m "docs: ジャモライコOptionType.CARDスコアリング追加の実装サマリーを追加"
```

---

## 完了条件

- [ ] Task 1〜6すべて完了
- [ ] `uv run pytest -q`がリポジトリ全体で全件PASS
- [ ] `src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`が最新のmain.pyで再生成済み
- [ ] `docs/implementations/20260713-jamoraiko-card-option-scoring.md`作成済み
- [ ] ユーザーへの申し送り：校正ノートブックをKaggleで再実行し、勝率の改善を確認してもらう必要がある（本計画のスコープ外、次のステップ）
