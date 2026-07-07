# ルカリオexデッキ サブアタッカー「オーガポン いしずえのめんex」導入 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ルカリオexデッキに「オーガポン いしずえのめんex」（Card ID 117）を1枚採用し、`src/lucario_agent/main.py`のスコアリングにサブアタッカーとして組み込む。

**Architecture:** 既存の`calc_attack_plan`内のif/elif連鎖（Mega Lucario ex / Solrock）に3つ目の分岐として追加する。技「ぶちやぶる」は弱点・抵抗力を計算しない仕様のため、共通のダメージ修正ブロックをオーガポンexのときだけスキップする。特性の「相手の効果を無視する」部分は実装しない（シミュレータ本体が処理するため）。

**Tech Stack:** Python 3.12 / uv / pytest（既存の`tests/conftest.py`のヘルパー関数を再利用）

## Global Constraints

- 設計書: `docs/superpowers/specs/2026-07-06-lucario-ogerpon-subattacker-design.md`（このPlanの元スペック。矛盾があれば設計書を優先）
- デッキ合計は常に60枚、ACE SPEC（Hero's Cape, ID 1159）は1枚のまま変更しない
- カードID定数は`src/lucario_agent/main.py`冒頭の定数ブロックに追加する（既存の命名規則`Card_Name = id`に従う）
- 実装完了後、`docs/implementations/20260706-lucario-ogerpon-subattacker.md`に実装サマリーを保存する（CLAUDE.mdフェーズ4の規約）

---

### Task 1: デッキ構成の変更（Solrock 4→3、オーガポンex 1枚追加）

**Files:**
- Modify: `decks/lucario_20260621.py`
- Modify: `tests/test_lucario_deck.py`

**Interfaces:**
- Consumes: なし（デッキ定義のみ）
- Produces: `DECK`リストに`(117, 1)`が含まれ、`(676, 4)`が`(676, 3)`に変わる。以降のタスクは`Ogerpon_ex = 117`という数値を`src/lucario_agent/main.py`の定数として参照する

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_deck.py`の末尾に追記：

```python
def test_ogerpon_ex_present_with_1_copy():
    counts = dict(DECK)
    assert counts[117] == 1  # Cornerstone Mask Ogerpon ex


def test_solrock_reduced_to_3():
    counts = dict(DECK)
    assert counts[676] == 3  # Solrock 4→3（オーガポンex採用のため1枚減）
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_lucario_deck.py -v`
Expected: `test_ogerpon_ex_present_with_1_copy`が`KeyError: 117`で失敗、`test_solrock_reduced_to_3`が`assert 4 == 3`で失敗

- [ ] **Step 3: デッキ定義を変更**

`decks/lucario_20260621.py`の該当行を変更：

```python
    (676, 3),    # Solrock（4→3。オーガポンex採用のため1枚減）
```

`(675, 2), # Lunatone`の直後に追加：

```python
    (117, 1),    # Cornerstone Mask Ogerpon ex（サブアタッカー新規採用）
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_lucario_deck.py -v`
Expected: 全件PASS（`test_deck_has_60_cards`など既存テストも合わせて全てPASSすること）

- [ ] **Step 5: コミット**

```bash
git add decks/lucario_20260621.py tests/test_lucario_deck.py
git commit -m "$(cat <<'EOF'
feat: ルカリオexデッキにオーガポンexを1枚追加（Solrock 4→3）

イワパレスのような特性持ち耐性ポケモン対策として、弱点・抵抗力を
無視するオーガポンexをサブアタッカーとして採用する。枠はSolrock
を1枚減らして確保した。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `calc_attack_plan`へのオーガポンex統合（アタッカー候補追加・弱点抵抗力無視）

**Files:**
- Modify: `src/lucario_agent/main.py:11-30`（定数ブロック）, `main.py:260-302`（`calc_attack_plan`内のアタッカー分岐とダメージ計算）
- Modify: `tests/test_lucario_agent.py:26-59`（`mock_card_table`フィクスチャ）, 末尾（`TestCalcAttackPlan`クラスへのテスト追加）

**Interfaces:**
- Consumes: `Task 1`で確定した`Ogerpon_ex = 117`という数値
- Produces: `lm.Ogerpon_ex`定数（後続タスクの`energy_score`・DISCARD保護から参照される）。`calc_attack_plan`が`my_pokemon.id == Ogerpon_ex`かつ`len(energies) >= 3`のとき`base_damage=140`・弱点抵抗力無視でアタッカー候補に含める

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`mock_card_table`フィクスチャ（26行目付近、`lm.Mega_Lucario_ex: _card(...)`の次の行）に追記：

```python
        lm.Ogerpon_ex:            _card(lm.Ogerpon_ex, ex=True),  # Cornerstone Mask Ogerpon ex
```

`class TestCalcAttackPlan`の最後のテストメソッド（`test_mega_brave_holds_when_rng_above_epsilon_and_no_ko_either_way`）の直後に追記：

```python
    def test_ogerpon_ex_selected_as_attacker_with_3_energy(self):
        """オーガポンexが3エネルギー確保時にアタッカー候補として選ばれ、140ダメ固定になる"""
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
        )
        assert result.attacker  == 0
        assert result.remain_hp == 100 - 140

    def test_ogerpon_ex_ignores_weakness(self):
        """ぶちやぶるは弱点を計算しないため、相手が格闘弱点でも140ダメ固定（280にならない）"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6, 6])
        my_ps = make_player_state(active_pokemon=ogerpon, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=300), prize_count=6)
        lm.card_table[lm.Riolu] = MockCardData(cardId=lm.Riolu, weakness=EnergyType.FIGHTING)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
        )
        assert result.remain_hp == 300 - 140

    def test_ogerpon_ex_not_selected_with_insufficient_energy(self):
        """2エネルギーでは「ぶちやぶる」(3エネ必要)を使えずアタッカー候補にならない"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=ogerpon, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
        )
        assert result.attacker == -1
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_lucario_agent.py -k ogerpon_ex -v`
Expected: `AttributeError: module 'lucario_agent.main' has no attribute 'Ogerpon_ex'`で3件とも失敗

- [ ] **Step 3: 実装（`src/lucario_agent/main.py`）**

定数ブロック（`Ciphermaniac_Codebreaking  = 1188`の行、17行目付近）の直後に追加：

```python
Ogerpon_ex                 = 117
```

`calc_attack_plan`内、Solrockの分岐（既存の`elif my_pokemon.id == Solrock:`ブロック）の直後に追加：

```python
            elif my_pokemon.id == Ogerpon_ex:
                energy_required = 3
                base_damage     = 140
```

同関数内のダメージ計算ブロック（`damage = base_damage`から`elif data.resistance == EnergyType.FIGHTING: damage -= 30`まで）を以下に変更：

```python
                damage = base_damage
                data   = card_table[op_pokemon.id]
                if my_pokemon.id != Ogerpon_ex:
                    if data.weakness == EnergyType.FIGHTING:
                        damage *= 2
                    elif data.resistance == EnergyType.FIGHTING:
                        damage -= 30
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: 全件PASS（新規3件含め、既存の`TestCalcAttackPlan`・`TestEnergyScore`等すべて回帰なし）

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
feat: calc_attack_planにオーガポンexをアタッカー候補として追加

技「ぶちやぶる」(3エネ, 140ダメ)は弱点・抵抗力を計算しない仕様の
ため、既存の弱点2倍/抵抗力-30処理をオーガポンexのときだけスキッ
プするようにした。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `energy_score`へのエネルギー配分優先度追加

**Files:**
- Modify: `src/lucario_agent/main.py:150-170`（`energy_score`関数）
- Modify: `tests/test_lucario_agent.py`（`TestEnergyScore`クラスの直後に新規テストクラス追加）

**Interfaces:**
- Consumes: `Task 2`で定義済みの`lm.Ogerpon_ex`
- Produces: `energy_score(pokemon, active, attacker1)`が`pokemon.id == Ogerpon_ex`のとき、3エネ未満なら+80、`attacker1=True`（ルカリオ系統が準備済み）ならさらに+40される

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`class TestEnergyScore:`の最後のメソッド（`test_attacker1_flag_lowers_score`）の直後、`# ==================== Task 4: フィールド状態ヘルパー ====================`コメントの手前に新規クラスを追加：

```python
class TestEnergyScoreOgerponEx:
    def test_charging_gets_bonus_below_3_energy(self):
        """3エネ未満（充填中）はボーナスが付く"""
        charging = make_pokemon(id=lm.Ogerpon_ex, energies=[6, 6])
        full     = make_pokemon(id=lm.Ogerpon_ex, energies=[6, 6, 6])
        assert lm.energy_score(charging, False, False) > lm.energy_score(full, False, False)

    def test_attacker1_ready_gives_extra_bonus(self):
        """ルカリオ系統(attacker1)が準備済みなら、余剰エネルギーをオーガポンexへ回すため加点される"""
        p = make_pokemon(id=lm.Ogerpon_ex, energies=[6])
        without_flag = lm.energy_score(p, False, False)
        with_flag    = lm.energy_score(p, False, True)
        assert with_flag > without_flag
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_lucario_agent.py -k OgerponEx -v`
Expected: 2件とも`assert 8000 > 8000`（変化なし、現状`energy_score`はOgerpon_exを未対応なのでデフォルトの8000点のまま）で失敗

- [ ] **Step 3: 実装（`src/lucario_agent/main.py`）**

`energy_score`関数内、`elif pokemon.id in (Riolu, Mega_Lucario_ex):`ブロックの直後（`return score`の手前）に追加：

```python
    elif pokemon.id == Ogerpon_ex:
        if energy_count < 3:
            score += 80
        if attacker1:
            score += 40  # ルカリオ確保済みなら余剰エネルギーをオーガポンexへ
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
feat: energy_scoreにオーガポンexへのエネルギー配分優先度を追加

ルカリオ系統(attacker1)が準備済みの場合に余剰エネルギーをオーガ
ポンexへ回す、グリムスナールデッキのマシマシラと同じパターンを
踏襲した。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: DISCARDコンテキストでの誤トラッシュ防止

**Files:**
- Modify: `src/lucario_agent/main.py:398`（`_score_card_option`のDISCARDケース）
- Modify: `tests/test_lucario_agent.py`（`class TestDiscardContext:`にテスト追加）

**Interfaces:**
- Consumes: `Task 2`で定義済みの`lm.Ogerpon_ex`
- Produces: `_score_card_option`のDISCARDコンテキストで`card.id == Ogerpon_ex`のとき`-100`を返す（1枚しかないため誤トラッシュを防ぐ）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`class TestDiscardContext:`内、`test_protects_key_pokemon`メソッドの直後に追記：

```python
    def test_protects_ogerpon_ex(self):
        """1枚しかないオーガポンexも誤トラッシュから保護する"""
        ogerpon = Card(id=lm.Ogerpon_ex, serial=1, playerIndex=0)
        obs = self._obs(ogerpon)
        score = lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )
        assert score == -100
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_lucario_agent.py -k protects_ogerpon_ex -v`
Expected: `assert 10 == -100`で失敗（現状はデフォルトの一般トレーナーズ扱い＝10点）

- [ ] **Step 3: 実装（`src/lucario_agent/main.py`）**

`_score_card_option`のDISCARDケース内、既存の行：

```python
            if card.id in (Riolu, Mega_Lucario_ex, Solrock, Lunatone):
                return -100
```

を以下に変更：

```python
            if card.id in (Riolu, Mega_Lucario_ex, Solrock, Lunatone, Ogerpon_ex):
                return -100
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "$(cat <<'EOF'
feat: DISCARDコンテキストでオーガポンexを誤トラッシュから保護

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: 全体回帰確認・実装サマリー作成

**Files:**
- Create: `docs/implementations/20260706-lucario-ogerpon-subattacker.md`

**Interfaces:**
- Consumes: Task 1〜4の全変更
- Produces: 実装サマリードキュメント（CLAUDE.mdフェーズ4の規約に基づく）

- [ ] **Step 1: リポジトリ全体のテストを実行**

Run: `uv run pytest -q`
Expected: 全件PASS（既存240件超 + 今回追加した6件、合計で回帰なし）

- [ ] **Step 2: 実装サマリーを作成**

`docs/implementations/20260706-lucario-ogerpon-subattacker.md`を作成し、以下を含める：
- 背景（イワパレスのような特性持ち耐性ポケモン対策としての導入目的）
- デッキ変更内容（Solrock 4→3、Cornerstone Mask Ogerpon ex 1枚追加）
- エージェントロジック変更内容（`calc_attack_plan`・`energy_score`・DISCARD保護）
- テスト結果（追加6件 + 既存全件PASS）
- 未対応事項（案2：アタッカー定義のテーブル化は将来の検討事項として設計書に記載済み。今回は着手せず）
- 次のステップ（`output/`用デッキCSV生成・Kaggleアップロードはユーザー判断待ち）

- [ ] **Step 3: コミット**

```bash
git add docs/implementations/20260706-lucario-ogerpon-subattacker.md
git commit -m "$(cat <<'EOF'
docs: ルカリオexデッキ オーガポンex導入の実装サマリーを追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## 実装後のワークフロー（CLAUDE.mdフェーズ6）

全タスク完了後、`superpowers:requesting-code-review`を使って最終ブランチレビューを依頼し、指摘があれば反映後に`docs/reviews/20260706-lucario-ogerpon-subattacker.md`へレビュー結果を保存する。
