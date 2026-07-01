# マリィのグリムスナールex エージェント実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Marnie's Grimmsnarl ex を単一主軸に、Rare Candyでの高速進化とPunk Upのエネルギー一括アタッチ→Shadow Bullet連打で戦うルールベースエージェントを実装する

**Architecture:** `cinderace_starmie_agent`（`src/cinderace_starmie_agent/main.py`）の構造をそのまま踏襲する。FieldState dataclass でターン状態を集約し、カード種別・コンテキストごとのスコア関数に分岐する。Shadow Bulletのベンチ30ダメ対象選択は `SelectContext.DAMAGE_COUNTER` で扱う。攻撃IDは `all_card_data()` から動的に取得する。

**Tech Stack:** Python 3.12, uv, cg.api, pytest

## Global Constraints

- Python 3.12.13 / uv 実行環境
- `cg.api` の `all_card_data()` / `all_attack()` は Kaggle 環境でのみ動作（macOS では libcg.so 未対応）
- テストは `tests/conftest.py` の `make_pokemon` / `make_player_state` / `make_main_obs` を使う
- `cg.sim` / `cg.game` は conftest で自動モック済み
- コメントは日本語、変数名・関数名は英語
- テスト実行コマンド: `uv run pytest tests/ -v`
- 参照設計書: `docs/superpowers/specs/2026-07-01-grimmsnarl-agent-design.md`

---

## ファイル構成

```
新規作成:
  decks/grimmsnarl_20260701.py            # デッキ定義（60枚）
  src/grimmsnarl_agent/__init__.py        # agent を公開
  src/grimmsnarl_agent/main.py            # エージェント本体
  tests/test_grimmsnarl_deck.py           # デッキバリデーションテスト
  tests/test_grimmsnarl_agent.py          # エージェントユニットテスト

参照（変更なし）:
  tests/conftest.py                       # make_pokemon / make_player_state / make_main_obs
  src/cinderace_starmie_agent/main.py     # 実装パターンの参照元
  data/cg/api.py                          # SelectContext.DAMAGE_COUNTER 等の定義元
```

---

## Task 1: デッキ定義

**Files:**
- Create: `decks/grimmsnarl_20260701.py`
- Test: `tests/test_grimmsnarl_deck.py`

**Interfaces:**
- Produces: `DECK: list[tuple[int, int]]` — `(card_id, count)` タプルのリスト、合計60枚

- [ ] **Step 1: テストを書く**

```python
# tests/test_grimmsnarl_deck.py
from decks.grimmsnarl_20260701 import DECK

ENERGY_IDS = {7}  # Basic {D} Energy


def test_deck_has_60_cards():
    assert sum(count for _, count in DECK) == 60


def test_no_non_energy_card_exceeds_4_copies():
    for card_id, count in DECK:
        if card_id not in ENERGY_IDS:
            assert count <= 4, f"Card {card_id} が {count} 枚（上限4枚）"


def test_key_pokemon_present():
    ids = {card_id for card_id, _ in DECK}
    assert 646 in ids, "Marnie's Impidimp が不在"
    assert 647 in ids, "Marnie's Morgrem が不在"
    assert 648 in ids, "Marnie's Grimmsnarl ex が不在"
    assert 649 in ids, "Marnie's Morpeko が不在"
    assert 112 in ids, "Munkidori が不在"
    assert 66  in ids, "Dudunsparce が不在"
    assert 305 in ids, "Dunsparce が不在"


def test_energy_count():
    darkness = sum(c for i, c in DECK if i == 7)
    assert darkness == 10


def test_no_duplicate_card_id_entries():
    ids = [card_id for card_id, _ in DECK]
    assert len(ids) == len(set(ids)), "同じcard_idが複数タプルに分かれている"
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_grimmsnarl_deck.py -v
```
期待: `ModuleNotFoundError: No module named 'decks.grimmsnarl_20260701'`

- [ ] **Step 3: デッキ定義ファイルを実装する**

```python
# decks/grimmsnarl_20260701.py
# マリィのグリムスナールex デッキ（20260701生成）
# 設計書: docs/superpowers/specs/2026-07-01-grimmsnarl-agent-design.md

DECK = [
    (646,  4),   # Marnie's Impidimp（進化元・Filchで初動ドロー・70HP）
    (647,  1),   # Marnie's Morgrem（進化中継・Rare Candy未引き時の保険）
    (648,  2),   # Marnie's Grimmsnarl ex（メインアタッカー）
    (649,  2),   # Marnie's Morpeko（初動アタッカー・ベンチ要員）
    (112,  1),   # Munkidori（Adrena-Brainでダメカン移動）
    (66,   1),   # Dudunsparce（ドローエンジン）
    (305,  1),   # Dunsparce（Dudunsparceの進化元）
    (1231, 4),   # Dawn（進化ライン一式サーチ）
    (1079, 4),   # Rare Candy（Impidimp→Grimmsnarl ex 一気進化）
    (1086, 4),   # Buddy-Buddy Poffin（低HP基本ポケモンをベンチ展開）
    (1227, 4),   # Lillie's Determination（手札リフレッシュ）
    (1152, 4),   # Poké Pad（ポケモンサーチ）
    (1097, 4),   # Night Stretcher（トラッシュ回収）
    (1197, 4),   # Xerosic's Machinations（相手ハンド圧縮）
    (1139, 4),   # Energy Recycler（エネルギー再利用）
    (1259, 3),   # Spikemuth Gym（毎ターンMarnie's系サーチ）
    (1159, 3),   # Hero's Cape（Grimmsnarl exにHP+100）
    (7,   10),   # Basic {D} Energy
]
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run pytest tests/test_grimmsnarl_deck.py -v
```
期待: 5件 PASSED

- [ ] **Step 5: コミット**

```bash
git add decks/grimmsnarl_20260701.py tests/test_grimmsnarl_deck.py
git commit -m "feat: グリムスナールexデッキ定義を追加"
```

---

## Task 2: エージェント骨格（定数・ユーティリティ・FieldState収集）

**Files:**
- Create: `src/grimmsnarl_agent/__init__.py`
- Create: `src/grimmsnarl_agent/main.py`（骨格部分）
- Test: `tests/test_grimmsnarl_agent.py`（FieldState 収集テスト）

**Interfaces:**
- Produces:
  - `_collect_field_state(my_state, op_state) -> FieldState`
  - `get_card(obs, area, index, player_index) -> Pokemon | Card | None`
  - モジュール定数: `Grimmsnarl_ex=648`, `Impidimp=646`, `Morgrem=647`, `Morpeko=649`, `Munkidori=112`, `Dudunsparce=66`, `Dunsparce=305`, `Basic_D_Energy=7`

- [ ] **Step 1: テストを書く**

```python
# tests/test_grimmsnarl_agent.py
import pytest
from dataclasses import dataclass, field
from collections import defaultdict
from cg.api import CardType, Card

import grimmsnarl_agent.main as gm
from tests.conftest import make_pokemon, make_player_state


@dataclass
class MockCardData:
    cardId:   int
    name:     str      = ""
    ex:       bool     = False
    stage1:   bool     = False
    stage2:   bool     = False
    cardType: CardType = CardType.POKEMON
    attacks:  list     = field(default_factory=list)


@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    table = {
        gm.Impidimp:        MockCardData(cardId=gm.Impidimp, attacks=[9101]),
        gm.Morgrem:         MockCardData(cardId=gm.Morgrem, stage1=True, attacks=[9101]),
        gm.Grimmsnarl_ex:   MockCardData(cardId=gm.Grimmsnarl_ex, stage2=True, ex=True, attacks=[9102]),
        gm.Morpeko:         MockCardData(cardId=gm.Morpeko, attacks=[9103]),
        gm.Munkidori:       MockCardData(cardId=gm.Munkidori, attacks=[9104]),
        gm.Dudunsparce:     MockCardData(cardId=gm.Dudunsparce, stage1=True, attacks=[9105]),
        gm.Dunsparce:       MockCardData(cardId=gm.Dunsparce, attacks=[9106]),
        gm.Rare_Candy:      MockCardData(cardId=gm.Rare_Candy, cardType=CardType.ITEM),
        gm.Buddy_Buddy_Poffin: MockCardData(cardId=gm.Buddy_Buddy_Poffin, cardType=CardType.ITEM),
        gm.Dawn:            MockCardData(cardId=gm.Dawn, cardType=CardType.SUPPORTER),
        gm.Lillie_Determination: MockCardData(cardId=gm.Lillie_Determination, cardType=CardType.SUPPORTER),
        gm.Basic_D_Energy:  MockCardData(cardId=gm.Basic_D_Energy, cardType=CardType.BASIC_ENERGY),
    }
    monkeypatch.setattr(gm, "card_table", table)
    monkeypatch.setattr(gm, "Shadow_Bullet_ID", 9102)
    monkeypatch.setattr(gm, "Spiky_Wheel_ID", 9103)
    return table


# ==================== _collect_field_state ====================
class TestCollectFieldState:
    def test_grimmsnarl_active_detected(self):
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, energies=[7, 7])
        my_ps = make_player_state(active_pokemon=grimmsnarl)
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.grimmsnarl_active is True
        assert fs.grimmsnarl_energy_count == 2

    def test_grimmsnarl_not_active_when_absent(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Impidimp))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.grimmsnarl_active is False
        assert fs.grimmsnarl_energy_count == 0

    def test_impidimp_bench_detected(self):
        impidimp = make_pokemon(id=gm.Impidimp)
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=gm.Morpeko),
            bench=[impidimp],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.impidimp_bench_idx == 0

    def test_impidimp_bench_absent_returns_minus1(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Morpeko))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.impidimp_bench_idx == -1

    def test_munkidori_bench_detected(self):
        munkidori = make_pokemon(id=gm.Munkidori, energies=[7])
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex),
            bench=[munkidori],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.munkidori_bench_idx == 0

    def test_rare_candy_in_hand_detected(self):
        candy = Card(id=gm.Rare_Candy, serial=1, playerIndex=0)
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=gm.Impidimp),
            hand=[candy],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.rare_candy_in_hand is True

    def test_op_active_hp(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex))
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=180))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.op_active_hp == 180

    def test_op_bench_hp_list(self):
        my_ps = make_player_state(active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex))
        op_bench = [make_pokemon(id=2, hp=30), make_pokemon(id=3, hp=90)]
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200), bench=op_bench)
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.op_bench_hp == [30, 90]
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_grimmsnarl_agent.py::TestCollectFieldState -v
```
期待: `ModuleNotFoundError: No module named 'grimmsnarl_agent'`

- [ ] **Step 3: `__init__.py` を作成する**

```python
# src/grimmsnarl_agent/__init__.py
from .main import agent
```

- [ ] **Step 4: `main.py` の骨格を実装する**

```python
# src/grimmsnarl_agent/main.py
import os
from collections import defaultdict
from dataclasses import dataclass

from cg.api import (
    AreaType, CardType, Observation, SelectContext,
    OptionType, Card, Pokemon, all_card_data, to_observation_class,
)

# ==================== カードID定数 ====================
Impidimp      = 646
Morgrem       = 647
Grimmsnarl_ex = 648
Morpeko       = 649
Munkidori     = 112
Dudunsparce   = 66
Dunsparce     = 305

Dawn                   = 1231
Rare_Candy             = 1079
Buddy_Buddy_Poffin     = 1086
Lillie_Determination   = 1227
Poke_Pad               = 1152
Night_Stretcher        = 1097
Xerosics_Machinations  = 1197
Energy_Recycler        = 1139
Spikemuth_Gym          = 1259
Heros_Cape             = 1159

Basic_D_Energy = 7

# ==================== アタックID（_build_card_table で設定）====================
Shadow_Bullet_ID: int = 0
Spiky_Wheel_ID:   int = 0

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築し、攻撃IDも設定する"""
    global card_table, Shadow_Bullet_ID, Spiky_Wheel_ID
    if not card_table:
        card_table       = {c.cardId: c for c in all_card_data()}
        grimmsnarl_data  = card_table[Grimmsnarl_ex]
        morpeko_data     = card_table[Morpeko]
        Shadow_Bullet_ID = grimmsnarl_data.attacks[0]  # Shadow Bullet
        Spiky_Wheel_ID   = morpeko_data.attacks[0]     # Spiky Wheel
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
    field_counts:            defaultdict
    hand_counts:             defaultdict
    discard_counts:          defaultdict
    grimmsnarl_active:       bool
    grimmsnarl_energy_count: int
    impidimp_bench_idx:      int
    munkidori_bench_idx:     int
    rare_candy_in_hand:      bool
    my_active_hp:            int
    op_active_hp:            int
    op_bench_hp:             list


def _collect_field_state(my_state, op_state) -> FieldState:
    """バトル場・ベンチ・手札・トラッシュから行動判断に必要な状態を収集する"""
    field_counts   = defaultdict(int)
    hand_counts    = defaultdict(int)
    discard_counts = defaultdict(int)

    grimmsnarl_active       = False
    grimmsnarl_energy_count = 0
    impidimp_bench_idx      = -1
    munkidori_bench_idx     = -1
    my_active_hp            = 0

    for card in my_state.active:
        if card is None:
            continue
        field_counts[card.id] += 1
        my_active_hp = card.hp
        if card.id == Grimmsnarl_ex:
            grimmsnarl_active       = True
            grimmsnarl_energy_count = len(card.energies)

    for i, card in enumerate(my_state.bench):
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id == Impidimp and impidimp_bench_idx == -1:
            impidimp_bench_idx = i
        elif card.id == Munkidori and munkidori_bench_idx == -1:
            munkidori_bench_idx = i

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    op_active_hp = 0
    for card in op_state.active:
        if card is not None:
            op_active_hp = card.hp

    op_bench_hp = [card.hp for card in op_state.bench if card is not None]

    rare_candy_in_hand = hand_counts[Rare_Candy] >= 1

    return FieldState(
        field_counts=field_counts,
        hand_counts=hand_counts,
        discard_counts=discard_counts,
        grimmsnarl_active=grimmsnarl_active,
        grimmsnarl_energy_count=grimmsnarl_energy_count,
        impidimp_bench_idx=impidimp_bench_idx,
        munkidori_bench_idx=munkidori_bench_idx,
        rare_candy_in_hand=rare_candy_in_hand,
        my_active_hp=my_active_hp,
        op_active_hp=op_active_hp,
        op_bench_hp=op_bench_hp,
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
uv run pytest tests/test_grimmsnarl_agent.py::TestCollectFieldState -v
```
期待: 8件 PASSED

- [ ] **Step 6: コミット**

```bash
git add src/grimmsnarl_agent/ tests/test_grimmsnarl_agent.py
git commit -m "feat: グリムスナールexエージェント骨格とFieldState収集を追加"
```

---

## Task 3: スコアリング関数群

**Files:**
- Modify: `src/grimmsnarl_agent/main.py`（スコアリング関数を追加）
- Test: `tests/test_grimmsnarl_agent.py`（スコアリングテストを追記）

**Interfaces:**
- Consumes: `FieldState`（Task 2）, `card_table`, `Shadow_Bullet_ID`, `Spiky_Wheel_ID`
- Produces:
  - `_score_play(card_id, fs, prize_count) -> int`
  - `_score_attach(pokemon, area, card_id, fs) -> int`
  - `_score_attack(attack_id, fs) -> int`
  - `_score_card_option(obs, o, context, my_index, fs, discard_hand_counts) -> int`

- [ ] **Step 1: スコアリングテストを追記する**

`tests/test_grimmsnarl_agent.py` に以下を追加:

```python
# ==================== _score_play ====================
class TestScorePlay:
    def _make_fs(self, **kwargs):
        defaults = dict(
            field_counts=defaultdict(int),
            hand_counts=defaultdict(int),
            discard_counts=defaultdict(int),
            grimmsnarl_active=False,
            grimmsnarl_energy_count=0,
            impidimp_bench_idx=-1,
            munkidori_bench_idx=-1,
            rare_candy_in_hand=False,
            my_active_hp=200,
            op_active_hp=200,
            op_bench_hp=[],
        )
        defaults.update(kwargs)
        return gm.FieldState(**defaults)

    def test_rare_candy_high_when_impidimp_on_field_and_grimmsnarl_in_hand(self):
        fc = defaultdict(int, {gm.Impidimp: 1})
        hc = defaultdict(int, {gm.Grimmsnarl_ex: 1, gm.Rare_Candy: 1})
        fs = self._make_fs(field_counts=fc, hand_counts=hc, rare_candy_in_hand=True)
        assert gm._score_play(gm.Rare_Candy, fs, prize_count=6) == 9000

    def test_rare_candy_low_when_grimmsnarl_not_in_hand(self):
        fc = defaultdict(int, {gm.Impidimp: 1})
        hc = defaultdict(int, {gm.Rare_Candy: 1})
        fs = self._make_fs(field_counts=fc, hand_counts=hc, rare_candy_in_hand=True)
        assert gm._score_play(gm.Rare_Candy, fs, prize_count=6) == -1

    def test_buddy_buddy_poffin_high_when_bench_targets_missing(self):
        fs = self._make_fs()
        assert gm._score_play(gm.Buddy_Buddy_Poffin, fs, prize_count=6) == 8000

    def test_buddy_buddy_poffin_low_when_bench_targets_present(self):
        fs = self._make_fs(impidimp_bench_idx=0, munkidori_bench_idx=1)
        assert gm._score_play(gm.Buddy_Buddy_Poffin, fs, prize_count=6) == 2000

    def test_dawn_high_when_line_missing_from_hand(self):
        fs = self._make_fs()
        assert gm._score_play(gm.Dawn, fs, prize_count=6) == 7000

    def test_lillie_determination_first_turn(self):
        fs = self._make_fs()
        assert gm._score_play(gm.Lillie_Determination, fs, prize_count=6) == 5000

    def test_xerosics_machinations_default_score(self):
        fs = self._make_fs()
        assert gm._score_play(gm.Xerosics_Machinations, fs, prize_count=4) == 3000

    def test_unhandled_card_returns_default(self):
        fs = self._make_fs()
        assert gm._score_play(gm.Energy_Recycler, fs, prize_count=4) == 1000


# ==================== _score_attach ====================
class TestScoreAttach:
    def test_basic_d_energy_to_grimmsnarl_low_energy_preferred(self):
        grimmsnarl_low  = make_pokemon(id=gm.Grimmsnarl_ex, energies=[])
        grimmsnarl_full = make_pokemon(id=gm.Grimmsnarl_ex, energies=[7, 7])
        fs = gm.FieldState(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), grimmsnarl_active=True,
            grimmsnarl_energy_count=0, impidimp_bench_idx=-1,
            munkidori_bench_idx=-1, rare_candy_in_hand=False,
            my_active_hp=200, op_active_hp=200, op_bench_hp=[],
        )
        score_low  = gm._score_attach(grimmsnarl_low,  AreaType.ACTIVE, gm.Basic_D_Energy, fs)
        score_full = gm._score_attach(grimmsnarl_full, AreaType.ACTIVE, gm.Basic_D_Energy, fs)
        assert score_low > score_full

    def test_heros_cape_only_for_grimmsnarl(self):
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex)
        morpeko    = make_pokemon(id=gm.Morpeko)
        fs = gm.FieldState(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), grimmsnarl_active=True,
            grimmsnarl_energy_count=0, impidimp_bench_idx=-1,
            munkidori_bench_idx=-1, rare_candy_in_hand=False,
            my_active_hp=200, op_active_hp=200, op_bench_hp=[],
        )
        assert gm._score_attach(grimmsnarl, AreaType.ACTIVE, gm.Heros_Cape, fs) == 8500
        assert gm._score_attach(morpeko,    AreaType.BENCH,  gm.Heros_Cape, fs) == -1


# ==================== _score_attack ====================
class TestScoreAttack:
    def _make_fs(self, op_hp=200, op_bench_hp=None):
        return gm.FieldState(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), grimmsnarl_active=True,
            grimmsnarl_energy_count=2, impidimp_bench_idx=-1,
            munkidori_bench_idx=-1, rare_candy_in_hand=False,
            my_active_hp=200, op_active_hp=op_hp, op_bench_hp=op_bench_hp or [],
        )

    def test_shadow_bullet_always_top_priority(self):
        fs = self._make_fs(op_hp=300)
        assert gm._score_attack(9102, fs) == 2000  # Shadow_Bullet_ID (mocked)

    def test_unknown_attack_returns_default(self):
        fs = self._make_fs()
        assert gm._score_attack(9999, fs) == 1000
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_grimmsnarl_agent.py::TestScorePlay tests/test_grimmsnarl_agent.py::TestScoreAttach tests/test_grimmsnarl_agent.py::TestScoreAttack -v
```
期待: `AttributeError: module has no attribute '_score_play'`

- [ ] **Step 3: スコアリング関数を `main.py` に追加する**

`# ==================== フィールド状態 ====================` ブロックの直後（`agent()`の手前）に追加:

```python
# ==================== スコアリング ====================
def _score_play(card_id: int, fs: FieldState, prize_count: int) -> int:
    """PLAY コンテキスト：手札からカードを使う際のスコア"""
    if card_id == Rare_Candy:
        has_impidimp     = fs.field_counts[Impidimp] >= 1
        grimmsnarl_ready = fs.hand_counts[Grimmsnarl_ex] >= 1
        return 9000 if (has_impidimp and grimmsnarl_ready) else -1
    if card_id == Buddy_Buddy_Poffin:
        needs_bench = fs.impidimp_bench_idx == -1 or fs.munkidori_bench_idx == -1
        return 8000 if needs_bench else 2000
    if card_id == Dawn:
        line_in_hand = (
            fs.hand_counts[Impidimp] >= 1
            and fs.hand_counts[Morgrem] >= 1
            and fs.hand_counts[Grimmsnarl_ex] >= 1
        )
        return 2500 if line_in_hand else 7000
    if card_id == Lillie_Determination:
        return 5000 if prize_count == 6 else 3500
    if card_id == Xerosics_Machinations:
        return 3000
    if card_id == Poke_Pad:
        return 4000
    if card_id == Night_Stretcher:
        return 2000
    return 1000


def _score_attach(pokemon: "Pokemon", area: AreaType, card_id: int, fs: FieldState) -> int:
    """ATTACH コンテキスト：エネルギー/ツールの付与先スコア"""
    energy_count = len(pokemon.energies)
    if card_id == Heros_Cape:
        return 8500 if pokemon.id == Grimmsnarl_ex else -1
    if card_id == Basic_D_Energy:
        if pokemon.id == Grimmsnarl_ex:
            return 9000 - energy_count * 1000
        if pokemon.id == Morpeko:
            return 4000
        return -1
    return 3000


def _score_attack(attack_id: int, fs: FieldState) -> int:
    """ATTACK コンテキスト：ワザ選択スコア"""
    if attack_id == Shadow_Bullet_ID:
        return 2000
    if attack_id == Spiky_Wheel_ID:
        return 1500
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
            if card.id == Impidimp:
                return 100
            if card.id == Morpeko:
                return 50
            return 10

        case SelectContext.SWITCH | SelectContext.TO_ACTIVE:
            if o.playerIndex != my_index or not isinstance(card, Pokemon):
                return 0
            score = len(card.energies) * 2
            if card.id == Grimmsnarl_ex:
                score += 100
            elif card.id == Morpeko:
                score += 30
            return score

        case SelectContext.TO_BENCH | SelectContext.TO_HAND:
            if not isinstance(card, Pokemon):
                return 10
            if card.id == Grimmsnarl_ex:
                return 100 if fs.field_counts[Grimmsnarl_ex] == 0 else 10
            if card.id == Impidimp:
                return 60 if fs.field_counts[Impidimp] < 2 else 20
            if card.id == Munkidori:
                return 40 if fs.munkidori_bench_idx == -1 else 10
            return 10

        case SelectContext.DAMAGE_COUNTER:
            # Shadow Bulletのベンチ30ダメ対象：最もKOに近い（HPが低い）相手ベンチを狙う
            if not isinstance(card, Pokemon):
                return 0
            return 100000 - card.hp

        case SelectContext.DISCARD:
            card_id = card.id
            score = 5
            if card_id in (Grimmsnarl_ex, Impidimp, Morgrem):
                score = -50
            elif card_id == Basic_D_Energy:
                score = 30
            if discard_hand_counts[card_id] >= 2:
                score += 100
            discard_hand_counts[card_id] -= 1
            return score

        case _:
            return 0
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run pytest tests/test_grimmsnarl_agent.py::TestScorePlay tests/test_grimmsnarl_agent.py::TestScoreAttach tests/test_grimmsnarl_agent.py::TestScoreAttack -v
```
期待: 全件 PASSED

- [ ] **Step 5: 全テストが引き続き通ることを確認する**

```bash
uv run pytest tests/ -v
```
期待: 全件 PASSED

- [ ] **Step 6: コミット**

```bash
git add src/grimmsnarl_agent/main.py
git commit -m "feat: グリムスナールexエージェントのスコアリング関数を追加"
```

---

## Task 4: `agent()` 関数完成 + Kaggleノートブック作成

**Files:**
- Modify: `src/grimmsnarl_agent/main.py`（`agent()` を完成させる）
- Test: `tests/test_grimmsnarl_agent.py`（agent() 統合テストを追記）
- Create: `src/grimmsnarl_agent.ipynb`（Kaggle提出用ノートブック）

**Interfaces:**
- Consumes: `_collect_field_state`, `_score_play`, `_score_attach`, `_score_attack`, `_score_card_option`（全 Task 2–3 産物）
- Produces: `agent(obs_dict: dict) -> list[int]`

- [ ] **Step 1: agent() 統合テストを追記する**

`tests/test_grimmsnarl_agent.py` に以下を追加:

```python
# ==================== agent() 統合テスト ====================
from unittest.mock import patch
from cg.api import Option, OptionType
from tests.conftest import make_main_obs


class TestAgent:
    def test_returns_deck_when_select_is_none(self):
        obs_dict = {"select": None, "logs": [], "current": None, "search_begin_input": None}
        with patch.object(gm, "my_deck", [1] * 60):
            result = gm.agent(obs_dict)
        assert result == [1] * 60

    def test_returns_valid_indices(self):
        options = [
            Option(type=OptionType.ATTACK, attackId=9102),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(options=options)
        result = gm.agent(obs_dict)
        assert all(0 <= i < len(options) for i in result)
        assert len(result) == len(set(result))

    def test_prefers_attack_over_end(self):
        options = [
            Option(type=OptionType.END),
            Option(type=OptionType.ATTACK, attackId=9102),
        ]
        obs_dict = make_main_obs(options=options)
        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.ATTACK

    def test_retreats_when_grimmsnarl_low_hp(self):
        low_hp_grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, hp=100, max_hp=320)
        my_ps = make_player_state(active_pokemon=low_hp_grimmsnarl)
        options = [
            Option(type=OptionType.RETREAT),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(my_state=my_ps, options=options)
        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.RETREAT

    def test_does_not_retreat_when_grimmsnarl_healthy(self):
        healthy_grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, hp=300, max_hp=320)
        my_ps = make_player_state(active_pokemon=healthy_grimmsnarl)
        options = [
            Option(type=OptionType.RETREAT),
            Option(type=OptionType.END),
        ]
        obs_dict = make_main_obs(my_state=my_ps, options=options)
        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.END
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_grimmsnarl_agent.py::TestAgent -v
```
期待: `AssertionError`（暫定の `return [0]` では ATTACK を選ばない）

- [ ] **Step 3: `agent()` 関数を完成させる**

`main.py` の `agent()` 関数を以下で置き換える:

```python
def agent(obs_dict: dict) -> list[int]:
    """Pokémon TCG エージェント（マリィのグリムスナールex）

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
            case OptionType.ABILITY:
                card = get_card(obs, o.area, o.index, my_index)
                score = 500 if card.id == Munkidori else 300
            case OptionType.RETREAT:
                # Grimmsnarl exが瀕死（想定される大技の一撃=180ダメ以下しか耐えられない）なら逃げる
                if fs.grimmsnarl_active and fs.my_active_hp <= 180:
                    score = 3000
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
uv run pytest tests/test_grimmsnarl_agent.py -v
```
期待: 全件 PASSED

- [ ] **Step 5: 全テストが通ることを確認する**

```bash
uv run pytest tests/ -v
```
期待: 全件 PASSED

- [ ] **Step 6: Kaggle ノートブックを作成する**

`src/grimmsnarl_agent.ipynb` を以下の内容で作成する（`%%writefile main.py` セル→提出 tar.gz 生成セルの2セル構成）。

ノートブックの `%%writefile main.py` セルの内容は `src/grimmsnarl_agent/main.py` の全文をそのまま貼り付ける。2セル目は以下のとおり:

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
uv run python scripts/build_deck.py decks/grimmsnarl_20260701.py
```
期待: `output/deck_YYYYMMDD_HHMMSS.csv` が生成される（60行）

- [ ] **Step 8: コミット**

```bash
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "feat: グリムスナールexエージェントのagent()関数を完成"
```

---

## セルフレビュー結果

**Spec coverage:**
- ✅ デッキリスト60枚（Task 1）
- ✅ カード定数・FieldState収集（Task 2）
- ✅ PLAY スコアリング（Rare Candy/Buddy-Buddy Poffin/Dawn/Lillie/Xerosic/Poké Pad/Night Stretcher）（Task 3）
- ✅ ATTACH スコアリング（Basic {D} Energy→Grimmsnarl ex優先 / Hero's Cape）（Task 3）
- ✅ ATTACK スコアリング（Shadow Bullet最優先 / Spiky Wheel）（Task 3）
- ✅ CARD スコアリング（SETUP/SWITCH/TO_BENCH/DAMAGE_COUNTER=Shadow Bulletベンチ対象選択/DISCARD）（Task 3）
- ✅ ABILITY（Munkidori Adrena-Brain優先）/ EVOLVE / agent() 本体（Task 4）
- ✅ Kaggleノートブック作成（Task 4）

**Type consistency:** 全タスクで `FieldState`、`Shadow_Bullet_ID`、`Spiky_Wheel_ID` の名前が統一されている

**設計書からの調整点（実装計画作成時に確定）:**
- `SelectContext.DAMAGE_COUNTER`（`data/cg/api.py:82`）をShadow Bulletのベンチ30ダメ対象選択に採用（相手ベンチの中で最もHPが低い＝KOに近いポケモンを狙う）
- Munkidori Adrena-Brain（ダメカン移動）はABILITY選択で高優先スコアを与える簡易実装とし、移動先・移動量の厳密な最適化は次PR以降の改善課題とする（YAGNI：メインの勝ち筋はShadow Bullet連打であり、Adrena-Brainはあくまで補助）
- RETREATは `FieldState.my_active_hp`（バトル場ポケモンの残りHP）を新設して判定する。Grimmsnarl exが場におり残りHPが180以下（＝Shadow Bullet相当の一撃を耐えられない想定）の場合のみ逃げる

**注意事項:**
- `Shadow_Bullet_ID` 等の攻撃IDは実際の Kaggle 環境で `all_card_data()` が返す値に依存する。macOS ではテスト時に monkeypatch でモック値（9102/9103）を使う
- ノートブック（.ipynb）は `.gitignore` 対象のため、`main.py` のコードを確実にコピー転記すること
- Kaggle アップロード後に `deck.csv`（output/以下）を新規データセット（例: `grimmsnarl-deck`）に手動アップロードが必要
