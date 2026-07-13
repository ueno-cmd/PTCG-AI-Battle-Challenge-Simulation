# ルカリオexデッキ 山札セーフティ移植 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/lucario_agent/main.py`の山札対策を、グリムスナールexで実戦検証済みの`_safe_draws`方式（山札残数−残りプライズ数−1を基準に、ドロー系カードを一律ゲート）に置き換え、実ログ85626724で確認された「プライズ有利なのに山札切れで敗北」を防ぐ

**Architecture:** `_safe_draws(my_state)`と`_deck_consumption(card_id, my_state, hand_counts)`という2つの純粋関数を新設し、`_score_play_option()`冒頭のガード節と`_score_option()`のLunatone特性分岐に組み込む。グリムスナールと異なり`FieldState`ラッパーは使わず、既存コードのスタイルに合わせて`my_state`・`hand_counts`を直接受け取る。フラグ化やKaggle校正実験は行わず直接有効化する（ユーザー承認済み）。

**Tech Stack:** Python 3.12 / uv / pytest

**設計書:** `docs/superpowers/specs/2026-07-13-lucario-deck-safety-design.md`

## Global Constraints

- コードコメント・ドキュメントは日本語（変数名・関数名は英語）
- テストコマンドは`uv run pytest -q`（リポジトリ全体。開始時点345件全PASSが前提）
- デッキ本体（`decks/lucario_20260621.py`）は変更しない（deck.csv再生成不要）
- 作業ブランチ: `feature/lucario-deck-safety`（Task 1冒頭で作成し、Task 5でmainへfast-forwardマージ）
- カードごとの山札消費量は設計書「B. カードごとの消費枚数」の表の値をそのまま使う（Lillie's Determination/Judgeは手札依存の可変式、Hilda=2固定、Pokegear/Ultra Ball/Poké Pad=1固定、Ciphermaniac's Codebreaking/Wally's Compassion/Night StretcherはNone＝ゲート対象外）

---

### Task 1: `_safe_draws`・`_deck_consumption`ヘルパーの新設

**Files:**
- Modify: `src/lucario_agent/main.py`（`_score_play_option`の直前、436行目の空行と442行目の`def _score_play_option`の間に追加）
- Test: `tests/test_lucario_agent.py`（538行目`class TestDeckSafetyGate:`の直前に追加）

**Interfaces:**
- Produces: `_safe_draws(my_state) -> int`、`_deck_consumption(card_id: int, my_state, hand_counts: defaultdict) -> "int | None"`（Task 2・3が利用）

- [ ] **Step 0: ブランチ作成**

```bash
git checkout -b feature/lucario-deck-safety
```

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の538行目`class TestDeckSafetyGate:`の直前（526行目の`_obs_with_hand`定義の後、空行2つを挟んだ場所）に追加：

```python
# ==================== 山札セーフティヘルパー ====================
class TestSafeDraws:
    def test_healthy_deck(self):
        my_state = make_player_state(deck_count=20, prize_count=6)
        assert lm._safe_draws(my_state) == 13

    def test_low_deck_with_few_prizes_left(self):
        my_state = make_player_state(deck_count=5, prize_count=2)
        assert lm._safe_draws(my_state) == 2

    def test_can_go_negative(self):
        """山札が残りプライズ数を下回っていれば負数（=即座に全ドロー系を止める）"""
        my_state = make_player_state(deck_count=1, prize_count=6)
        assert lm._safe_draws(my_state) == -6


class TestDeckConsumption:
    def test_lillie_determination_draws_8_when_6_prizes_left(self):
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Lillie_Determination: 3})
        assert lm._deck_consumption(lm.Lillie_Determination, my_state, hand_counts) == 6

    def test_lillie_determination_draws_6_when_prizes_taken(self):
        my_state = make_player_state(prize_count=3)
        hand_counts = defaultdict(int, {lm.Lillie_Determination: 1})
        assert lm._deck_consumption(lm.Lillie_Determination, my_state, hand_counts) == 6

    def test_judge_draws_4(self):
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Judge: 2})
        assert lm._deck_consumption(lm.Judge, my_state, hand_counts) == 3

    def test_hilda_is_fixed_2(self):
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Hilda: 1})
        assert lm._deck_consumption(lm.Hilda, my_state, hand_counts) == 2

    def test_pokegear_is_fixed_1(self):
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Pokegear: 1})
        assert lm._deck_consumption(lm.Pokegear, my_state, hand_counts) == 1

    def test_ultra_ball_is_fixed_1(self):
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Ultra_Ball: 1})
        assert lm._deck_consumption(lm.Ultra_Ball, my_state, hand_counts) == 1

    def test_poke_pad_is_fixed_1(self):
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Poke_Pad: 1})
        assert lm._deck_consumption(lm.Poke_Pad, my_state, hand_counts) == 1

    def test_ciphermaniac_codebreaking_is_not_gated(self):
        """山札の一番上に戻すだけで山札枚数は変わらない"""
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Ciphermaniac_Codebreaking: 1})
        assert lm._deck_consumption(lm.Ciphermaniac_Codebreaking, my_state, hand_counts) is None

    def test_wally_compassion_is_not_gated(self):
        """山札に一切触れない効果"""
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Wally_Compassion: 1})
        assert lm._deck_consumption(lm.Wally_Compassion, my_state, hand_counts) is None

    def test_night_stretcher_is_not_gated(self):
        """捨て札から回収するだけで山札には触れない"""
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Night_Stretcher: 1})
        assert lm._deck_consumption(lm.Night_Stretcher, my_state, hand_counts) is None

    def test_unrelated_card_returns_none(self):
        my_state = make_player_state(prize_count=6)
        hand_counts = defaultdict(int, {lm.Boss_Orders: 1})
        assert lm._deck_consumption(lm.Boss_Orders, my_state, hand_counts) is None
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestSafeDraws tests/test_lucario_agent.py::TestDeckConsumption -v`
Expected: FAIL（`AttributeError: module 'lucario_agent.main' has no attribute '_safe_draws'`）

- [ ] **Step 3: 最小実装を書く**

`src/lucario_agent/main.py`の436行目（空行）と442行目（`def _score_play_option`）の間に追加：

```python
# ==================== 山札セーフティ（battlecore B方式） ====================
def _safe_draws(my_state) -> int:
    """安全に消費できる山札枚数。残りプライズ数を残りターン数の見積もりとして使い、
    毎ターンの必須ドロー分を温存する（デッキアウト防止。実ログ85626724が直接の動機）"""
    return my_state.deckCount - len(my_state.prize) - 1


def _deck_consumption(card_id: int, my_state, hand_counts: defaultdict) -> "int | None":
    """このカードを使った場合の山札の正味消費枚数。山札を消費しない札はNone"""
    hand_count = sum(hand_counts.values())
    if card_id == Lillie_Determination:
        draws = 8 if len(my_state.prize) == 6 else 6
        return max(0, draws - (hand_count - 1))
    if card_id == Judge:
        return max(0, 4 - (hand_count - 1))
    if card_id == Hilda:
        return 2
    if card_id in (Pokegear, Ultra_Ball, Poke_Pad):
        return 1
    return None
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestSafeDraws tests/test_lucario_agent.py::TestDeckConsumption -v`
Expected: 13 passed

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat: 山札セーフティのヘルパー関数を新設（_safe_draws/_deck_consumption）"
```

---

### Task 2: PLAYコンテキストへの組み込み（ミツルの思いやり・ジャッジマン・ヒルダ・ポケギア3.0・ハイパーボール・ポケパッド）

**Files:**
- Modify: `src/lucario_agent/main.py:442-476`（`_score_play_option`冒頭にガード節を追加）
- Modify: `tests/test_lucario_agent.py:529-581`（`_obs_with_hand`に`prize_count`引数を追加し`TestDeckSafetyGate`を新方式に更新、新規カード5種のテストクラスを追加）

**Interfaces:**
- Consumes: `lm._safe_draws(my_state)`, `lm._deck_consumption(card_id, my_state, hand_counts)`（Task 1で新設）
- Produces: `_obs_with_hand(hand_cards, my_index=0, deck_count=50, prize_count=6)`（Task 3以降でも使えるよう`prize_count`引数を追加）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`_obs_with_hand`定義（529-535行目）を次のように置き換える：

```python
def _obs_with_hand(hand_cards, my_index=0, deck_count=50, prize_count=6):
    obs = MagicMock()
    my_ps = make_player_state(hand=hand_cards, deck_count=deck_count, prize_count=prize_count)
    op_ps = make_player_state()
    players = [my_ps, op_ps] if my_index == 0 else [op_ps, my_ps]
    obs.current.players = players
    return obs, players[my_index]


def _hand_counts(cards):
    """テスト用：手札カードリストからhand_counts(defaultdict)を作る"""
    counts = defaultdict(int)
    for c in cards:
        counts[c.id] += 1
    return counts
```

続けて、`class TestDeckSafetyGate:`（538行目）以下のブロック全体を次の内容で置き換える（`test_threshold_boundary_is_inclusive`は`_safe_draws`ベースの境界値テストに更新）：

```python
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
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
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
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1

    def test_allowed_when_consumption_equals_safe_draws(self):
        """手札1枚・プライズ6枚時のミツルの思いやりは消費8枚。山札15枚ならsafe_draws=8で丁度一致→許可"""
        card = Card(id=lm.Lillie_Determination, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=15)
        o = Option(type=OptionType.PLAY, index=0)
        state = _make_state()
        state.supporterPlayed = False
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=state, my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 3100

    def test_suppressed_when_consumption_exceeds_safe_draws(self):
        """山札14枚ならsafe_draws=7<消費8枚→抑制"""
        card = Card(id=lm.Lillie_Determination, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=14)
        o = Option(type=OptionType.PLAY, index=0)
        state = _make_state()
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=state, my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1


class TestJudgeDeckSafety:
    def test_scores_normally_when_deck_healthy(self):
        card = Card(id=lm.Judge, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=12)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 7000

    def test_suppressed_when_deck_low(self):
        card = Card(id=lm.Judge, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=10)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1


class TestHildaDeckSafety:
    def test_scores_normally_when_deck_healthy(self):
        card = Card(id=lm.Hilda, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=10)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 5300

    def test_suppressed_when_deck_low(self):
        card = Card(id=lm.Hilda, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=8)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1


class TestPokegearDeckSafety:
    def test_scores_normally_when_deck_healthy(self):
        card = Card(id=lm.Pokegear, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=8)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 5200

    def test_suppressed_when_deck_low(self):
        card = Card(id=lm.Pokegear, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=7)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1


class TestUltraBallDeckSafety:
    def test_scores_normally_when_deck_healthy(self):
        card = Card(id=lm.Ultra_Ball, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=8)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 6000

    def test_suppressed_when_deck_low(self):
        card = Card(id=lm.Ultra_Ball, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=7)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1


class TestPokePadDeckSafety:
    def test_scores_normally_when_deck_healthy(self):
        """Poké Padは専用スコアリングが無く汎用デフォルト10000にフォールバックする"""
        card = Card(id=lm.Poke_Pad, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=8)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 10000

    def test_suppressed_when_deck_low(self):
        card = Card(id=lm.Poke_Pad, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=7)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestDeckSafetyGate tests/test_lucario_agent.py::TestJudgeDeckSafety tests/test_lucario_agent.py::TestHildaDeckSafety tests/test_lucario_agent.py::TestPokegearDeckSafety tests/test_lucario_agent.py::TestUltraBallDeckSafety tests/test_lucario_agent.py::TestPokePadDeckSafety -v`
Expected: 一部PASS（旧`_score_play_option`は`Lillie_Determination`をまだ`DECK_SAFETY_THRESHOLD`でゲートしているため`test_allowed_when_consumption_equals_safe_draws`等が失敗）、Judge/Hilda/Pokegear/UltraBall/PokePadの「suppressed」系はまだゲートが無いためFAIL

- [ ] **Step 3: `_score_play_option`にガード節を追加する**

`src/lucario_agent/main.py`の446行目付近（`"""OptionType.PLAY のスコアを返す"""`の直後）に追加：

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
```

（`data.cardType == CardType.POKEMON`以降の既存コードはそのまま）

続けて、476行目付近の`if card.id == Lillie_Determination:`の行を次のように置き換える（`DECK_SAFETY_THRESHOLD`判定は冒頭ガード節に統合済みのため、ここでは通常スコアのみ返す）：

```python
    if card.id == Lillie_Determination:
        return 3100
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestDeckSafetyGate tests/test_lucario_agent.py::TestJudgeDeckSafety tests/test_lucario_agent.py::TestHildaDeckSafety tests/test_lucario_agent.py::TestPokegearDeckSafety tests/test_lucario_agent.py::TestUltraBallDeckSafety tests/test_lucario_agent.py::TestPokePadDeckSafety -v`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat: PLAYコンテキストに山札セーフティを組み込み（ミツルの思いやり/ジャッジマン/ヒルダ/ポケギア3.0/ハイパーボール/ポケパッド）"
```

---

### Task 3: ルナサイクル特性（Lunatoneのability）への組み込み

**Files:**
- Modify: `src/lucario_agent/main.py:558-562`（`_score_option`のABILITY分岐、Lunatone判定）
- Modify: `tests/test_lucario_agent.py:684-719`（`TestLunaCycleAbilityScore`を更新）

**Interfaces:**
- Consumes: `lm._safe_draws(my_state)`（Task 1）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`class TestLunaCycleAbilityScore:`（684行目）ブロックを次の内容で置き換える：

```python
class TestLunaCycleAbilityScore:
    def _obs_with_active_lunatone(self):
        lunatone = Card(id=lm.Lunatone, serial=1, playerIndex=0)
        obs = MagicMock()
        obs.current.players = [make_player_state(), make_player_state()]
        return obs, lunatone

    def test_scores_high_when_deck_healthy(self, mock_card_table):
        obs, lunatone = self._obs_with_active_lunatone()
        obs.current.players[0].active = [lunatone]
        my_state = make_player_state(deck_count=20, prize_count=6)
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

    def test_allowed_when_safe_draws_equals_3(self, mock_card_table):
        """山札10枚・プライズ6枚ならsafe_draws=3。消費3枚と丁度一致→許可"""
        obs, lunatone = self._obs_with_active_lunatone()
        obs.current.players[0].active = [lunatone]
        my_state = make_player_state(deck_count=10, prize_count=6)
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

    def test_suppressed_when_safe_draws_below_3(self, mock_card_table):
        """山札9枚・プライズ6枚ならsafe_draws=2<消費3枚→抑制"""
        obs, lunatone = self._obs_with_active_lunatone()
        obs.current.players[0].active = [lunatone]
        my_state = make_player_state(deck_count=9, prize_count=6)
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

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestLunaCycleAbilityScore -v`
Expected: `test_suppressed_when_safe_draws_below_3`がFAIL（現行コードは`deckCount >= DECK_SAFETY_THRESHOLD(15)`判定のため、deck_count=9では既に-1になり偶然PASSする可能性があるが、`test_allowed_when_safe_draws_equals_3`（deck_count=10）は現行コードだと10<15で-1になりFAILする）

- [ ] **Step 3: `_score_option`のLunatone分岐を書き換える**

`src/lucario_agent/main.py`の560-561行目を次のように置き換える：

```python
            if card.id == Lunatone:
                return 8500 if _safe_draws(my_state) >= 3 else -1
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestLunaCycleAbilityScore -v`
Expected: 3 passed

- [ ] **Step 5: `DECK_SAFETY_THRESHOLD`定数を削除する**

`src/lucario_agent/main.py`の35行目`DECK_SAFETY_THRESHOLD = 15  # 山札残数がこれ未満なら大量ドロー系を抑制`を削除する。

Run: `grep -n "DECK_SAFETY_THRESHOLD" src/lucario_agent/main.py tests/test_lucario_agent.py`
Expected: 出力なし（参照が完全に消えていること）

- [ ] **Step 6: コミット**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "feat: ルナサイクルの山札ゲートを_safe_draws方式に統一し、旧DECK_SAFETY_THRESHOLDを廃止"
```

---

### Task 4: 非対象カードの回帰テスト＋実ログ85626724の再現テスト＋全体回帰

**Files:**
- Modify: `tests/test_lucario_agent.py`（`TestDeckSafetyGate`ブロックの末尾に新規テストクラスを追加）

**Interfaces:**
- Consumes: `lm._score_play_option`（Task 1〜3で完成した最終形）

- [ ] **Step 1: 失敗しない（回帰保証用の）テストを書く**

`tests/test_lucario_agent.py`の`TestPokePadDeckSafety`クラスの直後に追加：

```python
class TestNonGatedCardsIgnoreDeckSafety:
    """山札が極端に少なくてもゲートされてはいけないカード群の回帰テスト"""

    def test_ciphermaniac_codebreaking_not_suppressed_at_deck_count_1(self):
        card = Card(id=lm.Ciphermaniac_Codebreaking, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=1, prize_count=6)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 5100

    def test_wally_compassion_not_suppressed_at_deck_count_1(self):
        card = Card(id=lm.Wally_Compassion, serial=1, playerIndex=0)
        damaged_lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=100, max_hp=200)
        obs, my_state = _obs_with_hand([card], deck_count=1, prize_count=6)
        my_state.active = [damaged_lucario]
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 6800

    def test_night_stretcher_not_suppressed_at_deck_count_1(self):
        card = Card(id=lm.Night_Stretcher, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=1, prize_count=6)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == 4800


class TestReplays85626724DeckOutLoss:
    """実ログ85626724（T17、山札切れで敗北した対戦）の再現テスト。
    実測：ポケギア3.0使用前=山札4枚・プライズ残3枚。新ゲートで温存されるべき"""

    def test_pokegear_would_be_suppressed_at_the_critical_moment(self):
        card = Card(id=lm.Pokegear, serial=1, playerIndex=0)
        obs, my_state = _obs_with_hand([card], deck_count=4, prize_count=3)
        o = Option(type=OptionType.PLAY, index=0)
        score = lm._score_play_option(
            obs, o, my_index=0, current_plan=lm.AttackPlan(),
            can_attack=False, state=_make_state(), my_state=my_state,
            hand_counts=_hand_counts([card]), field_counts=defaultdict(int),
            stadium_id=0,
        )
        assert score == -1
```

- [ ] **Step 2: テストを実行して結果を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestNonGatedCardsIgnoreDeckSafety tests/test_lucario_agent.py::TestReplays85626724DeckOutLoss -v`
Expected: 4 passed（Task 1〜3の実装が正しければ最初からPASSするはずだが、真に非対象カードがゲートされていないこと・実ログの臨界点で温存が働くことを明示的に固定するのが目的）

- [ ] **Step 3: リポジトリ全体の回帰テスト**

Run: `uv run pytest -q`
Expected: 全件PASS（開始時345件＋本計画の新規約30件）

- [ ] **Step 4: コミット**

```bash
git add tests/test_lucario_agent.py
git commit -m "test: 山札セーフティの非対象カード回帰テストと実ログ85626724の再現テストを追加"
```

---

### Task 5: mainへマージ＋実装サマリー作成

**Files:**
- Create: `docs/implementations/20260713-lucario-deck-safety.md`

- [ ] **Step 1: mainへfast-forwardマージ**

```bash
git checkout main
git merge --ff-only feature/lucario-deck-safety
git branch -d feature/lucario-deck-safety
```

- [ ] **Step 2: マージ後の最終回帰テスト**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 3: 実装サマリーを作成**

`docs/implementations/20260713-lucario-deck-safety.md`に以下を記載：

- 背景：ルカリオの直近バトルログ12件（2勝10敗）の敗因分析で、85626724がプライズ有利（3-1）にもかかわらず山札切れで敗北していたことを発見
- 原因：`DECK_SAFETY_THRESHOLD=15`がミツルの思いやり・ルナサイクルの2つしかゲートしておらず、ジャッジマン・ヒルダ・ポケギア3.0・ハイパーボール・ポケパッドが無制限に山札を消費していた
- 設計書・計画書へのリンク（`docs/superpowers/specs/2026-07-13-lucario-deck-safety-design.md` / 本計画書）
- 変更内容：`_safe_draws`/`_deck_consumption`ヘルパー新設、`_score_play_option`と`_score_option`（Lunatone特性）への組み込み、`DECK_SAFETY_THRESHOLD`廃止
- コミット範囲（`feature/lucario-deck-safety`ブランチのコミットハッシュ一覧）
- テスト件数（開始時345件→最終件数）
- 未実施事項：デッキ本体・提出用ノートブック（`src/sample_notebook/a-sample-rule-based-agent-mega-lucario-ex-deck.ipynb`）への転記・Kaggle再提出はユーザー作業。次にルカリオの新しいバトルログが取れたら、今回のような「有利なのに山札切れ」パターンが再発しないかを確認する
- スコープ外として残した9敗（プライズレース負け、うちメガルカリオexミラー戦2敗を含む）への対応は今回含まれないことを明記

- [ ] **Step 4: コミット**

```bash
git add docs/implementations/20260713-lucario-deck-safety.md
git commit -m "docs: ルカリオex山札セーフティ移植の実装サマリーを追加"
```

---

## 実装完了後の手順（ユーザー作業＋次セッション）

1. 提出用ノートブック`src/sample_notebook/a-sample-rule-based-agent-mega-lucario-ex-deck.ipynb`のセル0（`%%writefile main.py`）を今回の修正後の`main.py`全文で差し替える（デッキ本体は無変更のためdeck.csv再生成・Kaggleデータセット更新は不要）
2. Kaggleへ再提出
3. 次にルカリオの新しいバトルログが取れたら、デッキアウト負けが解消したか（プライズ有利なのに山札切れするパターンが再発しないか）を確認する
4. スコープ外の9敗（プライズレース負け）への対応が必要か、メガルカリオexミラー戦の意思決定差を深掘りするかは、次回セッションで改めて相談する
