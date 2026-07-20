# ルカリオexデッキ 居座りボーナス修正＋RETREAT HP温存観点追加 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `calc_attack_plan`の位置ボーナス（居座りボーナス）がダメージ0のプランを不当に優遇するバグを修正し、実質ノーダメージな攻撃しかできない高価値ポケモン（ex/megaEx）を温存退却させるロジックを追加する。

**Architecture:** `src/lucario_agent/combat.py`の`AttackPlan`データクラスに`damage`フィールドを追加し、`calc_attack_plan`が選択したプランの実ダメージ値を保持する。同関数内の位置ボーナス加算を`damage > 0`の場合のみに条件付ける。`_score_retreat_option`に`my_active`・`card_table`引数を追加し、実質ノーダメージかつ現在のアクティブがex/megaExのときに退却を推奨する分岐を追加する。`src/lucario_agent/main.py`側は`_score_option`のRETREATケースの呼び出しに新しい引数を渡すだけの変更に留める。

**Tech Stack:** Python 3.12 / pytest / uv（既存の`src/lucario_agent`パッケージへの追加変更のみ、新規依存なし）

## Global Constraints

- 既存567件のテストは全てPASSを維持すること（`uv run pytest -q`で確認）
- コードコメントは日本語で書く（CLAUDE.md準拠）
- `card_table`はモジュール間の暗黙グローバル参照ではなく明示引数として渡す既存方針（2026-07-20のcombat.py分割で確立済み）を踏襲する
- 設計書: `docs/superpowers/specs/2026-07-20-lucario-stay-bonus-retreat-hp-preservation-design.md`

---

### Task 1: `AttackPlan`に`damage`フィールドを追加し実ダメージ値を保持する

**Files:**
- Modify: `src/lucario_agent/combat.py:17-23`（`AttackPlan`データクラス）, `src/lucario_agent/combat.py:239-245`（`calc_attack_plan`のプラン更新箇所）
- Test: `tests/test_lucario_agent.py`（`TestCrustleAbilityInteraction`クラスの直後、680行目付近に新規クラスを追加）

**Interfaces:**
- Consumes: 既存の`calc_attack_plan(obs, my_state, op_state, state, field_counts, hand_counts, discard_counts, can_switch, can_op_switch, can_use_mega_brave, can_attack, my_prize, card_table, stadium_id=0, rng=None) -> AttackPlan`（シグネチャ変更なし）
- Produces: `AttackPlan.damage: int`（デフォルト`-1`。選択されたプランの実ダメージ量。Task 2・Task 3が参照する）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`TestCrustleAbilityInteraction`クラス（668行目で終了）の直後に、新規クラスを追加する。

```python
class TestAttackPlanDamageField:
    """AttackPlan.damage フィールド（選択したプランの実ダメージ量）のテスト"""

    def test_damage_matches_selected_plan(self, mock_card_table):
        mock_card_table[999] = MockCardData(cardId=999)
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=999, hp=200), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.damage == 130
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestAttackPlanDamageField -v`
Expected: FAIL（`AttributeError: 'AttackPlan' object has no attribute 'damage'`）

- [ ] **Step 3: `AttackPlan`に`damage`フィールドを追加する**

`src/lucario_agent/combat.py:17-23`を以下に置き換える：

```python
@dataclass
class AttackPlan:
    attacker:     int  = -1
    target:       int  = -1
    attack_index: int  = -1
    remain_hp:    int  = -1
    energy:       bool = False
    damage:       int  = -1
```

- [ ] **Step 4: `calc_attack_plan`が`damage`を保存するようにする**

`src/lucario_agent/combat.py:239-245`（`if best_score < score:`ブロック）を以下に置き換える：

```python
                if best_score < score:
                    best_score            = score
                    new_plan.attacker     = i
                    new_plan.target       = j
                    new_plan.attack_index = a
                    new_plan.remain_hp    = op_pokemon.hp - damage
                    new_plan.energy       = more_energy
                    new_plan.damage       = damage
```

- [ ] **Step 5: テストを実行し成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestAttackPlanDamageField -v`
Expected: PASS

- [ ] **Step 6: 既存テストの回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS（既存567件 + 新規1件 = 568件）

- [ ] **Step 7: コミット**

```bash
git add src/lucario_agent/combat.py tests/test_lucario_agent.py
git commit -m "feat(lucario): AttackPlanにdamageフィールドを追加し実ダメージ量を保持する"
```

---

### Task 2: 位置ボーナスをダメージ0のプランに加算しないよう修正する

**Files:**
- Modify: `src/lucario_agent/combat.py:233-236`（位置ボーナス加算）
- Test: `tests/test_lucario_agent.py`（`TestAttackPlanDamageField`クラスの直後に新規クラスを追加）

**Interfaces:**
- Consumes: Task 1で追加した`AttackPlan.damage`、`calc_attack_plan`内のローカル変数`damage`（既存、`_calc_attack_damage`の戻り値）
- Produces: なし（`calc_attack_plan`の外部シグネチャ・戻り値の型に変更なし。挙動のみ変更）

- [ ] **Step 1: 失敗するテストを書く**

`TestAttackPlanDamageField`クラスの直後に追加する。Crustle（ex技無効化持ち）対面で、メガルカリオexが0ダメージの攻撃を続けるより、ベンチのオーガポンexへ切り替えて実ダメージを与えるプランが選ばれることを確認する（実ログ`87053177`・`86898758`で確認された居座りボーナスバグの再現テスト）。

```python
class TestStayBonusDamageGating:
    """位置ボーナス(i==0/j==0)がダメージ0のプランに加算されないことを確認する回帰テスト"""

    def test_switches_to_real_damage_plan_over_zero_damage_stay(self, mock_card_table):
        """Crustle対面で、0ダメージの居座りよりOgerpon_exへの切替(実ダメージ)が選ばれる"""
        mock_card_table[lm.Crustle] = MockCardData(cardId=lm.Crustle, weakness=EnergyType.FIRE)
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6, 6])
        my_ps = make_player_state(active_pokemon=lucario, bench=[ogerpon], prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Crustle, hp=2000), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=True, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
            card_table=lm.card_table,
        )
        assert result.attacker == 1  # bench[0]=Ogerpon_exへの切替
        assert result.damage == 140
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestStayBonusDamageGating -v`
Expected: FAIL（`assert result.attacker == 1`で失敗。現状は位置ボーナスにより`attacker == 0`（メガルカリオexの居座り）が選ばれる）

- [ ] **Step 3: 位置ボーナスをダメージ0のプランに加算しないよう修正する**

`src/lucario_agent/combat.py:233-236`を以下に置き換える：

```python
                if damage > 0:
                    if i == 0:
                        score += 220
                    if j == 0:
                        score += 300
```

- [ ] **Step 4: テストを実行し成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestStayBonusDamageGating -v`
Expected: PASS

- [ ] **Step 5: 既存テストの回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS（既存568件 + 新規1件 = 569件）。特に`TestCrustleAbilityInteraction`クラスの3件が回帰なくPASSすることを確認する。

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/combat.py tests/test_lucario_agent.py
git commit -m "fix(lucario): 位置ボーナスがダメージ0のプランに加算される居座りボーナスバグを修正"
```

---

### Task 3: `_score_retreat_option`にHP温存退却の分岐を追加する

**Files:**
- Modify: `src/lucario_agent/combat.py:250-252`（`_score_retreat_option`）
- Test: `tests/test_lucario_agent.py:670-681`（既存`TestScoreRetreatOption`クラスにテストを追加）

**Interfaces:**
- Consumes: Task 1で追加した`AttackPlan.damage`
- Produces: `_score_retreat_option(current_plan: AttackPlan, my_active: Pokemon | None = None, card_table: dict | None = None) -> int`（Task 4がこの新シグネチャを`main.py`から呼び出す）

- [ ] **Step 1: 失敗するテストを書く**

既存の`TestScoreRetreatOption`クラス（`tests/test_lucario_agent.py:670-681`）に以下のメソッドを追加する（既存3メソッドの後）：

```python
    def test_positive_when_ineffective_attack_and_high_value_active(self):
        """居座り攻撃が無意味(damage<=0)で、現在のアクティブがex/megaExなら温存退却を推奨する"""
        plan = lm.AttackPlan(attacker=0, damage=0)
        megaex = make_pokemon(id=lm.Mega_Lucario_ex, hp=50)
        assert lm._score_retreat_option(plan, megaex, lm.card_table) == 2000

    def test_negative_when_ineffective_attack_but_regular_pokemon(self):
        """無意味な攻撃でも、現在のアクティブが無印(非ex)なら温存退却は推奨しない"""
        plan = lm.AttackPlan(attacker=0, damage=0)
        regular = make_pokemon(id=lm.Riolu, hp=50)
        assert lm._score_retreat_option(plan, regular, lm.card_table) == -1

    def test_negative_when_attack_is_effective(self):
        """実ダメージのある攻撃プランなら、温存退却の新分岐は発火しない"""
        plan = lm.AttackPlan(attacker=0, damage=130)
        megaex = make_pokemon(id=lm.Mega_Lucario_ex, hp=50)
        assert lm._score_retreat_option(plan, megaex, lm.card_table) == -1

    def test_existing_calls_remain_backward_compatible(self):
        """my_active/card_tableを省略した既存呼び出しは非破壊のまま-1/2000を返す"""
        assert lm._score_retreat_option(lm.AttackPlan(attacker=0)) == -1
        assert lm._score_retreat_option(lm.AttackPlan(attacker=1)) == 2000
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreRetreatOption -v`
Expected: 新規4件のうち`test_positive_when_ineffective_attack_and_high_value_active`がFAIL（`TypeError: _score_retreat_option() takes 1 positional argument but 3 were given`）。既存3件はPASSのまま。

- [ ] **Step 3: `_score_retreat_option`にHP温存退却の分岐を追加する**

`src/lucario_agent/combat.py:250-252`を以下に置き換える：

```python
def _score_retreat_option(current_plan: AttackPlan, my_active=None, card_table: dict | None = None) -> int:
    """OptionType.RETREAT のスコアを返す"""
    if current_plan.attacker >= 1:
        return 2000  # より良いアタッカーへ切り替える
    if current_plan.damage <= 0 and my_active is not None and card_table is not None:
        data = card_table[my_active.id]
        if data.megaEx or data.ex:
            return 2000  # 無効化等で攻撃が無意味な高価値ポケモンを温存退却する
    return -1
```

- [ ] **Step 4: テストを実行し成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreRetreatOption -v`
Expected: 全7件（既存3件＋新規4件）PASS

- [ ] **Step 5: 既存テストの回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS（569件 + 新規4件 = 573件）

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/combat.py tests/test_lucario_agent.py
git commit -m "feat(lucario): RETREATスコアに瀕死高価値ポケモンの温存退却分岐を追加"
```

---

### Task 4: `main.py`の呼び出し箇所を更新し統合テストを追加する

**Files:**
- Modify: `src/lucario_agent/main.py:516-517`（`_score_option`のRETREATケース）
- Test: `tests/test_lucario_agent.py`（`TestScoreRetreatOption`クラスの直後、または末尾に新規クラスを追加）

**Interfaces:**
- Consumes: Task 3で追加した`_score_retreat_option(current_plan, my_active, card_table)`の新シグネチャ
- Produces: なし（`main.py`の`agent()`が最終的にRETREATオプションを正しくスコアリングできることを保証する）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`TestScoreRetreatOption`クラスの直後に新規クラスを追加する。`_score_option`が`OptionType.RETREAT`を渡された際に、現在のアクティブポケモンと`card_table`を正しく`_score_retreat_option`へ引き渡していることを確認する。

```python
class TestScoreOptionRetreatWiring:
    """main.py側でRETREATケースがmy_state.active[0]とcard_tableを正しく渡すことの統合テスト"""

    def test_score_option_retreat_uses_current_active_and_card_table(self):
        megaex = make_pokemon(id=lm.Mega_Lucario_ex, hp=50)
        my_state = make_player_state(active_pokemon=megaex, prize_count=6)
        op_state = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        plan = lm.AttackPlan(attacker=0, damage=0)
        obs = MagicMock()
        option = Option(type=OptionType.RETREAT)
        score = lm._score_option(
            obs=obs, o=option, context=lm.SelectContext.MAIN, my_index=0,
            state=_make_state(), my_state=my_state, op_state=op_state,
            field_counts=defaultdict(int), hand_counts=defaultdict(int), discard_counts=defaultdict(int),
            attacker1=False, current_plan=plan, can_attack=True,
            stadium_id=0, ability_used_flag=False,
        )
        assert score == 2000
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreOptionRetreatWiring -v`
Expected: FAIL（`assert score == 2000`で失敗。現状の`main.py`は`_score_retreat_option(current_plan)`しか呼んでおらず、`my_active`が渡されないため`-1`が返る）

- [ ] **Step 3: `main.py`のRETREATケースを更新する**

`src/lucario_agent/main.py:516-517`を以下に置き換える：

```python
        case OptionType.RETREAT:
            return _score_retreat_option(
                current_plan,
                my_state.active[0] if my_state.active else None,
                card_table,
            )
```

- [ ] **Step 4: テストを実行し成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreOptionRetreatWiring -v`
Expected: PASS

- [ ] **Step 5: 全体回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS（573件 + 新規1件 = 574件）

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat(lucario): main.pyのRETREATケースがHP温存退却分岐へ現在のアクティブを渡すよう配線"
```

---

## 完了後の作業（このプランのスコープ外）

実装完了後、ユーザーが以下を実施する：
1. `scripts/build_lucario_submission_notebook.py`で提出用notebookを再生成し、Kaggleへアップロード・再提出
2. 新規20戦分のバトルログが溜まったら、居座りボーナスバグの再発有無・ミラー対面の戦績変化を実測検証する（`docs/implementations/`への実装サマリー記録は実装完了時に別途作成する）
