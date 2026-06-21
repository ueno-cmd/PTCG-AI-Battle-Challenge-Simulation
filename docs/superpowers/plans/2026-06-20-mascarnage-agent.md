# マスカーニャexエージェント 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** マスカーニャex（またはドラパルトex）デッキを使ったルールベーススコアリングエージェントをTDDで実装し、Kaggle Notebookへ貼り付け可能な状態にする。

**Architecture:** ドラパルトexサンプルと同じスコアリング方式（全選択肢に点数を付けて降順返却）をベースに、マスカーニャex専用のブーケマジックターゲット選択ロジックを追加する。ローカルではcg.simをモックしてPyTestでスコアリング関数を単体テスト、Kaggle Notebookに貼り付けて対戦確認する。

**Tech Stack:** Python 3.12.13、uv（仮想環境管理）、pytest

## Global Constraints

- Python 3.12.13（`uv`で管理）
- `cg/`ライブラリは `data/sample_submission/cg/` にある（macOSでは実行不可、テストではモック）
- カードID定数は「**Task 6実施前**にKaggleのDataタブで確認してから設定する」
- RLは対象外
- 提出5回/日制限のため、Kaggle投入前に必ずローカルTDDを通すこと
- gitリポジトリ未設定のためcommitステップは省略

---

## ファイルマップ

| パス | 役割 |
|------|------|
| `src/mascarnage_agent/main.py` | エージェント本体（Kaggleに貼るもの） |
| `src/mascarnage_agent/deck.csv` | デッキ60枚（Task 6で作成） |
| `tests/conftest.py` | cg.simモック + Observation/Pokemonファクトリ |
| `tests/test_helpers.py` | ヘルパー関数の単体テスト |
| `tests/test_scoring.py` | ブーケマジックスコアリングの単体テスト |
| `tests/test_agent.py` | agent()の統合テスト（明らかな誤り検出） |
| `pyproject.toml` | uv用プロジェクト設定 |

---

## Task 1: uv環境とpytest設定

**Files:**
- Create: `pyproject.toml`
- Create: `src/mascarnage_agent/__init__.py`（空ファイル）
- Create: `tests/__init__.py`（空ファイル）

**Interfaces:**
- Produces: `pytest` が `tests/` を認識できる環境

- [ ] **Step 1: pyproject.tomlを作成する**

```toml
[project]
name = "mascarnage-agent"
version = "0.1.0"
requires-python = "==3.12.13"

[dependency-groups]
dev = [
    "pytest>=8.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = [
    "src",
    "data/sample_submission",
]
```

- [ ] **Step 2: ディレクトリ構造を作成する**

```bash
mkdir -p src/mascarnage_agent tests
touch src/mascarnage_agent/__init__.py tests/__init__.py
```

- [ ] **Step 3: uv環境を構築してpytestをインストールする**

```bash
uv sync --group dev
```

- [ ] **Step 4: pytestが動くことを確認する**

```bash
uv run pytest --collect-only
```

期待出力:
```
====== no tests ran ======
```
（エラーなし、テストゼロで正常終了）

---

## Task 2: テスト基盤（conftest.py + ファクトリ）

**Files:**
- Create: `tests/conftest.py`

**Interfaces:**
- Produces: `make_pokemon()` / `make_obs_dict()` fixture（全テストで利用可能）
- Produces: `cg.api` のデータクラスがテストからインポート可能な状態

- [ ] **Step 1: conftest.pyを作成する**

```python
# tests/conftest.py
import sys
import os
from unittest.mock import MagicMock

# libcg.so のロードを防ぐため cg.sim を先にモック（必須）
sys.modules['cg.sim'] = MagicMock()
sys.modules['cg.game'] = MagicMock()

# cg.api のデータクラスをインポート（pure Pythonなのでモック不要）
from cg.api import (
    AreaType, CardType, EnergyType,
    SelectContext, OptionType, SelectType,
    Card, Pokemon, PlayerState, State,
    SelectData, Option, Observation,
)

import pytest


def make_pokemon(
    id: int = 1,
    hp: int = 100,
    max_hp: int = None,
    appear_this_turn: bool = False,
    energies: list = None,
) -> Pokemon:
    """テスト用Pokemonオブジェクトを生成する"""
    return Pokemon(
        id=id,
        serial=id,
        hp=hp,
        maxHp=max_hp if max_hp is not None else hp,
        appearThisTurn=appear_this_turn,
        energies=energies or [],
        energyCards=[],
        tools=[],
        preEvolution=[],
    )


def make_player_state(
    active_pokemon: Pokemon = None,
    bench: list = None,
    hand: list = None,
    hand_count: int = 5,
    deck_count: int = 50,
    prize_count: int = 6,
) -> PlayerState:
    """テスト用PlayerStateオブジェクトを生成する"""
    return PlayerState(
        active=[active_pokemon] if active_pokemon else [],
        bench=bench or [],
        benchMax=5,
        deckCount=deck_count,
        discard=[],
        prize=[None] * prize_count,
        handCount=hand_count,
        hand=hand or [],
        poisoned=False,
        burned=False,
        asleep=False,
        paralyzed=False,
        confused=False,
    )


def make_main_obs(
    your_index: int = 0,
    my_state: PlayerState = None,
    op_state: PlayerState = None,
    options: list = None,
    turn: int = 3,
) -> dict:
    """MAINコンテキストのobs_dictを生成する（agent()に渡すdict形式）"""
    my = my_state or make_player_state(active_pokemon=make_pokemon(id=1, hp=300))
    op = op_state or make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
    players = [my, op] if your_index == 0 else [op, my]

    def player_to_dict(ps: PlayerState) -> dict:
        def poke_to_dict(p) -> dict:
            if p is None:
                return None
            return {
                "id": p.id, "serial": p.serial,
                "hp": p.hp, "maxHp": p.maxHp,
                "appearThisTurn": p.appearThisTurn,
                "energies": [int(e) for e in p.energies],
                "energyCards": [], "tools": [], "preEvolution": [],
            }
        return {
            "active": [poke_to_dict(p) for p in ps.active],
            "bench": [poke_to_dict(p) for p in ps.bench],
            "benchMax": ps.benchMax,
            "deckCount": ps.deckCount,
            "discard": [],
            "prize": [None] * len(ps.prize),
            "handCount": ps.handCount,
            "hand": [],
            "poisoned": False, "burned": False,
            "asleep": False, "paralyzed": False, "confused": False,
        }

    def option_to_dict(o: Option) -> dict:
        return {k: v for k, v in {
            "type": int(o.type),
            "number": o.number,
            "area": int(o.area) if o.area is not None else None,
            "index": o.index,
            "playerIndex": o.playerIndex,
            "inPlayArea": int(o.inPlayArea) if o.inPlayArea is not None else None,
            "inPlayIndex": o.inPlayIndex,
            "attackId": o.attackId,
        }.items() if v is not None}

    return {
        "select": {
            "type": int(SelectType.MAIN),
            "context": int(SelectContext.MAIN),
            "minCount": 1,
            "maxCount": 1,
            "remainDamageCounter": 0,
            "remainEnergyCost": 0,
            "option": [option_to_dict(o) for o in (options or [])],
            "deck": None,
            "contextCard": None,
            "effect": None,
        },
        "logs": [],
        "current": {
            "turn": turn,
            "turnActionCount": 0,
            "yourIndex": your_index,
            "firstPlayer": 0,
            "supporterPlayed": False,
            "stadiumPlayed": False,
            "energyAttached": False,
            "retreated": False,
            "result": -1,
            "stadium": [],
            "looking": None,
            "players": [player_to_dict(p) for p in players],
        },
        "search_begin_input": None,
    }
```

- [ ] **Step 2: conftest.pyが構文エラーなく読み込めることを確認する**

```bash
uv run pytest --collect-only
```

期待出力:
```
====== no tests ran ======
```
（ImportErrorやAttributeErrorが出ないこと）

---

## Task 3: main.py骨格 + ヘルパー関数（TDD）

**Files:**
- Create: `src/mascarnage_agent/main.py`
- Create: `tests/test_helpers.py`

**Interfaces:**
- Produces:
  - `get_card(obs, area, index, player_index) -> Pokemon | Card | None`
  - `no_damage_counter(pokemon: Pokemon) -> bool`
  - `prize_count(pokemon: Pokemon, card_table: dict) -> int`
  - `agent(obs_dict: dict) -> list[int]`（デッキ返却のみ動く状態）

- [ ] **Step 1: テストを書く**

```python
# tests/test_helpers.py
import sys
# conftest.pyが先にロードされることで cg.sim はモック済み

from mascarnage_agent.main import no_damage_counter, prize_count
from tests.conftest import make_pokemon


def test_no_damage_counter_returns_true_for_milotic_ex():
    """ミロカロスex（207）はダメカンを置けない"""
    p = make_pokemon(id=207)
    assert no_damage_counter(p) is True


def test_no_damage_counter_returns_false_for_normal_pokemon():
    """通常ポケモンはダメカンを置ける"""
    p = make_pokemon(id=999)
    assert no_damage_counter(p) is False


def test_prize_count_normal_pokemon():
    """非exポケモンはサイド1枚"""
    from cg.api import CardData, CardType, EnergyType
    card_table = {
        1: CardData(
            cardId=1, name="Normal", cardType=CardType.POKEMON,
            retreatCost=1, hp=100, weakness=None, resistance=None,
            energyType=EnergyType.COLORLESS,
            basic=True, stage1=False, stage2=False,
            ex=False, megaEx=False, tera=False, aceSpec=False,
            evolvesFrom=None, skills=[], attacks=[],
        )
    }
    p = make_pokemon(id=1)
    assert prize_count(p, card_table) == 1


def test_prize_count_ex_pokemon():
    """exポケモンはサイド2枚"""
    from cg.api import CardData, CardType, EnergyType
    card_table = {
        2: CardData(
            cardId=2, name="Test ex", cardType=CardType.POKEMON,
            retreatCost=2, hp=300, weakness=None, resistance=None,
            energyType=EnergyType.COLORLESS,
            basic=False, stage1=False, stage2=False,
            ex=True, megaEx=False, tera=False, aceSpec=False,
            evolvesFrom=None, skills=[], attacks=[],
        )
    }
    p = make_pokemon(id=2)
    assert prize_count(p, card_table) == 2


def test_prize_count_mega_ex_pokemon():
    """メガexポケモンはサイド3枚"""
    from cg.api import CardData, CardType, EnergyType
    card_table = {
        3: CardData(
            cardId=3, name="Test Mega ex", cardType=CardType.POKEMON,
            retreatCost=3, hp=400, weakness=None, resistance=None,
            energyType=EnergyType.COLORLESS,
            basic=False, stage1=False, stage2=False,
            ex=True, megaEx=True, tera=False, aceSpec=False,
            evolvesFrom=None, skills=[], attacks=[],
        )
    }
    p = make_pokemon(id=3)
    assert prize_count(p, card_table) == 3
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_helpers.py -v
```

期待出力:
```
FAILED tests/test_helpers.py::... - ModuleNotFoundError: No module named 'mascarnage_agent.main'
```

- [ ] **Step 3: main.pyの骨格とヘルパー関数を実装する**

```python
# src/mascarnage_agent/main.py
import os
from collections import defaultdict

from cg.api import (
    AreaType, CardType, EnergyType,
    Observation, SelectContext, OptionType,
    Card, Pokemon, all_card_data, to_observation_class,
)

# =====================================================================
# カードID定数
# ※ Task 6実施前に Kaggle Dataタブでカードプールを確認してから設定する
# =====================================================================
# マスカーニャexデッキ（カード確認後に設定）
NYAHOJA       = 0   # ニャオハ
NYAROTE       = 0   # ニャローテ
MASCARNAGE_EX = 0   # マスカーニャex
# トレーナーズ等も同様に確認後に設定

# フォールバック用：ドラパルトex（カードプール確認済み）
DREEPY       = 119
DRAKLOAK     = 120
DRAGAPULT_EX = 121

# ダメカンを置けない免疫ポケモンID（既知リスト、環境変化で更新）
_IMMUNE_IDS = frozenset({
    28,   # ポットデス
    199,  # エンペルトex
    203,  # スケルジ
    207,  # ミロカロスex
    362,  # ミスティのコイキング
    1136, # むかしのふたのかせき
})

# ダメカンを置けない特殊エネルギーID
_IMMUNE_ENERGY_IDS = frozenset({
    11,  # ミストエネルギー
    20,  # がんせきかくとうエネルギー
})

# =====================================================================
# カードテーブル（遅延初期化 — agent()初回呼び出し時にロード）
# =====================================================================
_card_table: dict = {}


def _load_cards() -> dict:
    """カードテーブルを遅延初期化する"""
    global _card_table
    if not _card_table:
        all_card = all_card_data()
        _card_table = {c.cardId: c for c in all_card}
    return _card_table


# =====================================================================
# デッキ読み込み（モジュールロード時 — Kaggle実行環境用）
# =====================================================================
def _read_deck() -> list[int]:
    file_path = "deck.csv"
    if not os.path.exists(file_path):
        file_path = "/kaggle_simulations/agent/" + file_path
    if not os.path.exists(file_path):
        return []  # テスト環境ではデッキなし
    with open(file_path, "r") as f:
        lines = f.read().split("\n")
    return [int(lines[i]) for i in range(60)]


my_deck = _read_deck()


# =====================================================================
# ヘルパー関数
# =====================================================================

def get_card(obs: Observation, area: AreaType, index: int, player_index: int):
    """エリア×インデックスからカードまたはポケモンを取得する"""
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


def no_damage_counter(pokemon: Pokemon) -> bool:
    """相手ポケモンにダメカンを置けないかどうかを判定する"""
    if pokemon.id in _IMMUNE_IDS:
        return True
    for card in pokemon.energyCards:
        if card.id in _IMMUNE_ENERGY_IDS:
            return True
    return False


def prize_count(pokemon: Pokemon, card_table: dict) -> int:
    """ポケモンをKOしたときに相手が取るサイド枚数を返す"""
    data = card_table.get(pokemon.id)
    if data is None:
        return 1
    if data.megaEx:
        return 3
    if data.ex:
        return 2
    return 1


# =====================================================================
# エージェント本体（スコアリングは後続Taskで実装）
# =====================================================================

def agent(obs_dict: dict) -> list[int]:
    """ポケモンカードゲームAIエージェント本体"""
    obs = to_observation_class(obs_dict)

    # 初回呼び出し時のみ実行（カードテーブル初期化）
    card_table = _load_cards()

    # デッキ選択フェーズ（obs.selectがNoneの場合）
    if obs.select is None:
        return my_deck

    # TODO: スコアリングロジックはTask 4・5で実装
    # 暫定：ランダム順で返す（動作確認用）
    import random
    select = obs.select
    indices = list(range(len(select.option)))
    random.shuffle(indices)
    return indices[:select.maxCount]
```

- [ ] **Step 4: テストを実行してパスすることを確認する**

```bash
uv run pytest tests/test_helpers.py -v
```

期待出力:
```
PASSED tests/test_helpers.py::test_no_damage_counter_returns_true_for_milotic_ex
PASSED tests/test_helpers.py::test_no_damage_counter_returns_false_for_normal_pokemon
PASSED tests/test_helpers.py::test_prize_count_normal_pokemon
PASSED tests/test_helpers.py::test_prize_count_ex_pokemon
PASSED tests/test_helpers.py::test_prize_count_mega_ex_pokemon
====== 5 passed ======
```

---

## Task 4: ブーケマジックスコアリング（TDD）

**Files:**
- Modify: `src/mascarnage_agent/main.py`（`bouquet_magic_score`を追加）
- Create: `tests/test_scoring.py`

**Interfaces:**
- Consumes: `no_damage_counter(pokemon) -> bool`（Task 3で実装済み）
- Produces: `bouquet_magic_score(target: Pokemon) -> int`

- [ ] **Step 1: テストを書く**

```python
# tests/test_scoring.py
from mascarnage_agent.main import bouquet_magic_score
from tests.conftest import make_pokemon


def test_bouquet_prefers_lower_hp_target():
    """HPが低い相手を優先する（スコアが高くなる）"""
    low_hp  = make_pokemon(id=1, hp=30,  max_hp=200)
    high_hp = make_pokemon(id=2, hp=200, max_hp=200)
    assert bouquet_magic_score(low_hp) > bouquet_magic_score(high_hp)


def test_bouquet_bonus_for_already_damaged():
    """すでにダメカンが乗っている相手はボーナスが付く"""
    damaged = make_pokemon(id=1, hp=100, max_hp=200)  # 100点ダメージ済み
    fresh   = make_pokemon(id=2, hp=200, max_hp=200)  # ノーダメージ
    assert bouquet_magic_score(damaged) > bouquet_magic_score(fresh)


def test_bouquet_returns_minus1_for_immune_target():
    """ダメカン免疫の相手はスコア -1"""
    immune = make_pokemon(id=207)  # ミロカロスex
    assert bouquet_magic_score(immune) == -1


def test_bouquet_returns_positive_for_normal_target():
    """通常ポケモンへのスコアは正の値"""
    normal = make_pokemon(id=999, hp=100)
    assert bouquet_magic_score(normal) > 0
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_scoring.py -v
```

期待出力:
```
FAILED tests/test_scoring.py::... - ImportError: cannot import name 'bouquet_magic_score'
```

- [ ] **Step 3: bouquet_magic_scoreをmain.pyに追加する**

`# TODO: スコアリングロジックはTask 4・5で実装` の上の行に追加：

```python
def bouquet_magic_score(target: Pokemon) -> int:
    """ブーケマジックのターゲット選択スコアを計算する（高いほど優先）"""
    if no_damage_counter(target):
        return -1
    # HPが低いほど高スコア（早期KO優先）
    score = 10000 - target.hp
    # すでにダメカンが乗っていれば追加ボーナス
    if target.hp < target.maxHp:
        score += 5000
    return score
```

- [ ] **Step 4: テストを実行してパスすることを確認する**

```bash
uv run pytest tests/test_scoring.py -v
```

期待出力:
```
PASSED tests/test_scoring.py::test_bouquet_prefers_lower_hp_target
PASSED tests/test_scoring.py::test_bouquet_bonus_for_already_damaged
PASSED tests/test_scoring.py::test_bouquet_returns_minus1_for_immune_target
PASSED tests/test_scoring.py::test_bouquet_returns_positive_for_normal_target
====== 4 passed ======
```

- [ ] **Step 5: 全テストを実行して既存テストが壊れていないことを確認する**

```bash
uv run pytest -v
```

期待出力：全テストPASS

---

## Task 5: agent()スコアリング本体（TDD）

**Files:**
- Modify: `src/mascarnage_agent/main.py`（agent()のTODO部分を実装）
- Create: `tests/test_agent.py`

**Interfaces:**
- Consumes: `bouquet_magic_score(target) -> int`（Task 4で実装済み）
- Consumes: `make_main_obs()` / `make_pokemon()` / `make_player_state()`（conftest.py）
- Produces: `agent(obs_dict) -> list[int]`（完全動作版）

- [ ] **Step 1: テストを書く**

```python
# tests/test_agent.py
from cg.api import OptionType, AreaType, Option
from mascarnage_agent.main import agent
from tests.conftest import make_pokemon, make_player_state, make_main_obs


def _attack_option(attack_id: int = 100) -> Option:
    return Option(type=OptionType.ATTACK, attackId=attack_id)


def _end_option() -> Option:
    return Option(type=OptionType.END)


def test_agent_returns_deck_when_select_is_none():
    """obs.selectがNoneのとき（デッキ選択フェーズ）はデッキを返す"""
    obs_dict = {"select": None, "logs": [], "current": None,
                "search_begin_input": None}
    result = agent(obs_dict)
    # deck.csvがない環境では空リストが返る（エラーにならないこと）
    assert isinstance(result, list)


def test_agent_prefers_attack_over_end():
    """攻撃オプションがあるときはターン終了より攻撃を選ぶ"""
    options = [_end_option(), _attack_option(attack_id=100)]
    obs_dict = make_main_obs(options=options)
    result = agent(obs_dict)
    assert len(result) == 1
    selected_option_index = result[0]
    # 選ばれたオプションがATTACKであること
    assert options[selected_option_index].type == OptionType.ATTACK


def test_agent_returns_valid_indices():
    """返り値のインデックスがoption範囲内かつ重複がないこと"""
    # ABILITYはベンチアクセスが必要なため、ATTACK/ENDのみでテスト
    options = [_attack_option(attack_id=100), _attack_option(attack_id=101), _end_option()]
    obs_dict = make_main_obs(options=options)
    result = agent(obs_dict)
    assert len(result) >= 1
    assert len(result) == len(set(result))  # 重複なし
    assert all(0 <= i < len(options) for i in result)  # 範囲内
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```bash
uv run pytest tests/test_agent.py -v
```

期待出力：`test_agent_prefers_attack_over_end` が FAIL（暫定ランダム実装のため）

- [ ] **Step 3: agent()のスコアリング本体を実装する**

`main.py` の `agent()` 内の `# TODO` 以降を以下で置き換える：

```python
    state   = obs.current
    select  = obs.select
    context = select.context
    my_index   = state.yourIndex
    my_state   = state.players[my_index]
    op_state   = state.players[1 - my_index]

    scores = []
    for o in select.option:
        score = 0

        if o.type == OptionType.NUMBER:
            score = o.number or 0

        elif o.type == OptionType.YES:
            score = 1

        elif o.type == OptionType.EVOLVE:
            # 進化は最優先（後続ロジックを制御しやすくする）
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            score = 110000 + (len(pokemon.energies) if pokemon else 0)

        elif o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            if card is None:
                score = -1
            elif card_table.get(card.id) and card_table[card.id].cardType == CardType.POKEMON:
                score = 100000
            else:
                score = 70000  # トレーナーズ全般（詳細はデッキ確認後に調整）

        elif o.type == OptionType.ABILITY:
            # ブーケマジック（マスカーニャexの特性）
            card = get_card(obs, o.area, o.index, my_index)
            if card is not None and card.id == MASCARNAGE_EX:
                # ベンチ全体で最もスコアの高いターゲットを基準にする
                bench_scores = [
                    bouquet_magic_score(p) for p in op_state.bench
                ]
                best = max(bench_scores, default=-1)
                score = 60000 + best if best >= 0 else -1
            else:
                score = 40000  # 他のアビリティ

        elif o.type == OptionType.ATTACH:
            score = 50000

        elif o.type == OptionType.RETREAT:
            score = 30000

        elif o.type == OptionType.ATTACK:
            # 攻撃は最後（ターンを終わらせる行動）
            # スクラッチネイル：相手バトルポケモンにダメカンがあれば優先
            base = 1000 + (o.attackId or 0)
            if op_state.active and len(op_state.active) > 0:
                op_active = op_state.active[0]
                if op_active and op_active.hp < op_active.maxHp:
                    base += 5000  # ダメカンあり → スクラッチネイル高威力
            score = base

        elif o.type == OptionType.END:
            score = 0

        scores.append(score)

    sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return sorted_indices[:select.maxCount]
```

- [ ] **Step 4: テストを実行してパスすることを確認する**

```bash
uv run pytest tests/test_agent.py -v
```

期待出力:
```
PASSED tests/test_agent.py::test_agent_returns_deck_when_select_is_none
PASSED tests/test_agent.py::test_agent_prefers_attack_over_end
PASSED tests/test_agent.py::test_agent_returns_valid_indices
====== 3 passed ======
```

- [ ] **Step 5: 全テストを実行して全パスすることを確認する**

```bash
uv run pytest -v
```

期待出力：全12テストPASS

---

## Task 6: deck.csv + Kaggle提出準備

> ⚠️ **前提条件:** KaggleのDataタブでカードIDを確認してから実施する

**Files:**
- Create: `src/mascarnage_agent/deck.csv`
- Modify: `src/mascarnage_agent/main.py`（カードID定数を設定）

**Interfaces:**
- Produces: Kaggle Notebookに貼り付け可能な `main.py` + `deck.csv`

- [ ] **Step 1: カードIDを確認してmain.pyの定数を更新する**

Kaggle Dataタブ（`EN_Card_Data.csv`）でIDを確認後、`main.py` 冒頭の定数を設定：

```python
# マスカーニャexがある場合
NYAHOJA       = ???   # DataタブのCard IDを参照
NYAROTE       = ???
MASCARNAGE_EX = ???

# マスカーニャexがない場合は以下を使う（既にIDが確定している）
# DREEPY=119 / DRAKLOAK=120 / DRAGAPULT_EX=121
```

- [ ] **Step 2: deck.csvを作成する（60行、1行1枚）**

```
# マスカーニャexデッキの例（IDが確定してから記入）
???
???
...（60行）
```

- [ ] **Step 3: 全テストを実行してパスすることを確認する**

```bash
uv run pytest -v
```

- [ ] **Step 4: Kaggle Notebookにコピーする**

Kaggle Notebookで以下のセル構成を使う：

```python
# Cell 1: エージェント本体（main.pyの内容をそのままペースト）
%%writefile main.py
# （main.pyの内容をここに貼り付ける）
```

```python
# Cell 2: tar.gz生成・提出
import glob, os, tarfile
with tarfile.open("submission.tar.gz", "w:gz") as tar:
    tar.add("main.py", arcname="main.py")
    tar.add(glob.glob('/kaggle/input/**/cg-lib/cg', recursive=True)[0], arcname="cg")
    tar.add(glob.glob('/kaggle/input/**/deck.csv', recursive=True)[0], arcname="deck.csv")
os.remove('main.py')
```

- [ ] **Step 5: 1投目はサンプルノートブックそのままで提出して動作確認する**

（サンプルが通ることを確認してから自作エージェントに差し替える）
