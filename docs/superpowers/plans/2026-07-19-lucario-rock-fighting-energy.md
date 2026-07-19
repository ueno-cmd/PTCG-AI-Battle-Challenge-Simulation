# ルカリオexデッキ ロック闘エネルギー導入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ルカリオexデッキにロック闘エネルギー（ID20）を4枚導入し、Alakazam系デッキの技「ハンドパワー」（効果ベースの一撃必殺技）を無効化できるようにする。あわせて、エージェントロジックに潜在していた「闘エネルギーを基本闘エネルギー(ID6)のみで判定している」バグ2件を修正する。

**Architecture:** `decks/lucario_20260621.py`のエネルギー構成を変更し、`src/lucario_agent/main.py`の5箇所（ATTACH優先度・calc_attack_plan先読み・JudgePolicy・DISCARD保護・TO_HAND優先度）に最小限の分岐を追加する。既存のif/elifスタイルを踏襲し、新しい抽象化は導入しない。

**Tech Stack:** Python 3.12 / uv / pytest。設計書: `docs/superpowers/specs/2026-07-19-lucario-rock-fighting-energy-design.md`

## Global Constraints

- ワークスペース分離はgit worktreeでなくfeatureブランチを使う（`feature/lucario-rock-fighting-energy`、mainから分岐）
- デッキ合計は60枚を維持する
- 「基本」限定のカード効果（はどうづき・ルナサイクル）の判定は変更しない（設計書で変更不要と確認済み）
- 各タスック末尾で`uv run pytest -q`を実行し、全件PASSしてからコミットする
- コミットメッセージは日本語、`Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`を含める

---

## 事前準備: featureブランチ作成

- [ ] **Step 1: featureブランチを作成してチェックアウト**

```bash
git checkout -b feature/lucario-rock-fighting-energy
```

Expected: `Switched to a new branch 'feature/lucario-rock-fighting-energy'`

---

### Task 1: 定数追加・デッキ変更・テストスキャフォールディング

**Files:**
- Modify: `src/lucario_agent/main.py:24`
- Modify: `decks/lucario_20260621.py:24`
- Modify: `tests/test_lucario_deck.py:38-40`
- Modify: `tests/test_lucario_agent.py:29-58`（`mock_card_table`フィクスチャ）

**Interfaces:**
- Consumes: なし（最初のタスク）
- Produces: `lm.Rock_Fighting_Energy`（int定数、値20）。以降の全タスクがこれを参照する。`mock_card_table`フィクスチャに`lm.Rock_Fighting_Energy`のエントリが追加され、以降のテストで`CardType.SPECIAL_ENERGY`として参照可能になる

- [ ] **Step 1: `test_energy_count`を新しい枚数を期待する形に書き換える（Red）**

`tests/test_lucario_deck.py`の`test_energy_count`（38-40行目）を以下に置き換える：

```python
def test_energy_count():
    basic = sum(c for i, c in DECK if i == 6)
    rock = sum(c for i, c in DECK if i == 20)
    assert basic == 7
    assert rock == 4
    assert basic + rock == 11
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_lucario_deck.py::test_energy_count -v
```

Expected: FAIL（現行デッキは基本闘エネルギー11枚・ロック闘エネルギー0枚のため、`assert basic == 7`が失敗する）

- [ ] **Step 3: デッキ変更（Green）**

`decks/lucario_20260621.py`の以下の行を変更する。

変更前（24行目）:
```python
    (6, 11),     # Basic {F} Energy
```

変更後:
```python
    (6, 7),      # Basic {F} Energy
    (20, 4),     # Rock {F} Energy（Alakazam「ハンドパワー」対策。闘エネルギー1個分＋相手の技の効果を無効化）
```

- [ ] **Step 4: テストを実行して成功を確認**

```bash
uv run pytest tests/test_lucario_deck.py -v
```

Expected: 全件PASS（`test_deck_has_60_cards`も引き続きPASSすること＝60枚維持の確認）

- [ ] **Step 5: `main.py`に定数を追加（後続タスクのためのスキャフォールディング）**

`src/lucario_agent/main.py`の24行目（`Basic_Fighting_Energy = 6`の直後）に以下を追加：

```python
Basic_Fighting_Energy = 6
Rock_Fighting_Energy  = 20  # ロック闘エネルギー：装着ポケモンは相手の技の"効果"を受けない（Alakazam「ハンドパワー」対策）
```

- [ ] **Step 6: `mock_card_table`フィクスチャにエントリを追加（後続タスクのためのスキャフォールディング）**

`tests/test_lucario_agent.py`の10行目付近、`12:   _card(12,   cardType=CardType.SPECIAL_ENERGY),  # Legacy Energy`の直後に追加：

```python
        12:   _card(12,   cardType=CardType.SPECIAL_ENERGY),  # Legacy Energy
        lm.Rock_Fighting_Energy: _card(lm.Rock_Fighting_Energy, cardType=CardType.SPECIAL_ENERGY),  # ロック闘エネルギー
```

- [ ] **Step 7: リポジトリ全体を実行して回帰がないことを確認**

```bash
uv run pytest -q
```

Expected: 全件PASS（既存517件＋今回の変更で失敗が出ないこと。Step5・6は既存テストの挙動を変えないスキャフォールディングのため、新規の失敗は発生しない想定）

- [ ] **Step 8: コミット**

```bash
git add src/lucario_agent/main.py decks/lucario_20260621.py tests/test_lucario_deck.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
feat(lucario): ロック闘エネルギー4枚を導入（基本闘エネルギー11→7枚）

Alakazam「ハンドパワー」（効果ベースの一撃必殺技）対策の第一段階として、
デッキにロック闘エネルギーを追加。エージェントロジック側の対応は後続タスクで行う。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: ATTACH優先度 — ロック闘エネルギーをアクティブへ優先装着

**Files:**
- Modify: `src/lucario_agent/main.py:644-663`（`_score_attach_option`）
- Test: `tests/test_lucario_agent.py`（新規テストクラス`TestAttachRockFightingEnergyPriority`を追加）

**Interfaces:**
- Consumes: `lm.Rock_Fighting_Energy`（Task 1で追加済み）、`lm._score_attach_option(obs, o, my_index, current_plan, attacker1) -> int`（既存関数、シグネチャ変更なし）
- Produces: `_score_attach_option`がロック闘エネルギー×アクティブ装着の組み合わせで既存より高いスコアを返すようになる。後続タスクはこれに依存しない

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`TestNewCardScoring`クラスの直前（1089行目付近）に以下を追加：

```python
class TestAttachRockFightingEnergyPriority:
    """ロック闘エネルギーは、アクティブのポケモンへの装着時に基本闘エネルギーより優先される
    （Alakazam「ハンドパワー」はアクティブのポケモンのみを狙う技のため）"""

    def _score(self, card_id, in_play_area):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[])
        my_ps = make_player_state(
            active_pokemon=lucario,
            bench=[lucario] if in_play_area == lm.AreaType.BENCH else [],
            hand=[Card(id=card_id, serial=1, playerIndex=0)],
        )
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        option = Option(
            type=OptionType.ATTACH, index=0,
            inPlayArea=in_play_area, inPlayIndex=0,
        )
        return lm._score_attach_option(
            obs, option, my_index=0, current_plan=lm.AttackPlan(), attacker1=False,
        )

    def test_rock_energy_scores_higher_than_basic_on_active(self):
        rock  = self._score(lm.Rock_Fighting_Energy, lm.AreaType.ACTIVE)
        basic = self._score(lm.Basic_Fighting_Energy, lm.AreaType.ACTIVE)
        assert rock > basic

    def test_rock_energy_has_no_bonus_on_bench(self):
        """ベンチへの装着では基本闘エネルギーと同スコア（アクティブ限定のボーナスのため）"""
        rock  = self._score(lm.Rock_Fighting_Energy, lm.AreaType.BENCH)
        basic = self._score(lm.Basic_Fighting_Energy, lm.AreaType.BENCH)
        assert rock == basic
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestAttachRockFightingEnergyPriority -v
```

Expected: `test_rock_energy_scores_higher_than_basic_on_active`がFAIL（`rock == basic`で不等号を満たさない）

- [ ] **Step 3: `_score_attach_option`に分岐を追加**

`src/lucario_agent/main.py`の`_score_attach_option`（644-663行目）を以下に置き換える：

```python
def _score_attach_option(obs, o, my_index, current_plan, attacker1) -> int:
    """OptionType.ATTACH のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    if card.id == Hero_Cape:
        pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
        score = 7000
        if pokemon.id == Riolu:
            score += 100
        elif pokemon.id == Mega_Lucario_ex:
            score += 200
        return score
    pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
    score = energy_score(pokemon, o.inPlayArea == AreaType.ACTIVE, attacker1)
    if card.id == Rock_Fighting_Energy and o.inPlayArea == AreaType.ACTIVE:
        # Alakazam「ハンドパワー」はアクティブのポケモンのみを狙うため、
        # そのときアクティブの子を優先的に守る
        score += 500
    if o.inPlayArea == AreaType.ACTIVE:
        if current_plan.attacker == 0 and current_plan.energy:
            score += 200
    else:
        if current_plan.attacker == 1 + o.inPlayIndex and current_plan.energy:
            score += 200
    return score
```

- [ ] **Step 4: テストを実行して成功を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestAttachRockFightingEnergyPriority -v
```

Expected: 2件ともPASS

- [ ] **Step 5: リポジトリ全体を実行して回帰がないことを確認**

```bash
uv run pytest -q
```

Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
feat(lucario): ロック闘エネルギーをアクティブのポケモンへ優先装着

Alakazam「ハンドパワー」はアクティブのポケモンのみを狙う技のため、
_score_attach_optionにアクティブ装着時のボーナスを追加し、
デッキに入れただけでは運任せだった装着先を制御可能にする。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `calc_attack_plan`の先読みを基本+ロックの合算判定に修正（潜在バグ修正）

**Files:**
- Modify: `src/lucario_agent/main.py:317-320`
- Test: `tests/test_lucario_agent.py`（`TestCalcAttackPlan`クラスに新規テスト追加）

**Interfaces:**
- Consumes: `lm.Rock_Fighting_Energy`（Task 1）、既存の`calc_attack_plan(...)`シグネチャ（変更なし）
- Produces: 手札にロック闘エネルギーのみ（基本闘エネルギー0枚）でも、1エネルギー不足の攻撃候補が正しく候補に残るようになる

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`test_ogerpon_ex_not_selected_with_insufficient_energy`（`TestCalcAttackPlan`クラス内）の直後に追加：

```python
    def test_ogerpon_ex_selected_when_only_rock_energy_in_hand(self):
        """手札に基本闘エネルギーが0枚でも、ロック闘エネルギーがあれば
        「あと1エネルギーで技が届く」候補として正しく評価される（潜在バグ修正）"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=ogerpon, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int, {lm.Rock_Fighting_Energy: 1}), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
        )
        assert result.attacker == 0
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestCalcAttackPlan::test_ogerpon_ex_selected_when_only_rock_energy_in_hand -v
```

Expected: FAIL（`result.attacker == -1`のまま）

- [ ] **Step 3: `calc_attack_plan`の判定を合算に修正**

`src/lucario_agent/main.py`の317-320行目を以下に置き換える：

変更前:
```python
            if energy_count < energy_required:
                can_attach_energy_this_turn = (
                    hand_counts[Basic_Fighting_Energy] >= 1 and not state.energyAttached
                )
```

変更後:
```python
            if energy_count < energy_required:
                can_attach_energy_this_turn = (
                    hand_counts[Basic_Fighting_Energy] + hand_counts[Rock_Fighting_Energy] >= 1
                    and not state.energyAttached
                )
```

- [ ] **Step 4: テストを実行して成功を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestCalcAttackPlan -v
```

Expected: 全件PASS（新規テストに加え、既存の`test_ogerpon_ex_not_selected_with_insufficient_energy`＝基本もロックも0枚のケースが引き続きPASSすること）

- [ ] **Step 5: リポジトリ全体を実行して回帰がないことを確認**

```bash
uv run pytest -q
```

Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
fix(lucario): calc_attack_planの先読みが基本闘エネルギーのみを見ていた潜在バグを修正

「あと1エネルギーで技が届くか」の判定がhand_counts[Basic_Fighting_Energy]
のみを参照しており、手札にロック闘エネルギーしか無い場合に攻撃候補を
誤って見落とす恐れがあった。基本+ロックの合算判定に修正。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `JudgePolicy`の自己都合トリガーを合算判定に修正（潜在バグ修正）

**Files:**
- Modify: `src/lucario_agent/main.py:579`
- Test: `tests/test_lucario_agent.py`（`TestNewCardScoring`クラスに新規テスト追加）

**Interfaces:**
- Consumes: `lm.Rock_Fighting_Energy`（Task 1）、`PlayScoringContext.hand_counts`（既存フィールド）
- Produces: 手札にロック闘エネルギーのみでも「エネルギー切れ」と誤判定してジャッジマンを不要に切らなくなる

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`test_judge_held_when_attacker_ready`（`TestNewCardScoring`クラス内）の直後に追加：

```python
    def test_judge_not_self_triggered_when_only_rock_energy_in_hand(self):
        """手札にロック闘エネルギーのみ（基本闘エネルギー0枚）でも
        「エネルギー切れ」と誤判定しない（潜在バグ修正）"""
        my_ps = make_player_state(hand=[Card(id=lm.Judge, serial=1, playerIndex=0)])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        score = lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=False,
            state=_make_state(), my_state=my_ps,
            hand_counts=defaultdict(int, {lm.Rock_Fighting_Energy: 1}),
            field_counts=defaultdict(int), stadium_id=0,
        )
        assert score == -1
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestNewCardScoring::test_judge_not_self_triggered_when_only_rock_energy_in_hand -v
```

Expected: FAIL（`score == 7000`のまま）

- [ ] **Step 3: `JudgePolicy.play_score`を合算判定に修正**

`src/lucario_agent/main.py`の579行目を以下に置き換える：

変更前:
```python
        return 7000 if ctx.hand_counts[Basic_Fighting_Energy] == 0 and not ctx.attacker1 else -1
```

変更後:
```python
        no_fighting_energy_in_hand = (
            ctx.hand_counts[Basic_Fighting_Energy] + ctx.hand_counts[Rock_Fighting_Energy] == 0
        )
        return 7000 if no_fighting_energy_in_hand and not ctx.attacker1 else -1
```

- [ ] **Step 4: テストを実行して成功を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestNewCardScoring -v
```

Expected: 全件PASS（新規テストに加え、既存の`test_judge_used_when_hand_is_dead`＝基本もロックも0枚のケースが引き続きPASSすること）

- [ ] **Step 5: リポジトリ全体を実行して回帰がないことを確認**

```bash
uv run pytest -q
```

Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
fix(lucario): JudgePolicyの自己都合トリガーが基本闘エネルギーのみを見ていた潜在バグを修正

「手札に闘エネルギーが1枚も無い」判定がhand_counts[Basic_Fighting_Energy]
のみを参照しており、ロック闘エネルギーを保持していても誤ってジャッジマンを
切ってしまう恐れがあった。基本+ロックの合算判定に修正。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: DISCARD保護 — ロック闘エネルギーを誤トラッシュから保護

**Files:**
- Modify: `src/lucario_agent/main.py:438-447`
- Test: `tests/test_lucario_agent.py`（`TestDiscardContext`クラスに新規テスト追加）

**Interfaces:**
- Consumes: `lm.Rock_Fighting_Energy`（Task 1）、`lm._score_card_option(...)`（既存関数、シグネチャ変更なし）
- Produces: ロック闘エネルギーがハイパーボール等の捨て札コストで、手札枚数によらず常に温存されるようになる

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`test_prefers_spare_fighting_energy`（`TestDiscardContext`クラス内）の直後に追加：

```python
    def test_protects_rock_fighting_energy_regardless_of_count(self):
        """ロック闘エネルギーは夜のタンカで回収不可・デッキ内4枚のみのため、
        手札枚数によらず常に温存する（基本闘エネルギーは2枚以上あれば捨てて良いのと対照的）"""
        energy = Card(id=lm.Rock_Fighting_Energy, serial=1, playerIndex=0)
        obs = self._obs(energy)
        score = lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int, {lm.Rock_Fighting_Energy: 3}),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )
        assert score == -20
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestDiscardContext::test_protects_rock_fighting_energy_regardless_of_count -v
```

Expected: FAIL（`score == 10`、デフォルトの捨てやすいスコアのまま）

- [ ] **Step 3: `SelectContext.DISCARD`分岐にロック闘エネルギー保護を追加**

`src/lucario_agent/main.py`の438-447行目を以下に置き換える：

変更前:
```python
        case SelectContext.DISCARD:
            if o.playerIndex != my_index:
                return 0
            if card.id == Basic_Fighting_Energy:
                return 50 if hand_counts[Basic_Fighting_Energy] >= 2 else -20
            if card.id in (Riolu, Mega_Lucario_ex, Solrock, Lunatone, Ogerpon_ex, Judge):
                return -100
            if card.id in (Boss_Orders, Lillie_Determination):
                return -50
            return 10
```

変更後:
```python
        case SelectContext.DISCARD:
            if o.playerIndex != my_index:
                return 0
            if card.id == Basic_Fighting_Energy:
                return 50 if hand_counts[Basic_Fighting_Energy] >= 2 else -20
            if card.id == Rock_Fighting_Energy:
                # 夜のタンカで回収不可・デッキ内4枚のみのため、手札枚数によらず常時温存
                return -20
            if card.id in (Riolu, Mega_Lucario_ex, Solrock, Lunatone, Ogerpon_ex, Judge):
                return -100
            if card.id in (Boss_Orders, Lillie_Determination):
                return -50
            return 10
```

- [ ] **Step 4: テストを実行して成功を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestDiscardContext -v
```

Expected: 全件PASS

- [ ] **Step 5: リポジトリ全体を実行して回帰がないことを確認**

```bash
uv run pytest -q
```

Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
fix(lucario): ロック闘エネルギーをDISCARD分岐で誤トラッシュから保護

夜のタンカでは基本エネルギーしか回収できず、ロック闘エネルギーは
一度捨てると恒久的に失う。デッキ内4枚のみの希少カードのため、
手札枚数によらず常に温存するよう保護を追加。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: TO_HAND優先度 — サーチ時にロック闘エネルギーを優先

**Files:**
- Modify: `src/lucario_agent/main.py:420-436`
- Test: `tests/test_lucario_agent.py`（`TestToHandContext`クラスに新規テスト追加）

**Interfaces:**
- Consumes: `lm.Rock_Fighting_Energy`（Task 1）、`lm._score_card_option(...)`（既存関数、シグネチャ変更なし）
- Produces: トウコ等のエネルギーサーチで、ロック闘エネルギーが基本闘エネルギーより優先して手札に加えられるようになる

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`TestToHandContext`クラス末尾（`test_deprioritized_when_both_copies_in_play`の直後）に追加：

```python
    def test_rock_energy_prioritized_over_basic_energy(self):
        """コスト機能は同等だが効果無効化のボーナスがあるため、
        基本闘エネルギーより優先してサーチする"""
        rock  = self._score(lm.Rock_Fighting_Energy)
        basic = self._score(lm.Basic_Fighting_Energy)
        assert rock > basic
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestToHandContext::test_rock_energy_prioritized_over_basic_energy -v
```

Expected: FAIL（`rock == basic`、どちらも同じ基準スコアのまま）

- [ ] **Step 3: `SelectContext.TO_HAND`分岐にロック闘エネルギー優先度を追加**

`src/lucario_agent/main.py`の420-436行目を以下に置き換える：

変更前:
```python
        case SelectContext.TO_HAND:
            score = 200 - hand_counts[card.id] * 100
            if card.id == Lunatone:
                score += -250 if field_counts[card.id] >= 1 else 60
            elif card.id == Solrock:
                score += -250 if field_counts[card.id] >= 1 else 50
            elif card.id == Riolu:
                total = field_counts[Riolu] + field_counts[Mega_Lucario_ex]
                score += -150 if total >= 2 else (-3 if total >= 1 else 40)
            elif card.id == Mega_Lucario_ex:
                score += 40 if field_counts[Riolu] >= 1 else -15
            elif card.id == Ogerpon_ex:
                # デッキ採用枚数(2枚)に対する充足度で優先度を調整（Riolu方式を踏襲）
                score += -150 if field_counts[Ogerpon_ex] >= 2 else (-3 if field_counts[Ogerpon_ex] >= 1 else 40)
            elif card.id == Basic_Fighting_Energy:
                score += 30 if not ability_used_flag or not state.energyAttached else -1
            return score
```

変更後:
```python
        case SelectContext.TO_HAND:
            score = 200 - hand_counts[card.id] * 100
            if card.id == Lunatone:
                score += -250 if field_counts[card.id] >= 1 else 60
            elif card.id == Solrock:
                score += -250 if field_counts[card.id] >= 1 else 50
            elif card.id == Riolu:
                total = field_counts[Riolu] + field_counts[Mega_Lucario_ex]
                score += -150 if total >= 2 else (-3 if total >= 1 else 40)
            elif card.id == Mega_Lucario_ex:
                score += 40 if field_counts[Riolu] >= 1 else -15
            elif card.id == Ogerpon_ex:
                # デッキ採用枚数(2枚)に対する充足度で優先度を調整（Riolu方式を踏襲）
                score += -150 if field_counts[Ogerpon_ex] >= 2 else (-3 if field_counts[Ogerpon_ex] >= 1 else 40)
            elif card.id == Basic_Fighting_Energy:
                score += 30 if not ability_used_flag or not state.energyAttached else -1
            elif card.id == Rock_Fighting_Energy:
                # コスト機能は基本闘エネルギーと同等＋効果無効化のボーナスがあるため優先
                score += 50
            return score
```

- [ ] **Step 4: テストを実行して成功を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestToHandContext -v
```

Expected: 全件PASS

- [ ] **Step 5: リポジトリ全体を実行して回帰がないことを確認**

```bash
uv run pytest -q
```

Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
feat(lucario): TO_HANDでロック闘エネルギーを基本闘エネルギーより優先サーチ

トウコ等のエネルギーサーチ時、コスト機能は同等かつ効果無効化の
ボーナスがあるロック闘エネルギーを優先して手札に加えるよう調整。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: 全体回帰確認・実装サマリー作成

**Files:**
- Create: `docs/implementations/20260719-lucario-rock-fighting-energy.md`

**Interfaces:**
- Consumes: Task 1〜6の全変更
- Produces: 実装サマリードキュメント（CLAUDE.mdフェーズ4の完了物）

- [ ] **Step 1: リポジトリ全体テストを実行**

```bash
uv run pytest -q
```

Expected: 全件PASS（Task1〜6で追加した新規テスト全件＋既存517件、回帰なし）

- [ ] **Step 2: 実装サマリーを作成**

`docs/implementations/20260719-lucario-rock-fighting-energy.md`に以下の内容で作成する：

```markdown
# ルカリオexデッキ ロック闘エネルギー導入 実装サマリー

- 日付: 2026-07-19
- 設計書: `docs/superpowers/specs/2026-07-19-lucario-rock-fighting-energy-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-19-lucario-rock-fighting-energy.md`

## 背景

直近20戦の実戦解析（`docs/analyses/20260719-lucario-post-fix-20-games-analysis.md`）で
Alakazam系デッキとの対戦成績が1勝3敗（25%）と判明。フーディンの技「ハンドパワー」
（効果ベースの一撃必殺技）への対策として、ユーザーが実際のジムバトル環境から
発見したロック闘エネルギーを導入した。

## 変更内容

- デッキ（`decks/lucario_20260621.py`）：基本闘エネルギー11→7枚、ロック闘エネルギー0→4枚（60枚維持）
- エージェントロジック（`src/lucario_agent/main.py`）5箇所：
  1. `_score_attach_option`：ロック闘エネルギーをアクティブのポケモンへ優先装着
  2. `calc_attack_plan`の先読み：基本+ロックの合算判定に修正（潜在バグ修正）
  3. `JudgePolicy`の自己都合トリガー：基本+ロックの合算判定に修正（潜在バグ修正）
  4. `SelectContext.DISCARD`：ロック闘エネルギーを常時温存
  5. `SelectContext.TO_HAND`：ロック闘エネルギーを基本闘エネルギーより優先サーチ
- 変更不要と確認（カード原文で裏取り済み）：はどうづきのdiscard_counts判定、
  ルナサイクルの発動条件はいずれも「基本」限定のカード効果のため対象外のままで正しい

## テスト結果

`uv run pytest -q`でリポジトリ全体が全件PASS（既存517件＋新規[N]件）。

## 未対応・次回持ち越し

- ロック闘エネルギーが実際にハンドパワーを無効化できるかは、実戦ログでの検証が必要
  （次にAlakazam系と対戦した際のログで確認する）
- カイオーガ＋メガユキノオー対策、メガジガルデex＋コアメモリ、ロケット団の監視塔の
  採用検討は今回のスコープ外（将来の別ブレストで扱う）
```

（`[N]`は実行結果の実測値に置き換える）

- [ ] **Step 3: コミット**

```bash
git add docs/implementations/20260719-lucario-rock-fighting-energy.md
git commit -m "$(cat <<'EOF'
docs(lucario): ロック闘エネルギー導入の実装サマリーを追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## 完了後の次のステップ（このプラン範囲外）

- `superpowers:requesting-code-review`でfeatureブランチ全体の最終レビューを実施
- レビュー完了後、`docs/reviews/20260719-lucario-rock-fighting-energy.md`にレビュー結果を保存
- デッキCSV再生成・Kaggle再提出（ユーザー判断）
- 次にAlakazam系との対戦ログが取れたら、ロック闘エネルギーが実際にハンドパワーを
  無効化しているかを実測検証する（[[feedback_verify_analysis_claims]]方針）
