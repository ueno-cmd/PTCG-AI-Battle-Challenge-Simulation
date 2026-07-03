# ルカリオexデッキ 軽量版リビルド Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ルカリオexデッキをマクノシタ・ハリテヤマ撤去済みの軽量版に全面リビルドし、エージェントロジックをルールベース＋コンテキストバンディット（ε-greedy）のハイブリッドに刷新して、デッキアウト負けと速攻デッキへの脆弱性を解消する。

**Architecture:** `decks/lucario_20260621.py`（デッキ定義）と`src/lucario_agent/main.py`（エージェントロジック）の2ファイルを対象に、既存のスコアリング関数群（`_score_play_option`, `_score_card_option`, `calc_attack_plan`等）を段階的に改修する。`src/grimmsnarl_agent/main.py`のε-greedyパターン（`EPSILON`定数＋テスト注入可能な`_rng`）をそのまま踏襲する。

**Tech Stack:** Python 3.12 / uv / pytest / cg.api（コンペ提供ゲームAPI）

## Global Constraints

- デッキは必ず60枚、ACE SPECカードは1デッキ1枚まで（`data/EN_Card_Data.csv`の`Rule`列で確認）
- 既存コードスタイル：日本語コメント、関数はキーワード引数で呼び出す既存パターンを踏襲
- `uv run pytest -q` で全テストが通ることを各タスクの完了条件とする
- 設計書：`docs/superpowers/specs/2026-07-03-lucario-deck-revision-design.md`

---

### Task 1: デッキ定義の全面差し替え

**Files:**
- Modify: `decks/lucario_20260621.py`（全面差し替え）
- Create: `tests/test_lucario_deck.py`

**Interfaces:**
- Produces: `DECK: list[tuple[int, int]]`（カードID, 枚数のタプルリスト、合計60枚）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_deck.py` を新規作成：

```python
from decks.lucario_20260621 import DECK

ENERGY_IDS = {6}  # Basic {F} Energy
ACE_SPEC_IDS = {1159}  # Hero's Cape


def test_deck_has_60_cards():
    assert sum(count for _, count in DECK) == 60


def test_no_non_energy_card_exceeds_4_copies():
    for card_id, count in DECK:
        if card_id not in ENERGY_IDS:
            assert count <= 4, f"Card {card_id} が {count} 枚（上限4枚）"


def test_key_pokemon_present():
    ids = {card_id for card_id, _ in DECK}
    assert 677 in ids, "Riolu が不在"
    assert 678 in ids, "Mega Lucario ex が不在"
    assert 676 in ids, "Solrock が不在"
    assert 675 in ids, "Lunatone が不在"


def test_makuhita_hariyama_line_removed():
    ids = {card_id for card_id, _ in DECK}
    assert 673 not in ids, "Makuhita は今回の改修で削除されたはず"
    assert 674 not in ids, "Hariyama は今回の改修で削除されたはず"


def test_dusk_ball_and_carmine_and_switch_removed():
    ids = {card_id for card_id, _ in DECK}
    assert 1102 not in ids, "Dusk Ball は今回の改修で削除されたはず"
    assert 1192 not in ids, "Carmine は今回の改修で削除されたはず"
    assert 1123 not in ids, "Switch は今回の改修で削除されたはず"


def test_energy_count():
    fighting = sum(c for i, c in DECK if i == 6)
    assert fighting == 11


def test_ace_spec_does_not_exceed_1_copy():
    for card_id, count in DECK:
        if card_id in ACE_SPEC_IDS:
            assert count <= 1, f"ACE SPECカード {card_id} が {count} 枚（上限1枚）"


def test_no_duplicate_card_id_entries():
    ids = [card_id for card_id, _ in DECK]
    assert len(ids) == len(set(ids)), "同じcard_idが複数タプルに分かれている"


def test_new_cards_present_with_expected_counts():
    counts = dict(DECK)
    assert counts[1121] == 4  # Ultra Ball
    assert counts[1122] == 4  # Pokégear 3.0
    assert counts[1097] == 2  # Night Stretcher
    assert counts[1213] == 2  # Judge
    assert counts[1225] == 2  # Hilda
    assert counts[1229] == 1  # Wally's Compassion
    assert counts[1188] == 1  # Ciphermaniac's Codebreaking
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_lucario_deck.py -v`
Expected: FAIL（現行の`decks/lucario_20260621.py`はマクノシタ・ハリテヤマを含む旧構成のため`test_makuhita_hariyama_line_removed`等が失敗）

- [ ] **Step 3: デッキ定義を全面差し替え**

`decks/lucario_20260621.py` の内容を以下に置き換える：

```python
# ルカリオデッキ定義（20260703 軽量版リビルド）
# 2026-07-02大会優勝デッキをベースに、マクノシタ・ハリテヤマ系統を撤去した軽量プラン

DECK = [
    (677, 4),    # Riolu
    (678, 3),    # Mega Lucario ex
    (676, 4),    # Solrock
    (675, 2),    # Lunatone
    (1142, 4),   # Fighting Gong
    (1121, 4),   # Ultra Ball
    (1152, 2),   # Poké Pad
    (1141, 4),   # Premium Power Pro
    (1097, 2),   # Night Stretcher
    (1122, 4),   # Pokégear 3.0
    (1159, 1),   # Hero's Cape (ACE SPEC)
    (1227, 4),   # Lillie's Determination
    (1182, 4),   # Boss's Orders
    (1213, 2),   # Judge
    (1225, 2),   # Hilda
    (1229, 1),   # Wally's Compassion
    (1188, 1),   # Ciphermaniac's Codebreaking
    (1252, 1),   # Gravity Mountain
    (6, 11),     # Basic {F} Energy
]
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_lucario_deck.py -v`
Expected: PASS（全9件）

- [ ] **Step 5: コミット**

```bash
git add decks/lucario_20260621.py tests/test_lucario_deck.py
git commit -m "feat: ルカリオexデッキを軽量版に全面差し替え"
```

---

### Task 2: 不要ロジックの削除（マクノシタ・ハリテヤマ・Dusk Ball・Carmine・Switch）

このタスクは振る舞い変更のないリファクタリングであり、既存テストが通り続けることを確認しながら進める。`attacker2`（Hariyama専用のアタッカー準備フラグ）は他の全ポケモンに影響しないため完全に削除する。

**Files:**
- Modify: `src/lucario_agent/main.py`（全体にわたる削除）
- Modify: `tests/test_lucario_agent.py`（削除したカード・パラメータに追従）

**Interfaces:**
- Produces: `energy_score(pokemon, active, attacker1) -> int`（`attacker2`引数を削除）
- Produces: `_collect_field_state(my_state) -> tuple[field_counts, hand_counts, discard_counts, attacker1]`（4要素タプルに変更、`attacker2`を削除）

- [ ] **Step 1: 既存テストを新シグネチャに合わせて修正**

`tests/test_lucario_agent.py` の `mock_card_table` フィクスチャから以下の行を削除：

```python
        lm.Makuhita:              _card(lm.Makuhita),
        lm.Hariyama:              _card(lm.Hariyama, stage1=True),
```
```python
        lm.Switch:               _card(lm.Switch,               cardType=CardType.ITEM),
```
```python
        lm.Carmine:              _card(lm.Carmine,              cardType=CardType.SUPPORTER),
```
```python
        lm.Dusk_Ball:            _card(lm.Dusk_Ball,            cardType=CardType.ITEM),
```

`TestPokemonScore.test_stage1_gets_bonus` を、削除される`lm.Hariyama`の代わりにローカルの stage1 テスト用IDを使う形に書き換える：

```python
    def test_stage1_gets_bonus(self, mock_card_table):
        """stage1 ポケモンは同 HP の basic より高スコア"""
        mock_card_table[900] = MockCardData(cardId=900, stage1=True)
        p_stage1 = make_pokemon(id=900, hp=130)
        p_basic  = make_pokemon(id=lm.Riolu, hp=130)
        assert lm.pokemon_score(p_stage1) > lm.pokemon_score(p_basic)
```

`TestCollectFieldState.test_counts_active_and_bench` を、削除される`lm.Hariyama`の代わりに`lm.Solrock`を使う形に書き換える：

```python
    def test_counts_active_and_bench(self):
        riolu   = make_pokemon(id=lm.Riolu)
        solrock = make_pokemon(id=lm.Solrock)
        ps = make_player_state(active_pokemon=riolu, bench=[solrock])
        fc, hc, dc, a1 = lm._collect_field_state(ps)
        assert fc[lm.Riolu]   == 1
        assert fc[lm.Solrock] == 1
```

`TestCollectFieldState.test_attacker2_true_when_hariyama_has_3_energy` を削除する（Hariyama撤去に伴い`attacker2`概念自体が不要）。

`TestCollectFieldState.test_attacker1_true_when_lucario_has_2_energy` と `test_no_attacker1_when_energy_insufficient` の戻り値アンパックを4要素に修正：

```python
    def test_attacker1_true_when_lucario_has_2_energy(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[6, 6])
        ps = make_player_state(active_pokemon=lucario)
        _, _, _, a1 = lm._collect_field_state(ps)
        assert a1 is True

    def test_no_attacker1_when_energy_insufficient(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[6])  # 1 枚のみ
        ps = make_player_state(active_pokemon=lucario)
        _, _, _, a1 = lm._collect_field_state(ps)
        assert a1 is False
```

`TestEnergyScore` の全メソッドから`attacker2`引数（末尾の`False`）を削除：

```python
class TestEnergyScore:
    def test_active_slot_gets_bonus(self):
        p      = make_pokemon(id=lm.Riolu, energies=[])
        active = lm.energy_score(p, True,  False)
        bench  = lm.energy_score(p, False, False)
        assert active > bench

    def test_riolu_low_energy_gets_bonus(self):
        """Riolu にエネルギーが足りない場合はスコアが高い"""
        no_e  = make_pokemon(id=lm.Riolu, energies=[])
        two_e = make_pokemon(id=lm.Riolu, energies=[6, 6])
        assert lm.energy_score(no_e, False, False) > lm.energy_score(two_e, False, False)

    def test_lunatone_deprioritised(self):
        p_luna  = make_pokemon(id=lm.Lunatone, energies=[])
        p_riolu = make_pokemon(id=lm.Riolu,    energies=[])
        assert lm.energy_score(p_riolu, False, False) > lm.energy_score(p_luna, False, False)

    def test_solrock_deprioritised_after_one_energy(self):
        p_no  = make_pokemon(id=lm.Solrock, energies=[])
        p_one = make_pokemon(id=lm.Solrock, energies=[6])
        assert lm.energy_score(p_no, False, False) > lm.energy_score(p_one, False, False)

    def test_attacker1_flag_lowers_score(self):
        """既に attacker1 が準備できている場合、Riolu へのエネルギー優先度を下げる"""
        p            = make_pokemon(id=lm.Riolu, energies=[])
        without_flag = lm.energy_score(p, False, False)
        with_flag    = lm.energy_score(p, False, True)
        assert without_flag > with_flag
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: FAIL（`main.py`が未修正のため、`lm.Makuhita`等のAttributeErrorや引数個数不一致で失敗）

- [ ] **Step 3: `src/lucario_agent/main.py` を修正**

カードID定数ブロック（ファイル冒頭）を以下に置き換え：

```python
# ==================== カードID定数 ====================
Lunatone              = 675
Solrock               = 676
Riolu                 = 677
Mega_Lucario_ex       = 678
Premium_Power_Pro     = 1141
Fighting_Gong         = 1142
Poke_Pad              = 1152
Hero_Cape             = 1159
Boss_Orders           = 1182
Lillie_Determination  = 1227
Gravity_Mountain      = 1252
Basic_Fighting_Energy = 6
```

`energy_score()` を以下に置き換え：

```python
def energy_score(pokemon: Pokemon, active: bool, attacker1: bool) -> int:
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
    return score
```

`_collect_field_state()` を以下に置き換え：

```python
def _collect_field_state(my_state):
    """バトル場・ベンチ・手札・捨て山のカード枚数とアタッカー準備状況を返す"""
    field_counts   = defaultdict(int)
    hand_counts    = defaultdict(int)
    discard_counts = defaultdict(int)
    attacker1 = False

    for card in my_state.active + my_state.bench:
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id in (Riolu, Mega_Lucario_ex):
            if len(card.energies) >= 2:
                attacker1 = True

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    return field_counts, hand_counts, discard_counts, attacker1
```

`_analyze_main_options()` を以下に置き換え：

```python
def _analyze_main_options(obs: Observation, select, my_index: int) -> tuple[bool, bool, bool, bool]:
    """MAIN コンテキストのオプション一覧から行動フラグを抽出する"""
    can_switch         = False
    can_op_switch      = False
    can_use_mega_brave = False
    can_attack         = False

    for o in select.option:
        if o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            if card.id == Boss_Orders:
                can_op_switch = True
        elif o.type == OptionType.RETREAT:
            can_switch = True
        elif o.type == OptionType.ATTACK:
            can_attack = True
            if o.attackId == 983:  # Mega Brave
                can_use_mega_brave = True

    return can_switch, can_op_switch, can_use_mega_brave, can_attack
```

`calc_attack_plan()` 内の攻撃分岐（`if my_pokemon.id == Mega_Lucario_ex:` から `elif my_pokemon.id == Solrock:` までの部分）を以下に置き換え（Hariyama・Makuhita分岐を削除）：

```python
            if my_pokemon.id == Mega_Lucario_ex:
                if a == 0:
                    energy_required = 1
                    base_damage     = 130
                    base_score     += 60 * min(3, discard_counts[Basic_Fighting_Energy])
                else:
                    energy_required = 2
                    base_damage     = 270
                if a == 1 and my_prize in (2, 3):
                    base_score -= 500
            elif a == 1:
                break
            elif my_pokemon.id == Solrock:
                if field_counts[Lunatone] >= 1:
                    energy_required = 1
                    base_damage     = 70
```

`_score_card_option()` のシグネチャから`attacker2`を削除し、SWITCH/TO_ACTIVE分岐とTO_HAND分岐からMakuhita/Hariyama行を削除：

```python
def _score_card_option(obs, o, context, my_index, state, my_state,
                       field_counts, hand_counts, discard_counts,
                       attacker1, current_plan, ability_used_flag) -> int:
    """OptionType.CARD のスコアをコンテキスト別に返す"""
    card = get_card(obs, o.area, o.index, o.playerIndex)
    if card is None:
        return 0
    energy_count = len(card.energies) if isinstance(card, Pokemon) else 0

    match context:
        case SelectContext.SWITCH | SelectContext.TO_ACTIVE:
            if o.playerIndex == my_index:
                score = energy_count * 2
                if o.index == current_plan.attacker - 1:
                    score += 100
                if card.id == Mega_Lucario_ex:
                    score += 8 if len(my_state.prize) in (2, 3) else 20
                elif card.id == Solrock:
                    score += 5
                elif card.id == Riolu:
                    score += 4
            else:
                score = 100 if o.index == current_plan.target - 1 else 0
            return score

        case SelectContext.SETUP_ACTIVE_POKEMON:
            if card.id == Solrock:
                return 4 if state.firstPlayer != my_index else 2
            if card.id == Riolu:
                return 3
            return 0

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
            elif card.id == Basic_Fighting_Energy:
                score += 30 if not ability_used_flag or not state.energyAttached else -1
            return score

        case SelectContext.ATTACH_FROM:
            return energy_score(card, o.area == AreaType.ACTIVE, attacker1)

        case _:
            return 0
```

（`SelectContext.SETUP_ACTIVE_POKEMON`から`if card.id == Makuhita: return 1`の行も削除済み）

`_score_play_option()` からSwitch・Carmineの分岐を削除：

```python
def _score_play_option(obs, o, my_index, current_plan, can_attack,
                       state, hand_counts, field_counts, stadium_id) -> int:
    """OptionType.PLAY のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    data = card_table[card.id]
    if data.cardType == CardType.POKEMON:
        if card.id in (Lunatone, Solrock):
            return -1 if field_counts[card.id] >= 1 else 20000
        if card.id == Riolu:
            return -1 if field_counts[Riolu] + field_counts[Mega_Lucario_ex] >= 2 else 20000
        return 20000
    # トレーナーズ
    if card.id == Premium_Power_Pro:
        if state.supporterPlayed and current_plan.remain_hp <= 0:
            return -1
        if not can_attack:
            if not state.supporterPlayed and hand_counts[Boss_Orders] == 0 and hand_counts[Lillie_Determination] == 0:
                return 3050
            return -1
        return 5000
    if card.id == Boss_Orders:
        return 3200 if current_plan.target >= 1 else -1
    if card.id == Lillie_Determination:
        return 3100
    if card.id == Gravity_Mountain:
        return -1 if stadium_id == 0 else 10000
    return 10000
```

（元コードで`hand_counts[Carmine] > 0`だった条件は、Carmine撤去に伴い`hand_counts[Boss_Orders] == 0`に置き換えた。これは「有力なサポーターを持っていない時だけPremium Power Proの先出しを許容する」という元の意図を維持するための代替条件）

`_score_attach_option()` のシグネチャと呼び出しから`attacker2`を削除：

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
    if o.inPlayArea == AreaType.ACTIVE:
        if current_plan.attacker == 0 and current_plan.energy:
            score += 200
    else:
        if current_plan.attacker == 1 + o.inPlayIndex and current_plan.energy:
            score += 200
    return score
```

`_score_option()` のシグネチャと呼び出しから`attacker2`を削除：

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
                state, hand_counts, field_counts, stadium_id,
            )
        case OptionType.ATTACH:
            return _score_attach_option(obs, o, my_index, current_plan, attacker1)
        case OptionType.EVOLVE:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            return 9000 + len(pokemon.energies)
        case OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            return 1 if card.id == 1267 else 30000  # Lumiose City は低優先
        case OptionType.RETREAT:
            return 2000 if current_plan.attacker >= 1 else -1
        case OptionType.ATTACK:
            score = 1000
            if current_plan.attack_index == 1:
                score += 100 if o.attackId == 983 else 0  # Mega Brave 優先
            else:
                score += 0 if o.attackId == 983 else 100
            return score
        case _:
            return 0
```

（`OptionType.EVOLVE`の`if pokemon.id == Makuhita and current_plan.target == 0: score = -1`の分岐も削除済み）

`agent()` 内の`_collect_field_state`呼び出しと`_score_option`呼び出しから`attacker2`を削除：

```python
    field_counts, hand_counts, discard_counts, attacker1 = _collect_field_state(my_state)
    stadium_id = _get_stadium_id(state)

    can_switch = can_op_switch = can_use_mega_brave = can_attack = False
    if context == SelectContext.MAIN and state.turn >= 2:
        can_switch, can_op_switch, can_use_mega_brave, can_attack = _analyze_main_options(obs, select, my_index)
        plan = calc_attack_plan(
            obs, my_state, op_state, state,
            field_counts, hand_counts, discard_counts,
            can_switch, can_op_switch, can_use_mega_brave, can_attack,
            my_prize,
        )

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

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: PASS（全件）

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "refactor: マクノシタ・ハリテヤマ・Dusk Ball・Carmine・Switch関連ロジックを削除"
```

---

### Task 3: デッキアウト防止ゲート（共通しきい値）＋ リーリエの決心へ適用

**Files:**
- Modify: `src/lucario_agent/main.py`
- Modify: `tests/test_lucario_agent.py`

**Interfaces:**
- Consumes: `_score_play_option`（Task2で確定したシグネチャ）
- Produces: `_score_play_option(obs, o, my_index, current_plan, can_attack, state, my_state, hand_counts, field_counts, stadium_id) -> int`（`my_state`引数を追加）
- Produces: モジュール定数 `DECK_SAFETY_THRESHOLD = 15`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py` に以下を追加（ファイル末尾）：

```python
# ==================== Task 3: デッキアウト防止ゲート ====================
from unittest.mock import MagicMock as _MM


def _obs_with_hand(hand_cards, my_index=0, deck_count=50):
    obs = MagicMock()
    my_ps = make_player_state(hand=hand_cards, deck_count=deck_count)
    op_ps = make_player_state()
    players = [my_ps, op_ps] if my_index == 0 else [op_ps, my_ps]
    obs.current.players = players
    return obs, players[my_index]


class TestDeckSafetyGate:
    def test_lillie_determination_scores_normally_when_deck_healthy(self):
        card = Card(id=lm.Lillie_Determination, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=20)
        o = Option(type=OptionType.PLAY, index=0)
        state = _make_state()
        state.supporterPlayed = False
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=state, my_state=my_state,
            hand_counts=defaultdict(int), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 3100

    def test_lillie_determination_suppressed_when_deck_low(self):
        card = Card(id=lm.Lillie_Determination, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=10)
        o = Option(type=OptionType.PLAY, index=0)
        state = _make_state()
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=state, my_state=my_state,
            hand_counts=defaultdict(int), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1

    def test_threshold_boundary_is_inclusive(self):
        """山札残数がちょうどしきい値なら通常スコア"""
        card = Card(id=lm.Lillie_Determination, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=lm.DECK_SAFETY_THRESHOLD)
        o = Option(type=OptionType.PLAY, index=0)
        state = _make_state()
        state.supporterPlayed = False
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=state, my_state=my_state,
            hand_counts=defaultdict(int), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 3100
```

（既存の`_score_play_option`呼び出しテストが他にあれば、`my_state=`引数を追加する必要がある。現時点でこの関数を直接呼ぶテストはこの節が最初）

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestDeckSafetyGate -v`
Expected: FAIL（`_score_play_option()`が`my_state`引数を受け取らない、`DECK_SAFETY_THRESHOLD`が未定義）

- [ ] **Step 3: `src/lucario_agent/main.py` を修正**

カードID定数ブロックの直後に定数を追加：

```python
DECK_SAFETY_THRESHOLD = 15  # 山札残数がこれ未満なら大量ドロー系を抑制
```

`_score_play_option()` のシグネチャに`my_state`を追加し、Lillie's Determinationの分岐を修正：

```python
def _score_play_option(obs, o, my_index, current_plan, can_attack,
                       state, my_state, hand_counts, field_counts, stadium_id) -> int:
    """OptionType.PLAY のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    data = card_table[card.id]
    if data.cardType == CardType.POKEMON:
        if card.id in (Lunatone, Solrock):
            return -1 if field_counts[card.id] >= 1 else 20000
        if card.id == Riolu:
            return -1 if field_counts[Riolu] + field_counts[Mega_Lucario_ex] >= 2 else 20000
        return 20000
    # トレーナーズ
    if card.id == Premium_Power_Pro:
        if state.supporterPlayed and current_plan.remain_hp <= 0:
            return -1
        if not can_attack:
            if not state.supporterPlayed and hand_counts[Boss_Orders] == 0 and hand_counts[Lillie_Determination] == 0:
                return 3050
            return -1
        return 5000
    if card.id == Boss_Orders:
        return 3200 if current_plan.target >= 1 else -1
    if card.id == Lillie_Determination:
        return 3100 if my_state.deckCount >= DECK_SAFETY_THRESHOLD else -1
    if card.id == Gravity_Mountain:
        return -1 if stadium_id == 0 else 10000
    return 10000
```

`_score_option()` 内のPLAY呼び出しに`my_state`を追加：

```python
        case OptionType.PLAY:
            return _score_play_option(
                obs, o, my_index, current_plan, can_attack,
                state, my_state, hand_counts, field_counts, stadium_id,
            )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: PASS（全件）

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat: デッキアウト防止ゲートを追加しリーリエの決心に適用"
```

---

### Task 4: ルナサイクル（ルナトーンの特性）の新規実装

**Files:**
- Modify: `src/lucario_agent/main.py`
- Modify: `tests/test_lucario_agent.py`

**Interfaces:**
- Consumes: `DECK_SAFETY_THRESHOLD`（Task3で定義）
- Produces: `_score_option()`のABILITYケースにルナサイクル分岐を追加
- Produces: `_score_card_option()`に`SelectContext.DISCARD`ケースを追加（ルナサイクルの闘エネルギー捨て・ハイパーボールの2枚捨て共用）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py` に追加：

`_score_card_option`は内部で`get_card(obs, o.area, o.index, o.playerIndex)`を呼ぶため、`obs.current.players[0].hand = [card]`のように事前にカードをセットしておく必要がある点に注意する。

```python
# ==================== Task 4: ルナサイクル ====================
class TestDiscardContext:
    def _obs(self, hand_card):
        obs = MagicMock()
        my_ps = make_player_state(hand=[hand_card])
        obs.current.players = [my_ps, make_player_state()]
        return obs

    def test_prefers_spare_fighting_energy(self):
        energy = Card(id=lm.Basic_Fighting_Energy, serial=1, playerIndex=0)
        obs = self._obs(energy)
        score = lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int, {lm.Basic_Fighting_Energy: 2}),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )
        assert score == 50

    def test_protects_key_pokemon(self):
        riolu = Card(id=lm.Riolu, serial=1, playerIndex=0)
        obs = self._obs(riolu)
        score = lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )
        assert score == -100

    def test_protects_key_supporters(self):
        boss = Card(id=lm.Boss_Orders, serial=1, playerIndex=0)
        obs = self._obs(boss)
        score = lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )
        assert score == -50

    def test_default_trainer_is_low_priority_but_positive(self):
        stretcher = Card(id=1097, serial=1, playerIndex=0)  # Night Stretcher（まだ定数化前）
        obs = self._obs(stretcher)
        score = lm._score_card_option(
            obs, Option(type=OptionType.CARD, area=lm.AreaType.HAND, index=0, playerIndex=0),
            context=lm.SelectContext.DISCARD, my_index=0, state=_make_state(),
            my_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
        )
        assert score == 10


class TestLunaCycleAbilityScore:
    def _obs_with_active_lunatone(self):
        lunatone = Card(id=lm.Lunatone, serial=1, playerIndex=0)
        obs = MagicMock()
        obs.current.players = [make_player_state(), make_player_state()]
        return obs, lunatone

    def test_scores_high_when_deck_healthy(self, mock_card_table):
        obs, lunatone = self._obs_with_active_lunatone()
        obs.current.players[0].active = [lunatone]
        my_state = make_player_state(deck_count=20)
        score = lm._score_option(
            obs, Option(type=OptionType.ABILITY, area=lm.AreaType.ACTIVE, index=0),
            context=lm.SelectContext.MAIN, my_index=0, state=_make_state(),
            my_state=my_state, op_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), can_attack=False,
            stadium_id=0, ability_used_flag=False,
        )
        assert score == 8500

    def test_suppressed_when_deck_low(self, mock_card_table):
        obs, lunatone = self._obs_with_active_lunatone()
        obs.current.players[0].active = [lunatone]
        my_state = make_player_state(deck_count=10)
        score = lm._score_option(
            obs, Option(type=OptionType.ABILITY, area=lm.AreaType.ACTIVE, index=0),
            context=lm.SelectContext.MAIN, my_index=0, state=_make_state(),
            my_state=my_state, op_state=make_player_state(),
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), can_attack=False,
            stadium_id=0, ability_used_flag=False,
        )
        assert score == -1
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v -k "DiscardContext or LunaCycle"`
Expected: FAIL（`SelectContext.DISCARD`ケース未実装、ABILITY分岐にルナトーン処理なし）

- [ ] **Step 3: `src/lucario_agent/main.py` を修正**

`_score_card_option()` に `SelectContext.DISCARD` ケースを追加（`ATTACH_FROM`ケースの直前に挿入）：

```python
        case SelectContext.DISCARD:
            if o.playerIndex != my_index:
                return 0
            if card.id == Basic_Fighting_Energy:
                return 50 if hand_counts[Basic_Fighting_Energy] >= 2 else -20
            if card.id in (Riolu, Mega_Lucario_ex, Solrock, Lunatone):
                return -100
            if card.id in (Boss_Orders, Lillie_Determination):
                return -50
            return 10
```

`_score_option()` のABILITYケースを修正：

```python
        case OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if card.id == 1267:
                return 1  # Lumiose City は低優先
            if card.id == Lunatone:
                return 8500 if my_state.deckCount >= DECK_SAFETY_THRESHOLD else -1
            return 30000
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: PASS（全件）

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat: ルナサイクル特性の判定ロジックとDISCARDコンテキストを追加"
```

---

### Task 5: 新規アイテム・サポーターのスコアリング追加

**Files:**
- Modify: `src/lucario_agent/main.py`
- Modify: `tests/test_lucario_agent.py`

**Interfaces:**
- Produces: カード定数 `Ultra_Ball=1121`, `Pokegear=1122`, `Night_Stretcher=1097`, `Judge=1213`, `Hilda=1225`, `Wally_Compassion=1229`, `Ciphermaniac_Codebreaking=1188`
- Produces: `_score_play_option()`に上記7枚のスコアリング分岐を追加（シグネチャに`my_state`を追加：Wally's Compassionの判定にメガルカリオexのHP参照が必要なため）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py` の`mock_card_table`フィクスチャに新規カードを追加：

```python
        lm.Ultra_Ball:            _card(lm.Ultra_Ball,            cardType=CardType.ITEM),
        lm.Pokegear:              _card(lm.Pokegear,              cardType=CardType.ITEM),
        lm.Night_Stretcher:       _card(lm.Night_Stretcher,       cardType=CardType.ITEM),
        lm.Judge:                 _card(lm.Judge,                 cardType=CardType.SUPPORTER),
        lm.Hilda:                 _card(lm.Hilda,                 cardType=CardType.SUPPORTER),
        lm.Wally_Compassion:      _card(lm.Wally_Compassion,      cardType=CardType.SUPPORTER),
        lm.Ciphermaniac_Codebreaking: _card(lm.Ciphermaniac_Codebreaking, cardType=CardType.SUPPORTER),
```

続けて新規テストクラスを追加：

```python
# ==================== Task 5: 新規カードのスコアリング ====================
class TestNewCardScoring:
    def _score(self, card_id, my_state=None, hand_counts=None, field_counts=None,
               attacker1=False, can_attack=False, state=None):
        obs = MagicMock()
        my_ps = my_state or make_player_state(hand=[Card(id=card_id, serial=1, playerIndex=0)])
        obs.current.players = [my_ps, make_player_state()]
        return lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=can_attack,
            state=state or _make_state(), my_state=my_ps,
            hand_counts=hand_counts or defaultdict(int),
            field_counts=field_counts or defaultdict(int), stadium_id=0,
        )

    def test_ultra_ball_prioritised_when_riolu_not_found(self):
        score = self._score(lm.Ultra_Ball, hand_counts=defaultdict(int))
        assert score == 6000

    def test_ultra_ball_still_positive_when_riolu_present(self):
        fc = defaultdict(int, {lm.Riolu: 1})
        score = self._score(lm.Ultra_Ball, field_counts=fc)
        assert score == 5500

    def test_pokegear_flat_priority(self):
        assert self._score(lm.Pokegear) == 5200

    def test_night_stretcher_flat_priority(self):
        assert self._score(lm.Night_Stretcher) == 4800

    def test_hilda_flat_priority(self):
        assert self._score(lm.Hilda) == 5300

    def test_ciphermaniac_codebreaking_flat_priority(self):
        assert self._score(lm.Ciphermaniac_Codebreaking) == 5100

    def test_judge_used_when_hand_is_dead(self):
        score = self._score(
            lm.Judge, hand_counts=defaultdict(int), attacker1=False,
        )
        assert score == 7000

    def test_judge_held_when_attacker_ready(self):
        my_ps = make_player_state(hand=[Card(id=lm.Judge, serial=1, playerIndex=0)])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        score = lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=False,
            state=_make_state(), my_state=my_ps,
            hand_counts=defaultdict(int, {lm.Basic_Fighting_Energy: 1}),
            field_counts=defaultdict(int), stadium_id=0,
        )
        assert score == -1

    def test_wally_compassion_used_when_lucario_damaged(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=200, max_hp=440)
        my_ps = make_player_state(
            active_pokemon=lucario,
            hand=[Card(id=lm.Wally_Compassion, serial=1, playerIndex=0)],
        )
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        score = lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=False,
            state=_make_state(), my_state=my_ps,
            hand_counts=defaultdict(int), field_counts=defaultdict(int), stadium_id=0,
        )
        assert score == 6800

    def test_wally_compassion_held_when_lucario_full_hp(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=440, max_hp=440)
        my_ps = make_player_state(
            active_pokemon=lucario,
            hand=[Card(id=lm.Wally_Compassion, serial=1, playerIndex=0)],
        )
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        score = lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=lm.AttackPlan(), can_attack=False,
            state=_make_state(), my_state=my_ps,
            hand_counts=defaultdict(int), field_counts=defaultdict(int), stadium_id=0,
        )
        assert score == -1
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestNewCardScoring -v`
Expected: FAIL（`lm.Ultra_Ball`等の定数が未定義でAttributeError）

- [ ] **Step 3: `src/lucario_agent/main.py` を修正**

カードID定数ブロックに追加：

```python
Ultra_Ball                 = 1121
Pokegear                   = 1122
Night_Stretcher            = 1097
Judge                      = 1213
Hilda                      = 1225
Wally_Compassion           = 1229
Ciphermaniac_Codebreaking  = 1188
```

`_score_play_option()` に以下を追加（`if card.id == Gravity_Mountain:` の直前に挿入）：

```python
    if card.id == Ultra_Ball:
        already_found = field_counts[Riolu] + field_counts[Mega_Lucario_ex] + hand_counts[Riolu] + hand_counts[Mega_Lucario_ex]
        return 6000 if already_found == 0 else 5500
    if card.id == Pokegear:
        return 5200
    if card.id == Night_Stretcher:
        return 4800
    if card.id == Judge:
        return 7000 if hand_counts[Basic_Fighting_Energy] == 0 and not attacker1 else -1
    if card.id == Hilda:
        return 5300
    if card.id == Ciphermaniac_Codebreaking:
        return 5100
    if card.id == Wally_Compassion:
        my_lucario = next(
            (p for p in ([my_state.active[0]] if my_state.active else []) + list(my_state.bench)
             if p is not None and p.id == Mega_Lucario_ex),
            None,
        )
        if my_lucario is not None and my_lucario.hp < my_lucario.maxHp:
            return 6800
        return -1
```

`_score_play_option()` のシグネチャに `attacker1: bool` を追加し、`_score_option()` のPLAY呼び出しに `attacker1` を渡すよう更新：

```python
def _score_play_option(obs, o, my_index, current_plan, can_attack,
                       state, my_state, hand_counts, field_counts, stadium_id,
                       attacker1: bool = False) -> int:
```

```python
        case OptionType.PLAY:
            return _score_play_option(
                obs, o, my_index, current_plan, can_attack,
                state, my_state, hand_counts, field_counts, stadium_id,
                attacker1,
            )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: PASS（全件）

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat: ハイパーボール・ポケギア3.0・夜のタンカ・ジャッジマン・トウコ・ミツルの思いやり・暗号マニアの解読のスコアリングを追加"
```

---

### Task 6: ボスの指令のε-greedy化

`src/grimmsnarl_agent/main.py`のパターンをそのまま移植する。

**Files:**
- Modify: `src/lucario_agent/main.py`
- Modify: `tests/test_lucario_agent.py`

**Interfaces:**
- Produces: モジュール定数 `EPSILON = 0.28`、`_rng = random.Random()`
- Produces: `_score_play_option(..., attacker1=False, rng: "random.Random | None" = None) -> int`（`rng`引数を追加）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py` に追加：

```python
# ==================== Task 6: ボスの指令のε-greedy ====================
class _StubRng:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


class TestBossOrdersEpsilonGreedy:
    def _score(self, target, remain_hp, rng=None):
        my_ps = make_player_state(hand=[Card(id=lm.Boss_Orders, serial=1, playerIndex=0)])
        obs = MagicMock()
        obs.current.players = [my_ps, make_player_state()]
        plan = lm.AttackPlan(attacker=0, target=target, attack_index=0, remain_hp=remain_hp)
        return lm._score_play_option(
            obs, Option(type=OptionType.PLAY, index=0), my_index=0,
            current_plan=plan, can_attack=True,
            state=_make_state(), my_state=my_ps,
            hand_counts=defaultdict(int), field_counts=defaultdict(int),
            stadium_id=0, attacker1=True, rng=rng,
        )

    def test_holds_when_no_target(self):
        assert self._score(target=-1, remain_hp=0) == -1

    def test_uses_immediately_when_ko_confirmed(self):
        assert self._score(target=1, remain_hp=0) == 8800

    def test_explores_when_rng_below_epsilon(self):
        score = self._score(target=1, remain_hp=50, rng=_StubRng(0.1))
        assert score == 6000

    def test_holds_when_rng_above_epsilon(self):
        score = self._score(target=1, remain_hp=50, rng=_StubRng(0.9))
        assert score == -1
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestBossOrdersEpsilonGreedy -v`
Expected: FAIL（`_score_play_option()`が`rng`引数を受け付けない、ボスの指令が固定スコア3200のまま）

- [ ] **Step 3: `src/lucario_agent/main.py` を修正**

ファイル冒頭のimportブロックに`random`を追加：

```python
import os
import random
from collections import defaultdict
from dataclasses import dataclass
```

カードID定数ブロックの後、`DECK_SAFETY_THRESHOLD`の隣に追加：

```python
EPSILON = 0.28  # 温存判断時に探索的先出しをする確率
_rng    = random.Random()  # 本番用の実乱数。テストではスタブを注入する
```

`_score_play_option()` のシグネチャを更新し、Boss_Ordersの分岐を修正：

```python
def _score_play_option(obs, o, my_index, current_plan, can_attack,
                       state, my_state, hand_counts, field_counts, stadium_id,
                       attacker1: bool = False,
                       rng: "random.Random | None" = None) -> int:
    """OptionType.PLAY のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    data = card_table[card.id]
    if data.cardType == CardType.POKEMON:
        if card.id in (Lunatone, Solrock):
            return -1 if field_counts[card.id] >= 1 else 20000
        if card.id == Riolu:
            return -1 if field_counts[Riolu] + field_counts[Mega_Lucario_ex] >= 2 else 20000
        return 20000
    # トレーナーズ
    if card.id == Premium_Power_Pro:
        if state.supporterPlayed and current_plan.remain_hp <= 0:
            return -1
        if not can_attack:
            if not state.supporterPlayed and hand_counts[Boss_Orders] == 0 and hand_counts[Lillie_Determination] == 0:
                return 3050
            return -1
        return 5000
    if card.id == Boss_Orders:
        if current_plan.target < 1:
            return -1  # 対象不在なら温存
        if current_plan.remain_hp <= 0:
            return 8800  # 即使用（確定KO）
        active_rng = rng if rng is not None else _rng
        if active_rng.random() < EPSILON:
            return 6000  # 探索的先出し
        return -1  # 温存
    if card.id == Lillie_Determination:
        return 3100 if my_state.deckCount >= DECK_SAFETY_THRESHOLD else -1
    if card.id == Gravity_Mountain:
        return -1 if stadium_id == 0 else 10000
    if card.id == Ultra_Ball:
        already_found = field_counts[Riolu] + field_counts[Mega_Lucario_ex] + hand_counts[Riolu] + hand_counts[Mega_Lucario_ex]
        return 6000 if already_found == 0 else 5500
    if card.id == Pokegear:
        return 5200
    if card.id == Night_Stretcher:
        return 4800
    if card.id == Judge:
        return 7000 if hand_counts[Basic_Fighting_Energy] == 0 and not attacker1 else -1
    if card.id == Hilda:
        return 5300
    if card.id == Ciphermaniac_Codebreaking:
        return 5100
    if card.id == Wally_Compassion:
        my_lucario = next(
            (p for p in ([my_state.active[0]] if my_state.active else []) + list(my_state.bench)
             if p is not None and p.id == Mega_Lucario_ex),
            None,
        )
        if my_lucario is not None and my_lucario.hp < my_lucario.maxHp:
            return 6800
        return -1
    return 10000
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: PASS（全件）

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat: ボスの指令をグリムスナールex方式のε-greedy判断に変更"
```

---

### Task 7: メガブレイブのε-greedy化 ＋ 統合テスト・実装サマリー作成

**Files:**
- Modify: `src/lucario_agent/main.py`
- Modify: `tests/test_lucario_agent.py`
- Create: `docs/implementations/20260703-lucario-deck-revision.md`

**Interfaces:**
- Produces: `calc_attack_plan(..., rng: "random.Random | None" = None) -> AttackPlan`（`rng`引数を追加）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py` の `TestCalcAttackPlan` クラスに追加：

```python
    def test_mega_brave_held_when_normal_attack_already_ko(self):
        """通常攻撃(130)で確定KOできる相手には、メガブレイブを温存し通常攻撃を選ぶ"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=100), prize_count=6)
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
        )
        assert result.attack_index == 0

    def test_mega_brave_explores_when_rng_below_epsilon_and_no_ko_either_way(self):
        """どちらの技でも確定KOできない場面で、rngがEPSILON未満ならメガブレイブを選ぶ"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=1000), prize_count=6)
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
            rng=_StubRng(0.1),
        )
        assert result.attack_index == 1

    def test_mega_brave_holds_when_rng_above_epsilon_and_no_ko_either_way(self):
        """どちらの技でも確定KOできない場面で、rngがEPSILON以上なら通常攻撃を選ぶ"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=1000), prize_count=6)
        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True, my_prize=6,
            rng=_StubRng(0.9),
        )
        assert result.attack_index == 0
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest tests/test_lucario_agent.py::TestCalcAttackPlan -v`
Expected: FAIL（`calc_attack_plan()`が`rng`引数を受け付けない、メガブレイブ温存ロジックが未実装）

- [ ] **Step 3: `src/lucario_agent/main.py` を修正**

`calc_attack_plan()` のシグネチャに `rng` を追加：

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

`for j, op_pokemon in enumerate(op_cards):` ループ内、`score += base_score` の直後・`if len(op_state.prize) <= prize:` の直前に以下を挿入：

```python
                if my_pokemon.id == Mega_Lucario_ex and a == 1:
                    base_dmg_normal = 130
                    if data.weakness == EnergyType.FIGHTING:
                        base_dmg_normal *= 2
                    elif data.resistance == EnergyType.FIGHTING:
                        base_dmg_normal -= 30
                    if op_pokemon.hp <= base_dmg_normal:
                        score -= 1000  # 通常攻撃で足りるならメガブレイブは温存
                    elif op_pokemon.hp > damage:
                        active_rng = rng if rng is not None else _rng
                        if active_rng.random() >= EPSILON:
                            score -= 300  # 探索に外れたら温存寄り
```

`if a == 1 and my_prize in (2, 3): base_score -= 500` の行は削除する（上記の新ロジックに置き換え）。修正後の`calc_attack_plan`本体は次の形になる：

```python
            if my_pokemon.id == Mega_Lucario_ex:
                if a == 0:
                    energy_required = 1
                    base_damage     = 130
                    base_score     += 60 * min(3, discard_counts[Basic_Fighting_Energy])
                else:
                    energy_required = 2
                    base_damage     = 270
            elif a == 1:
                break
            elif my_pokemon.id == Solrock:
                if field_counts[Lunatone] >= 1:
                    energy_required = 1
                    base_damage     = 70
```

（`base_score -= 500`の行を削除。`a == 1 and my_prize in (2, 3)`は新しいメガブレイブ判断ロジックに完全に置き換わるため）

`agent()` 内の `calc_attack_plan(...)` 呼び出しは変更不要（`rng`はデフォルト`None`で本番は`_rng`にフォールバックするため）。

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest tests/test_lucario_agent.py -v`
Expected: PASS（全件、既存の`test_lucario_plans_mega_brave_when_it_can_ko`・`test_fighting_weakness_doubles_damage`等も含め全て通ること）

- [ ] **Step 5: リポジトリ全体のテストを実行**

Run: `uv run pytest -q`
Expected: 全件PASS（既存の他デッキ・他エージェントのテストに影響がないことを確認）

- [ ] **Step 6: 実装サマリーを作成**

`docs/implementations/20260703-lucario-deck-revision.md` を新規作成し、以下を記載する：
- 背景（バトルログ8件の解析結果と2つの敗因）
- 変更内容（デッキ構成、削除ロジック、新規カードスコアリング、ルナサイクル、デッキアウトゲート、ボスの指令・メガブレイブのε-greedy化）
- テスト結果（`uv run pytest -q`の全体件数とPASS状況）
- 未対応・次回持ち越し事項（しきい値15枚は仮置き、ミツルの思いやり・暗号マニアの解読の一部follow-up選択肢は汎用スコアリングに委ねている点、83574179で見られたリオル展開遅延の根本原因はハイパーボール導入後の実戦ログで再検証が必要な点）

- [ ] **Step 7: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py docs/implementations/20260703-lucario-deck-revision.md
git commit -m "feat: メガブレイブをε-greedy判断に変更し実装サマリーを作成"
```

---

## 未確定・次回以降の検討事項

- `DECK_SAFETY_THRESHOLD = 15` は仮置きの値。次回以降のバトルログで有効性を確認し調整する
- ミツルの思いやり（対象複数時の選択）・暗号マニアの解読（山札上2枚の並び替え）の詳細なfollow-up選択ロジックは、実際にどの`SelectContext`が発火するか確認できていないため、汎用スコアリング（デフォルト0点でのタイブレーク）に委ねている。実戦ログで挙動確認後に専用ロジックを追加するか判断する
- 83574179（対アラカザム）で見られた「リオル展開がターン8までかかった」現象の根本原因は未解明のまま。今回のハイパーボール導入で改善するかは次回のバトルログで検証する
