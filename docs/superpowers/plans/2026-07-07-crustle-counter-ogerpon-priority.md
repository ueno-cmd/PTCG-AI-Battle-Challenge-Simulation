# Crustle対策強化・オーガポンex優先ロジック導入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** バトルログ84580427（player1 Kagura_UT敗北）の解析で判明した、Crustle（イワパレス、Card ID 345、特性「ふしぎな岩の宿／しんぴのいしやど」＝相手のexポケモンの技ダメージを無効化）に対するロジックエラーを修正し、デッキ側もオーガポンexを増量する。

**Architecture:** 3点を変更する。(1) `decks/lucario_20260621.py` のカード構成変更（Solrock 3→2、Ogerpon_ex 1→2）。(2) `calc_attack_plan` にCrustle固有の耐性チェックを追加し、Mega Lucario exの技ダメージはCrustle相手には0として評価する（オーガポンexの「ぶちやぶる」は"相手の効果を計算しない"仕様のためこの耐性を貫通する、というルールに基づく）。(3) `_score_card_option` のSWITCH/TO_ACTIVEスコアリングにOgerpon_exの優先度分岐を追加し、攻撃プランが定まっていない強制交代の場面でも優先されるようにする。

**Tech Stack:** Python 3.12 / pytest / uv

## Global Constraints

- コードコメントは日本語で書く（変数名・関数名は英語）。
- 既存のテスト規約に従う：`tests/test_lucario_agent.py` は `MockCardData` と `mock_card_table` フィクスチャを使い、個別テストで追加カードが必要な場合は `lm.card_table[ID] = MockCardData(...)` を直接代入する。
- デッキは60枚固定・ACE SPEC（Hero's Cape, 1159）は1枚のまま変更しない。
- 既存の `uv run pytest -q` が全件PASSする状態を常に維持する（実装完了後に必ず全体を再実行して回帰がないことを確認する）。
- 過去の実装（`docs/implementations/20260706-lucario-ogerpon-subattacker.md`）では「特性の効果無視部分はシミュレータが処理するためエージェント側の実装対象外」としていたが、今回の調査でこの前提が原因でCrustle戦において270ダメージの技を無限に選び続ける実害が確認されたため、その前提を本タスクで明示的に見直す。実装サマリーにこの経緯を明記すること。

---

### Task 1: デッキ構成変更（Solrock 3→2、Ogerpon_ex 1→2）

**Files:**
- Modify: `decks/lucario_20260621.py`
- Modify: `tests/test_lucario_deck.py`

**Interfaces:**
- Consumes: なし（デッキ定義ファイルのみ）
- Produces: `DECK`（`decks/lucario_20260621.py` のリスト定数）は変わらず60枚・タプルのリスト形式

- [ ] **Step 1: 既存テストを新しい期待値に書き換える**

`tests/test_lucario_deck.py` の以下2関数を置き換える：

```python
def test_ogerpon_ex_present_with_2_copies():
    counts = dict(DECK)
    assert counts[117] == 2  # Cornerstone Mask Ogerpon ex（1→2に増量）


def test_solrock_reduced_to_2():
    counts = dict(DECK)
    assert counts[676] == 2  # Solrock 3→2（オーガポンex増量のため1枚減）
```

（旧 `test_ogerpon_ex_present_with_1_copy` と `test_solrock_reduced_to_3` をこの2関数で置き換える。他の関数はそのまま。）

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_lucario_deck.py -v`
Expected: `test_ogerpon_ex_present_with_2_copies` と `test_solrock_reduced_to_2` が FAIL（現在の値は Ogerpon_ex=1, Solrock=3のため）

- [ ] **Step 3: デッキ定義を変更する**

`decks/lucario_20260621.py` の該当行を書き換える：

```python
    (676, 2),    # Solrock（3→2。オーガポンex増量のため1枚減）
    (675, 2),    # Lunatone
    (117, 2),    # Cornerstone Mask Ogerpon ex（1→2に増量。Crustle対策の要）
```

（`677, 678, 675` など他の行は変更しない。合計が60枚のままであることを確認する。）

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_lucario_deck.py -v`
Expected: 全件PASS（`test_deck_has_60_cards` を含む）

- [ ] **Step 5: コミット**

```bash
git add decks/lucario_20260621.py tests/test_lucario_deck.py
git commit -m "feat: オーガポンexを1→2枚に増量しSolrockを2枚に削減"
```

---

### Task 2: `calc_attack_plan` にCrustleの耐性チェックを追加する

**Files:**
- Modify: `src/lucario_agent/main.py:31`（定数追加）, `src/lucario_agent/main.py:306-313`（ダメージ計算ループ）
- Test: `tests/test_lucario_agent.py`（`TestCalcAttackPlan` の末尾に新クラス追加）

**Interfaces:**
- Consumes: `lm.Ogerpon_ex`（既存定数, main.py:31）, `lm.Mega_Lucario_ex`（既存定数, main.py:15）
- Produces: `lm.Crustle`（新規定数 = 345）。以降のタスクからは参照しない。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py` の `TestCalcAttackPlan` クラスの直後（391行目付近、`# ==================== Task 6:` コメントの前）に新しいテストクラスを追加する：

```python
class TestCrustleAbilityInteraction:
    """Crustle(345)の特性「ふしぎな岩の宿」対策のテスト"""

    def test_mega_lucario_ex_damage_nullified_by_crustle_ability(self):
        """Crustleの特性は相手のexポケモンの技ダメージを無効化する"""
        lm.card_table[lm.Crustle] = MockCardData(cardId=lm.Crustle, weakness=EnergyType.FIRE)
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Crustle, hp=150), prize_count=6)
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
        )
        assert result.remain_hp == 150  # 0ダメージなのでHPは変化しない

    def test_ogerpon_ex_bypasses_crustle_ability(self):
        """オーガポンexの「ぶちやぶる」は効果を計算しないためCrustleの特性を貫通する"""
        lm.card_table[lm.Crustle] = MockCardData(cardId=lm.Crustle, weakness=EnergyType.FIRE)
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6, 6])
        my_ps = make_player_state(active_pokemon=ogerpon, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Crustle, hp=150), prize_count=6)
        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True, my_prize=6,
        )
        assert result.remain_hp == 150 - 140

    def test_switches_to_ogerpon_ex_over_mega_lucario_ex_against_crustle(self):
        """Crustle相手にはメガルカリオexではなくオーガポンexへの切り替えが選ばれる"""
        lm.card_table[lm.Crustle] = MockCardData(cardId=lm.Crustle, weakness=EnergyType.FIRE)
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, hp=210, energies=[6, 6, 6])
        my_ps = make_player_state(active_pokemon=lucario, bench=[ogerpon], prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Crustle, hp=150), prize_count=6)
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=True, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
        )
        assert result.attacker  == 1  # my_cards=[active, *bench] → bench[0]はindex1
        assert result.remain_hp == 150 - 140
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestCrustleAbilityInteraction -v`
Expected: 3件とも FAIL（`lm.Crustle` が未定義で `AttributeError`、または `remain_hp` が期待値と異なる）

- [ ] **Step 3: `Crustle` 定数を追加する**

`src/lucario_agent/main.py:31`（`Ogerpon_ex = 117` の直後）に追加：

```python
Ogerpon_ex                 = 117
Crustle                     = 345  # 特性「ふしぎな岩の宿」：相手の「ポケモン【ex】」の技ダメージを無効化する壁ポケモン
```

- [ ] **Step 4: `calc_attack_plan` のダメージ計算にCrustle耐性チェックを追加する**

`src/lucario_agent/main.py:306-313` の該当ブロックを以下に書き換える：

```python
                damage = base_damage
                data   = card_table[op_pokemon.id]
                if my_pokemon.id != Ogerpon_ex:
                    if data.weakness == EnergyType.FIGHTING:
                        damage *= 2
                    elif data.resistance == EnergyType.FIGHTING:
                        damage -= 30
                if op_pokemon.id == Crustle and my_pokemon.id == Mega_Lucario_ex:
                    damage = 0  # Crustleの特性により、ex ポケモンの技ダメージは通らない
```

- [ ] **Step 5: テストが通ることを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestCrustleAbilityInteraction -v`
Expected: 3件ともPASS

- [ ] **Step 6: 既存の `TestCalcAttackPlan` に回帰がないことを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestCalcAttackPlan -v`
Expected: 既存9件も全てPASS（Crustle以外の相手には影響しない変更のため）

- [ ] **Step 7: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "fix: calc_attack_planにCrustleの特性耐性チェックを追加"
```

---

### Task 3: `_score_card_option` のSWITCH/TO_ACTIVEにオーガポンex優先度を追加する

**Files:**
- Modify: `src/lucario_agent/main.py:365-379`
- Test: `tests/test_lucario_agent.py`（新クラス `TestSwitchContext` を `TestDiscardContext` の直前に追加）

**Interfaces:**
- Consumes: `lm.Ogerpon_ex`（既存定数）, `lm._score_card_option`（既存関数、シグネチャ変更なし）
- Produces: なし（スコアリングの内部ロジックのみ）

**背景:** `calc_attack_plan` が攻撃プランを計算できていれば `o.index == current_plan.attacker - 1` の +100 加点で正しい切り替え先が選ばれる（Task 2で対応済み）。しかし、自分のアクティブポケモンが撃破された直後の強制交代（`TO_ACTIVE`）などプラン未確定の場面に備え、他の候補（Mega_Lucario_ex, Solrock, Riolu）と同様にOgerpon_ex単体でも優先度を持たせる。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py` の `TestDiscardContext` クラスの直前（494行目付近、`class TestDiscardContext:` の前）に追加：

```python
class TestSwitchContext:
    """SWITCH/TO_ACTIVEコンテキストでのオーガポンex優先度テスト"""

    def _score(self, energies):
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
        )

    def test_ogerpon_ex_prioritized_when_charged(self):
        """3エネルギー確保済み（ぶちやぶる可能）なら高優先度になる"""
        assert self._score([6, 6, 6]) == 3 * 2 + 20  # energy_count*2 + 充填済みボーナス

    def test_ogerpon_ex_low_priority_when_not_charged(self):
        """2エネルギー以下（ぶちやぶる不可）では優先度が低いまま"""
        assert self._score([6, 6]) == 2 * 2 + 6  # energy_count*2 + 充填中ボーナス
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestSwitchContext -v`
Expected: 2件とも FAIL（現状 `Ogerpon_ex` のケースがなく `score == energy_count * 2` のまま。3エネなら6、2エネなら4になり期待値と不一致）

- [ ] **Step 3: `_score_card_option` にOgerpon_exの分岐を追加する**

`src/lucario_agent/main.py:371-376` の該当ブロックを以下に書き換える：

```python
                if card.id == Mega_Lucario_ex:
                    score += 8 if len(my_state.prize) in (2, 3) else 20
                elif card.id == Solrock:
                    score += 5
                elif card.id == Riolu:
                    score += 4
                elif card.id == Ogerpon_ex:
                    score += 20 if energy_count >= 3 else 6
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestSwitchContext -v`
Expected: 2件ともPASS

- [ ] **Step 5: 既存のDISCARDコンテキストテスト（`TestDiscardContext::test_protects_ogerpon_ex` 含む）に回帰がないことを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestDiscardContext -v`
Expected: 全件PASS（変更はSWITCH/TO_ACTIVE分岐のみで、DISCARD分岐には影響しない）

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat: SWITCH/TO_ACTIVEスコアリングにオーガポンexの優先度分岐を追加"
```

---

### Task 4: 全体回帰テストと実装サマリー作成

**Files:**
- Create: `docs/implementations/20260707-crustle-counter-ogerpon-priority.md`

**Interfaces:**
- Consumes: Task 1〜3の変更内容とテスト結果
- Produces: なし（ドキュメントのみ）

- [ ] **Step 1: リポジトリ全体のテストを実行し、回帰がないことを確認する**

Run: `uv run pytest -q`
Expected: 全件PASS（Task 1〜3で追加した8件を含む）。件数は前回の248件から `+8`（デッキ2件+Crustle3件+Switch2件+旧2件置換で純増は差し引き調整、実行結果の総数をそのまま記録する）。

- [ ] **Step 2: 実装サマリーを作成する**

`docs/implementations/20260707-crustle-counter-ogerpon-priority.md` を以下の内容で作成する（Step 1で得た実際のテスト件数・出力に置き換えること）：

```markdown
# 実装サマリー：Crustle対策強化とオーガポンex優先ロジック導入

**実装日：** 2026-07-07
**関連計画書：** `docs/superpowers/plans/2026-07-07-crustle-counter-ogerpon-priority.md`
**関連バトルログ：** `data/battle_logs/84580427.json`（player1 Kagura_UT敗北）

## 背景

バトルログ84580427の解析で、相手デッキ（Crustle×4、Card ID 345、特性「ふしぎな
岩の宿」＝相手の「ポケモン【ex】」の技ダメージを無効化）に対し、メガルカリオex
の攻撃が試合を通じて一度も実際のダメージを与えられていなかったことが判明した
（HP_CHANGEログが常にvalue=0）。`calc_attack_plan`はこの特性を考慮しておらず、
メガブレイブ（270ダメージ）でKOできると誤って評価し続けていた。

一方、ベンチのオーガポンex（Card ID 117）は「ぶちやぶる」（相手のバトルポケモン
にかかっている効果を計算しない仕様）により、この特性を貫通して実ダメージを与え
られる可能性がある（ユーザーからの裁定指摘）。しかし試合を通じて一度もアクティブ
に切り替えられなかった。

なお過去の実装（`docs/implementations/20260706-lucario-ogerpon-subattacker.md`）
では「特性の効果無視部分はシミュレータが処理するためエージェント側の実装対象外」
としていたが、今回の調査でこの前提が原因で実害（270ダメージの技を無意味に選び
続け、120ダメージの反撃を毎ターン受けて敗北）が確認されたため、この前提を撤回し、
`calc_attack_plan`にCrustle固有の耐性チェックを追加する方針に切り替えた。

## 変更内容

### デッキ（`decks/lucario_20260621.py`）
- Solrock (676) を3枚→2枚に削減
- Cornerstone Mask Ogerpon ex (117) を1枚→2枚に増量

### エージェントロジック（`src/lucario_agent/main.py`）
- `calc_attack_plan`：Crustle(345)を相手にする場合、メガルカリオexの技ダメージを
  0として評価するチェックを追加。オーガポンexの「ぶちやぶる」は対象外（既存の
  weakness/resistance無視ロジックと同様、`my_pokemon.id`で分岐）。
- `_score_card_option`（SWITCH/TO_ACTIVE）：Ogerpon_exの優先度分岐を追加
  （3エネルギー以上で+20、未満で+6）。攻撃プラン未確定の強制交代場面での
  フォールバックとして機能する。

## テスト結果

（`uv run pytest -q` の実際の出力をここに貼る）

## 未対応事項

- Crustle以外の「特性による技ダメージ無効化」を持つ壁ポケモンが今後の対戦相手
  デッキに出てきた場合、同様の個別対応が必要になる（現状は345のみハードコード）。
  複数種類が確認された時点でテーブル化を検討する。
- オーガポンexの「ぶちやぶる」がCrustleの特性を実際に貫通するかどうかは、
  ユーザーの裁定情報に基づく実装であり、次戦の実バトルログで実際に貫通した
  ことを確認できていない。次回オーガポンexがCrustle相手に攻撃した試合が
  あれば、ログで実ダメージが入ったかを検証すること。
```

- [ ] **Step 3: コミット**

```bash
git add docs/implementations/20260707-crustle-counter-ogerpon-priority.md
git commit -m "docs: Crustle対策・オーガポンex優先ロジックの実装サマリーを追加"
```
