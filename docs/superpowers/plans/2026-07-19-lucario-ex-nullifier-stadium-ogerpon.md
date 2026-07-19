# ルカリオexデッキ ex無効化検知汎用化・スタジアム考慮・オーガポンex優先度連動 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/lucario_agent/main.py`の実バグ2件（ex無効化のCrustle専用ハードコード／`calc_attack_plan`のスタジアム未考慮）を修正し、相手アクティブがex無効化持ちのときにオーガポンexへのエネルギー配分・SWITCH優先度を連動させる。

**Architecture:** 静的レジストリ`EX_DAMAGE_NULLIFIER_IDS`（Crustle・Sylveonの2ID）を導入し、`_calc_attack_damage`の攻撃側exチェックを`CardData.ex`/`.megaEx`ベースに一般化する。相手アクティブの無効化判定は新規ヘルパー`_op_active_nullifies_ex`で1箇所に集約し、`energy_score`・`_score_card_option`（SWITCH/TO_ACTIVE）まで既存のパラメータ引き回しパターンで配線する。`calc_attack_plan`には`stadium_id`と`tera`フラグを使った汎用コスト補正`_tera_stadium_cost_bonus`を追加する。いずれも新しい抽象化レイヤーは導入せず、既存の関数・パラメータ構造に沿った最小限の追加とする。

**Tech Stack:** Python 3.12 / uv / pytest。設計書: `docs/superpowers/specs/2026-07-19-lucario-ex-nullifier-stadium-ogerpon-design.md`

## Global Constraints

- ワークスペース分離はgit worktreeでなくfeatureブランチを使う（`feature/lucario-ex-nullifier-stadium-ogerpon`、mainから分岐）
- 新規パラメータ（`op_active_nullifies_ex`、`stadium_id`）はすべてデフォルト値を持たせ、既存テストの呼び出しを壊さない
- コードコメントは日本語（CLAUDE.md準拠）
- 各タスク末尾で`uv run pytest -q`を実行し、全件PASSしてからコミットする
- コミットメッセージは日本語、`Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`を含める

---

## 事前準備: featureブランチ作成

- [ ] **Step 1: featureブランチを作成してチェックアウト**

```bash
git checkout -b feature/lucario-ex-nullifier-stadium-ogerpon
```

Expected: `Switched to a new branch 'feature/lucario-ex-nullifier-stadium-ogerpon'`

---

### Task 1: ex無効化検知の汎用化（`EX_DAMAGE_NULLIFIER_IDS`・`_calc_attack_damage`）

**Files:**
- Modify: `src/lucario_agent/main.py:33-34`（定数）、`:234-248`（`_calc_attack_damage`）
- Test: `tests/test_lucario_agent.py:230-263`（`TestCalcAttackDamage`クラスに追加）

**Interfaces:**
- Consumes: なし（最初のタスク）
- Produces: `lm.Sylveon`（int定数、値330）、`lm.EX_DAMAGE_NULLIFIER_IDS`（`frozenset[int]`、`{Crustle, Sylveon}`）。以降のタスクがこれを参照する。`lm._calc_attack_damage`のシグネチャは変更しない

- [ ] **Step 1: 失敗するテストを`TestCalcAttackDamage`に追加する（Red）**

`tests/test_lucario_agent.py`の`test_crustle_does_not_nullify_non_ex_attacker_damage`（262行目）の直後に追加：

```python
    def test_sylveon_nullifies_ex_attacker_damage(self):
        """Sylveon(330)もCrustleと同じ効果文の特性を持つため無効化対象に含める"""
        defender = MockCardData(cardId=lm.Sylveon)
        assert lm._calc_attack_damage(lm.Mega_Lucario_ex, 270, lm.Sylveon, defender) == 0

    def test_ogerpon_ex_bypasses_sylveon_ability(self):
        """ぶちやぶるはSylveonの特性も貫通する"""
        defender = MockCardData(cardId=lm.Sylveon)
        assert lm._calc_attack_damage(lm.Ogerpon_ex, 140, lm.Sylveon, defender) == 140

    def test_generalizes_to_any_ex_attacker_not_just_mega_lucario(self):
        """攻撃側がexなら誰でも無効化される（Mega_Lucario_ex固定ではなくCardData.ex/megaExで判定）"""
        defender = MockCardData(cardId=lm.Crustle)
        assert lm._calc_attack_damage(337, 200, lm.Crustle, defender) == 0  # Archaludon ex（ex=True）
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestCalcAttackDamage -v
```

Expected: FAIL（`lm.Sylveon`が存在しないため`AttributeError`。3件とも失敗する）

- [ ] **Step 3: 定数と`_calc_attack_damage`を実装する（Green）**

`src/lucario_agent/main.py`の33-34行目を以下に置き換える：

変更前：
```python
Ogerpon_ex                 = 117
Crustle                     = 345  # 特性「ふしぎな岩の宿」：相手の「ポケモン【ex】」の技ダメージを無効化する壁ポケモン
```

変更後：
```python
Ogerpon_ex                 = 117
Crustle                     = 345  # 特性「ふしぎな岩の宿」：相手の「ポケモン【ex】」の技ダメージを無効化する壁ポケモン
Sylveon                     = 330  # 特性「Safeguard」：Crustleと同一効果文（相手のポケモンexの技ダメージを無効化）
EX_DAMAGE_NULLIFIER_IDS = frozenset({Crustle, Sylveon})
```

続いて`_calc_attack_damage`（234-248行目）を以下に置き換える：

変更前：
```python
def _calc_attack_damage(attacker_id: int, base_damage: int, defender_id: int, defender_data) -> int:
    """弱点・抵抗力・Crustleの特性無効化を考慮した実ダメージを1箇所で計算する"""
    damage = base_damage
    attack_ignores_defender_effects = attacker_id == Ogerpon_ex  # ぶちやぶる：相手にかかっている効果を計算しない
    if not attack_ignores_defender_effects:
        if defender_data.weakness == EnergyType.FIGHTING:
            damage *= 2
        elif defender_data.resistance == EnergyType.FIGHTING:
            damage -= 30

    defender_nullifies_ex_damage = defender_id == Crustle and attacker_id == Mega_Lucario_ex
    if defender_nullifies_ex_damage:
        damage = 0  # Crustleの特性「ふしぎな岩の宿」：相手のexポケモンの技ダメージを無効化する

    return damage
```

変更後：
```python
def _calc_attack_damage(attacker_id: int, base_damage: int, defender_id: int, defender_data) -> int:
    """弱点・抵抗力・ex技無効化ポケモンの特性を考慮した実ダメージを1箇所で計算する"""
    damage = base_damage
    attack_ignores_defender_effects = attacker_id == Ogerpon_ex  # ぶちやぶる：相手にかかっている効果を計算しない
    if not attack_ignores_defender_effects:
        if defender_data.weakness == EnergyType.FIGHTING:
            damage *= 2
        elif defender_data.resistance == EnergyType.FIGHTING:
            damage -= 30

    attacker_is_ex = card_table[attacker_id].ex or card_table[attacker_id].megaEx
    defender_nullifies_ex_damage = (
        not attack_ignores_defender_effects  # ぶちやぶるは無効化を貫通するため対象外
        and defender_id in EX_DAMAGE_NULLIFIER_IDS
        and attacker_is_ex
    )
    if defender_nullifies_ex_damage:
        damage = 0  # Crustle/Sylveonの特性：相手のポケモンexの技ダメージを無効化する

    return damage
```

- [ ] **Step 4: テストを実行して成功を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestCalcAttackDamage tests/test_lucario_agent.py::TestCrustleAbilityInteraction -v
```

Expected: 全件PASS（既存の`TestCrustleAbilityInteraction`が引き続きPASSすることも確認。回帰なし）

- [ ] **Step 5: リポジトリ全体を実行して回帰がないことを確認**

```bash
uv run pytest -q
```

Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
fix(lucario): ex無効化検知をCrustle専用ハードコードから静的レジストリへ一般化

Sylveon(330)がCrustleと同一の効果文を持つ特性を確認し、
EX_DAMAGE_NULLIFIER_IDSレジストリに追加。攻撃側のex判定も
Mega_Lucario_ex固定からCardData.ex/megaExベースに一般化した。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: 相手アクティブのex無効化判定とオーガポンex優先度連動

**Files:**
- Modify: `src/lucario_agent/main.py:151-176`（`energy_score`）、`:655-678`（`_score_attach_option`）、`:389-411`（`_score_card_option`のSWITCH/TO_ACTIVE分岐）、`:681-731`（`_score_option`）、`:734-794`（`agent()`）
- Test: `tests/test_lucario_agent.py`（新規テストクラス`TestOpActiveNullifiesEx`を追加、`TestEnergyScoreOgerponEx`・`TestSwitchContext`・`TestAttachRockFightingEnergyPriority`直後に新規テスト追加）

**Interfaces:**
- Consumes: `lm.EX_DAMAGE_NULLIFIER_IDS`（Task 1で追加済み）
- Produces: `lm._op_active_nullifies_ex(op_state) -> bool`（新規関数）。`energy_score`・`_score_attach_option`・`_score_card_option`・`_score_option`の各シグネチャに`op_active_nullifies_ex: bool = False`が追加される（すべてデフォルト値付きなので既存呼び出しは無変更で動作する）

- [ ] **Step 1: `_op_active_nullifies_ex`の失敗するテストを追加する（Red）**

`tests/test_lucario_agent.py`の`TestGetStadiumId`クラス（204-213行目）の直後に新規クラスを追加：

```python
class TestOpActiveNullifiesEx:
    def test_true_when_op_active_is_crustle(self):
        ps = make_player_state(active_pokemon=make_pokemon(id=lm.Crustle))
        assert lm._op_active_nullifies_ex(ps) is True

    def test_true_when_op_active_is_sylveon(self):
        ps = make_player_state(active_pokemon=make_pokemon(id=lm.Sylveon))
        assert lm._op_active_nullifies_ex(ps) is True

    def test_false_when_op_active_is_regular_pokemon(self):
        ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu))
        assert lm._op_active_nullifies_ex(ps) is False

    def test_false_when_no_active(self):
        ps = make_player_state()
        assert lm._op_active_nullifies_ex(ps) is False
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestOpActiveNullifiesEx -v
```

Expected: FAIL（`AttributeError: module 'lucario_agent.main' has no attribute '_op_active_nullifies_ex'`）

- [ ] **Step 3: `_op_active_nullifies_ex`を実装する（Green）**

`src/lucario_agent/main.py`の`_get_stadium_id`関数（204-208行目）の直後に追加：

```python
def _op_active_nullifies_ex(op_state) -> bool:
    """相手アクティブが「ポケモンexの技ダメージを無効化する」特性持ちかどうかを判定する"""
    op_active = op_state.active[0] if op_state.active else None
    return op_active is not None and op_active.id in EX_DAMAGE_NULLIFIER_IDS
```

- [ ] **Step 4: テストを実行して成功を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestOpActiveNullifiesEx -v
```

Expected: 全件PASS

- [ ] **Step 5: `energy_score`の失敗するテストを追加する（Red）**

`tests/test_lucario_agent.py`の`TestEnergyScoreOgerponEx`クラス（161-173行目）に追加：

```python
    def test_op_active_nullifies_ex_gives_priority_over_mega_lucario_ex(self):
        """相手アクティブがex無効化持ちなら、オーガポンexがメガルカリオexより優先される"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, energies=[6])
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[])
        ogerpon_score = lm.energy_score(ogerpon, False, False, op_active_nullifies_ex=True)
        lucario_score = lm.energy_score(lucario, False, True, op_active_nullifies_ex=True)
        assert ogerpon_score > lucario_score

    def test_op_active_nullifies_ex_bonus_only_applies_when_true(self):
        p = make_pokemon(id=lm.Ogerpon_ex, energies=[6])
        without_flag = lm.energy_score(p, False, False, op_active_nullifies_ex=False)
        with_flag    = lm.energy_score(p, False, False, op_active_nullifies_ex=True)
        assert with_flag > without_flag
```

- [ ] **Step 6: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestEnergyScoreOgerponEx -v
```

Expected: FAIL（`TypeError: energy_score() got an unexpected keyword argument 'op_active_nullifies_ex'`）

- [ ] **Step 7: `energy_score`を実装する（Green）**

`src/lucario_agent/main.py`の`energy_score`（151-176行目）を以下に置き換える：

```python
def energy_score(pokemon: Pokemon, active: bool, attacker1: bool, op_active_nullifies_ex: bool = False) -> int:
    """エネルギー付与先ポケモンの優先度スコアを返す"""
    energy_count = len(pokemon.energies)
    score = 8000
    if active:
        score += 10
    if pokemon.id == Lunatone:
        score -= 100
    elif pokemon.id == Solrock:
        if energy_count < 1:
            score += 20
        else:
            score -= 100
    elif pokemon.id in (Riolu, Mega_Lucario_ex):
        if pokemon.id == Mega_Lucario_ex:
            score += 1
        if energy_count < 2:
            score += 100
        if attacker1:
            score -= 50
    elif pokemon.id == Ogerpon_ex:
        if energy_count < 3:
            score += 80
        if attacker1:
            score += 40  # ルカリオ確保済みなら余剰エネルギーをオーガポンexへ
        if op_active_nullifies_ex:
            score += 150  # 相手がex無効化持ちならメガルカリオex系より優先してエネルギーを回す
    return score
```

- [ ] **Step 8: テストを実行して成功を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestEnergyScoreOgerponEx -v
```

Expected: 全件PASS

- [ ] **Step 9: `_score_attach_option`の失敗するテストを追加する（Red）**

`tests/test_lucario_agent.py`の`TestAttachRockFightingEnergyPriority`クラス（1122-1152行目）の直後に新規クラスを追加：

```python
class TestAttachOgerponExPriority:
    def _score(self, energies, op_active_nullifies_ex):
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, energies=energies)
        my_ps = make_player_state(bench=[ogerpon])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        option = Option(type=OptionType.ATTACH, index=0, inPlayArea=lm.AreaType.BENCH, inPlayIndex=0)
        return lm._score_attach_option(
            obs, option, my_index=0, current_plan=lm.AttackPlan(), attacker1=False,
            op_active_nullifies_ex=op_active_nullifies_ex,
        )

    def test_op_active_nullifies_ex_boosts_ogerpon_ex_attach_priority(self):
        without_flag = self._score([6], op_active_nullifies_ex=False)
        with_flag    = self._score([6], op_active_nullifies_ex=True)
        assert with_flag > without_flag
```

- [ ] **Step 10: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestAttachOgerponExPriority -v
```

Expected: FAIL（`TypeError: _score_attach_option() got an unexpected keyword argument 'op_active_nullifies_ex'`）

- [ ] **Step 11: `_score_attach_option`を実装する（Green）**

`src/lucario_agent/main.py`の`_score_attach_option`（655-678行目）のシグネチャと`energy_score`呼び出し箇所を変更する。

変更前：
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
```

変更後：
```python
def _score_attach_option(obs, o, my_index, current_plan, attacker1, op_active_nullifies_ex: bool = False) -> int:
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
    score = energy_score(pokemon, o.inPlayArea == AreaType.ACTIVE, attacker1, op_active_nullifies_ex)
```

（残りの行は変更しない）

- [ ] **Step 12: テストを実行して成功を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestAttachOgerponExPriority tests/test_lucario_agent.py::TestAttachRockFightingEnergyPriority -v
```

Expected: 全件PASS

- [ ] **Step 13: `_score_card_option`の失敗するテストを追加する（Red）**

`tests/test_lucario_agent.py`の`TestSwitchContext`クラス（905-928行目）を以下に置き換える：

```python
class TestSwitchContext:
    """SWITCH/TO_ACTIVEコンテキストでのオーガポンex優先度テスト"""

    def _score(self, energies, op_active_nullifies_ex=False):
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=energies)
        my_ps = make_player_state(bench=[ogerpon])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        return lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.BENCH, index=0, playerIndex=0),
            context=lm.SelectContext.SWITCH, my_index=0, state=_make_state(),
            my_state=my_ps,
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
            op_active_nullifies_ex=op_active_nullifies_ex,
        )

    def test_ogerpon_ex_prioritized_when_charged(self):
        """3エネルギー確保済み（ぶちやぶる可能）なら高優先度になる"""
        assert self._score([6, 6, 6]) == 3 * 2 + 20  # energy_count*2 + 充填済みボーナス

    def test_ogerpon_ex_low_priority_when_not_charged(self):
        """2エネルギー以下（ぶちやぶる不可）では優先度が低いまま"""
        assert self._score([6, 6]) == 2 * 2 + 6  # energy_count*2 + 充填中ボーナス

    def test_op_active_nullifies_ex_adds_extra_priority(self):
        """相手アクティブがex無効化持ちなら追加で優先度が上がる"""
        base    = self._score([6, 6, 6], op_active_nullifies_ex=False)
        boosted = self._score([6, 6, 6], op_active_nullifies_ex=True)
        assert boosted == base + 30
```

- [ ] **Step 14: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestSwitchContext -v
```

Expected: FAIL（`TypeError: _score_card_option() got an unexpected keyword argument 'op_active_nullifies_ex'`）

- [ ] **Step 15: `_score_card_option`を実装する（Green）**

`src/lucario_agent/main.py`の`_score_card_option`のシグネチャ（379-381行目）とSWITCH/TO_ACTIVE分岐内のOgerpon_ex優先度（407-408行目）を変更する。

変更前：
```python
def _score_card_option(obs, o, context, my_index, state, my_state,
                       field_counts, hand_counts, discard_counts,
                       attacker1, current_plan, ability_used_flag) -> int:
```

変更後：
```python
def _score_card_option(obs, o, context, my_index, state, my_state,
                       field_counts, hand_counts, discard_counts,
                       attacker1, current_plan, ability_used_flag,
                       op_active_nullifies_ex: bool = False) -> int:
```

変更前（SWITCH/TO_ACTIVE分岐内）：
```python
                elif card.id == Ogerpon_ex:
                    score += 20 if energy_count >= 3 else 6
```

変更後：
```python
                elif card.id == Ogerpon_ex:
                    score += 20 if energy_count >= 3 else 6
                    if op_active_nullifies_ex:
                        score += 30  # 相手がex無効化持ちなら優先的にアクティブへ出す
```

- [ ] **Step 16: テストを実行して成功を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestSwitchContext -v
```

Expected: 全件PASS

- [ ] **Step 17: `_score_option`と`agent()`を配線する（統合、テストなし＝既存の`TestAgent`統合テストで間接的に回帰確認）**

`src/lucario_agent/main.py`の`_score_option`のシグネチャ（681-684行目）とCARD/ATTACH分岐（691-704行目）を変更する。

変更前：
```python
def _score_option(obs, o, context, my_index, state, my_state, op_state,
                  field_counts, hand_counts, discard_counts,
                  attacker1, current_plan, can_attack,
                  stadium_id, ability_used_flag) -> int:
    """1 つのオプションにヒューリスティックスコアを付ける"""
    match o.type:
        case OptionType.NUMBER:
            return o.number
        case OptionType.YES:
            return 1
        case OptionType.CARD:
            return _score_card_option(
                obs, o, context, my_index, state, my_state,
                field_counts, hand_counts, discard_counts,
                attacker1, current_plan, ability_used_flag,
            )
        case OptionType.PLAY:
            return _score_play_option(
                obs, o, my_index, current_plan, can_attack,
                state, my_state, hand_counts, field_counts, stadium_id,
                attacker1, op_hand_count=op_state.handCount,
            )
        case OptionType.ATTACH:
            return _score_attach_option(obs, o, my_index, current_plan, attacker1)
```

変更後：
```python
def _score_option(obs, o, context, my_index, state, my_state, op_state,
                  field_counts, hand_counts, discard_counts,
                  attacker1, current_plan, can_attack,
                  stadium_id, ability_used_flag,
                  op_active_nullifies_ex: bool = False) -> int:
    """1 つのオプションにヒューリスティックスコアを付ける"""
    match o.type:
        case OptionType.NUMBER:
            return o.number
        case OptionType.YES:
            return 1
        case OptionType.CARD:
            return _score_card_option(
                obs, o, context, my_index, state, my_state,
                field_counts, hand_counts, discard_counts,
                attacker1, current_plan, ability_used_flag,
                op_active_nullifies_ex=op_active_nullifies_ex,
            )
        case OptionType.PLAY:
            return _score_play_option(
                obs, o, my_index, current_plan, can_attack,
                state, my_state, hand_counts, field_counts, stadium_id,
                attacker1, op_hand_count=op_state.handCount,
            )
        case OptionType.ATTACH:
            return _score_attach_option(obs, o, my_index, current_plan, attacker1, op_active_nullifies_ex)
```

続いて`agent()`内、`_reset_turn_state`呼び出しの後・`can_switch = can_op_switch = ...`の前（762-764行目付近）に判定を追加し、`scores`のリスト内包表記（775-783行目）に引数を追加する。

変更前：
```python
    field_counts, hand_counts, discard_counts, attacker1 = _collect_field_state(my_state)
    stadium_id = _get_stadium_id(state)

    can_switch = can_op_switch = can_use_mega_brave = can_attack = False
```

変更後：
```python
    field_counts, hand_counts, discard_counts, attacker1 = _collect_field_state(my_state)
    stadium_id = _get_stadium_id(state)
    op_active_nullifies_ex = _op_active_nullifies_ex(op_state)

    can_switch = can_op_switch = can_use_mega_brave = can_attack = False
```

変更前：
```python
    scores = [
        _score_option(
            obs, o, context, my_index, state, my_state, op_state,
            field_counts, hand_counts, discard_counts,
            attacker1, plan, can_attack,
            stadium_id, ability_used,
        )
        for o in select.option
    ]
```

変更後：
```python
    scores = [
        _score_option(
            obs, o, context, my_index, state, my_state, op_state,
            field_counts, hand_counts, discard_counts,
            attacker1, plan, can_attack,
            stadium_id, ability_used, op_active_nullifies_ex,
        )
        for o in select.option
    ]
```

- [ ] **Step 18: リポジトリ全体を実行して回帰がないことを確認**

```bash
uv run pytest -q
```

Expected: 全件PASS（`TestAgent`クラスの既存統合テストも引き続きPASSすること）

- [ ] **Step 19: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
feat(lucario): 相手のex無効化持ち対面でオーガポンexへエネルギー・SWITCH優先度を連動

_op_active_nullifies_exで相手アクティブの無効化持ちを判定し、
energy_score・SWITCH/TO_ACTIVEスコアリングまで配線。壁デッキ対面で
オーガポンexへのエネルギー供給が滞る不発パターンへの対策。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `calc_attack_plan`のスタジアム（Nighttime Mine）考慮

**Files:**
- Modify: `src/lucario_agent/main.py`（定数追加、`_tera_stadium_cost_bonus`新規関数、`calc_attack_plan`シグネチャ・ループ内、`agent()`の`calc_attack_plan`呼び出し箇所）
- Modify: `tests/test_lucario_agent.py:8-19`（`MockCardData`に`tera`フィールド追加）、`:34`（`mock_card_table`のOgerpon_exエントリに`tera=True`追加）
- Test: `tests/test_lucario_agent.py`（新規テストクラス`TestTeraStadiumCostBonus`、`TestCalcAttackPlan`に追加）

**Interfaces:**
- Consumes: なし（Task 1・2とは独立）
- Produces: `lm.Nighttime_Mine`（int定数、値1266）、`lm._tera_stadium_cost_bonus(pokemon_id, stadium_id) -> int`（新規関数）。`lm.calc_attack_plan`のシグネチャに`stadium_id: int = 0`が追加される（デフォルト値付きなので既存呼び出しは無変更で動作する）

- [ ] **Step 1: `MockCardData`に`tera`フィールドを追加する**

`tests/test_lucario_agent.py`の`MockCardData`データクラス（8-19行目）を以下に置き換える：

```python
@dataclass
class MockCardData:
    """テスト用 CardData 代替クラス（cg.api.CardData と同一フィールドのみ定義）"""
    cardId:     int
    name:       str               = ""
    megaEx:     bool              = False
    ex:         bool              = False
    stage2:     bool              = False
    stage1:     bool              = False
    tera:       bool              = False
    cardType:   CardType          = CardType.POKEMON
    weakness:   EnergyType | None = None
    resistance: EnergyType | None = None
```

続いて`mock_card_table`フィクスチャ（34行目）のOgerpon_exエントリを以下に置き換える：

変更前：
```python
        lm.Ogerpon_ex:            _card(lm.Ogerpon_ex, ex=True),  # Cornerstone Mask Ogerpon ex
```

変更後：
```python
        lm.Ogerpon_ex:            _card(lm.Ogerpon_ex, ex=True, tera=True),  # Cornerstone Mask Ogerpon ex
```

- [ ] **Step 2: `_tera_stadium_cost_bonus`の失敗するテストを追加する（Red）**

`tests/test_lucario_agent.py`の`TestGetStadiumId`クラス（204-213行目）の直後（Task 2で追加した`TestOpActiveNullifiesEx`がある場合はその直後）に新規クラスを追加：

```python
class TestTeraStadiumCostBonus:
    def test_no_bonus_without_nighttime_mine(self):
        assert lm._tera_stadium_cost_bonus(lm.Ogerpon_ex, stadium_id=0) == 0

    def test_no_bonus_for_non_tera_pokemon_under_nighttime_mine(self):
        """メガルカリオexはテラスタルではないためコスト変化なし"""
        assert lm._tera_stadium_cost_bonus(lm.Mega_Lucario_ex, stadium_id=lm.Nighttime_Mine) == 0

    def test_bonus_for_tera_pokemon_under_nighttime_mine(self):
        assert lm._tera_stadium_cost_bonus(lm.Ogerpon_ex, stadium_id=lm.Nighttime_Mine) == 1
```

- [ ] **Step 3: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestTeraStadiumCostBonus -v
```

Expected: FAIL（`AttributeError: module 'lucario_agent.main' has no attribute 'Nighttime_Mine'`）

- [ ] **Step 4: 定数と`_tera_stadium_cost_bonus`を実装する（Green）**

`src/lucario_agent/main.py`の`Gravity_Mountain = 1252`の行の直後に追加：

```python
Gravity_Mountain      = 1252
Nighttime_Mine        = 1266  # テラスタルポケモンの技コスト+1（両プレイヤー対象）
```

続いて`_get_stadium_id`関数（`_op_active_nullifies_ex`をTask 2で追加済みならその直後）の後に追加：

```python
def _tera_stadium_cost_bonus(pokemon_id: int, stadium_id: int) -> int:
    """Nighttime Mine下でテラスタルポケモンが支払う追加コストを返す"""
    if stadium_id == Nighttime_Mine and card_table[pokemon_id].tera:
        return 1
    return 0
```

- [ ] **Step 5: テストを実行して成功を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestTeraStadiumCostBonus -v
```

Expected: 全件PASS

- [ ] **Step 6: `calc_attack_plan`の失敗するテストを追加する（Red）**

`tests/test_lucario_agent.py`の`TestCalcAttackPlan`クラス内、`test_ogerpon_ex_selected_when_only_rock_energy_in_hand`（426-440行目）の直後に追加：

```python
    def test_ogerpon_ex_requires_4_energy_under_nighttime_mine(self):
        """Nighttime Mine下ではオーガポンexの技コストが3→4になり、3エネルギーでは発動しない"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6, 6])
        my_ps = make_player_state(active_pokemon=ogerpon, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            stadium_id=lm.Nighttime_Mine,
        )
        assert result.attacker == -1

    def test_ogerpon_ex_attacks_normally_without_nighttime_mine(self):
        """Nighttime Mine以外では従来通り3エネルギーで攻撃候補になる（回帰確認）"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6, 6])
        my_ps = make_player_state(active_pokemon=ogerpon, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            stadium_id=lm.Gravity_Mountain,
        )
        assert result.attacker == 0

    def test_mega_lucario_ex_unaffected_by_nighttime_mine(self):
        """メガルカリオexは非テラスタルのためNighttime Mine下でもコスト変化なし（回帰確認）"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            stadium_id=lm.Nighttime_Mine,
        )
        assert result.attacker     == 0
        assert result.attack_index == 0
```

- [ ] **Step 7: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestCalcAttackPlan -v
```

Expected: FAIL（`TypeError: calc_attack_plan() got an unexpected keyword argument 'stadium_id'`。新規3件が失敗する）

- [ ] **Step 8: `calc_attack_plan`を実装する（Green）**

`src/lucario_agent/main.py`の`calc_attack_plan`のシグネチャに`stadium_id`を追加する。

変更前：
```python
def calc_attack_plan(
    obs: Observation,
    my_state,
    op_state,
    state,
    field_counts:   defaultdict,
    hand_counts:    defaultdict,
    discard_counts: defaultdict,
    can_switch:         bool,
    can_op_switch:      bool,
    can_use_mega_brave: bool,
    can_attack:         bool,
    my_prize:           int,
    rng: "random.Random | None" = None,
) -> AttackPlan:
```

変更後：
```python
def calc_attack_plan(
    obs: Observation,
    my_state,
    op_state,
    state,
    field_counts:   defaultdict,
    hand_counts:    defaultdict,
    discard_counts: defaultdict,
    can_switch:         bool,
    can_op_switch:      bool,
    can_use_mega_brave: bool,
    can_attack:         bool,
    my_prize:           int,
    stadium_id: int = 0,
    rng: "random.Random | None" = None,
) -> AttackPlan:
```

続いてループ内、if/elif連鎖の直後・`if base_damage <= 0:`の直前に1行追加する。

変更前：
```python
            elif my_pokemon.id == Ogerpon_ex:
                energy_required = 3
                base_damage     = 140

            if base_damage <= 0:
                continue
```

変更後：
```python
            elif my_pokemon.id == Ogerpon_ex:
                energy_required = 3
                base_damage     = 140

            energy_required += _tera_stadium_cost_bonus(my_pokemon.id, stadium_id)

            if base_damage <= 0:
                continue
```

- [ ] **Step 9: テストを実行して成功を確認**

```bash
uv run pytest tests/test_lucario_agent.py::TestCalcAttackPlan -v
```

Expected: 全件PASS

- [ ] **Step 10: `agent()`から`stadium_id`を配線する**

`src/lucario_agent/main.py`の`agent()`内、`calc_attack_plan`呼び出し箇所を変更する。

変更前：
```python
        plan = calc_attack_plan(
            obs, my_state, op_state, state,
            field_counts, hand_counts, discard_counts,
            can_switch, can_op_switch, can_use_mega_brave, can_attack,
            my_prize,
        )
```

変更後：
```python
        plan = calc_attack_plan(
            obs, my_state, op_state, state,
            field_counts, hand_counts, discard_counts,
            can_switch, can_op_switch, can_use_mega_brave, can_attack,
            my_prize, stadium_id=stadium_id,
        )
```

- [ ] **Step 11: リポジトリ全体を実行して回帰がないことを確認**

```bash
uv run pytest -q
```

Expected: 全件PASS

- [ ] **Step 12: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
fix(lucario): calc_attack_planにNighttime Mineのテラスタルコスト+1を考慮

CardData.teraフラグを使った汎用判定のため、オーガポンex専用ではなく
テラスタルポケモン全般に対応する。スタジアム下での確定KO誤算定
（フルHPのメガルカリオexを不要に退却させた実バグ）を修正。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: 全体回帰確認・実装サマリー作成

**Files:**
- Create: `docs/implementations/20260719-lucario-ex-nullifier-stadium-ogerpon.md`

**Interfaces:**
- Consumes: Task 1〜3の全変更
- Produces: 実装サマリードキュメント（CLAUDE.mdフェーズ4の運用ルールに従う）

- [ ] **Step 1: リポジトリ全体のテストを実行し、件数を記録する**

```bash
uv run pytest -q
```

Expected: 全件PASS。実行結果の末尾（`XXX passed`）をメモしておく（実装サマリーに記載するため）

- [ ] **Step 2: 実装サマリードキュメントを作成する**

`docs/implementations/20260719-lucario-ex-nullifier-stadium-ogerpon.md`を新規作成し、以下を含める：
- 対象の設計書（`docs/superpowers/specs/2026-07-19-lucario-ex-nullifier-stadium-ogerpon-design.md`）へのリンク
- 実装したバグ修正2件（ex無効化検知の汎用化、Nighttime Mineコスト考慮）とオーガポンex優先度連動の概要
- Step 1で記録したテスト件数（開始前の件数→完了後の件数）
- コミット範囲（`feature/lucario-ex-nullifier-stadium-ogerpon`ブランチの最初のコミット〜最後のコミット）
- 未対応・次回持ち越し事項：①Full Metal Lab等の他スタジアム対応（今回スコープ外、ユーザー判断済み）、②エネルギー優先度の具体値（+150/+30）は叩き台であり、Kaggle再提出後の実戦ログで効果検証が必要

- [ ] **Step 3: 実装サマリーをコミット**

```bash
git add docs/implementations/20260719-lucario-ex-nullifier-stadium-ogerpon.md
git commit -m "$(cat <<'EOF'
docs(lucario): ex無効化検知汎用化・スタジアム考慮・オーガポンex優先度連動の実装サマリーを追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: ユーザーへ完了報告し、mainへのマージ方針を確認する**

`superpowers:finishing-a-development-branch`スキルの要領で、featureブランチの扱い（mainへマージするか、レビューを先に行うか）をユーザーに確認する。CLAUDE.mdのフェーズ6（レビュー）に従い、正常動作確認後はコードレビューを依頼する旨を伝える。
