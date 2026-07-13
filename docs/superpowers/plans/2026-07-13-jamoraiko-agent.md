# ジャモライコエージェント Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 実店舗ジムバトルで6回優勝している「ジャモライコ」（ナンジャモ系ポケモン＋タケルライコex）構成を、テーブル駆動の4アタッカー体制でルールベースAIとしてv1移植する。

**Architecture:** `lucario_agent`/`grimmsnarl_agent`と同じ構成（カードID定数・`get_card`ヘルパー・`agent()`エントリポイント・`_score_*`系関数群）に、ダメージ計算式がバラバラな4技を扱うための`Attacker`テーブル（`damage_fn`を持つ）を追加する。`attackId`はKaggle環境でしか取得できない実行時情報のため、`all_attack()`から技名で逆引きする方式にする（マジックナンバーの決め打ちをしない）。

**Tech Stack:** Python 3.12 / uv / pytest / `cg.api`（Kaggle提供のゲームエンジンAPI、`cg.sim`はmacOSでロード不可のため`tests/conftest.py`で既にモック済み）

## Global Constraints

- 言語：コードコメント・ドキュメントは日本語（CLAUDE.md）
- 60枚デッキ・ACE SPEC1枚制限を厳守（[[feedback_ace_spec_deck_rule]]）。今回のACE SPECは「つりざおMAX」(ID1110)のみで1枚採用
- v1スコープ外：基本闘エネルギーの自動サーチ→トラッシュ→回収の周回ループ自動化（手貼りのみ実装）、Kaggle提出用ノートブックへの転記（デッキCSV生成まで）
- 既存の`src/sample_notebook/a-sample-rule-based-agent-iono-s-deck.ipynb`は変更しない
- 山札セーフティは`_safe_draws`/`_deck_consumption`パターン（`src/lucario_agent/main.py`実装済み）を最初から統合する
- テストは`uv run pytest -q`でリポジトリ全体が回帰なく通ること

---

## 事前確認済みのカードデータ

| 定数名 | Card ID | 備考 |
|---|---|---|
| `Raging_Bolt_ex` | 63 | HP240。技「Burst Roar」(コスト●・手札全トラッシュ+6ドロー)、技「Bellowing Thunder」(コスト{L}{F}・70×自分の場の基本エネルギー破棄数) |
| `Iono_Voltorb` | 265 | HP70。技「Voltaic Chain」(コスト●●・20+ナンジャモのポケモン全員の雷エネ数×20) |
| `Iono_Tadbulb` | 268 | HP60（ハラバリーexの進化前） |
| `Iono_Bellibolt_ex` | 269 | HP280。特性「Electric Streamer」(手札の基本雷エネをナンジャモのポケモン誰にでも何回でも装填可)。技「Thunderous Bolt」(コスト{L}{L}{L}●・230・次の自分の番は技が使えない) |
| `Iono_Wattrel` | 270 | HP60（タイカイデンの進化前） |
| `Iono_Kilowattrel` | 271 | HP120。特性「Flashing Draw」(自身についている基本雷エネ1個をトラッシュし、手札が6枚になるまでドロー、1ターン1回)。技「Mach Bolt」(コスト{L}●●・70) |

トレーナーズは`src/sample_notebook/a-sample-rule-based-agent-iono-s-deck.ipynb`と同一IDのため定数を流用：`Buddy_Buddy_Poffin=1086`, `Night_Stretcher=1097`, `Max_Rod=1110`, `Energy_Retrieval=1118`, `Ultra_Ball=1121`, `Lillie_Determination=1227`, `Canari=1233`, `Boss_Orders=1182`, `Levincia=1254`。新規：`Energy_Search=1119`（エネルギー転送）、`Switch=1123`（ポケモンいれかえ）。

`EnergyType.LIGHTNING=4`, `EnergyType.FIGHTING=6`（`cg.api.EnergyType`、カードIDの4/6とは別の名前空間なので混同しないこと）。

---

### Task 1: デッキ定義とデッキテスト

**Files:**
- Create: `decks/jamoraiko_20260713.py`
- Test: `tests/test_jamoraiko_deck.py`

**Interfaces:**
- Produces: `decks.jamoraiko_20260713.DECK`（`list[tuple[int, int]]`、`(card_id, count)`のリスト。他Taskはこれをimportしない）

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_jamoraiko_deck.py
from decks.jamoraiko_20260713 import DECK

ENERGY_IDS = {4, 6}  # Basic {L} Energy, Basic {F} Energy
ACE_SPEC_IDS = {1110}  # つりざおMAX


def test_deck_has_60_cards():
    assert sum(count for _, count in DECK) == 60


def test_no_non_energy_card_exceeds_4_copies():
    for card_id, count in DECK:
        if card_id not in ENERGY_IDS:
            assert count <= 4, f"Card {card_id} が {count} 枚（上限4枚）"


def test_ace_spec_does_not_exceed_1_copy():
    for card_id, count in DECK:
        if card_id in ACE_SPEC_IDS:
            assert count <= 1, f"ACE SPECカード {card_id} が {count} 枚（上限1枚）"


def test_no_duplicate_card_id_entries():
    ids = [card_id for card_id, _ in DECK]
    assert len(ids) == len(set(ids)), "同じcard_idが複数タプルに分かれている"


def test_key_pokemon_present_with_expected_counts():
    counts = dict(DECK)
    assert counts[63] == 2     # タケルライコex
    assert counts[268] == 3    # ズピカ
    assert counts[269] == 3    # ハラバリーex
    assert counts[270] == 3    # カイデン
    assert counts[271] == 3    # タイカイデン
    assert counts[265] == 1    # ビリリダマ


def test_trainer_counts():
    counts = dict(DECK)
    assert counts[1121] == 4   # ハイパーボール
    assert counts[1086] == 4   # なかよしポフィン
    assert counts[1118] == 2   # エネルギー回収
    assert counts[1097] == 3   # 夜のタンカ
    assert counts[1119] == 2   # エネルギー転送
    assert counts[1123] == 2   # ポケモンいれかえ
    assert counts[1110] == 1   # つりざおMAX
    assert counts[1227] == 3   # リーリエの決心
    assert counts[1233] == 4   # カナリィ
    assert counts[1182] == 2   # ボスの指令
    assert counts[1254] == 3   # ハッコウシティ


def test_energy_counts():
    counts = dict(DECK)
    assert counts[4] == 12  # 基本雷エネルギー
    assert counts[6] == 3   # 基本闘エネルギー
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_deck.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'decks.jamoraiko_20260713'`）

- [ ] **Step 3: デッキ定義を実装する**

```python
# decks/jamoraiko_20260713.py
# ジャモライコデッキ定義（さくさくさん7/9ジムバトル優勝レシピを移植）
# ナンジャモ系ポケモン（雷）+ タケルライコexの2軸フィニッシャー構成

DECK = [
    (63, 2),     # タケルライコex (Raging Bolt ex)
    (268, 3),    # ナンジャモのズピカ (Iono's Tadbulb)
    (269, 3),    # ナンジャモのハラバリーex (Iono's Bellibolt ex)
    (270, 3),    # ナンジャモのカイデン (Iono's Wattrel)
    (271, 3),    # ナンジャモのタイカイデン (Iono's Kilowattrel)
    (265, 1),    # ナンジャモのビリリダマ (Iono's Voltorb)
    (1121, 4),   # ハイパーボール (Ultra Ball)
    (1086, 4),   # なかよしポフィン (Buddy-Buddy Poffin)
    (1118, 2),   # エネルギー回収 (Energy Retrieval)
    (1097, 3),   # 夜のタンカ (Night Stretcher)
    (1119, 2),   # エネルギー転送 (Energy Search)
    (1123, 2),   # ポケモンいれかえ (Switch)
    (1110, 1),   # つりざおMAX (Max Rod, ACE SPEC)
    (1227, 3),   # リーリエの決心 (Lillie's Determination)
    (1233, 4),   # カナリィ (Canari)
    (1182, 2),   # ボスの指令 (Boss's Orders)
    (1254, 3),   # ハッコウシティ (Levincia)
    (4, 12),     # 基本{雷}エネルギー
    (6, 3),      # 基本{闘}エネルギー
]
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_deck.py -v`
Expected: PASS（8テスト全て）

- [ ] **Step 5: コミット**

```bash
git add decks/jamoraiko_20260713.py tests/test_jamoraiko_deck.py
git commit -m "feat: ジャモライコデッキ定義を追加"
```

---

### Task 2: エージェント骨格

**Files:**
- Create: `src/jamoraiko_agent/__init__.py`（空ファイル）
- Create: `src/jamoraiko_agent/main.py`
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: `decks.jamoraiko_20260713.DECK`（Task 1）
- Produces: `get_card(obs, area, index, player_index) -> Pokemon | Card | None`、`card_table: dict`（グローバル、`_build_card_table()`で遅延初期化）、`agent(obs_dict: dict) -> list[int]`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_jamoraiko_agent.py
import jamoraiko_agent.main as jm


class TestAgentDeckSelection:
    def test_agent_returns_deck_when_select_is_none(self):
        result = jm.agent({"select": None})
        assert len(result) == 60
        assert result[0] == 63  # タケルライコex が先頭
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'jamoraiko_agent'`）

- [ ] **Step 3: エージェント骨格を実装する**

```python
# src/jamoraiko_agent/__init__.py
```

```python
# src/jamoraiko_agent/main.py
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, all_card_data, all_attack, to_observation_class,
)

# ==================== カードID定数 ====================
Raging_Bolt_ex          = 63    # タケルライコex
Iono_Voltorb            = 265   # ナンジャモのビリリダマ
Iono_Tadbulb            = 268   # ナンジャモのズピカ
Iono_Bellibolt_ex       = 269   # ナンジャモのハラバリーex
Iono_Wattrel            = 270   # ナンジャモのカイデン
Iono_Kilowattrel        = 271   # ナンジャモのタイカイデン
Buddy_Buddy_Poffin      = 1086  # なかよしポフィン
Night_Stretcher         = 1097  # 夜のタンカ
Max_Rod                 = 1110  # つりざおMAX (ACE SPEC)
Energy_Retrieval        = 1118  # エネルギー回収
Energy_Search           = 1119  # エネルギー転送（山札から基本エネルギー1枚サーチ）
Ultra_Ball               = 1121  # ハイパーボール
Switch                   = 1123  # ポケモンいれかえ
Boss_Orders               = 1182  # ボスの指令
Lillie_Determination       = 1227  # リーリエの決心
Canari                     = 1233  # カナリィ
Levincia                   = 1254  # ハッコウシティ
Basic_Lightning_Energy      = 4
Basic_Fighting_Energy       = 6

IONO_POKEMON_IDS = {Iono_Voltorb, Iono_Tadbulb, Iono_Bellibolt_ex, Iono_Wattrel, Iono_Kilowattrel}

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}
attack_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築する"""
    global card_table
    if not card_table:
        card_table = {c.cardId: c for c in all_card_data()}
    return card_table


def _build_attack_table() -> dict:
    """attack_table（attackId -> Attack）を初回のみ構築する"""
    global attack_table
    if not attack_table:
        attack_table = {a.attackId: a for a in all_attack()}
    return attack_table


def _attack_id_by_name(name: str) -> "int | None":
    """技名からattackIdを逆引きする（cg.apiはKaggle環境でしか実行できないため、
    マジックナンバーを決め打ちせずattack_tableから解決する）"""
    for attack_id, attack in attack_table.items():
        if attack.name == name:
            return attack_id
    return None


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
        from decks.jamoraiko_20260713 import DECK
        my_deck = [card_id for card_id, count in DECK for _ in range(count)]
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


# ==================== メインエージェント ====================
def agent(obs_dict: dict) -> list[int]:
    """Pokémon TCG エージェント（ジャモライコ）。

    Returns:
        list[int]: 選択するオプションのインデックスリスト
    """
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return _load_deck()

    _build_card_table()
    _build_attack_table()

    state    = obs.current
    select   = obs.select
    my_index = state.yourIndex

    # Task 3以降でスコアリングを追加するまでは先頭を返す暫定実装
    return list(range(select.minCount))
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add src/jamoraiko_agent/ tests/test_jamoraiko_agent.py
git commit -m "feat: ジャモライコエージェントの骨格を追加"
```

---

### Task 3: FieldState収集ヘルパー

**Files:**
- Modify: `src/jamoraiko_agent/main.py`
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: `IONO_POKEMON_IDS`, `EnergyType`（Task 2）
- Produces: `FieldState`（dataclass）、`_collect_field_state(my_state) -> FieldState`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_jamoraiko_agent.py に追記
from tests.conftest import make_pokemon, make_player_state


class TestCollectFieldState:
    def test_iono_lightning_on_board_counts_only_iono_pokemon(self):
        voltorb = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])       # 雷2
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4])  # 雷3
        non_iono = make_pokemon(id=999, energies=[4, 4, 4, 4])            # 対象外のはずが混入しないことを確認
        my_state = make_player_state(active_pokemon=voltorb, bench=[bellibolt, non_iono])
        fs = jm._collect_field_state(my_state)
        assert fs.iono_lightning_on_board == 5

    def test_own_board_basic_energy_total_counts_lightning_and_fighting(self):
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 6])  # 雷1闘1
        my_state = make_player_state(active_pokemon=raging_bolt, bench=[])
        fs = jm._collect_field_state(my_state)
        assert fs.own_board_basic_energy_total == 2

    def test_active_energy_count_reflects_active_pokemon_only(self):
        active = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])
        bench_mon = make_pokemon(id=jm.Iono_Tadbulb, energies=[4, 4, 4])
        my_state = make_player_state(active_pokemon=active, bench=[bench_mon])
        fs = jm._collect_field_state(my_state)
        assert fs.active_energy_count == 2

    def test_field_counts_and_hand_counts_are_tracked(self):
        active = make_pokemon(id=jm.Iono_Voltorb)
        hand_card = make_pokemon(id=jm.Canari)
        my_state = make_player_state(active_pokemon=active, bench=[], hand=[hand_card])
        fs = jm._collect_field_state(my_state)
        assert fs.field_counts[jm.Iono_Voltorb] == 1
        assert fs.hand_counts[jm.Canari] == 1
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestCollectFieldState -v`
Expected: FAIL（`AttributeError: module 'jamoraiko_agent.main' has no attribute '_collect_field_state'`）

- [ ] **Step 3: FieldStateと収集関数を実装する**

`src/jamoraiko_agent/main.py`の`IONO_POKEMON_IDS`定義の直後に追加：

```python
# ==================== フィールド状態 ====================
@dataclass
class FieldState:
    field_counts: defaultdict
    hand_counts: defaultdict
    discard_counts: defaultdict
    iono_lightning_on_board: int
    own_board_basic_energy_total: int
    active_energy_count: int


def _collect_field_state(my_state) -> FieldState:
    """バトル場・ベンチ・手札・捨て山のカード枚数と、
    チェインボルト/きょくらいごうのダメージ計算に必要なエネルギー集計を返す。

    own_board_basic_energy_total は雷・闘の基本エネルギーのみを数える
    （本デッキは基本エネルギー2種のみ採用のためv1はこれで正確）。
    """
    field_counts   = defaultdict(int)
    hand_counts    = defaultdict(int)
    discard_counts = defaultdict(int)
    iono_lightning_on_board = 0
    own_board_basic_energy_total = 0
    active_energy_count = 0

    active = my_state.active[0] if my_state.active else None

    for card in my_state.active + my_state.bench:
        if card is None:
            continue
        field_counts[card.id] += 1
        lightning = card.energies.count(EnergyType.LIGHTNING)
        fighting  = card.energies.count(EnergyType.FIGHTING)
        if card.id in IONO_POKEMON_IDS:
            iono_lightning_on_board += lightning
        own_board_basic_energy_total += lightning + fighting

    if active is not None:
        active_energy_count = len(active.energies)

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    return FieldState(
        field_counts=field_counts,
        hand_counts=hand_counts,
        discard_counts=discard_counts,
        iono_lightning_on_board=iono_lightning_on_board,
        own_board_basic_energy_total=own_board_basic_energy_total,
        active_energy_count=active_energy_count,
    )
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestCollectFieldState -v`
Expected: PASS（4テスト）

- [ ] **Step 5: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "feat: FieldState収集ヘルパーを追加"
```

---

### Task 4: アタッカーテーブルと攻撃プラン選定ロジック

**Files:**
- Modify: `src/jamoraiko_agent/main.py`
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: `FieldState`, `_attack_id_by_name`（Task 2・3）
- Produces: `Attacker`（dataclass）、`ATTACKERS: list[Attacker]`、`AttackPlan`（dataclass）、`calc_attack_plan(my_active, op_active_hp, fs, my_state) -> AttackPlan`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_jamoraiko_agent.py に追記
from dataclasses import dataclass as _dc


@_dc
class MockAttack:
    """テスト用 Attack 代替クラス（cg.api.Attack と同一フィールドのみ定義）"""
    attackId: int
    name: str
    text: str = ""
    damage: int = 0
    energies: list = None


@pytest.fixture(autouse=True)
def mock_attack_table(monkeypatch):
    table = {
        1001: MockAttack(attackId=1001, name="Voltaic Chain"),
        1002: MockAttack(attackId=1002, name="Thunderous Bolt"),
        1003: MockAttack(attackId=1003, name="Mach Bolt"),
        1004: MockAttack(attackId=1004, name="Bellowing Thunder"),
        1005: MockAttack(attackId=1005, name="Burst Roar"),
    }
    monkeypatch.setattr(jm, "attack_table", table)
    return table


class TestCalcAttackPlan:
    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            own_board_basic_energy_total=0, active_energy_count=0,
        )
        base.update(overrides)
        return jm.FieldState(**base)

    def test_voltaic_chain_damage_scales_with_iono_lightning_on_board(self):
        voltorb = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])
        fs = self._fs(active_energy_count=2, iono_lightning_on_board=5)
        my_state = make_player_state(active_pokemon=voltorb, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(voltorb, op_active_hp=999, fs=fs, my_state=my_state)
        assert plan.damage == 20 + 20 * 5

    def test_lethal_attack_is_preferred_over_non_lethal(self):
        voltorb = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])
        fs = self._fs(active_energy_count=2, iono_lightning_on_board=10)  # 20+200=220ダメ
        my_state = make_player_state(active_pokemon=voltorb, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(voltorb, op_active_hp=200, fs=fs, my_state=my_state)
        assert plan.is_lethal is True

    def test_lethal_non_bellowing_thunder_preferred_over_lethal_bellowing_thunder(self):
        """確定KOが複数ある場合、場のエネルギーを消費しないきょくらいごう以外を優先する"""
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4, 6])
        fs = self._fs(active_energy_count=2, own_board_basic_energy_total=10)  # きょくらいごうは700ダメ
        my_state = make_player_state(active_pokemon=raging_bolt, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(raging_bolt, op_active_hp=50, fs=fs, my_state=my_state)
        assert plan.attack_id != 1004  # Bellowing Thunder ではない

    def test_thunderous_bolt_penalised_when_not_lethal(self):
        """確定KOでない場合、次ターン技封じのサンダーボルトより他技を優先する"""
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])
        fs = self._fs(active_energy_count=4, iono_lightning_on_board=4)
        my_state = make_player_state(active_pokemon=bellibolt, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(bellibolt, op_active_hp=9999, fs=fs, my_state=my_state)
        # サンダーボルト(230)一択のはずだが、ペナルティが付いていても他に選択肢がないので選ばれる
        assert plan.attacker_id == jm.Iono_Bellibolt_ex

    def test_burst_roar_only_chosen_when_no_other_attack_available(self):
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4])  # 闘エネなし＝きょくらいごう不可
        fs = self._fs(active_energy_count=1, own_board_basic_energy_total=1)
        my_state = make_player_state(active_pokemon=raging_bolt, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(raging_bolt, op_active_hp=200, fs=fs, my_state=my_state)
        assert plan.attack_id == 1005  # Burst Roar

    def test_no_active_pokemon_returns_empty_plan(self):
        fs = self._fs()
        my_state = make_player_state(active_pokemon=None, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(None, op_active_hp=100, fs=fs, my_state=my_state)
        assert plan.attacker_id == -1
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestCalcAttackPlan -v`
Expected: FAIL（`AttributeError: module 'jamoraiko_agent.main' has no attribute 'calc_attack_plan'`）

- [ ] **Step 3: アタッカーテーブルと選定ロジックを実装する**

`src/jamoraiko_agent/main.py`の`FieldState`関連コードの後に追加：

```python
# ==================== アタッカーテーブル ====================
@dataclass(frozen=True)
class Attacker:
    id: int
    attack_name: str
    energy_required: int
    damage_fn: Callable[[FieldState], int]
    locks_next_turn: bool = False
    is_utility: bool = False


ATTACKERS: list[Attacker] = [
    Attacker(id=Iono_Voltorb, attack_name="Voltaic Chain", energy_required=2,
             damage_fn=lambda fs: 20 + 20 * fs.iono_lightning_on_board),
    Attacker(id=Iono_Bellibolt_ex, attack_name="Thunderous Bolt", energy_required=4,
             damage_fn=lambda fs: 230, locks_next_turn=True),
    Attacker(id=Iono_Kilowattrel, attack_name="Mach Bolt", energy_required=3,
             damage_fn=lambda fs: 70),
    Attacker(id=Raging_Bolt_ex, attack_name="Bellowing Thunder", energy_required=2,
             damage_fn=lambda fs: 70 * fs.own_board_basic_energy_total),
    Attacker(id=Raging_Bolt_ex, attack_name="Burst Roar", energy_required=1,
             damage_fn=lambda fs: 0, is_utility=True),
]


# ==================== 攻撃プラン計算 ====================
@dataclass
class AttackPlan:
    attacker_id: int = -1
    attack_id:   int = -1
    damage:      int = 0
    is_lethal:   bool = False


def calc_attack_plan(my_active: "Pokemon | None", op_active_hp: int,
                      fs: FieldState, my_state) -> AttackPlan:
    """アクティブなポケモンについて、テーブル上の候補技から最適な1つを選ぶ。

    優先順位：
    1. 確定KOできる技があれば、場のエネルギーを消費しない技を優先
       （きょくらいごうは他に確定KO手段がない場合のみ使用）
    2. 確定KOがなければ最大ダメージを選ぶが、次ターン技封じの技は減点評価
    3. はじけるほうこう（is_utility）はダメージ0のため、
       他に使える技がない場合のみ自然に選ばれる
    """
    if my_active is None:
        return AttackPlan()

    candidates = []
    for atk in ATTACKERS:
        if atk.id != my_active.id:
            continue
        if fs.active_energy_count < atk.energy_required:
            continue
        if atk.is_utility and 6 > _safe_draws(my_state):
            continue  # 山札温存（Task 6で_safe_drawsを実装）
        damage = atk.damage_fn(fs)
        is_lethal = (not atk.is_utility) and damage >= op_active_hp
        candidates.append((atk, damage, is_lethal))

    if not candidates:
        return AttackPlan()

    lethal = [c for c in candidates if c[2]]
    if lethal:
        non_nuke = [c for c in lethal if c[0].id != Raging_Bolt_ex or c[0].attack_name != "Bellowing Thunder"]
        chosen = non_nuke[0] if non_nuke else lethal[0]
    else:
        def effective_damage(c):
            atk, damage, _ = c
            return damage - (150 if atk.locks_next_turn else 0)
        chosen = max(candidates, key=effective_damage)

    atk, damage, is_lethal = chosen
    attack_id = _attack_id_by_name(atk.attack_name)
    return AttackPlan(
        attacker_id=atk.id,
        attack_id=attack_id if attack_id is not None else -1,
        damage=damage,
        is_lethal=is_lethal,
    )
```

`calc_attack_plan`が`_safe_draws`を参照するため、`FieldState`定義の直前に追加する（これが最終実装であり、Task 6で他の山札セーフティ関数を追加する際も本関数は変更しない）：

```python
def _safe_draws(my_state) -> int:
    """安全に消費できる山札枚数。残りプライズ数を残りターン数の見積もりとして使い、
    毎ターンの必須ドロー分を温存する（デッキアウト防止）"""
    return my_state.deckCount - len(my_state.prize) - 1
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestCalcAttackPlan -v`
Expected: PASS（6テスト）

- [ ] **Step 5: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "feat: アタッカーテーブルと攻撃プラン選定ロジックを追加"
```

---

### Task 5: エネルギー装填スコアリング

**Files:**
- Modify: `src/jamoraiko_agent/main.py`
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: `IONO_POKEMON_IDS`, `EnergyType`
- Produces: `energy_score(pokemon, active) -> int`、`_score_attach_option(obs, o, my_index) -> int`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_jamoraiko_agent.py に追記
class TestEnergyScore:
    def test_active_slot_gets_bonus(self):
        p = make_pokemon(id=jm.Iono_Voltorb, energies=[])
        assert jm.energy_score(p, True) > jm.energy_score(p, False)

    def test_voltorb_prioritised_below_2_energy(self):
        no_e  = make_pokemon(id=jm.Iono_Voltorb, energies=[])
        two_e = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])
        assert jm.energy_score(no_e, False) > jm.energy_score(two_e, False)

    def test_bellibolt_ex_prioritised_below_4_energy(self):
        low  = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4])
        full = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])
        assert jm.energy_score(low, False) > jm.energy_score(full, False)

    def test_kilowattrel_prioritised_below_3_energy(self):
        low  = make_pokemon(id=jm.Iono_Kilowattrel, energies=[4])
        full = make_pokemon(id=jm.Iono_Kilowattrel, energies=[4, 4, 4])
        assert jm.energy_score(low, False) > jm.energy_score(full, False)


class TestScoreAttachOption:
    def test_fighting_energy_prioritises_raging_bolt_ex_without_fighting(self):
        from cg.api import Option

        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4])
        energy_card = make_pokemon(id=jm.Basic_Fighting_Energy)
        my_state = make_player_state(
            active_pokemon=raging_bolt, hand=[energy_card],
        )
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ATTACH, index=0, inPlayArea=AreaType.ACTIVE, inPlayIndex=0)
        score = jm._score_attach_option(obs, o, my_index=0)
        assert score > 1000  # タケルライコexへの初回闘エネは高優先
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestEnergyScore tests/test_jamoraiko_agent.py::TestScoreAttachOption -v`
Expected: FAIL（`AttributeError: ... has no attribute 'energy_score'`）

- [ ] **Step 3: スコアリング関数を実装する**

`src/jamoraiko_agent/main.py`のアタッカーテーブル定義の後に追加：

```python
# ==================== エネルギー装填スコアリング ====================
def energy_score(pokemon: Pokemon, active: bool) -> int:
    """雷エネルギー装填先の優先度スコアを返す（攻撃射程に近いほど高スコア）"""
    lightning_count = pokemon.energies.count(EnergyType.LIGHTNING)
    score = 8000
    if active:
        score += 10
    if pokemon.id == Iono_Voltorb:
        if lightning_count < 2:
            score += 100
    elif pokemon.id == Iono_Bellibolt_ex:
        if lightning_count < 4:
            score += 60
    elif pokemon.id == Iono_Kilowattrel:
        if lightning_count < 3:
            score += 40
    return score


def _score_attach_option(obs, o, my_index: int) -> int:
    """OptionType.ATTACH のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
    if pokemon is None or card is None:
        return 0
    if card.id == Basic_Fighting_Energy:
        if pokemon.id == Raging_Bolt_ex:
            fighting_count = pokemon.energies.count(EnergyType.FIGHTING)
            return 7000 if fighting_count < 1 else 100
        return 50  # タケルライコex以外への闘エネは低優先
    if card.id == Basic_Lightning_Energy:
        return energy_score(pokemon, o.inPlayArea == AreaType.ACTIVE)
    return 0
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestEnergyScore tests/test_jamoraiko_agent.py::TestScoreAttachOption -v`
Expected: PASS（5テスト）

- [ ] **Step 5: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "feat: エネルギー装填スコアリングを追加"
```

---

### Task 6: 山札セーフティ統合

**Files:**
- Modify: `src/jamoraiko_agent/main.py`
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: `Lillie_Determination`（Task 2）
- Produces: `_safe_draws(my_state) -> int`（Task 4のスタブを置き換え）、`_deck_consumption(card_id, my_state, hand_counts) -> int | None`、`_flashing_draw_consumption(my_state, hand_counts) -> int`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_jamoraiko_agent.py に追記
class TestDeckSafety:
    def test_safe_draws_reserves_one_draw_per_remaining_prize(self):
        my_state = make_player_state(deck_count=20, prize_count=6)
        assert jm._safe_draws(my_state) == 20 - 6 - 1

    def test_lillie_determination_consumption_scales_with_prize(self):
        hand_counts = defaultdict(int, {jm.Lillie_Determination: 1})
        my_state_full_prize = make_player_state(deck_count=40, prize_count=6)
        my_state_low_prize  = make_player_state(deck_count=40, prize_count=2)
        assert jm._deck_consumption(jm.Lillie_Determination, my_state_full_prize, hand_counts) == 8 - 0
        assert jm._deck_consumption(jm.Lillie_Determination, my_state_low_prize, hand_counts) == 6 - 0

    def test_deck_consumption_returns_none_for_unrelated_card(self):
        hand_counts = defaultdict(int, {jm.Canari: 1})
        my_state = make_player_state(deck_count=40, prize_count=6)
        assert jm._deck_consumption(jm.Canari, my_state, hand_counts) is None

    def test_flashing_draw_consumption_fills_hand_to_6(self):
        hand_counts = defaultdict(int, {jm.Canari: 2})  # 手札2枚
        my_state = make_player_state(deck_count=40, prize_count=6)
        assert jm._flashing_draw_consumption(my_state, hand_counts) == 4

    def test_burst_roar_blocked_when_deck_thin(self):
        """山札が薄い時、はじけるほうこう(6枚ドロー固定)は選ばれない"""
        raging_bolt = make_pokemon(id=jm.Raging_Bolt_ex, energies=[4])
        fs = self._fs(active_energy_count=1, own_board_basic_energy_total=1)
        my_state = make_player_state(active_pokemon=raging_bolt, deck_count=5, prize_count=6)  # safe_draws = -2
        plan = jm.calc_attack_plan(raging_bolt, op_active_hp=200, fs=fs, my_state=my_state)
        assert plan.attacker_id == -1  # 使える技がない

    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            own_board_basic_energy_total=0, active_energy_count=0,
        )
        base.update(overrides)
        return jm.FieldState(**base)
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestDeckSafety -v`
Expected: FAIL（`AttributeError: ... has no attribute '_deck_consumption'`。`test_burst_roar_blocked_when_deck_thin`はTask 4で実装済みの`_safe_draws`により既にPASSする可能性があるが、他が失敗するためタスク全体はFAILとして扱う）

- [ ] **Step 3: 残りの山札セーフティ関数を実装する**

`_safe_draws`はTask 4で実装済みのため変更しない。`src/jamoraiko_agent/main.py`の`_safe_draws`定義の直後に以下を追加する：

```python
def _deck_consumption(card_id: int, my_state, hand_counts: defaultdict) -> "int | None":
    """このカードを使った場合の山札の正味消費枚数。山札を消費しない札はNone"""
    hand_count = sum(hand_counts.values())
    if card_id == Lillie_Determination:
        draws = 8 if len(my_state.prize) == 6 else 6
        return max(0, draws - (hand_count - 1))
    return None


def _flashing_draw_consumption(my_state, hand_counts: defaultdict) -> int:
    """タイカイデンの特性「フラッシュドロー」による山札消費枚数
    （自身の雷エネ1個をコストにトラッシュし、手札が6枚になるまでドロー）"""
    hand_count = sum(hand_counts.values())
    return max(0, 6 - hand_count)
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestDeckSafety -v`
Expected: PASS（5テスト）

- [ ] **Step 5: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "feat: 山札セーフティ(_safe_draws/_deck_consumption)を統合"
```

---

### Task 7: 残りのスコアリングとagent()の完全統合

**Files:**
- Modify: `src/jamoraiko_agent/main.py`
- Test: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: `calc_attack_plan`, `energy_score`, `_score_attach_option`, `_deck_consumption`, `_flashing_draw_consumption`, `_safe_draws`（Task 3〜6）
- Produces: `_score_play_option(obs, o, my_index, fs, my_state, plan) -> int`、`_score_option(obs, o, context, my_index, state, my_state, fs, plan) -> int`、完全実装済みの`agent()`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_jamoraiko_agent.py に追記
class TestScorePlayOption:
    def _make_obs_with_hand_card(self, card_id, my_state):
        from cg.api import Option
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.PLAY, index=0)
        return obs, o

    def test_buddy_buddy_poffin_scores_positively(self, mock_card_table):
        mock_card_table[jm.Buddy_Buddy_Poffin] = MockCardData(cardId=jm.Buddy_Buddy_Poffin, cardType=CardType.ITEM)
        poffin = make_pokemon(id=jm.Buddy_Buddy_Poffin)
        my_state = make_player_state(hand=[poffin], deck_count=40, prize_count=6)
        obs, o = self._make_obs_with_hand_card(jm.Buddy_Buddy_Poffin, my_state)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_play_option(obs, o, my_index=0, fs=fs, my_state=my_state, plan=plan)
        assert score > 0

    def test_lillie_determination_blocked_when_deck_thin(self, mock_card_table):
        mock_card_table[jm.Lillie_Determination] = MockCardData(cardId=jm.Lillie_Determination, cardType=CardType.SUPPORTER)
        lillie = make_pokemon(id=jm.Lillie_Determination)
        my_state = make_player_state(hand=[lillie], deck_count=5, prize_count=6)  # safe_draws = -2
        obs, o = self._make_obs_with_hand_card(jm.Lillie_Determination, my_state)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_play_option(obs, o, my_index=0, fs=fs, my_state=my_state, plan=plan)
        assert score == -1

    def test_boss_orders_scores_high_when_lethal(self, mock_card_table):
        mock_card_table[jm.Boss_Orders] = MockCardData(cardId=jm.Boss_Orders, cardType=CardType.SUPPORTER)
        boss = make_pokemon(id=jm.Boss_Orders)
        my_state = make_player_state(hand=[boss], deck_count=40, prize_count=6)
        obs, o = self._make_obs_with_hand_card(jm.Boss_Orders, my_state)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan(attacker_id=jm.Iono_Voltorb, attack_id=1001, damage=300, is_lethal=True)
        score = jm._score_play_option(obs, o, my_index=0, fs=fs, my_state=my_state, plan=plan)
        assert score >= 8000


class TestAgentEndToEnd:
    def test_agent_picks_lethal_attack_when_available(self):
        from cg.api import Option

        my_active = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])
        my_bench  = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4, 4, 4, 4, 4])
        my_state  = make_player_state(active_pokemon=my_active, bench=[my_bench], deck_count=40, prize_count=6)
        op_active = make_pokemon(id=999, hp=50)
        op_state  = make_player_state(active_pokemon=op_active, deck_count=40, prize_count=6)

        options = [
            Option(type=OptionType.RETREAT),
            Option(type=OptionType.ATTACK, attackId=jm._attack_id_by_name("Voltaic Chain") or 1001),
        ]
        obs_dict = make_main_obs(your_index=0, my_state=my_state, op_state=op_state, options=options)
        result = jm.agent(obs_dict)
        chosen = options[result[0]]
        assert chosen.type == OptionType.ATTACK
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py::TestScorePlayOption tests/test_jamoraiko_agent.py::TestAgentEndToEnd -v`
Expected: FAIL（`AttributeError: ... has no attribute '_score_play_option'`）

- [ ] **Step 3: 残りのスコアリングとagent()を実装する**

`src/jamoraiko_agent/main.py`の末尾（暫定`agent()`実装）を以下に置き換える：

```python
# ==================== PLAYオプションのスコアリング ====================
def _score_play_option(obs, o, my_index: int, fs: FieldState, my_state, plan: AttackPlan) -> int:
    """OptionType.PLAY のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    data = card_table[card.id]

    if card.id == Lillie_Determination:
        consumption = _deck_consumption(card.id, my_state, fs.hand_counts)
        if consumption is not None and consumption > _safe_draws(my_state):
            return -1
        return 3100

    if card.id == Boss_Orders:
        return 8800 if plan.is_lethal else 500

    if data.cardType == CardType.POKEMON:
        return 20000

    if card.id == Buddy_Buddy_Poffin:
        return 8000
    if card.id == Ultra_Ball:
        return 6000
    if card.id == Night_Stretcher:
        return 4800
    if card.id == Energy_Retrieval:
        return 6100
    if card.id == Energy_Search:
        return 6050
    if card.id == Max_Rod:
        return 5500
    if card.id == Switch:
        return 2500
    if card.id == Canari:
        return 5900
    if card.id == Levincia:
        return 8500

    return 1000


# ==================== オプション全体のスコアリング ====================
def _score_option(obs, o, context, my_index: int, state, my_state,
                  fs: FieldState, plan: AttackPlan) -> int:
    """1つのオプションにヒューリスティックスコアを付ける"""
    match o.type:
        case OptionType.NUMBER:
            return o.number
        case OptionType.YES:
            return 1
        case OptionType.PLAY:
            return _score_play_option(obs, o, my_index, fs, my_state, plan)
        case OptionType.ATTACH:
            return _score_attach_option(obs, o, my_index)
        case OptionType.EVOLVE:
            return 9000
        case OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if card.id == Iono_Bellibolt_ex:
                return 9500  # エレキストリーマーは常に高優先
            if card.id == Iono_Kilowattrel:
                consumption = _flashing_draw_consumption(my_state, fs.hand_counts)
                return 8000 if consumption <= _safe_draws(my_state) else -1
            return -1
        case OptionType.RETREAT:
            return -1
        case OptionType.ATTACK:
            return 10000 if o.attackId == plan.attack_id else 100
        case _:
            return 0


# ==================== メインエージェント ====================
def agent(obs_dict: dict) -> list[int]:
    """Pokémon TCG エージェント（ジャモライコ）。

    Returns:
        list[int]: 選択するオプションのインデックスリスト
    """
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return _load_deck()

    _build_card_table()
    _build_attack_table()

    state    = obs.current
    select   = obs.select
    context  = select.context
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]

    fs = _collect_field_state(my_state)

    my_active = my_state.active[0] if my_state.active else None
    op_active_hp = op_state.active[0].hp if op_state.active and op_state.active[0] is not None else 10000
    plan = calc_attack_plan(my_active, op_active_hp, fs, my_state)

    scores = [
        _score_option(obs, o, context, my_index, state, my_state, fs, plan)
        for o in select.option
    ]

    desc_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return desc_indices[:select.maxCount]
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `uv run pytest tests/test_jamoraiko_agent.py -v`
Expected: PASS（全テスト）

- [ ] **Step 5: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "feat: 残りのスコアリングとagent()の完全統合"
```

---

### Task 8: リポジトリ全体の回帰確認とデッキCSV生成

**Files:**
- Test: リポジトリ全体（変更なし、確認のみ）
- Create: `output/deck_<実行時刻>.csv`（生成のみ、コミット対象外）

**Interfaces:**
- Consumes: `decks.jamoraiko_20260713.DECK`（Task 1）

- [ ] **Step 1: リポジトリ全体のテストを実行する**

Run: `uv run pytest -q`
Expected: 既存の全テスト + 本タスクで追加したテストがすべてPASS（回帰なし）

- [ ] **Step 2: デッキCSVを生成する**

既存デッキ（例：`decks/lucario_20260621.py`）のCSV化に使っているスクリプト・手順を確認し、同じ形式で`decks/jamoraiko_20260713.py`の`DECK`をカードID1列×60行のCSVとして`output/`配下に出力する。専用スクリプトが無ければ以下のワンライナーで代替する：

```bash
uv run python -c "
from decks.jamoraiko_20260713 import DECK
rows = [str(card_id) for card_id, count in DECK for _ in range(count)]
assert len(rows) == 60
with open('output/deck_jamoraiko_20260713.csv', 'w') as f:
    f.write('\n'.join(rows))
print('written', len(rows), 'rows')
"
```

Expected: `written 60 rows`と出力され、`output/deck_jamoraiko_20260713.csv`が生成される

- [ ] **Step 3: 実装サマリーを作成する**

`docs/implementations/20260713-jamoraiko-agent.md`に以下を記録する：
- 実装したファイル一覧（Task 1〜7の成果物）
- テスト件数（Task 1〜7の合計）
- v1スコープ外とした項目（基本闘エネルギーの自動周回ループ、Kaggle提出）
- 次のステップ（Kaggleへのデッキアップロード・ノートブック作成はユーザー判断）

- [ ] **Step 4: コミット**

```bash
git add docs/implementations/20260713-jamoraiko-agent.md
git commit -m "docs: ジャモライコエージェントの実装サマリーを追加"
```

（`output/deck_jamoraiko_20260713.csv`は`.gitignore`対象の場合はコミット対象外。対象外でなければ追加する）

---

## 未解決・次回以降の検討事項（設計書からの引き継ぎ）

- v2：基本闘エネルギーのサーチ→手貼り→トラッシュ→回収の周回ループの自動化
- さくさくさんの追加の投稿・知見を反映するかどうかの再検討
- 実バトルログでの検証（きょくらいごうが決め手として機能するか、イワパレスの特性を素通りできるかは未確認）
