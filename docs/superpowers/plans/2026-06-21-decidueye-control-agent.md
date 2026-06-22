# ジュナイパーexコントロール エージェント 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ジュナイパーexの「Sniper's Eye」特性を軸に手札コントロールで勝つルールベースエージェントを実装する

**Architecture:** Lucarioエージェントと同一のスコアリング方式を踏襲。相手手札数を毎ターン評価し、4枚なら攻撃・それ以外ならJudge/Xerosicで4枚に誘導する優先度スコアを返す。`src/decidueye_agent/main.py` 1ファイル完結構成（Kaggle転記用）。

**Tech Stack:** Python 3.12, cg.api (Kaggle環境), pytest, uv

## Global Constraints

- `main.py` は1ファイル完結。外部ファイルへの依存禁止（Kaggle転記のため）
- `cg.sim` と `cg.game` はローカルで動かないため `tests/conftest.py` のモックを使用
- テストは既存の `conftest.py` のファクトリ（`make_pokemon`, `make_player_state`, `make_main_obs`）を再利用
- `card_table` はグローバル変数として宣言し、`monkeypatch.setattr` でテスト時に差し替える
- コードコメントは日本語

---

## ファイル構成

| パス | 役割 |
|---|---|
| `src/decidueye_agent/__init__.py` | モジュール宣言（空） |
| `src/decidueye_agent/main.py` | エージェント本体（全ロジック） |
| `tests/test_decidueye_agent.py` | 単体・統合テスト |

---

### Task 1: モジュール基盤（定数・初期化・agent()スタブ）

**Files:**
- Create: `src/decidueye_agent/__init__.py`
- Create: `src/decidueye_agent/main.py`
- Create: `tests/test_decidueye_agent.py`

**Interfaces:**
- Produces: `agent(obs_dict: dict) -> list[int]`、カードID定数群、`DecidPlan` dataclass

- [ ] **Step 1: テストを書く**

`tests/test_decidueye_agent.py` を作成:

```python
import pytest
from dataclasses import dataclass
from cg.api import CardType, EnergyType
import decidueye_agent.main as dm
from unittest.mock import patch


@dataclass
class MockCardData:
    cardId:     int
    name:       str               = ""
    ex:         bool              = False
    stage2:     bool              = False
    stage1:     bool              = False
    cardType:   CardType          = CardType.POKEMON
    weakness:   EnergyType | None = None
    resistance: EnergyType | None = None


def _card(card_id: int, **kwargs) -> MockCardData:
    return MockCardData(cardId=card_id, **kwargs)


@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    table = {
        dm.Rowlet:               _card(dm.Rowlet),
        dm.Dartrix:              _card(dm.Dartrix, stage1=True),
        dm.Decidueye_ex:         _card(dm.Decidueye_ex, ex=True, stage2=True),
        dm.Teal_Mask_Ogerpon_ex: _card(dm.Teal_Mask_Ogerpon_ex, ex=True),
        dm.Budew:                _card(dm.Budew),
        dm.Iron_Leaves:          _card(dm.Iron_Leaves),
        dm.Judge:                _card(dm.Judge,     cardType=CardType.SUPPORTER),
        dm.Xerosic:              _card(dm.Xerosic,   cardType=CardType.SUPPORTER),
        dm.Rare_Candy:           _card(dm.Rare_Candy,         cardType=CardType.ITEM),
        dm.Ultra_Ball:           _card(dm.Ultra_Ball,         cardType=CardType.ITEM),
        dm.Buddy_Buddy_Poffin:   _card(dm.Buddy_Buddy_Poffin, cardType=CardType.ITEM),
        dm.Bug_Catching_Set:     _card(dm.Bug_Catching_Set,   cardType=CardType.ITEM),
        dm.Dusk_Ball:            _card(dm.Dusk_Ball,          cardType=CardType.ITEM),
        dm.Crushing_Hammer:      _card(dm.Crushing_Hammer,    cardType=CardType.ITEM),
        dm.Boss_Orders:          _card(dm.Boss_Orders,        cardType=CardType.SUPPORTER),
        dm.Carmine:              _card(dm.Carmine,            cardType=CardType.SUPPORTER),
        dm.Explorer_Guidance:    _card(dm.Explorer_Guidance,  cardType=CardType.SUPPORTER),
        dm.Night_Stretcher:      _card(dm.Night_Stretcher,    cardType=CardType.ITEM),
        dm.Hand_Trimmer:         _card(dm.Hand_Trimmer,       cardType=CardType.ITEM),
        dm.Prime_Catcher:        _card(dm.Prime_Catcher,      cardType=CardType.ITEM),
        dm.Pokegear:             _card(dm.Pokegear,           cardType=CardType.ITEM),
        dm.Basic_G_Energy:       _card(dm.Basic_G_Energy,     cardType=CardType.ENERGY),
        12: _card(12, cardType=CardType.SPECIAL_ENERGY),
    }
    monkeypatch.setattr(dm, "card_table", table)
    return table


class TestAgentInit:
    def test_returns_deck_when_select_is_none(self):
        """select が None のとき my_deck を返す"""
        obs_dict = {"select": None, "logs": [], "current": None, "search_begin_input": None}
        with patch.object(dm, "my_deck", [1] * 60):
            result = dm.agent(obs_dict)
        assert result == [1] * 60
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
uv run pytest tests/test_decidueye_agent.py::TestAgentInit::test_returns_deck_when_select_is_none -v
```

Expected: `ModuleNotFoundError: No module named 'decidueye_agent'`

- [ ] **Step 3: モジュール基盤を実装する**

`src/decidueye_agent/__init__.py` を作成（空ファイル）:
```python
```

`src/decidueye_agent/main.py` を作成:

```python
import os
from collections import defaultdict
from dataclasses import dataclass

from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, all_card_data, to_observation_class,
)

# ==================== カードID定数 ====================
Rowlet               = 1020
Dartrix              = 1021
Decidueye_ex         = 1022
Teal_Mask_Ogerpon_ex = 96
Budew                = 235
Iron_Leaves          = 27
Basic_G_Energy       = 1
Judge                = 1213
Xerosic              = 1197
Crushing_Hammer      = 1120
Rare_Candy           = 1079
Ultra_Ball           = 1121
Buddy_Buddy_Poffin   = 1086
Bug_Catching_Set     = 1094
Dusk_Ball            = 1102
Boss_Orders          = 1182
Carmine              = 1192
Explorer_Guidance    = 1185
Night_Stretcher      = 1097
Hand_Trimmer         = 1087
Prime_Catcher        = 1088
Pokegear             = 1122

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}


def _build_card_table() -> dict:
    global card_table
    if not card_table:
        card_table = {c.cardId: c for c in all_card_data()}
    return card_table


# ==================== デッキ（遅延初期化）====================
my_deck: list[int] = []


def _load_deck() -> list[int]:
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
class DecidPlan:
    attacker:      int  = -1
    target:        int  = -1
    attack_index:  int  = -1
    sniper_active: bool = False


plan:     DecidPlan = DecidPlan()
pre_turn: int       = 0


def _reset_turn_state() -> None:
    global plan
    plan = DecidPlan()


# ==================== メインエージェント（スタブ）====================
def agent(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        _load_deck()
        return my_deck

    _build_card_table()

    global plan, pre_turn

    state    = obs.current
    select   = obs.select
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]

    if pre_turn != state.turn:
        pre_turn = state.turn
        _reset_turn_state()

    scores = [0] * len(select.option)
    return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
```

- [ ] **Step 4: テストがパスすることを確認**

```bash
uv run pytest tests/test_decidueye_agent.py::TestAgentInit -v
```

Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add src/decidueye_agent/ tests/test_decidueye_agent.py
git commit -m "feat: ジュナイパーexエージェント基盤を追加"
```

---

### Task 2: ユーティリティ関数（prize_count, pokemon_score, energy_score, _collect_field_state）

**Files:**
- Modify: `src/decidueye_agent/main.py`（ユーティリティ関数を追加）
- Modify: `tests/test_decidueye_agent.py`

**Interfaces:**
- Consumes: `card_table`, `make_pokemon`, `make_player_state` (conftest)
- Produces:
  - `prize_count(pokemon: Pokemon) -> int`
  - `pokemon_score(pokemon: Pokemon) -> int`
  - `energy_score(pokemon: Pokemon) -> int`
  - `_collect_field_state(my_state) -> tuple[defaultdict, defaultdict, defaultdict, bool]`
    - 戻り値: `(field_counts, hand_counts, discard_counts, decidueye_ready)`
    - `decidueye_ready`: Decidueye ex が場にいてエネルギー ≥ 1

- [ ] **Step 1: テストを書く**

`tests/test_decidueye_agent.py` に追加:

```python
from tests.conftest import make_pokemon, make_player_state
from cg.api import Card


class TestPrizeCount:
    def test_regular_pokemon_yields_1(self):
        p = make_pokemon(id=dm.Rowlet)
        assert dm.prize_count(p) == 1

    def test_ex_pokemon_yields_2(self):
        p = make_pokemon(id=dm.Decidueye_ex)
        assert dm.prize_count(p) == 2

    def test_legacy_energy_reduces_count(self):
        p = make_pokemon(id=dm.Decidueye_ex)
        legacy = Card(id=12, serial=12, playerIndex=0)
        object.__setattr__(p, "energyCards", [legacy])
        assert dm.prize_count(p) == 1


class TestPokemonScore:
    def test_ex_scores_higher_than_regular(self):
        ex  = make_pokemon(id=dm.Decidueye_ex, hp=320)
        reg = make_pokemon(id=dm.Rowlet, hp=60)
        assert dm.pokemon_score(ex) > dm.pokemon_score(reg)

    def test_more_energies_yields_higher_score(self):
        no_e  = make_pokemon(id=dm.Decidueye_ex, energies=[])
        two_e = make_pokemon(id=dm.Decidueye_ex, energies=[1, 1])
        assert dm.pokemon_score(two_e) > dm.pokemon_score(no_e)


class TestEnergyScore:
    def test_decidueye_ex_prioritised(self):
        """Decidueye ex はその他ポケモンより高いエネルギー付与優先度"""
        decidueye = make_pokemon(id=dm.Decidueye_ex, energies=[])
        rowlet    = make_pokemon(id=dm.Rowlet, energies=[])
        assert dm.energy_score(decidueye) > dm.energy_score(rowlet)

    def test_decidueye_deprioritised_when_full(self):
        """Decidueye ex に 2 枚以上エネルギーがある場合は優先度を下げる"""
        low_e  = make_pokemon(id=dm.Decidueye_ex, energies=[1])
        full_e = make_pokemon(id=dm.Decidueye_ex, energies=[1, 1, 1])
        assert dm.energy_score(low_e) > dm.energy_score(full_e)


class TestCollectFieldState:
    def test_counts_decidueye_ex_in_field(self):
        dec = make_pokemon(id=dm.Decidueye_ex)
        ps  = make_player_state(active_pokemon=dec)
        fc, _, _, ready = dm._collect_field_state(ps)
        assert fc[dm.Decidueye_ex] == 1
        assert ready is False  # エネルギーなし

    def test_decidueye_ready_when_has_energy(self):
        dec = make_pokemon(id=dm.Decidueye_ex, energies=[1])
        ps  = make_player_state(active_pokemon=dec)
        _, _, _, ready = dm._collect_field_state(ps)
        assert ready is True
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
uv run pytest tests/test_decidueye_agent.py::TestPrizeCount tests/test_decidueye_agent.py::TestPokemonScore tests/test_decidueye_agent.py::TestEnergyScore tests/test_decidueye_agent.py::TestCollectFieldState -v
```

Expected: FAIL（関数未定義）

- [ ] **Step 3: ユーティリティ関数を実装する**

`src/decidueye_agent/main.py` の `_reset_turn_state` の直後に追加:

```python
# ==================== ユーティリティ ====================
def get_card(obs: Observation, area: AreaType, index: int, player_index: int):
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
    """KO 時に相手が取るプライズ枚数を返す"""
    data = card_table[pokemon.id]
    count = 2 if data.ex else 1
    for card in pokemon.energyCards:
        if card.id == 12:  # Legacy Energy
            count -= 1
    return max(0, count)


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
    score += pokemon.hp
    return score


def energy_score(pokemon: Pokemon) -> int:
    """エネルギー付与先ポケモンの優先度スコアを返す"""
    score        = 8000
    energy_count = len(pokemon.energies)
    if pokemon.id == Decidueye_ex:
        score += 500
        if energy_count < 2:
            score += 200
        else:
            score -= 300
    elif pokemon.id in (Rowlet, Dartrix):
        score += 50
    elif pokemon.id == Teal_Mask_Ogerpon_ex:
        score -= 200
    return score


# ==================== フィールド状態 ====================
def _collect_field_state(my_state) -> tuple:
    """バトル場・ベンチ・手札・捨て山のカウントと Decidueye ex 準備状況を返す"""
    field_counts    = defaultdict(int)
    hand_counts     = defaultdict(int)
    discard_counts  = defaultdict(int)
    decidueye_ready = False

    for card in my_state.active + my_state.bench:
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id == Decidueye_ex and len(card.energies) >= 1:
            decidueye_ready = True

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    return field_counts, hand_counts, discard_counts, decidueye_ready
```

- [ ] **Step 4: テストがパスすることを確認**

```bash
uv run pytest tests/test_decidueye_agent.py::TestPrizeCount tests/test_decidueye_agent.py::TestPokemonScore tests/test_decidueye_agent.py::TestEnergyScore tests/test_decidueye_agent.py::TestCollectFieldState -v
```

Expected: 8 tests PASS

- [ ] **Step 5: コミット**

```bash
git add src/decidueye_agent/main.py tests/test_decidueye_agent.py
git commit -m "feat: prize_count / pokemon_score / energy_score / _collect_field_state を追加"
```

---

### Task 3: 攻撃プラン計算（calc_attack_plan + Sniper's Eye）

**Files:**
- Modify: `src/decidueye_agent/main.py`
- Modify: `tests/test_decidueye_agent.py`

**Interfaces:**
- Consumes: `DecidPlan`, `Decidueye_ex`, `_collect_field_state` の戻り値
- Produces:
  - `calc_attack_plan(my_state, sniper_active: bool, can_switch: bool) -> DecidPlan`
    - `sniper_active`: `op_state.handCount == 4` のとき True
    - `can_switch`: RETREAT または Switch カードがオプションにある場合 True

- [ ] **Step 1: テストを書く**

`tests/test_decidueye_agent.py` に追加:

```python
class TestCalcAttackPlan:
    def test_attacks_when_sniper_active_and_energy_ready(self):
        """Sniper's Eye 発動中 + Decidueye ex にエネルギー 1 枚 → 攻撃プランを立てる"""
        dec = make_pokemon(id=dm.Decidueye_ex, energies=[1])
        ps  = make_player_state(active_pokemon=dec)
        result = dm.calc_attack_plan(ps, sniper_active=True, can_switch=False)
        assert result.attacker     == 0
        assert result.attack_index == 0
        assert result.sniper_active is True

    def test_no_attack_without_sniper(self):
        """op_hand != 4（Sniper's Eye 未発動）→ 攻撃しない"""
        dec = make_pokemon(id=dm.Decidueye_ex, energies=[1])
        ps  = make_player_state(active_pokemon=dec)
        result = dm.calc_attack_plan(ps, sniper_active=False, can_switch=False)
        assert result.attacker == -1

    def test_no_attack_without_energy(self):
        """Sniper's Eye 発動中でもエネルギー 0 枚 → 攻撃しない"""
        dec = make_pokemon(id=dm.Decidueye_ex, energies=[])
        ps  = make_player_state(active_pokemon=dec)
        result = dm.calc_attack_plan(ps, sniper_active=True, can_switch=False)
        assert result.attacker == -1

    def test_attacks_from_bench_when_can_switch(self):
        """ベンチの Decidueye ex + can_switch=True → 攻撃プランを立てる"""
        rowlet = make_pokemon(id=dm.Rowlet)
        dec    = make_pokemon(id=dm.Decidueye_ex, energies=[1])
        ps     = make_player_state(active_pokemon=rowlet, bench=[dec])
        result = dm.calc_attack_plan(ps, sniper_active=True, can_switch=True)
        assert result.attacker == 1  # ベンチ index 0 → 全体 index 1
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
uv run pytest tests/test_decidueye_agent.py::TestCalcAttackPlan -v
```

Expected: FAIL（`calc_attack_plan` 未定義）

- [ ] **Step 3: calc_attack_plan を実装する**

`src/decidueye_agent/main.py` の `_collect_field_state` の直後に追加:

```python
# ==================== 攻撃プラン計算 ====================
def calc_attack_plan(my_state, sniper_active: bool, can_switch: bool) -> DecidPlan:
    """Sniper's Eye が発動しているときのみ Crushing Arrow プランを立てる"""
    new_plan = DecidPlan()

    if not sniper_active:
        return new_plan

    # バトル場 → ベンチの順に Decidueye ex を探す
    my_cards = list(my_state.active) + list(my_state.bench)
    for i, pokemon in enumerate(my_cards):
        if pokemon is None:
            continue
        if i != 0 and not can_switch:
            break
        if pokemon.id == Decidueye_ex and len(pokemon.energies) >= 1:
            new_plan.attacker     = i
            new_plan.attack_index = 0   # Crushing Arrow（唯一の技）
            new_plan.target       = 0   # 相手アクティブを狙う
            new_plan.sniper_active = True
            break

    return new_plan
```

- [ ] **Step 4: テストがパスすることを確認**

```bash
uv run pytest tests/test_decidueye_agent.py::TestCalcAttackPlan -v
```

Expected: 4 tests PASS

- [ ] **Step 5: コミット**

```bash
git add src/decidueye_agent/main.py tests/test_decidueye_agent.py
git commit -m "feat: calc_attack_plan（Sniper's Eye 起動判定）を追加"
```

---

### Task 4: スコアリング + agent()完成 + 統合テスト

**Files:**
- Modify: `src/decidueye_agent/main.py`（スコアリング関数 + agent() 完成）
- Modify: `tests/test_decidueye_agent.py`（統合テスト追加）

**Interfaces:**
- Consumes: `calc_attack_plan`, `_collect_field_state`, `energy_score`, `get_card`, `DecidPlan`
- Produces: 完全な `agent(obs_dict: dict) -> list[int]`

- [ ] **Step 1: 統合テストを書く**

`tests/test_decidueye_agent.py` に追加:

```python
from tests.conftest import make_main_obs
from cg.api import Option, OptionType


class TestAgent:
    def test_returns_valid_indices(self):
        """返り値が option の範囲内で重複なし"""
        options = [
            Option(type=OptionType.ATTACK, attackId=100),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(options=options)
        result = dm.agent(obs_dict)
        assert all(0 <= i < len(options) for i in result)
        assert len(result) == len(set(result))

    def test_attacks_when_sniper_active(self):
        """Sniper's Eye 発動中（op_hand=4）は ATTACK を END より優先する"""
        dec = make_pokemon(id=dm.Decidueye_ex, energies=[1])
        my_ps = make_player_state(active_pokemon=dec)
        op_ps = make_player_state(
            active_pokemon=make_pokemon(id=1, hp=200),
            hand_count=4,   # Sniper's Eye 発動条件
        )
        options = [
            Option(type=OptionType.END),
            Option(type=OptionType.ATTACK, attackId=999),
        ]
        obs_dict = make_main_obs(my_state=my_ps, op_state=op_ps, options=options, turn=3)
        result = dm.agent(obs_dict)
        assert options[result[0]].type == OptionType.ATTACK

    def test_no_attack_when_sniper_inactive(self):
        """Sniper's Eye 未発動（op_hand=7）は ATTACK を END より低優先にする"""
        dec = make_pokemon(id=dm.Decidueye_ex, energies=[1])
        my_ps = make_player_state(active_pokemon=dec)
        op_ps = make_player_state(
            active_pokemon=make_pokemon(id=1, hp=200),
            hand_count=7,   # Sniper's Eye 未発動
        )
        options = [
            Option(type=OptionType.END),
            Option(type=OptionType.ATTACK, attackId=999),
        ]
        obs_dict = make_main_obs(my_state=my_ps, op_state=op_ps, options=options, turn=3)
        result = dm.agent(obs_dict)
        assert options[result[0]].type == OptionType.END

    def test_resets_plan_on_new_turn(self):
        """ターンが変わったら plan がリセットされる"""
        dm.pre_turn = 5
        dm.plan     = dm.DecidPlan(attacker=1, target=0, attack_index=0, sniper_active=True)
        obs_dict    = make_main_obs(options=[Option(type=OptionType.END)], turn=6)
        dm.agent(obs_dict)
        assert dm.plan.attacker == -1
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
uv run pytest tests/test_decidueye_agent.py::TestAgent -v
```

Expected: `test_attacks_when_sniper_active` と `test_no_attack_when_sniper_inactive` が FAIL（スコアリング未実装）

- [ ] **Step 3: スコアリング関数を実装する**

`src/decidueye_agent/main.py` の `calc_attack_plan` の直後に追加:

```python
# ==================== スコアリング ====================
def _score_play_option(
    obs, o, my_index: int, my_state, op_state,
    field_counts: defaultdict, hand_counts: defaultdict,
    current_plan: DecidPlan, sniper_active: bool, op_hand_count: int,
) -> int:
    """PLAY オプション（手札からカードを出す）のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    if card is None:
        return -1

    # Judge: Sniper's Eye 未発動なら最優先
    if card.id == Judge:
        return 10000 if not sniper_active else 1000

    # Xerosic: 相手手札 > 4 枚なら高優先（次ターン相手が 1 ドローして 4 枚になる）
    if card.id == Xerosic:
        return 8000 if op_hand_count > 4 else -1

    # Rare Candy: 手札に Decidueye ex があり場に Rowlet/Dartrix がいる
    if card.id == Rare_Candy:
        if hand_counts[Decidueye_ex] > 0 and (field_counts[Rowlet] + field_counts[Dartrix]) > 0:
            return 9000
        return -1

    # Ultra Ball: Decidueye ex 未展開なら高優先
    if card.id == Ultra_Ball:
        return 7000 if field_counts[Decidueye_ex] == 0 else 5000

    # Bug Catching Set: G ポケモン・G エネ検索
    if card.id == Bug_Catching_Set:
        return 7000 if field_counts[Decidueye_ex] == 0 else 3000

    # Dusk Ball: ポケモン検索
    if card.id == Dusk_Ball:
        return 6000 if field_counts[Decidueye_ex] == 0 else 2500

    # Buddy-Buddy Poffin: 序盤の基本展開
    if card.id == Buddy_Buddy_Poffin:
        return 5000

    # Crushing Hammer: 相手アクティブにエネルギーあり
    if card.id == Crushing_Hammer:
        op_active = op_state.active[0] if op_state.active else None
        return 4000 if (op_active and len(op_active.energies) > 0) else 2000

    # Boss's Orders: 呼び出し
    if card.id == Boss_Orders:
        return 3000

    # Carmine / Explorer's Guidance: ドロー
    if card.id in (Carmine, Explorer_Guidance):
        return 2000

    # Night Stretcher: ポケモン回収
    if card.id == Night_Stretcher:
        return 2000

    # Prime Catcher: ACE SPEC 入れ替え
    if card.id == Prime_Catcher:
        return 2500

    # Hand Trimmer: 相手手札 > 5 のとき使う
    if card.id == Hand_Trimmer:
        return 3000 if op_hand_count > 5 else -1

    # Pokégear: サポーター検索
    if card.id == Pokegear:
        return 1500

    return 1000


def _score_option(
    obs, o, context, my_index: int, my_state, op_state,
    field_counts: defaultdict, hand_counts: defaultdict,
    current_plan: DecidPlan, sniper_active: bool, op_hand_count: int,
) -> int:
    """1 つのオプションにスコアを付ける"""
    match o.type:
        case OptionType.NUMBER:
            return o.number
        case OptionType.YES:
            return 1
        case OptionType.PLAY:
            return _score_play_option(
                obs, o, my_index, my_state, op_state,
                field_counts, hand_counts, current_plan, sniper_active, op_hand_count,
            )
        case OptionType.ATTACH:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            return energy_score(pokemon) if pokemon else 0
        case OptionType.EVOLVE:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            if card.id == Decidueye_ex:
                return 20000
            if card.id == Dartrix:
                return 15000
            return 9000
        case OptionType.ABILITY:
            return 5000
        case OptionType.RETREAT:
            return 2000 if current_plan.attacker >= 1 else -1
        case OptionType.ATTACK:
            return 15000 if current_plan.sniper_active else -1  # Sniper's Eye 未発動時は攻撃しない
        case _:
            return 0
```

- [ ] **Step 4: agent() を完成させる**

`src/decidueye_agent/main.py` の `agent()` 関数全体を以下に差し替える:

```python
def agent(obs_dict: dict) -> list[int]:
    """Pokémon TCG エージェント（ジュナイパーexコントロール）"""
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        _load_deck()
        return my_deck

    _build_card_table()

    global plan, pre_turn

    state        = obs.current
    select       = obs.select
    context      = select.context
    my_index     = state.yourIndex
    my_state     = state.players[my_index]
    op_state     = state.players[1 - my_index]
    op_hand_count = op_state.handCount

    if pre_turn != state.turn:
        pre_turn = state.turn
        _reset_turn_state()

    field_counts, hand_counts, discard_counts, decidueye_ready = _collect_field_state(my_state)
    sniper_active = (op_hand_count == 4)

    # MAIN コンテキストでのみ攻撃プランを計算
    can_switch = False
    if context == SelectContext.MAIN and state.turn >= 2:
        for o in select.option:
            if o.type in (OptionType.RETREAT,):
                can_switch = True
        plan = calc_attack_plan(my_state, sniper_active, can_switch)

    scores = [
        _score_option(
            obs, o, context, my_index, my_state, op_state,
            field_counts, hand_counts, plan, sniper_active, op_hand_count,
        )
        for o in select.option
    ]

    return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
```

- [ ] **Step 5: 全テストがパスすることを確認**

```bash
uv run pytest tests/test_decidueye_agent.py -v
```

Expected: 全テスト PASS

- [ ] **Step 6: 既存テストへの影響がないことを確認**

```bash
uv run pytest tests/ -v
```

Expected: 全テスト PASS

- [ ] **Step 7: コミット**

```bash
git add src/decidueye_agent/main.py tests/test_decidueye_agent.py
git commit -m "feat: ジュナイパーexコントロールエージェント完成"
```
