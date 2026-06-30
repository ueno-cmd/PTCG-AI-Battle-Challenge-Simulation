# Cinderace + Mega Starmie ex エージェント実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cinderace の Turbo Flare でエネ加速し、Mega Starmie ex が Nebula Beam 210 を連打するルールベースエージェントを実装する

**Architecture:** Lucario エージェント（`src/lucario_agent/main.py`）の構造をベースに、FieldState dataclass でターン状態を集約し、カード種別ごとのスコア関数に分岐する。攻撃IDは `all_card_data()` から動的に取得し、ハードコードを避ける。

**Tech Stack:** Python 3.12, uv, cg.api, pytest

## Global Constraints

- Python 3.12.13 / uv 実行環境
- `cg.api` の `all_card_data()` / `all_attack()` は Kaggle 環境でのみ動作（macOS では libcg.so 未対応）
- テストは `conftest.py` の `make_pokemon` / `make_player_state` / `make_main_obs` を使う
- `cg.sim` / `cg.game` は conftest で自動モック済み
- コメントは日本語、変数名・関数名は英語
- テスト実行コマンド: `uv run pytest tests/ -v`

---

## ファイル構成

```
新規作成:
  decks/cinderace_starmie_20260630.py          # デッキ定義（60枚）
  src/cinderace_starmie_agent/__init__.py      # agent を公開
  src/cinderace_starmie_agent/main.py          # エージェント本体
  tests/test_cinderace_starmie_deck.py         # デッキバリデーションテスト
  tests/test_cinderace_starmie_agent.py        # エージェントユニットテスト

参照（変更なし）:
  tests/conftest.py                            # make_pokemon / make_player_state / make_main_obs
  src/lucario_agent/main.py                    # 実装パターンの参照元
```

---

## Task 1: デッキ定義

**Files:**
- Create: `decks/cinderace_starmie_20260630.py`
- Test: `tests/test_cinderace_starmie_deck.py`

**Interfaces:**
- Produces: `DECK: list[tuple[int, int]]` — `(card_id, count)` タプルのリスト、合計60枚

- [ ] **Step 1: テストを書く**

```python
# tests/test_cinderace_starmie_deck.py
from decks.cinderace_starmie_20260630 import DECK

ENERGY_IDS = {3, 17}  # Basic Water Energy, Ignition Energy


def test_deck_has_60_cards():
    assert sum(count for _, count in DECK) == 60


def test_no_non_energy_card_exceeds_4_copies():
    for card_id, count in DECK:
        if card_id not in ENERGY_IDS:
            assert count <= 4, f"Card {card_id} が {count} 枚（上限4枚）"


def test_key_pokemon_present():
    ids = {card_id for card_id, _ in DECK}
    assert 664  in ids, "Scorbunny が不在"
    assert 666  in ids, "Cinderace が不在"
    assert 1030 in ids, "Staryu が不在"
    assert 1031 in ids, "Mega Starmie ex が不在"


def test_energy_counts():
    water    = sum(c for i, c in DECK if i == 3)
    ignition = sum(c for i, c in DECK if i == 17)
    assert water    == 11
    assert ignition == 4
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_cinderace_starmie_deck.py -v
```
期待: `ModuleNotFoundError: No module named 'decks.cinderace_starmie_20260630'`

- [ ] **Step 3: デッキ定義ファイルを実装する**

```python
# decks/cinderace_starmie_20260630.py
# エースバーン + メガスターミーex デッキ（20260630生成）
# 設計書: docs/superpowers/specs/2026-06-30-cinderace-starmie-agent-design.md

DECK = [
    (664,  4),   # Scorbunny（Cinderace進化元・Buddy-Buddy Poffin対象70HP）
    (665,  2),   # Raboot（中間進化）
    (666,  4),   # Cinderace（Explosiveness特性でバトル場スタート可）
    (1030, 4),   # Staryu（Mega Starmie ex進化元・Buddy-Buddy Poffin対象70HP）
    (1031, 4),   # Mega Starmie ex（メインアタッカー）
    (1086, 4),   # Buddy-Buddy Poffin（Scorbunny+Staryuを同時ベンチへ）
    (1121, 3),   # Ultra Ball（万能サーチ）
    (1145, 3),   # Mega Signal（Mega Starmie ex専用サーチ）
    (1097, 2),   # Night Stretcher（トラッシュ回収）
    (1159, 1),   # Hero's Cape（Mega Starmie ex HP+100=430）
    (1122, 3),   # Pokégear 3.0（山上7枚からサポートサーチ）
    (1120, 1),   # Crushing Hammer（相手エネ破壊）
    (1189, 3),   # Salvatore（Staryu→Mega Starmie ex直接進化）
    (1225, 3),   # Hilda（進化ポケモン+エネサーチ）
    (1227, 2),   # Lillie's Determination（ドロー6枚）
    (1229, 2),   # Wally's Compassion（Mega Starmie ex全回復+エネ手札回収）
    (3,   11),   # Basic Water Energy
    (17,   4),   # Ignition Energy（Turbo Flare起動用・ターン終了で自動トラッシュ）
]
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run pytest tests/test_cinderace_starmie_deck.py -v
```
期待: 4件 PASSED

- [ ] **Step 5: コミット**

```bash
git add decks/cinderace_starmie_20260630.py tests/test_cinderace_starmie_deck.py
git commit -m "feat: Cinderace+Starmieデッキ定義を追加"
```

---

## Task 2: エージェント骨格（定数・ユーティリティ・FieldState収集）

**Files:**
- Create: `src/cinderace_starmie_agent/__init__.py`
- Create: `src/cinderace_starmie_agent/main.py`（骨格部分）
- Test: `tests/test_cinderace_starmie_agent.py`（FieldState 収集テスト）

**Interfaces:**
- Produces:
  - `_collect_field_state(my_state, op_state) -> FieldState`
  - `get_card(obs, area, index, player_index) -> Pokemon | Card | None`
  - モジュール定数: `Cinderace=666`, `Mega_Starmie_ex=1031`, etc.

- [ ] **Step 1: テストを書く**

```python
# tests/test_cinderace_starmie_agent.py
import pytest
from dataclasses import dataclass, field
from collections import defaultdict
from cg.api import CardType, Card

import cinderace_starmie_agent.main as cm
from tests.conftest import make_pokemon, make_player_state


@dataclass
class MockCardData:
    cardId:   int
    name:     str      = ""
    megaEx:   bool     = False
    ex:       bool     = False
    stage1:   bool     = False
    stage2:   bool     = False
    cardType: CardType = CardType.POKEMON
    attacks:  list     = field(default_factory=list)


@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    table = {
        cm.Scorbunny:            MockCardData(cardId=cm.Scorbunny),
        cm.Raboot:               MockCardData(cardId=cm.Raboot, stage1=True),
        cm.Cinderace:            MockCardData(cardId=cm.Cinderace, stage2=True, attacks=[9001]),
        cm.Staryu:               MockCardData(cardId=cm.Staryu),
        cm.Mega_Starmie_ex:      MockCardData(cardId=cm.Mega_Starmie_ex, megaEx=True, attacks=[9002, 9003]),
        cm.Buddy_Buddy_Poffin:   MockCardData(cardId=cm.Buddy_Buddy_Poffin,   cardType=CardType.ITEM),
        cm.Ultra_Ball:           MockCardData(cardId=cm.Ultra_Ball,           cardType=CardType.ITEM),
        cm.Mega_Signal:          MockCardData(cardId=cm.Mega_Signal,          cardType=CardType.ITEM),
        cm.Night_Stretcher:      MockCardData(cardId=cm.Night_Stretcher,      cardType=CardType.ITEM),
        cm.Heros_Cape:           MockCardData(cardId=cm.Heros_Cape,           cardType=CardType.TOOL),
        cm.Pokegear_30:          MockCardData(cardId=cm.Pokegear_30,          cardType=CardType.ITEM),
        cm.Crushing_Hammer:      MockCardData(cardId=cm.Crushing_Hammer,      cardType=CardType.ITEM),
        cm.Salvatore:            MockCardData(cardId=cm.Salvatore,            cardType=CardType.SUPPORTER),
        cm.Hilda:                MockCardData(cardId=cm.Hilda,                cardType=CardType.SUPPORTER),
        cm.Lillie_Determination: MockCardData(cardId=cm.Lillie_Determination, cardType=CardType.SUPPORTER),
        cm.Wallys_Compassion:    MockCardData(cardId=cm.Wallys_Compassion,    cardType=CardType.SUPPORTER),
        cm.Basic_Water_Energy:   MockCardData(cardId=cm.Basic_Water_Energy,   cardType=CardType.ENERGY),
        cm.Ignition_Energy:      MockCardData(cardId=cm.Ignition_Energy,      cardType=CardType.SPECIAL_ENERGY),
    }
    monkeypatch.setattr(cm, "card_table",       table)
    monkeypatch.setattr(cm, "Turbo_Flare_ID",   9001)
    monkeypatch.setattr(cm, "Jetting_Blow_ID",  9002)
    monkeypatch.setattr(cm, "Nebula_Beam_ID",   9003)
    return table


# ==================== _collect_field_state ====================
class TestCollectFieldState:
    def test_cinderace_active_with_energy(self):
        cinderace = make_pokemon(id=cm.Cinderace, energies=[3])
        my_ps = make_player_state(active_pokemon=cinderace)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.cinderace_active is True

    def test_cinderace_active_without_energy_is_false(self):
        cinderace = make_pokemon(id=cm.Cinderace, energies=[])
        my_ps = make_player_state(active_pokemon=cinderace)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.cinderace_active is False

    def test_starmie_bench_detected(self):
        starmie = make_pokemon(id=cm.Mega_Starmie_ex, energies=[3, 3, 3])
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=cm.Cinderace),
            bench=[starmie],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.starmie_bench_idx    == 0
        assert fs.starmie_bench_energy == 3

    def test_starmie_bench_absent_returns_minus1(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=cm.Scorbunny))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.starmie_bench_idx == -1

    def test_switch_to_starmie_when_ready(self):
        starmie   = make_pokemon(id=cm.Mega_Starmie_ex, energies=[3])
        scorbunny = make_pokemon(id=cm.Scorbunny)
        my_ps = make_player_state(active_pokemon=scorbunny, bench=[starmie])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.switch_to_starmie is True

    def test_no_switch_when_cinderace_active(self):
        cinderace = make_pokemon(id=cm.Cinderace, energies=[3])
        starmie   = make_pokemon(id=cm.Mega_Starmie_ex, energies=[3])
        my_ps = make_player_state(active_pokemon=cinderace, bench=[starmie])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.switch_to_starmie is False

    def test_wally_in_hand(self):
        wally = Card(id=cm.Wallys_Compassion, serial=1, playerIndex=0)
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=cm.Mega_Starmie_ex, hp=200, max_hp=330),
            hand=[wally],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.wally_in_hand is True

    def test_starmie_active_damage(self):
        starmie = make_pokemon(id=cm.Mega_Starmie_ex, hp=200, max_hp=330)
        my_ps = make_player_state(active_pokemon=starmie)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = cm._collect_field_state(my_ps, op_ps)
        assert fs.starmie_active_damage == 130  # 330 - 200
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_cinderace_starmie_agent.py::TestCollectFieldState -v
```
期待: `ModuleNotFoundError: No module named 'cinderace_starmie_agent'`

- [ ] **Step 3: `__init__.py` を作成する**

```python
# src/cinderace_starmie_agent/__init__.py
from .main import agent
```

- [ ] **Step 4: `main.py` の骨格を実装する**

```python
# src/cinderace_starmie_agent/main.py
import os
from collections import defaultdict
from dataclasses import dataclass, field

from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, all_card_data, to_observation_class,
)

# ==================== カードID定数 ====================
Scorbunny            = 664
Raboot               = 665
Cinderace            = 666
Staryu               = 1030
Mega_Starmie_ex      = 1031

Buddy_Buddy_Poffin   = 1086
Ultra_Ball           = 1121
Mega_Signal          = 1145
Night_Stretcher      = 1097
Heros_Cape           = 1159
Pokegear_30          = 1122
Crushing_Hammer      = 1120
Salvatore            = 1189
Hilda                = 1225
Lillie_Determination = 1227
Wallys_Compassion    = 1229

Basic_Water_Energy   = 3
Ignition_Energy      = 17

# ==================== アタックID（_build_card_table で設定）====================
Turbo_Flare_ID:  int = 0
Jetting_Blow_ID: int = 0
Nebula_Beam_ID:  int = 0

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築し、攻撃IDも設定する"""
    global card_table, Turbo_Flare_ID, Jetting_Blow_ID, Nebula_Beam_ID
    if not card_table:
        card_table      = {c.cardId: c for c in all_card_data()}
        cinderace_data  = card_table[Cinderace]
        starmie_data    = card_table[Mega_Starmie_ex]
        Turbo_Flare_ID  = cinderace_data.attacks[0]   # Turbo Flare
        Jetting_Blow_ID = starmie_data.attacks[0]     # Jetting Blow
        Nebula_Beam_ID  = starmie_data.attacks[1]     # Nebula Beam
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


# ==================== フィールド状態 ====================
@dataclass
class FieldState:
    """毎ターン計算されるフィールド状態"""
    field_counts:          defaultdict
    hand_counts:           defaultdict
    discard_counts:        defaultdict
    cinderace_active:      bool
    starmie_bench_idx:     int
    starmie_bench_energy:  int
    starmie_active_damage: int
    op_active_hp:          int
    wally_in_hand:         bool
    switch_to_starmie:     bool


def _collect_field_state(my_state, op_state) -> FieldState:
    """バトル場・ベンチ・手札・トラッシュから行動判断に必要な状態を収集する"""
    field_counts   = defaultdict(int)
    hand_counts    = defaultdict(int)
    discard_counts = defaultdict(int)

    cinderace_active     = False
    starmie_bench_idx    = -1
    starmie_bench_energy = 0
    starmie_active_dmg   = 0

    for card in my_state.active:
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id == Cinderace and len(card.energies) >= 1:
            cinderace_active = True
        elif card.id == Mega_Starmie_ex:
            starmie_active_dmg = card.maxHp - card.hp

    for i, card in enumerate(my_state.bench):
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id == Mega_Starmie_ex and starmie_bench_idx == -1:
            starmie_bench_idx    = i
            starmie_bench_energy = len(card.energies)

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    op_active_hp = 0
    for card in op_state.active:
        if card is not None:
            op_active_hp = card.hp

    wally_in_hand     = hand_counts[Wallys_Compassion] >= 1
    switch_to_starmie = (
        starmie_bench_idx >= 0
        and starmie_bench_energy >= 1
        and not cinderace_active
    )

    return FieldState(
        field_counts=field_counts,
        hand_counts=hand_counts,
        discard_counts=discard_counts,
        cinderace_active=cinderace_active,
        starmie_bench_idx=starmie_bench_idx,
        starmie_bench_energy=starmie_bench_energy,
        starmie_active_damage=starmie_active_dmg,
        op_active_hp=op_active_hp,
        wally_in_hand=wally_in_hand,
        switch_to_starmie=switch_to_starmie,
    )


def agent(obs_dict: dict) -> list[int]:
    """暫定実装（Task 4 で完成させる）"""
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        _load_deck()
        return my_deck
    return [0]
```

- [ ] **Step 5: テストが通ることを確認する**

```bash
uv run pytest tests/test_cinderace_starmie_agent.py::TestCollectFieldState -v
```
期待: 8件 PASSED

- [ ] **Step 6: コミット**

```bash
git add src/cinderace_starmie_agent/ tests/test_cinderace_starmie_agent.py
git commit -m "feat: Cinderace+Starmieエージェント骨格とFieldState収集を追加"
```

---

## Task 3: スコアリング関数群

**Files:**
- Modify: `src/cinderace_starmie_agent/main.py`（スコアリング関数を追加）
- Test: `tests/test_cinderace_starmie_agent.py`（スコアリングテストを追記）

**Interfaces:**
- Consumes: `FieldState`（Task 2）, `card_table`, `Turbo_Flare_ID`, `Jetting_Blow_ID`, `Nebula_Beam_ID`
- Produces:
  - `_score_play(card_id, fs, prize_count) -> int`
  - `_score_attach(pokemon, area, card_id, fs) -> int`
  - `_score_attack(attack_id, fs) -> int`
  - `_score_card_option(obs, o, context, my_index, fs, discard_hand_counts) -> int`

- [ ] **Step 1: スコアリングテストを追記する**

`tests/test_cinderace_starmie_agent.py` に以下を追加:

```python
# ==================== _score_play ====================
class TestScorePlay:
    def _make_fs(self, **kwargs):
        defaults = dict(
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int),
            discard_counts=defaultdict(int),
            cinderace_active=False,
            starmie_bench_idx=-1,
            starmie_bench_energy=0,
            starmie_active_damage=0,
            op_active_hp=200,
            wally_in_hand=False,
            switch_to_starmie=False,
        )
        defaults.update(kwargs)
        return cm.FieldState(**defaults)

    def test_lillie_determination_first_turn(self):
        fs = self._make_fs()
        assert cm._score_play(cm.Lillie_Determination, fs, prize_count=6) == 10000

    def test_lillie_determination_normal_turn(self):
        fs = self._make_fs()
        assert cm._score_play(cm.Lillie_Determination, fs, prize_count=4) == 3000

    def test_buddy_buddy_poffin_high_when_lines_missing(self):
        fs = self._make_fs()  # field_counts と hand_counts は空
        score = cm._score_play(cm.Buddy_Buddy_Poffin, fs, prize_count=6)
        assert score == 8000

    def test_salvatore_high_when_staryu_present_starmie_absent(self):
        fc = defaultdict(int, {cm.Staryu: 1})
        fs = self._make_fs(field_counts=fc)
        score = cm._score_play(cm.Salvatore, fs, prize_count=6)
        assert score == 7000

    def test_wally_compassion_high_when_starmie_damaged(self):
        fs = self._make_fs(starmie_active_damage=100)
        score = cm._score_play(cm.Wallys_Compassion, fs, prize_count=6)
        assert score == 6500

    def test_wally_compassion_minus1_when_no_damage(self):
        fs = self._make_fs(starmie_active_damage=0)
        score = cm._score_play(cm.Wallys_Compassion, fs, prize_count=6)
        assert score == -1

    def test_mega_signal_high_when_starmie_absent(self):
        fs = self._make_fs()
        score = cm._score_play(cm.Mega_Signal, fs, prize_count=6)
        assert score == 4500

    def test_mega_signal_low_when_starmie_present(self):
        fc = defaultdict(int, {cm.Mega_Starmie_ex: 1})
        fs = self._make_fs(field_counts=fc)
        score = cm._score_play(cm.Mega_Signal, fs, prize_count=6)
        assert score == 1000


# ==================== _score_attach ====================
class TestScoreAttach:
    def _make_fs(self, **kwargs):
        defaults = dict(
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int),
            discard_counts=defaultdict(int),
            cinderace_active=False,
            starmie_bench_idx=0,
            starmie_bench_energy=0,
            starmie_active_damage=0,
            op_active_hp=200,
            wally_in_hand=False,
            switch_to_starmie=False,
        )
        defaults.update(kwargs)
        return cm.FieldState(**defaults)

    def test_ignition_to_cinderace_with_0_energy(self):
        cinderace = make_pokemon(id=cm.Cinderace, energies=[])
        fs = self._make_fs()
        score = cm._score_attach(cinderace, AreaType.ACTIVE, cm.Ignition_Energy, fs)
        assert score == 9000

    def test_ignition_to_cinderace_with_existing_energy_is_minus1(self):
        cinderace = make_pokemon(id=cm.Cinderace, energies=[17])
        fs = self._make_fs()
        score = cm._score_attach(cinderace, AreaType.ACTIVE, cm.Ignition_Energy, fs)
        assert score == -1

    def test_ignition_to_non_cinderace_is_minus1(self):
        starmie = make_pokemon(id=cm.Mega_Starmie_ex, energies=[])
        fs = self._make_fs()
        score = cm._score_attach(starmie, AreaType.BENCH, cm.Ignition_Energy, fs)
        assert score == -1

    def test_water_to_bench_starmie_low_energy_preferred(self):
        starmie_low  = make_pokemon(id=cm.Mega_Starmie_ex, energies=[])
        starmie_full = make_pokemon(id=cm.Mega_Starmie_ex, energies=[3, 3, 3])
        fs = self._make_fs()
        score_low  = cm._score_attach(starmie_low,  AreaType.BENCH, cm.Basic_Water_Energy, fs)
        score_full = cm._score_attach(starmie_full, AreaType.BENCH, cm.Basic_Water_Energy, fs)
        assert score_low > score_full


# ==================== _score_attack ====================
class TestScoreAttack:
    def _make_fs(self, op_hp=200, **kwargs):
        defaults = dict(
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int),
            discard_counts=defaultdict(int),
            cinderace_active=False,
            starmie_bench_idx=-1,
            starmie_bench_energy=0,
            starmie_active_damage=0,
            op_active_hp=op_hp,
            wally_in_hand=False,
            switch_to_starmie=False,
        )
        defaults.update(kwargs)
        return cm.FieldState(**defaults)

    def test_turbo_flare_always_scores_1000(self):
        fs = self._make_fs(op_hp=300)
        assert cm._score_attack(9001, fs) == 1000

    def test_nebula_beam_preferred_when_hp_high(self):
        fs = self._make_fs(op_hp=300)
        assert cm._score_attack(9003, fs) > cm._score_attack(9002, fs)

    def test_jetting_blow_preferred_when_hp_low(self):
        fs = self._make_fs(op_hp=100)
        assert cm._score_attack(9002, fs) > cm._score_attack(9003, fs)
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_cinderace_starmie_agent.py::TestScorePlay tests/test_cinderace_starmie_agent.py::TestScoreAttach tests/test_cinderace_starmie_agent.py::TestScoreAttack -v
```
期待: `AttributeError: module has no attribute '_score_play'`

- [ ] **Step 3: スコアリング関数を `main.py` に追加する**

`# ==================== フィールド状態 ====================` ブロックの直後に追加:

```python
# ==================== スコアリング ====================
def _score_play(card_id: int, fs: FieldState, prize_count: int) -> int:
    """PLAY コンテキスト：手札からカードを使う際のスコア"""
    if card_id == Lillie_Determination:
        return 10000 if prize_count == 6 else 3000
    if card_id == Buddy_Buddy_Poffin:
        needs_scorbunny = fs.field_counts[Scorbunny] + fs.hand_counts[Scorbunny] == 0
        needs_staryu    = fs.field_counts[Staryu]    + fs.hand_counts[Staryu]    == 0
        return 8000 if (needs_scorbunny or needs_staryu) else 2000
    if card_id == Salvatore:
        has_staryu    = fs.field_counts[Staryu] >= 1
        needs_starmie = (
            fs.field_counts[Mega_Starmie_ex] + fs.hand_counts[Mega_Starmie_ex] == 0
        )
        return 7000 if (has_staryu and needs_starmie) else 2000
    if card_id == Wallys_Compassion:
        return 6500 if fs.starmie_active_damage > 0 else -1
    if card_id == Hilda:
        needs_cinderace = fs.field_counts[Cinderace] + fs.hand_counts[Cinderace] == 0
        needs_starmie   = (
            fs.field_counts[Mega_Starmie_ex] + fs.hand_counts[Mega_Starmie_ex] == 0
        )
        return 5000 if (needs_cinderace or needs_starmie) else 2000
    if card_id == Mega_Signal:
        return 4500 if fs.field_counts[Mega_Starmie_ex] == 0 else 1000
    if card_id == Pokegear_30:
        has_supporter = any(
            fs.hand_counts[c] >= 1
            for c in (Salvatore, Hilda, Lillie_Determination, Wallys_Compassion)
        )
        return 4000 if not has_supporter else 1500
    if card_id == Ultra_Ball:
        needs_any = (
            fs.field_counts[Cinderace]       + fs.hand_counts[Cinderace]       == 0
            or fs.field_counts[Mega_Starmie_ex] + fs.hand_counts[Mega_Starmie_ex] == 0
        )
        return 3000 if needs_any else -1
    if card_id == Night_Stretcher:
        useful = (
            fs.discard_counts[Staryu] >= 1
            or fs.discard_counts[Basic_Water_Energy] >= 1
            or fs.discard_counts[Cinderace] >= 1
        )
        return 2000 if useful else 500
    if card_id == Crushing_Hammer:
        return 1000
    return 2000


def _score_attach(pokemon: "Pokemon", area: AreaType, card_id: int, fs: FieldState) -> int:
    """ATTACH コンテキスト：エネルギー/ツールの付与先スコア"""
    energy_count = len(pokemon.energies)
    if card_id == Ignition_Energy:
        # Cinderaceへのみ・0エネのときだけ（Turbo Flare 起動用）
        if pokemon.id == Cinderace and energy_count == 0:
            return 9000
        return -1
    if card_id == Heros_Cape:
        # Mega Starmie ex への Hero's Cape 装着を最優先
        return 8500 if pokemon.id == Mega_Starmie_ex else -1
    if card_id == Basic_Water_Energy:
        if pokemon.id == Mega_Starmie_ex:
            if area == AreaType.BENCH and energy_count <= 2:
                return 8000 + (3 - energy_count) * 100
            if area == AreaType.ACTIVE and energy_count == 0:
                return 7500
        if pokemon.id == Cinderace and energy_count == 0:
            return 7000
        return -1
    return 5000


def _score_attack(attack_id: int, fs: FieldState) -> int:
    """ATTACK コンテキスト：ワザ選択スコア"""
    if attack_id == Turbo_Flare_ID:
        return 1000
    if attack_id == Jetting_Blow_ID:
        # 相手HP ≤ 170 なら Jetting Blow + ベンチ50 でちょうど倒せる圏内
        return 1200 if fs.op_active_hp <= 170 else 800
    if attack_id == Nebula_Beam_ID:
        return 1200 if fs.op_active_hp > 170 else 800
    return 1000


def _score_card_option(
    obs: Observation,
    o,
    context,
    my_index: int,
    fs: FieldState,
    discard_hand_counts: defaultdict,
) -> int:
    """OptionType.CARD のコンテキスト別スコア"""
    card = get_card(obs, o.area, o.index, o.playerIndex)
    if card is None:
        return 0

    match context:
        case SelectContext.SETUP_ACTIVE_POKEMON:
            if card.id == Cinderace:
                return 100   # Explosiveness 特性でバトル場スタート最優先
            if card.id == Scorbunny:
                return 50
            if card.id == Staryu:
                return 30
            return 10

        case SelectContext.SWITCH | SelectContext.TO_ACTIVE:
            if o.playerIndex != my_index:
                return 0
            if not isinstance(card, Pokemon):
                return 0
            energy_count = len(card.energies)
            score = energy_count * 2
            if card.id == Mega_Starmie_ex:
                score += 50
                if fs.switch_to_starmie and o.index == fs.starmie_bench_idx:
                    score += 100
            elif card.id == Cinderace:
                score += 20
            elif card.id == Scorbunny:
                score += 5
            return score

        case SelectContext.TO_BENCH | SelectContext.TO_HAND:
            if not isinstance(card, Pokemon):
                return 10
            if card.id == Mega_Starmie_ex:
                return 100 if fs.field_counts[Mega_Starmie_ex] == 0 else 10
            if card.id == Cinderace:
                return 80
            if card.id == Staryu:
                return 60 if (
                    fs.field_counts[Staryu] + fs.field_counts[Mega_Starmie_ex] < 2
                ) else 20
            if card.id == Scorbunny:
                return 40 if (
                    fs.field_counts[Scorbunny] + fs.field_counts[Cinderace] < 2
                ) else 10
            return 10

        case SelectContext.DISCARD:
            card_id = card.id if isinstance(card, Card) else card.id
            score = 5
            if card_id in (Mega_Starmie_ex, Cinderace):
                score = -50
            elif card_id == Ignition_Energy:
                score = 80   # ターン終了で消えるため惜しくない
            elif card_id == Wallys_Compassion:
                score = -100
            elif card_id in (Salvatore, Hilda):
                score = 20 if discard_hand_counts[card_id] >= 2 else -20
            elif card_id == Basic_Water_Energy:
                score = 30
            elif card_id in (Staryu, Scorbunny):
                score = 10
            if discard_hand_counts[card_id] >= 2:
                score += 100  # 重複カードは積極トラッシュ
            discard_hand_counts[card_id] -= 1
            return score

        case _:
            return 0
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run pytest tests/test_cinderace_starmie_agent.py::TestScorePlay tests/test_cinderace_starmie_agent.py::TestScoreAttach tests/test_cinderace_starmie_agent.py::TestScoreAttack -v
```
期待: 全件 PASSED

- [ ] **Step 5: 全テストが引き続き通ることを確認する**

```bash
uv run pytest tests/ -v
```
期待: 全件 PASSED

- [ ] **Step 6: コミット**

```bash
git add src/cinderace_starmie_agent/main.py
git commit -m "feat: Cinderace+Starmieエージェントのスコアリング関数を追加"
```

---

## Task 4: `agent()` 関数完成 + Kaggleノートブック作成

**Files:**
- Modify: `src/cinderace_starmie_agent/main.py`（`agent()` を完成させる）
- Test: `tests/test_cinderace_starmie_agent.py`（agent() 統合テストを追記）
- Create: `src/cinderace_starmie_agent.ipynb`（Kaggle提出用ノートブック）

**Interfaces:**
- Consumes: `_collect_field_state`, `_score_play`, `_score_attach`, `_score_attack`, `_score_card_option`（全 Task 2–3 産物）
- Produces: `agent(obs_dict: dict) -> list[int]`

- [ ] **Step 1: agent() 統合テストを追記する**

`tests/test_cinderace_starmie_agent.py` に以下を追加:

```python
# ==================== agent() 統合テスト ====================
from unittest.mock import patch
from cg.api import Option, OptionType
from tests.conftest import make_main_obs


class TestAgent:
    def test_returns_deck_when_select_is_none(self):
        obs_dict = {"select": None, "logs": [], "current": None, "search_begin_input": None}
        with patch.object(cm, "my_deck", [1] * 60):
            result = cm.agent(obs_dict)
        assert result == [1] * 60

    def test_returns_valid_indices(self):
        options = [
            Option(type=OptionType.ATTACK, attackId=9001),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(options=options)
        result = cm.agent(obs_dict)
        assert all(0 <= i < len(options) for i in result)
        assert len(result) == len(set(result))

    def test_prefers_attack_over_end(self):
        options = [
            Option(type=OptionType.END),
            Option(type=OptionType.ATTACK, attackId=9001),
        ]
        obs_dict = make_main_obs(options=options)
        result = cm.agent(obs_dict)
        assert options[result[0]].type == OptionType.ATTACK
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_cinderace_starmie_agent.py::TestAgent -v
```
期待: `AssertionError` (暫定の `return [0]` では ATTACK を選ばない)

- [ ] **Step 3: `agent()` 関数を完成させる**

`main.py` の `agent()` 関数を以下で置き換える:

```python
def agent(obs_dict: dict) -> list[int]:
    """Pokémon TCG エージェント（Cinderace + Mega Starmie ex）

    Returns:
        list[int]: 選択するオプションのインデックスリスト
    """
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        _load_deck()
        return my_deck

    _build_card_table()

    state    = obs.current
    select   = obs.select
    context  = select.context
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]
    prize_count = len(my_state.prize)

    fs = _collect_field_state(my_state, op_state)

    # DISCARD コンテキスト用に手札カウントのコピーを保持（段階的な選択を追跡）
    discard_hand_counts = defaultdict(int, fs.hand_counts)

    scores = []
    for o in select.option:
        match o.type:
            case OptionType.NUMBER:
                score = o.number
            case OptionType.YES:
                score = 1
            case OptionType.CARD:
                score = _score_card_option(
                    obs, o, context, my_index, fs, discard_hand_counts
                )
            case OptionType.PLAY:
                card  = get_card(obs, AreaType.HAND, o.index, my_index)
                score = _score_play(card.id, fs, prize_count)
            case OptionType.ATTACH:
                card    = get_card(obs, AreaType.HAND, o.index, my_index)
                pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
                score   = _score_attach(pokemon, o.inPlayArea, card.id, fs)
            case OptionType.EVOLVE:
                pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
                score   = 10000 + len(pokemon.energies)
            case OptionType.RETREAT:
                if fs.wally_in_hand and fs.starmie_active_damage > 0:
                    score = 3000  # Wally's Compassion ループ準備
                elif fs.switch_to_starmie:
                    score = 2000
                else:
                    score = -1
            case OptionType.ATTACK:
                score = _score_attack(o.attackId, fs)
            case _:
                score = 0
        scores.append(score)

    desc_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return desc_indices[:select.maxCount]
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run pytest tests/test_cinderace_starmie_agent.py -v
```
期待: 全件 PASSED

- [ ] **Step 5: 全テストが通ることを確認する**

```bash
uv run pytest tests/ -v
```
期待: 全件 PASSED

- [ ] **Step 6: Kaggle ノートブックを作成する**

`src/cinderace_starmie_agent.ipynb` を以下の内容で作成する（`%%writefile main.py` セル→提出 tar.gz 生成セルの2セル構成）。

ノートブックの `%%writefile main.py` セルの内容は `src/cinderace_starmie_agent/main.py` の全文をそのまま貼り付ける。2セル目は以下のとおり:

```python
import glob
import os
import tarfile

with tarfile.open("submission.tar.gz", "w:gz") as tar:
    tar.add("main.py", arcname="main.py")
    tar.add(glob.glob('/kaggle/input/**/cg-lib/cg', recursive=True)[0], arcname="cg")
    tar.add(glob.glob('/kaggle/input/datasets/**/deck.csv', recursive=True)[0], arcname="deck.csv")

os.remove('main.py')
```

- [ ] **Step 7: デッキCSVを生成する**

```bash
uv run python scripts/build_deck.py decks/cinderace_starmie_20260630.py
```
期待: `output/deck_YYYYMMDD_HHMMSS.csv` が生成される（60行）

- [ ] **Step 8: コミット**

```bash
git add src/cinderace_starmie_agent/main.py tests/test_cinderace_starmie_agent.py
git commit -m "feat: Cinderace+Starmieエージェントのagent()関数を完成"
```

---

## セルフレビュー結果

**Spec coverage:**
- ✅ デッキリスト60枚（Task 1）
- ✅ Cinderace/Starmieライン定数（Task 2）
- ✅ FieldState収集（Task 2）
- ✅ PLAY スコアリング（Lillie/Buddy/Salvatore/Wally/Hilda/Mega Signal/Pokégear/Ultra Ball/Night Stretcher/Crushing Hammer）（Task 3）
- ✅ ATTACH スコアリング（Ignition→Cinderace / Water→Starmie / Hero's Cape）（Task 3）
- ✅ ATTACK スコアリング（Turbo Flare / Jetting Blow / Nebula Beam）（Task 3）
- ✅ CARD スコアリング（SETUP/SWITCH/TO_BENCH/DISCARD）（Task 3）
- ✅ EVOLVE/RETREAT/agent() 本体（Task 4）
- ✅ Kaggleノートブック作成（Task 4）

**Type consistency:** 全タスクで `FieldState`、`Turbo_Flare_ID`、`Jetting_Blow_ID`、`Nebula_Beam_ID` の名前が統一されている

**注意事項:**
- `Turbo_Flare_ID` 等の攻撃IDは実際の Kaggle 環境で `all_card_data()` が返す値に依存する。macOS ではテスト時に monkeypatch でモック値（9001/9002/9003）を使う
- ノートブック（.ipynb）は `.gitignore` 対象のため、`main.py` のコードを確実にコピー転記すること
- Kaggle アップロード後に `deck.csv`（output/以下）を `iono-deck` 等のデータセットに手動アップロードが必要
