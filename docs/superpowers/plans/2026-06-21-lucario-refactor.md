# Lucario エージェント リファクタリング 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/a-sample-rule-based-agent-mega-lucario-ex-deck.ipynb` のエージェントロジックを `src/lucario_agent/main.py` として Python モジュールに切り出し、振る舞いを変えずに構造を整理し、テストでカバーする。

**Architecture:** ノートブックの `%%writefile main.py` セルコードを `src/lucario_agent/main.py` に移植。`@dataclass`・`match` 文・関数分解で可読性を上げる。カードテーブルは `mascarnage_agent/main.py` と同じ遅延初期化パターンで管理してテスト時のモック差し替えを可能にする。ロジックの変更は一切行わない。

**Tech Stack:** Python 3.12.13, pytest, `cg.api`（pure Python）, uv

## Global Constraints

- Python 3.12.13（`pyproject.toml` 固定）
- **ロジック変更なし**：スコア計算・優先度・グローバル状態のリセットタイミングはすべて元のノートブックと同一
- テストは `uv run pytest` で全 PASS を維持（既存 12 件 + 今回追加分）
- コメントは日本語、識別子は英語
- `cg.sim`・`cg.game` は既存 conftest.py でモック済み（libcg.so はローカル不可）
- `card_table` は遅延初期化（モジュールロード時に `all_card_data()` を呼ばない）
- テストでは `monkeypatch.setattr(lm, "card_table", ...)` でモックに差し替える

---

### Task 1: モジュール骨格 + テストインフラ

**Files:**
- Create: `src/lucario_agent/__init__.py`
- Create: `src/lucario_agent/main.py`（import・定数・遅延初期化・グローバル状態のみ）
- Create: `tests/test_lucario_agent.py`（`MockCardData` + `mock_card_table` fixture）

**Interfaces:**
- Produces: `lucario_agent.main.card_table: dict`（テストで monkeypatch 可能）
- Produces: `lucario_agent.main.my_deck: list[int]`（テストで patch.object 可能）
- Produces: `lucario_agent.main.AttackPlan`（dataclass）
- Produces: `lucario_agent.main._reset_turn_state() -> None`

- [ ] **Step 1: `src/lucario_agent/__init__.py` を作成する（空ファイル）**

```python
```

- [ ] **Step 2: `src/lucario_agent/main.py` の骨格を作成する**

```python
import os
from collections import defaultdict
from dataclasses import dataclass

from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, all_card_data, to_observation_class,
)

# ==================== カードID定数 ====================
Makuhita             = 673
Hariyama             = 674
Lunatone             = 675
Solrock              = 676
Riolu                = 677
Mega_Lucario_ex      = 678
Dusk_Ball            = 1102
Switch               = 1123
Premium_Power_Pro    = 1141
Fighting_Gong        = 1142
Poke_Pad             = 1152
Hero_Cape            = 1159
Boss_Orders          = 1182
Carmine              = 1192
Lillie_Determination = 1227
Gravity_Mountain     = 1252
Basic_Fighting_Energy = 6

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築する"""
    global card_table
    if not card_table:
        card_table = {c.cardId: c for c in all_card_data()}
    return card_table


# ==================== デッキ（遅延初期化）====================
my_deck: list[int] = []


def _load_deck() -> list[int]:
    """deck.csv を初回のみ読み込む"""
    global my_deck
    if my_deck:
        return my_deck
    file_path = "deck.csv"
    if not os.path.exists(file_path):
        file_path = "/kaggle_simulations/agent/" + file_path
    try:
        with open(file_path, "r") as f:
            rows = f.read().split("\n")
        my_deck = [int(rows[i]) for i in range(60)]
    except FileNotFoundError:
        my_deck = []
    return my_deck


# ==================== ターン状態管理 ====================
@dataclass
class AttackPlan:
    attacker:     int  = -1
    target:       int  = -1
    attack_index: int  = -1
    remain_hp:    int  = -1
    energy:       bool = False


plan:         AttackPlan = AttackPlan()
pre_turn:     int        = 0
ability_used: bool       = False


def _reset_turn_state() -> None:
    """ターン開始時にグローバル攻撃プランとアビリティフラグをリセットする"""
    global plan, ability_used
    plan = AttackPlan()
    ability_used = False
```

- [ ] **Step 3: `tests/test_lucario_agent.py` の土台を作成する**

```python
# tests/test_lucario_agent.py
import pytest
from dataclasses import dataclass
from cg.api import CardType, EnergyType
import lucario_agent.main as lm


@dataclass
class MockCardData:
    """テスト用 CardData 代替クラス（cg.api.CardData と同一フィールドのみ定義）"""
    cardId:     int
    name:       str              = ""
    megaEx:     bool             = False
    ex:         bool             = False
    stage2:     bool             = False
    stage1:     bool             = False
    cardType:   CardType         = CardType.POKEMON
    weakness:   EnergyType | None = None
    resistance: EnergyType | None = None


def _card(card_id: int, **kwargs) -> MockCardData:
    return MockCardData(cardId=card_id, **kwargs)


@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    """全テストで card_table をモックに差し替える"""
    table = {
        lm.Makuhita:              _card(lm.Makuhita),
        lm.Hariyama:              _card(lm.Hariyama, stage1=True),
        lm.Lunatone:              _card(lm.Lunatone),
        lm.Solrock:               _card(lm.Solrock),
        lm.Riolu:                 _card(lm.Riolu),
        lm.Mega_Lucario_ex:       _card(lm.Mega_Lucario_ex, megaEx=True),
        144:  _card(144,  ex=True),   # Squawkabilly ex
        322:  _card(322),             # Noctowl
        323:  _card(323),             # Fan Rotom
        337:  _card(337,  ex=True),   # Archaludon ex
        112:  _card(112),             # Munkidori
        1267: _card(1267),            # Lumiose City
        12:   _card(12,   cardType=CardType.SPECIAL_ENERGY),  # Legacy Energy
        1172: _card(1172, cardType=CardType.TOOL),            # Lillie's Pearl
        lm.Switch:               _card(lm.Switch,               cardType=CardType.ITEM),
        lm.Premium_Power_Pro:    _card(lm.Premium_Power_Pro,    cardType=CardType.ITEM),
        lm.Boss_Orders:          _card(lm.Boss_Orders,          cardType=CardType.SUPPORTER),
        lm.Carmine:              _card(lm.Carmine,              cardType=CardType.SUPPORTER),
        lm.Lillie_Determination: _card(lm.Lillie_Determination, cardType=CardType.SUPPORTER),
        lm.Gravity_Mountain:     _card(lm.Gravity_Mountain,     cardType=CardType.STADIUM),
        lm.Hero_Cape:            _card(lm.Hero_Cape,            cardType=CardType.TOOL),
        lm.Fighting_Gong:        _card(lm.Fighting_Gong,        cardType=CardType.ITEM),
        lm.Poke_Pad:             _card(lm.Poke_Pad,             cardType=CardType.ITEM),
        lm.Dusk_Ball:            _card(lm.Dusk_Ball,            cardType=CardType.ITEM),
    }
    monkeypatch.setattr(lm, "card_table", table)
    return table
```

- [ ] **Step 4: インポートとコレクトが通ることを確認する**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
uv run pytest tests/test_lucario_agent.py --collect-only
```

期待: エラーなし（`no tests ran` または `0 items`）

---

### Task 2: `get_card` + `prize_count` + テスト

**Files:**
- Modify: `src/lucario_agent/main.py`（`get_card`・`prize_count` を追加）
- Modify: `tests/test_lucario_agent.py`（`TestPrizeCount` を追加）

**Interfaces:**
- Consumes: `card_table`（Task 1）
- Produces: `get_card(obs, area, index, player_index) -> Pokemon | Card | None`
- Produces: `prize_count(pokemon: Pokemon) -> int`

- [ ] **Step 1: 失敗テストを書く（`tests/test_lucario_agent.py` に追記）**

```python
from cg.api import Card
from tests.conftest import make_pokemon


class TestPrizeCount:
    def test_regular_pokemon_yields_1(self):
        p = make_pokemon(id=lm.Riolu)
        assert lm.prize_count(p) == 1

    def test_ex_pokemon_yields_2(self):
        p = make_pokemon(id=337)  # Archaludon ex
        assert lm.prize_count(p) == 2

    def test_mega_ex_yields_3(self):
        p = make_pokemon(id=lm.Mega_Lucario_ex)
        assert lm.prize_count(p) == 3

    def test_legacy_energy_reduces_count_by_1(self):
        """Legacy Energy(id=12) を装備した ex は 2 - 1 = 1 プライズ"""
        p = make_pokemon(id=337)
        legacy = Card(id=12, serial=12)
        object.__setattr__(p, "energyCards", [legacy])
        assert lm.prize_count(p) == 1

    def test_minimum_prize_is_0(self):
        """複数の減算があっても 0 を下限とする"""
        p = make_pokemon(id=lm.Riolu)  # 通常 → 1
        legacy = Card(id=12, serial=12)
        object.__setattr__(p, "energyCards", [legacy, legacy])
        assert lm.prize_count(p) == 0
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_lucario_agent.py::TestPrizeCount -v
```

期待: `AttributeError: module 'lucario_agent.main' has no attribute 'prize_count'`

- [ ] **Step 3: `get_card` と `prize_count` を実装する（`src/lucario_agent/main.py` に追記）**

```python
# ==================== ユーティリティ ====================
def get_card(obs: Observation, area: AreaType, index: int, player_index: int) -> "Pokemon | Card | None":
    """指定ゾーンからカードを安全に取得する"""
    ps = obs.current.players[player_index]
    match area:
        case AreaType.DECK:
            return obs.select.deck[index]
        case AreaType.HAND:
            return ps.hand[index]
        case AreaType.DISCARD:
            return ps.discard[index]
        case AreaType.ACTIVE:
            return ps.active[index]
        case AreaType.BENCH:
            return ps.bench[index]
        case AreaType.PRIZE:
            return ps.prize[index]
        case AreaType.STADIUM:
            return obs.current.stadium[index]
        case AreaType.LOOKING:
            return obs.current.looking[index]
        case _:
            return None


def prize_count(pokemon: Pokemon) -> int:
    """KO 時に相手が取るプライズ枚数を返す（修飾カードを考慮）"""
    data = card_table[pokemon.id]
    count = 3 if data.megaEx else 2 if data.ex else 1
    for card in pokemon.energyCards:
        if card.id == 12:  # Legacy Energy
            count -= 1
    for card in pokemon.tools:
        if card.id == 1172 and "Lillie" in data.name:  # Lillie's Pearl
            count -= 1
    return max(0, count)
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run pytest tests/test_lucario_agent.py::TestPrizeCount -v
```

期待: 5 passed

---

### Task 3: `pokemon_score` + `energy_score` + テスト

**Files:**
- Modify: `src/lucario_agent/main.py`（`pokemon_score`・`energy_score` を追加）
- Modify: `tests/test_lucario_agent.py`（`TestPokemonScore`・`TestEnergyScore` を追加）

**Interfaces:**
- Consumes: `prize_count`・`card_table`（Task 1・2）
- Produces: `pokemon_score(pokemon: Pokemon) -> int`
- Produces: `energy_score(pokemon: Pokemon, active: bool, attacker1: bool, attacker2: bool) -> int`

- [ ] **Step 1: 失敗テストを書く（`tests/test_lucario_agent.py` に追記）**

```python
class TestPokemonScore:
    def test_ex_pokemon_scores_higher_than_regular(self):
        ex  = make_pokemon(id=337, hp=200)       # ex → 2 prize
        reg = make_pokemon(id=lm.Riolu, hp=200)  # regular → 1 prize
        assert lm.pokemon_score(ex) > lm.pokemon_score(reg)

    def test_more_energies_yields_higher_score(self):
        p_no  = make_pokemon(id=lm.Riolu, hp=100, energies=[])
        p_two = make_pokemon(id=lm.Riolu, hp=100, energies=[6, 6])
        assert lm.pokemon_score(p_two) > lm.pokemon_score(p_no)

    def test_special_ids_are_penalised(self):
        """Squawkabilly ex(144)・Noctowl(322)・Fan Rotom(323)・Archaludon ex(337) は -200 補正"""
        normal = make_pokemon(id=lm.Riolu, hp=70)
        squawk = make_pokemon(id=144,      hp=70)
        assert lm.pokemon_score(normal) > lm.pokemon_score(squawk)

    def test_munkidori_gets_bonus_with_energy(self):
        """Munkidori(112) はエネルギーが 1 枚以上で +300"""
        no_e   = make_pokemon(id=112, hp=90, energies=[])
        with_e = make_pokemon(id=112, hp=90, energies=[6])
        assert lm.pokemon_score(with_e) > lm.pokemon_score(no_e)

    def test_stage1_gets_bonus(self, monkeypatch):
        """stage1 ポケモンは stage1 でないポケモンよりスコアが高い"""
        p_stage1 = make_pokemon(id=lm.Hariyama, hp=130)  # stage1=True in mock
        p_basic  = make_pokemon(id=lm.Riolu,    hp=130)  # basic
        assert lm.pokemon_score(p_stage1) > lm.pokemon_score(p_basic)


class TestEnergyScore:
    def test_active_slot_gets_bonus(self):
        p      = make_pokemon(id=lm.Riolu, energies=[])
        active = lm.energy_score(p, True,  False, False)
        bench  = lm.energy_score(p, False, False, False)
        assert active > bench

    def test_riolu_low_energy_gets_bonus(self):
        """Riolu にエネルギーが足りない場合はスコアが高い"""
        no_e  = make_pokemon(id=lm.Riolu, energies=[])
        two_e = make_pokemon(id=lm.Riolu, energies=[6, 6])
        assert lm.energy_score(no_e, False, False, False) > lm.energy_score(two_e, False, False, False)

    def test_lunatone_deprioritised(self):
        p_luna  = make_pokemon(id=lm.Lunatone, energies=[])
        p_riolu = make_pokemon(id=lm.Riolu,    energies=[])
        assert lm.energy_score(p_riolu, False, False, False) > lm.energy_score(p_luna, False, False, False)

    def test_solrock_deprioritised_after_one_energy(self):
        p_no  = make_pokemon(id=lm.Solrock, energies=[])
        p_one = make_pokemon(id=lm.Solrock, energies=[6])
        assert lm.energy_score(p_no, False, False, False) > lm.energy_score(p_one, False, False, False)

    def test_attacker1_flag_lowers_score(self):
        """既に attacker1 が準備できている場合、Riolu へのエネルギー優先度を下げる"""
        p            = make_pokemon(id=lm.Riolu, energies=[])
        without_flag = lm.energy_score(p, False, False, False)
        with_flag    = lm.energy_score(p, False, True,  False)  # attacker1=True
        assert without_flag > with_flag
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_lucario_agent.py::TestPokemonScore tests/test_lucario_agent.py::TestEnergyScore -v
```

期待: `AttributeError`

- [ ] **Step 3: `pokemon_score` と `energy_score` を実装する（`src/lucario_agent/main.py` に追記）**

```python
def pokemon_score(pokemon: Pokemon) -> int:
    """対象ポケモンの戦術的価値をヒューリスティックに評価する"""
    data  = card_table[pokemon.id]
    score = prize_count(pokemon) * 1000
    score += len(pokemon.energies) * 150
    score += len(pokemon.tools) * 100
    if data.stage2:
        score += 250
    elif data.stage1:
        score += 130
    id_ = pokemon.id
    if id_ in (144, 322, 323, 337):  # Squawkabilly ex, Noctowl, Fan Rotom, Archaludon ex
        score -= 200
    if id_ == 112 and len(pokemon.energies) >= 1:  # Munkidori
        score += 300
    score += pokemon.hp
    return score


def energy_score(pokemon: Pokemon, active: bool, attacker1: bool, attacker2: bool) -> int:
    """エネルギー付与先ポケモンの優先度スコアを返す"""
    energy_count = len(pokemon.energies)
    score = 8000
    if active:
        score += 10
    if pokemon.id in (Makuhita, Hariyama):
        if pokemon.id == Hariyama:
            score += 1
        if energy_count < 3:
            score += 100
        if attacker2:
            score -= 50
    elif pokemon.id == Lunatone:
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

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run pytest tests/test_lucario_agent.py::TestPokemonScore tests/test_lucario_agent.py::TestEnergyScore -v
```

期待: 9 passed

---

### Task 4: フィールド状態ヘルパー + テスト

**Files:**
- Modify: `src/lucario_agent/main.py`（`_collect_field_state`・`_get_stadium_id`・`_analyze_main_options` を追加）
- Modify: `tests/test_lucario_agent.py`（`TestCollectFieldState`・`TestGetStadiumId` を追加）

**Interfaces:**
- Consumes: `get_card`・カードID定数（Task 1・2）
- Produces: `_collect_field_state(my_state) -> tuple[defaultdict, defaultdict, defaultdict, bool, bool]`
- Produces: `_get_stadium_id(state) -> int`
- Produces: `_analyze_main_options(obs, select, my_index: int) -> tuple[bool, bool, bool, bool]`

- [ ] **Step 1: 失敗テストを書く（`tests/test_lucario_agent.py` に追記）**

```python
from unittest.mock import MagicMock
from cg.api import Card
from tests.conftest import make_pokemon, make_player_state


class TestCollectFieldState:
    def test_counts_active_and_bench(self):
        riolu    = make_pokemon(id=lm.Riolu)
        hariyama = make_pokemon(id=lm.Hariyama)
        ps = make_player_state(active_pokemon=riolu, bench=[hariyama])
        fc, hc, dc, a1, a2 = lm._collect_field_state(ps)
        assert fc[lm.Riolu]    == 1
        assert fc[lm.Hariyama] == 1

    def test_attacker1_true_when_lucario_has_2_energy(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[6, 6])
        ps = make_player_state(active_pokemon=lucario)
        _, _, _, a1, a2 = lm._collect_field_state(ps)
        assert a1 is True
        assert a2 is False

    def test_attacker2_true_when_hariyama_has_3_energy(self):
        hariyama = make_pokemon(id=lm.Hariyama, energies=[6, 6, 6])
        ps = make_player_state(active_pokemon=hariyama)
        _, _, _, a1, a2 = lm._collect_field_state(ps)
        assert a2 is True

    def test_no_attackers_when_energy_insufficient(self):
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[6])  # 1 枚のみ
        ps = make_player_state(active_pokemon=lucario)
        _, _, _, a1, a2 = lm._collect_field_state(ps)
        assert a1 is False


class TestGetStadiumId:
    def test_returns_0_when_no_stadium(self):
        state = MagicMock()
        state.stadium = []
        assert lm._get_stadium_id(state) == 0

    def test_returns_stadium_card_id(self):
        state = MagicMock()
        state.stadium = [Card(id=lm.Gravity_Mountain, serial=1)]
        assert lm._get_stadium_id(state) == lm.Gravity_Mountain
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_lucario_agent.py::TestCollectFieldState tests/test_lucario_agent.py::TestGetStadiumId -v
```

期待: `AttributeError`

- [ ] **Step 3: ヘルパー関数を実装する（`src/lucario_agent/main.py` に追記）**

```python
# ==================== フィールド状態 ====================
def _collect_field_state(my_state):
    """バトル場・ベンチ・手札・捨て山のカード枚数とアタッカー準備状況を返す"""
    field_counts   = defaultdict(int)
    hand_counts    = defaultdict(int)
    discard_counts = defaultdict(int)
    attacker1 = False
    attacker2 = False

    for card in my_state.active + my_state.bench:
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id in (Makuhita, Hariyama):
            if len(card.energies) >= 3:
                attacker2 = True
        elif card.id in (Riolu, Mega_Lucario_ex):
            if len(card.energies) >= 2:
                attacker1 = True

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    return field_counts, hand_counts, discard_counts, attacker1, attacker2


def _get_stadium_id(state) -> int:
    """現在のスタジアムカード ID を返す（なければ 0）"""
    for card in state.stadium:
        return card.id
    return 0


def _analyze_main_options(obs: Observation, select, my_index: int) -> tuple[bool, bool, bool, bool]:
    """MAIN コンテキストのオプション一覧から行動フラグを抽出する"""
    can_switch         = False
    can_op_switch      = False
    can_use_mega_brave = False
    can_attack         = False

    for o in select.option:
        if o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            if card.id == Switch:
                can_switch = True
            elif card.id == Boss_Orders:
                can_op_switch = True
        elif o.type == OptionType.EVOLVE:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            if card.id == Hariyama:
                can_op_switch = True
        elif o.type == OptionType.RETREAT:
            can_switch = True
        elif o.type == OptionType.ATTACK:
            can_attack = True
            if o.attackId == 983:  # Mega Brave
                can_use_mega_brave = True

    return can_switch, can_op_switch, can_use_mega_brave, can_attack
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run pytest tests/test_lucario_agent.py::TestCollectFieldState tests/test_lucario_agent.py::TestGetStadiumId -v
```

期待: 6 passed

---

### Task 5: `calc_attack_plan` + テスト

**Files:**
- Modify: `src/lucario_agent/main.py`（`calc_attack_plan` を追加）
- Modify: `tests/test_lucario_agent.py`（`TestCalcAttackPlan` を追加）

**Interfaces:**
- Consumes: `AttackPlan`・`prize_count`・`pokemon_score`・`card_table`（Task 1-3）
- Produces: `calc_attack_plan(obs, my_state, op_state, state, field_counts, hand_counts, discard_counts, can_switch, can_op_switch, can_use_mega_brave, can_attack, my_prize) -> AttackPlan`

- [ ] **Step 1: 失敗テストを書く（`tests/test_lucario_agent.py` に追記）**

```python
from collections import defaultdict
from unittest.mock import MagicMock
from cg.api import Option
from tests.conftest import make_pokemon, make_player_state


def _make_state(turn=3, energy_attached=False, first_player=0):
    state = MagicMock()
    state.turn           = turn
    state.energyAttached = energy_attached
    state.firstPlayer    = first_player
    return state


class TestCalcAttackPlan:
    def test_no_attackers_returns_default_plan(self):
        """攻撃可能なポケモンがいない場合はデフォルト AttackPlan(-1) を返す"""
        solrock = make_pokemon(id=lm.Solrock, hp=80, energies=[])
        my_ps = make_player_state(active_pokemon=solrock)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=60), prize_count=6)

        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=False,
            my_prize=6,
        )
        assert result.attacker == -1
        assert result.target   == -1

    def test_lucario_plans_mega_brave_when_it_can_ko(self):
        """Mega Lucario ex に 2 エネ・相手 HP200 → Mega Brave(270) でのみ KO 可→ attack_index=1"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        # HP200: 通常攻撃130では KO 不可、Mega Brave270では KO 可
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=200), prize_count=6)

        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]  # Mega Brave あり
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True,
            my_prize=6,
        )
        assert result.attacker     == 0
        assert result.attack_index == 1  # Mega Brave

    def test_win_condition_is_detected(self):
        """KO で相手の残りプライズが 0 になる局面を選択する（attacker != -1）"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6, 6])
        my_ps = make_player_state(active_pokemon=lucario, prize_count=4)
        # Archaludon ex (id=337, ex → 2 prize), 残りプライズも 2 → KO で勝ち
        op_ps = make_player_state(active_pokemon=make_pokemon(id=337, hp=60), prize_count=2)

        obs = MagicMock()
        obs.select.option = [Option(type=OptionType.ATTACK, attackId=983)]
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=True, can_attack=True,
            my_prize=4,
        )
        assert result.attacker == 0

    def test_fighting_weakness_doubles_damage(self):
        """格闘弱点の相手には実質ダメージが 2 倍になり KO 判定に影響する"""
        # 通常攻撃130 → 弱点で260 → HP200 を KO 可能
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, hp=300, energies=[6])  # エネ1でも可
        my_ps = make_player_state(active_pokemon=lucario, prize_count=6)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=lm.Riolu, hp=200), prize_count=6)

        # Riolu の weakness を FIGHTING に設定
        import lucario_agent.main as lm2
        lm2.card_table[lm.Riolu] = MockCardData(cardId=lm.Riolu, weakness=EnergyType.FIGHTING)

        obs = MagicMock()
        obs.select.option = []
        result = lm.calc_attack_plan(
            obs, my_ps, op_ps, _make_state(),
            defaultdict(int), defaultdict(int), defaultdict(int),
            can_switch=False, can_op_switch=False,
            can_use_mega_brave=False, can_attack=True,
            my_prize=6,
        )
        # 弱点込みで KO できるので attacker が選ばれる
        assert result.attacker == 0
        assert result.attack_index == 0  # 通常攻撃
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_lucario_agent.py::TestCalcAttackPlan -v
```

期待: `AttributeError`

- [ ] **Step 3: `calc_attack_plan` を実装する（`src/lucario_agent/main.py` に追記）**

```python
# ==================== 攻撃プラン計算 ====================
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
) -> AttackPlan:
    """最適な攻撃プランを計算して返す"""
    new_plan   = AttackPlan()
    best_score = -1

    my_cards = [my_state.active[0]] + list(my_state.bench)
    op_cards = [op_state.active[0]] + list(op_state.bench)

    for i, my_pokemon in enumerate(my_cards):
        if my_pokemon is None:
            continue
        if i != 0 and not can_switch:
            break
        for a in range(2):
            energy_required = 0
            base_damage     = 0
            base_score      = 0

            if my_pokemon.id == Mega_Lucario_ex:
                if a == 0:
                    energy_required = 1
                    base_damage     = 130
                    base_score     += 60 * min(3, discard_counts[Basic_Fighting_Energy])
                else:
                    energy_required = 2
                    base_damage     = 270
                if my_prize in (2, 3):
                    base_score -= 500
            elif a == 1:
                break
            elif my_pokemon.id == Hariyama:
                energy_required = 3
                base_damage     = 210
            elif my_pokemon.id == Makuhita:
                for o in obs.select.option:
                    if o.type == OptionType.EVOLVE:
                        idx = o.inPlayIndex + (1 if o.inPlayArea == AreaType.BENCH else 0)
                        if idx == i:
                            break
                else:
                    break
                base_score     -= 100
                energy_required = 3
                base_damage     = 210
            elif my_pokemon.id == Solrock:
                if field_counts[Lunatone] >= 1:
                    energy_required = 1
                    base_damage     = 70

            if base_damage <= 0:
                continue

            energy_count = len(my_pokemon.energies)
            more_energy  = False
            if a == 1 and i == 0 and energy_count >= 2 and not can_use_mega_brave:
                break
            if energy_count < energy_required:
                if hand_counts[Basic_Fighting_Energy] >= 1 and not state.energyAttached:
                    energy_count += 1
                    if energy_count < energy_required:
                        continue
                    else:
                        more_energy = True
                else:
                    continue

            for j, op_pokemon in enumerate(op_cards):
                if op_pokemon is None:
                    continue
                if j != 0 and not can_op_switch:
                    break
                damage = base_damage
                data   = card_table[op_pokemon.id]
                if data.weakness == EnergyType.FIGHTING:
                    damage *= 2
                elif data.resistance == EnergyType.FIGHTING:
                    damage -= 30

                prize = 0
                score = pokemon_score(op_pokemon)
                if op_pokemon.hp <= damage:
                    prize = prize_count(op_pokemon)
                else:
                    score *= damage / op_pokemon.hp
                score += base_score

                if len(op_state.prize) <= prize:
                    score = 50000

                if i == 0:
                    score += 220
                if j == 0:
                    score += 300
                score += energy_count

                if best_score < score:
                    best_score            = score
                    new_plan.attacker     = i
                    new_plan.target       = j
                    new_plan.attack_index = a
                    new_plan.remain_hp    = op_pokemon.hp - damage
                    new_plan.energy       = more_energy

    return new_plan
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run pytest tests/test_lucario_agent.py::TestCalcAttackPlan -v
```

期待: 4 passed

---

### Task 6: スコアヘルパー + `agent()` 最終形 + 統合テスト

**Files:**
- Modify: `src/lucario_agent/main.py`（`_score_card_option`・`_score_play_option`・`_score_attach_option`・`_score_option`・`agent()` を追加）
- Modify: `tests/test_lucario_agent.py`（`TestAgent` を追加）

**Interfaces:**
- Consumes: Task 1-5 のすべての関数
- Produces: `agent(obs_dict: dict) -> list[int]`

- [ ] **Step 1: 統合テストを書く（`tests/test_lucario_agent.py` に追記）**

```python
from unittest.mock import patch
from cg.api import Option, OptionType
from tests.conftest import make_pokemon, make_player_state, make_main_obs


class TestAgent:
    def test_returns_deck_when_select_is_none(self):
        """select が None のとき my_deck を返す（デッキ選択フェーズ）"""
        obs_dict = {"select": None, "logs": [], "current": None, "search_begin_input": None}
        with patch.object(lm, "my_deck", [1] * 60):
            result = lm.agent(obs_dict)
        assert result == [1] * 60

    def test_returns_valid_indices(self):
        """返り値が option の範囲内で重複なし"""
        options = [
            Option(type=OptionType.ATTACK, attackId=100),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(options=options)
        result = lm.agent(obs_dict)
        assert all(0 <= i < len(options) for i in result)
        assert len(result) == len(set(result))

    def test_prefers_attack_over_end(self):
        """ATTACK オプションは END より優先される"""
        options = [
            Option(type=OptionType.END),
            Option(type=OptionType.ATTACK, attackId=100),
        ]
        obs_dict = make_main_obs(options=options)
        result = lm.agent(obs_dict)
        assert options[result[0]].type == OptionType.ATTACK

    def test_resets_plan_on_new_turn(self):
        """ターンが変わったら plan と ability_used がリセットされる"""
        lm.pre_turn     = 5
        lm.plan         = lm.AttackPlan(attacker=1, target=1, attack_index=0)
        lm.ability_used = True

        obs_dict = make_main_obs(options=[Option(type=OptionType.END)], turn=6)
        lm.agent(obs_dict)

        assert lm.plan.attacker == -1
        assert lm.ability_used  is False
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_lucario_agent.py::TestAgent -v
```

期待: `AttributeError: module 'lucario_agent.main' has no attribute 'agent'`

- [ ] **Step 3: スコアヘルパーと `agent()` を実装する（`src/lucario_agent/main.py` に追記）**

```python
# ==================== スコアリング ====================
def _score_card_option(obs, o, context, my_index, state, my_state,
                       field_counts, hand_counts, discard_counts,
                       attacker1, attacker2, current_plan, ability_used_flag) -> int:
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
                elif card.id == Hariyama and energy_count >= 2:
                    score += 15
                elif card.id == Makuhita and energy_count >= 2:
                    score += 10
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
            if card.id == Makuhita:
                return 1
            return 0

        case SelectContext.TO_HAND:
            score = 200 - hand_counts[card.id] * 100
            if card.id == Makuhita:
                score += 10 if field_counts[card.id] < 1 else -10
            elif card.id == Hariyama:
                score += 20 if field_counts[Makuhita] >= 1 else -20
            elif card.id == Lunatone:
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
            return energy_score(card, o.area == AreaType.ACTIVE, attacker1, attacker2)

        case _:
            return 0


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
    if card.id == Switch:
        return 6000 if current_plan.attacker > 0 else -1
    if card.id == Premium_Power_Pro:
        if state.supporterPlayed and current_plan.remain_hp <= 0:
            return -1
        if not can_attack:
            if not state.supporterPlayed and hand_counts[Carmine] > 0 and hand_counts[Lillie_Determination] == 0:
                return 3050
            return -1
        return 5000
    if card.id == Boss_Orders:
        return 3200 if current_plan.target >= 1 else -1
    if card.id == Carmine:
        return 3000
    if card.id == Lillie_Determination:
        return 3100
    if card.id == Gravity_Mountain:
        return -1 if stadium_id == 0 else 10000
    return 10000


def _score_attach_option(obs, o, my_index, current_plan, attacker1, attacker2) -> int:
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
    score = energy_score(pokemon, o.inPlayArea == AreaType.ACTIVE, attacker1, attacker2)
    if o.inPlayArea == AreaType.ACTIVE:
        if current_plan.attacker == 0 and current_plan.energy:
            score += 200
    else:
        if current_plan.attacker == 1 + o.inPlayIndex and current_plan.energy:
            score += 200
    return score


def _score_option(obs, o, context, my_index, state, my_state, op_state,
                  field_counts, hand_counts, discard_counts,
                  attacker1, attacker2, current_plan, can_attack,
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
                attacker1, attacker2, current_plan, ability_used_flag,
            )
        case OptionType.PLAY:
            return _score_play_option(
                obs, o, my_index, current_plan, can_attack,
                state, hand_counts, field_counts, stadium_id,
            )
        case OptionType.ATTACH:
            return _score_attach_option(obs, o, my_index, current_plan, attacker1, attacker2)
        case OptionType.EVOLVE:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            score = 9000 + len(pokemon.energies)
            if pokemon.id == Makuhita and current_plan.target == 0:
                score = -1
            return score
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


# ==================== メインエージェント ====================
def agent(obs_dict: dict) -> list[int]:
    """Pokémon TCG エージェント。

    Returns:
        list[int]: 選択するオプションのインデックスリスト
    """
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        _load_deck()
        return my_deck

    _build_card_table()

    global plan, pre_turn, ability_used

    state    = obs.current
    select   = obs.select
    context  = select.context
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]
    my_prize = len(my_state.prize)

    if pre_turn != state.turn:
        pre_turn = state.turn
        _reset_turn_state()

    field_counts, hand_counts, discard_counts, attacker1, attacker2 = _collect_field_state(my_state)
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
            attacker1, attacker2, plan, can_attack,
            stadium_id, ability_used,
        )
        for o in select.option
    ]

    desc_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    if context == SelectContext.MAIN:
        o = select.option[desc_indices[0]]
        if o.type == OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if card.id == Lunatone:
                ability_used = True

    return desc_indices[:select.maxCount]
```

- [ ] **Step 4: 統合テストが通ることを確認する**

```bash
uv run pytest tests/test_lucario_agent.py::TestAgent -v
```

期待: 4 passed

- [ ] **Step 5: 全テストが通ることを確認する（既存 12 件含む）**

```bash
uv run pytest -v
```

期待: 全 PASS（既存 12 件 + 今回追加分）

---

## 自己レビュー

| 要件 | 対応タスク |
|---|---|
| ロジック変更なし（スコア値・条件・グローバル状態リセットが元と同一） | Task 2-6（ノートブックから転写） |
| `energy_score` をモジュールレベルに抽出 | Task 3 |
| `AttackPlan` を `@dataclass` に変換 | Task 1 |
| `agent()` から関数を分離 | Task 4-6 |
| `match` 文でコンテキスト別スコアを整理 | Task 6 |
| `card_table` がテストでモック可能 | Task 1（遅延初期化 + monkeypatch） |
| 全テスト PASS | Task 6 Step 5 |
| プレースホルダーなし | ✓ 全ステップにコード記載 |
