# ドラパルトex `attach_score()` ベンチ配分バグ再検証 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 20戦分のバトルログ（`data/battle_logs/87204277.json`〜`87214695.json`）に含まれる、ドラパルトexデッキのベンチ向けエネルギー装着イベント全件を、スナップショットに頼らないイベント再生方式で正しく再判定し、`attach_score()`のロジックに実際のバグがあるかを確定させる。

**Architecture:** `src/etl/gold.py`に生イベントを1件ずつ適用してインクリメンタルに場の状態を追跡する`GameStateTracker`クラスを新規実装する。`src/dragapult_agent/main.py`の`attach_score()`はクロージャから独立関数`_attach_score()`へ引数化（純粋リファクタリング、ロジック変更なし）する。両者を使う検証スクリプト`scripts/analyze_dragapult_attach_scoring.py`で20戦を通し実行し、矛盾件数をレポート出力する。

**Tech Stack:** Python 3.12 / uv / pytest。`cg.api`のネイティブライブラリ(`cg.sim`)はmacOSで動かないため、テスト・分析スクリプトは`tests/conftest.py`と同じ`MagicMock()`モック方式で`cg.sim`/`cg.game`を回避する。

## Global Constraints

- 全てのコメント・ドキュメントは日本語で書く（変数名・関数名は英語）
- `uv run pytest -q`でリポジトリ全体が常に全件PASSであること（各タスク末尾で確認）
- `attach_score()`のリファクタリングはロジック変更を一切含まない（動作を変えないことをテストで保証する）
- 新規ファイルは既存の`scripts/analyze_*.py` / `tests/test_analyze_*.py`の命名・構造規約に従う

---

### Task 1: `GameStateTracker`のイベント処理実装

**Files:**
- Modify: `src/etl/gold.py`
- Test: `tests/test_etl_gold.py`

**Interfaces:**
- Produces: `class GameStateTracker` with `__init__(self, target_player_index: int, tool_card_ids: frozenset[int] = frozenset())`、属性`active_serial: int | None`, `bench_serials: set[int]`, `species: dict[int, int]`, `energy_count: dict[int, int]`（`collections.defaultdict(int)`）, `asleep: bool`, `paralyzed: bool`, `opponent_prize_remaining: int`。メソッド`apply(self, event: dict) -> None`。

- [ ] **Step 1: 失敗するテストを書く（MOVE_CARD: アクティブへの新規登場）**

`tests/test_etl_gold.py`の末尾に追記：

```python
from etl.gold import GameStateTracker


def test_tracker_move_card_to_active_sets_active_serial():
    tracker = GameStateTracker(target_player_index=0)
    tracker.apply({
        "type": 6, "playerIndex": 0, "cardId": 121, "serial": 10,
        "fromArea": 2, "toArea": 4,
    })
    assert tracker.active_serial == 10
    assert tracker.species[10] == 121
    assert tracker.energy_count[10] == 0


def test_tracker_move_card_to_bench_adds_bench_serial():
    tracker = GameStateTracker(target_player_index=0)
    tracker.apply({
        "type": 6, "playerIndex": 0, "cardId": 119, "serial": 11,
        "fromArea": 2, "toArea": 5,
    })
    assert 11 in tracker.bench_serials
    assert tracker.species[11] == 119


def test_tracker_move_card_active_to_discard_removes_pokemon():
    tracker = GameStateTracker(target_player_index=0)
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 121, "serial": 10, "fromArea": 2, "toArea": 4})
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 121, "serial": 10, "fromArea": 4, "toArea": 3})
    assert tracker.active_serial is None
    assert 10 not in tracker.species
    assert 10 not in tracker.energy_count


def test_tracker_ignores_other_players_move_card():
    tracker = GameStateTracker(target_player_index=0)
    tracker.apply({"type": 6, "playerIndex": 1, "cardId": 999, "serial": 50, "fromArea": 2, "toArea": 4})
    assert tracker.active_serial is None
    assert 50 not in tracker.species
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_etl_gold.py -k test_tracker_move_card -v`
Expected: FAIL（`ImportError: cannot import name 'GameStateTracker'`）

- [ ] **Step 3: `GameStateTracker`とMOVE_CARD処理を実装する**

`src/etl/gold.py`の`LOG_TYPE_RESULT = 23`の直後に追記：

```python
LOG_TYPE_MOVE_CARD = 6
LOG_TYPE_ATTACH = 11
LOG_TYPE_EVOLVE = 12
LOG_TYPE_ASLEEP = 19
LOG_TYPE_PARALYZED = 20

AREA_HAND = 2
AREA_DISCARD = 3
AREA_ACTIVE = 4
AREA_BENCH = 5
AREA_PRIZE = 6


class GameStateTracker:
    """自分(target_player_index)の場の状態と相手の残りサイド枚数を、
    生イベントを1件ずつ適用してインクリメンタルに追跡する。

    1つの観測ステップに複数ターン分のイベントが混在しうるため、
    ステップ単位のスナップショット(observation.current)は一切参照しない。
    build_event_timeline()が返すフラットなイベント列を順番にapply()するだけで、
    任意の時点の「本当のアクティブ/ベンチ構成」を再現できる。
    """

    INITIAL_PRIZE_COUNT = 6

    def __init__(self, target_player_index: int, tool_card_ids: frozenset = frozenset()):
        self.target_player_index = target_player_index
        self.opponent_index = 1 - target_player_index
        self.tool_card_ids = tool_card_ids
        self.active_serial: int | None = None
        self.bench_serials: set = set()
        self.species: dict = {}
        self.energy_count: dict = collections.defaultdict(int)
        self.energy_cards: dict = collections.defaultdict(list)  # serial -> 装着済みエネルギーcard_idのリスト
        self.asleep = False
        self.paralyzed = False
        self.opponent_prize_remaining = self.INITIAL_PRIZE_COUNT

    def apply(self, event: dict) -> None:
        event_type = event.get("type")
        player_index = event.get("playerIndex")

        if (event_type == LOG_TYPE_MOVE_CARD and player_index == self.opponent_index
                and event.get("fromArea") == AREA_PRIZE and event.get("toArea") == AREA_HAND):
            self.opponent_prize_remaining -= 1

        if player_index != self.target_player_index:
            return

        if event_type == LOG_TYPE_MOVE_CARD:
            self._apply_move_card(event)
        elif event_type == LOG_TYPE_SWITCH:
            self._apply_switch(event)
        elif event_type == LOG_TYPE_ATTACH:
            self._apply_attach(event)
        elif event_type == LOG_TYPE_EVOLVE:
            self._apply_evolve(event)
        elif event_type == LOG_TYPE_ASLEEP:
            self.asleep = not event.get("isRecover", False)
        elif event_type == LOG_TYPE_PARALYZED:
            self.paralyzed = not event.get("isRecover", False)

    def _apply_move_card(self, event: dict) -> None:
        serial = event["serial"]
        card_id = event["cardId"]
        from_area = event.get("fromArea")
        to_area = event.get("toArea")
        if to_area == AREA_ACTIVE:
            self.active_serial = serial
            self.species[serial] = card_id
            self.energy_count[serial]  # defaultdictでキーを作るだけ
        elif to_area == AREA_BENCH:
            self.bench_serials.add(serial)
            self.species[serial] = card_id
            self.energy_count[serial]
        elif to_area == AREA_DISCARD and from_area in (AREA_ACTIVE, AREA_BENCH):
            self._remove_serial(serial)

    def _apply_switch(self, event: dict) -> None:
        # cardIdActive/serialActive: アクティブから退場しベンチへ行く側
        # cardIdBench/serialBench: ベンチから登場しアクティブになる側
        # (cg/api.pyのコメントはフィールド名と意味が逆になっている点に注意。
        #  2026-07-22に一度取り違えて誤診断した実績があるため、この対応関係を変更する際は要注意)
        outgoing_serial = event["serialActive"]
        incoming_serial = event["serialBench"]
        assert self.active_serial == outgoing_serial, (
            f"SWITCH整合性エラー: tracker.active_serial={self.active_serial} "
            f"がイベントのserialActive={outgoing_serial}と一致しない"
        )
        self.bench_serials.discard(incoming_serial)
        self.bench_serials.add(outgoing_serial)
        self.active_serial = incoming_serial

    def _apply_attach(self, event: dict) -> None:
        target_serial = event["serialTarget"]
        card_id = event["cardId"]
        if card_id not in self.tool_card_ids:
            self.energy_count[target_serial] += 1
            self.energy_cards[target_serial].append(card_id)

    def _apply_evolve(self, event: dict) -> None:
        pre_serial = event["serialTarget"]
        post_serial = event["serial"]
        post_card_id = event["cardId"]
        energy = self.energy_count.pop(pre_serial, 0)
        energy_cards = self.energy_cards.pop(pre_serial, [])
        self.species.pop(pre_serial, None)
        if self.active_serial == pre_serial:
            self.active_serial = post_serial
        elif pre_serial in self.bench_serials:
            self.bench_serials.discard(pre_serial)
            self.bench_serials.add(post_serial)
        self.species[post_serial] = post_card_id
        self.energy_count[post_serial] = energy
        self.energy_cards[post_serial] = energy_cards

    def _remove_serial(self, serial: int) -> None:
        self.species.pop(serial, None)
        self.energy_count.pop(serial, None)
        self.energy_cards.pop(serial, None)
        self.bench_serials.discard(serial)
        if self.active_serial == serial:
            self.active_serial = None
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_etl_gold.py -k test_tracker_move_card -v`
Expected: PASS（4件）

- [ ] **Step 5: SWITCH/ATTACH/EVOLVE/ASLEEP/PARALYZED/opponent_prize_remainingの失敗するテストを書く**

`tests/test_etl_gold.py`に追記：

```python
def test_tracker_switch_swaps_active_and_bench_correctly():
    """SWITCHのフィールド名は意味と逆(serialActive=退場/serialBench=登場)。
    ここを取り違えると2026-07-22に発覚したのと同じ致命的な誤判定が再発する"""
    tracker = GameStateTracker(target_player_index=0)
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 121, "serial": 10, "fromArea": 2, "toArea": 4})
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 119, "serial": 11, "fromArea": 2, "toArea": 5})
    tracker.apply({
        "type": 8, "playerIndex": 0,
        "cardIdActive": 121, "serialActive": 10,
        "cardIdBench": 119, "serialBench": 11,
    })
    assert tracker.active_serial == 11
    assert 10 in tracker.bench_serials
    assert 11 not in tracker.bench_serials


def test_tracker_attach_energy_increments_count():
    tracker = GameStateTracker(target_player_index=0, tool_card_ids=frozenset({1159}))
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 121, "serial": 10, "fromArea": 2, "toArea": 4})
    tracker.apply({"type": 11, "playerIndex": 0, "cardId": 6, "serial": 90, "cardIdTarget": 121, "serialTarget": 10})
    assert tracker.energy_count[10] == 1


def test_tracker_attach_energy_records_card_id_in_energy_cards_list():
    """_attach_score()のenergy_count==1分岐がpokemon.energyCards[0].idを参照するため、
    countだけでなく実際に貼られたエネルギーのcard_idも保持できていないと後段のTask5で
    再現できない（energy_countをintのみで持つ設計だとここが欠落することに自己レビューで気付いた）"""
    tracker = GameStateTracker(target_player_index=0, tool_card_ids=frozenset({1159}))
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 121, "serial": 10, "fromArea": 2, "toArea": 4})
    tracker.apply({"type": 11, "playerIndex": 0, "cardId": 6, "serial": 90, "cardIdTarget": 121, "serialTarget": 10})
    assert tracker.energy_cards[10] == [6]


def test_tracker_attach_tool_does_not_increment_energy_count():
    tracker = GameStateTracker(target_player_index=0, tool_card_ids=frozenset({1159}))
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 121, "serial": 10, "fromArea": 2, "toArea": 4})
    tracker.apply({"type": 11, "playerIndex": 0, "cardId": 1159, "serial": 91, "cardIdTarget": 121, "serialTarget": 10})
    assert tracker.energy_count[10] == 0


def test_tracker_evolve_preserves_position_and_energy():
    tracker = GameStateTracker(target_player_index=0)
    tracker.apply({"type": 6, "playerIndex": 0, "cardId": 119, "serial": 11, "fromArea": 2, "toArea": 5})
    tracker.apply({"type": 11, "playerIndex": 0, "cardId": 6, "serial": 90, "cardIdTarget": 119, "serialTarget": 11})
    tracker.apply({
        "type": 12, "playerIndex": 0,
        "cardId": 121, "serial": 12,
        "cardIdTarget": 119, "serialTarget": 11,
    })
    assert 12 in tracker.bench_serials
    assert 11 not in tracker.bench_serials
    assert tracker.species[12] == 121
    assert tracker.energy_count[12] == 1
    assert tracker.energy_cards[12] == [6]
    assert 11 not in tracker.species


def test_tracker_asleep_and_paralyzed_toggle_with_is_recover():
    tracker = GameStateTracker(target_player_index=0)
    tracker.apply({"type": 19, "playerIndex": 0, "cardId": 121, "serial": 10, "isRecover": False})
    assert tracker.asleep is True
    tracker.apply({"type": 19, "playerIndex": 0, "cardId": 121, "serial": 10, "isRecover": True})
    assert tracker.asleep is False
    tracker.apply({"type": 20, "playerIndex": 0, "cardId": 121, "serial": 10, "isRecover": False})
    assert tracker.paralyzed is True


def test_tracker_opponent_prize_taken_decrements_remaining():
    tracker = GameStateTracker(target_player_index=0)
    assert tracker.opponent_prize_remaining == 6
    tracker.apply({"type": 6, "playerIndex": 1, "fromArea": 6, "toArea": 2, "cardId": 5, "serial": 40})
    assert tracker.opponent_prize_remaining == 5
```

- [ ] **Step 6: テストが失敗することを確認する（SWITCH/EVOLVE等が未実装の場合の挙動を目視確認）**

Run: `uv run pytest tests/test_etl_gold.py -k "test_tracker_switch or test_tracker_attach or test_tracker_evolve or test_tracker_asleep or test_tracker_opponent_prize" -v`
Expected: 全てPASS（Step 3で全イベント種別を実装済みのため。もしFAILする場合はStep 3の実装漏れを修正する）

- [ ] **Step 7: リポジトリ全体の回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 8: コミット**

```bash
git add src/etl/gold.py tests/test_etl_gold.py
git commit -m "$(cat <<'EOF'
feat(etl): イベント再生ベースのGameStateTrackerを追加

前回の分析でスナップショット判定が誤りだったと判明したため、
生イベントを1件ずつ適用してインクリメンタルに場の状態を追跡する
方式に切り替える。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: 既存ログでの結合テスト（クロスチェック）

**Files:**
- Test: `tests/test_etl_gold.py`

**Interfaces:**
- Consumes: `build_event_timeline`（既存）, `GameStateTracker`（Task 1）, `_find_energy_count`（既存）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_etl_gold.py`に追記（既存の`test_extract_attack_events_includes_energy_count_at_that_time`が
「player_index=1のserial=66がstep=20時点でenergy_count=1」であることをスナップショットベースの
`_find_energy_count`で確認済みであることを利用し、同じ値をトラッカーでクロスチェックする）：

```python
def test_tracker_full_game_replay_matches_snapshot_energy_count(sample_log):
    from etl.gold import _find_energy_count

    tracker = GameStateTracker(target_player_index=1)
    timeline = build_event_timeline(sample_log, player_index=0)
    for step_index, event in timeline:
        tracker.apply(event)
        if step_index > 20:
            break

    expected = _find_energy_count(sample_log, step_index=20, owner_index=1, serial=66)
    assert tracker.energy_count[66] == expected
```

- [ ] **Step 2: テストを実行し、通ることを確認する**

Run: `uv run pytest tests/test_etl_gold.py -k test_tracker_full_game_replay -v`
Expected: PASS。もしFAILした場合は、`data/battle_logs/84580427.json`のstep 20周辺のイベント列を
`python3 -c "..."`で目視し、Task 1のイベント処理漏れ（特にEVOLVE/ATTACHの対象serial取り違え）を
特定して修正する。ここで安易に期待値を書き換えて帳尻を合わせないこと（既存のスナップショット
ヘルパーの方が単純で信頼性が高い時点での値のため、トラッカー側にバグがある可能性が高い）

- [ ] **Step 3: リポジトリ全体の回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 4: コミット**

```bash
git add tests/test_etl_gold.py
git commit -m "$(cat <<'EOF'
test(etl): GameStateTrackerを実ログでスナップショットとクロスチェック

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `attach_score()`の引数化リファクタリング

**Files:**
- Modify: `src/dragapult_agent/main.py:412-466`（定義）, `:593,595,730,826`（呼び出し箇所）
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Produces: モジュールレベル関数 `_attach_score(attach_id: int, pokemon: Pokemon, active: bool, *, card_table: dict, can_switch: bool, bench_attacker: bool, no_more_dex: bool, field_counts: dict, my_asleep: bool, my_paralyzed: bool) -> int`（Task 5で検証スクリプトが直接importして使う）

- [ ] **Step 1: 失敗するテストを書く（既存ロジックの回帰確認用の最小テスト）**

`tests/test_dragapult_agent.py`に追記：

```python
from collections import defaultdict
from dataclasses import dataclass, field as dc_field

from cg.api import CardType


@dataclass
class _MockCardData:
    cardId: int
    cardType: CardType = CardType.BASIC_ENERGY


@dataclass
class _MockPokemon:
    id: int
    energies: list = dc_field(default_factory=list)
    energyCards: list = dc_field(default_factory=list)


def test_attach_score_active_gets_priority_when_bench_attacker_ready_and_zero_energy():
    """energy_count=0・active=True・bench_attackerありなら+400点される既存挙動を維持"""
    card_table = {dm.Basic_Fire_Energy: _MockCardData(cardId=dm.Basic_Fire_Energy)}
    pokemon = _MockPokemon(id=dm.Dragapult_ex)
    score = dm._attach_score(
        dm.Basic_Fire_Energy, pokemon, True,
        card_table=card_table, can_switch=False, bench_attacker=True,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    assert score == 20000 + 400


def test_attach_score_returns_minus_one_for_bench_pokemon_with_full_energy():
    """energy_count>=2かつactive=Falseの控えポケモンには、これ以上エネルギーを
    貼る意味がないため-1（非採用）を返す既存挙動を維持"""
    card_table = {dm.Basic_Fire_Energy: _MockCardData(cardId=dm.Basic_Fire_Energy)}
    pokemon = _MockPokemon(id=dm.Dragapult_ex, energies=[1, 1], energyCards=[
        _MockCardData(cardId=dm.Basic_Fire_Energy)])
    score = dm._attach_score(
        dm.Basic_Fire_Energy, pokemon, False,
        card_table=card_table, can_switch=False, bench_attacker=False,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    assert score == -1
```

`Basic_Fire_Energy`は`src/dragapult_agent/constants.py:24`で`Basic_Fire_Energy = 2`と
定義済みの実在の定数（ドラパルトexデッキが実際に採用する基本エネルギー）。

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -k test_attach_score -v`
Expected: FAIL（`AttributeError: module 'dragapult_agent.main' has no attribute '_attach_score'`）

- [ ] **Step 3: `attach_score`をモジュールレベル関数`_attach_score`へ引数化する**

`src/dragapult_agent/main.py`の412-466行目（`def attach_score(...)`全体）を削除し、
同じ内容をファイル冒頭（`card_table: dict = {}`の定義より後、`_build_card_table()`の後）に
モジュールレベル関数として移動する：

```python
def _attach_score(
    attach_id: int,
    pokemon: Pokemon,
    active: bool,
    *,
    card_table: dict,
    can_switch: bool,
    bench_attacker: bool,
    no_more_dex: bool,
    field_counts: dict,
    my_asleep: bool,
    my_paralyzed: bool,
) -> int:
    energy_count = len(pokemon.energies)
    if card_table[attach_id].cardType == CardType.TOOL:
        # Attach tool
        score = 60000
        if active:
            score += 1000
        return score

    # Attach energy
    if pokemon.id == Budew:
        return -1
    elif pokemon.id == Meowth_ex or pokemon.id == Fezandipiti_ex or pokemon.id == Latias_ex:
        if active and not can_switch and not my_asleep and not my_paralyzed:
            if bench_attacker or field_counts[Budew] >= 1:
                return 22000
            else:
                return 18000
        else:
            return -1
    if active and can_main_attack:
        return -1
    score = 20000
    if energy_count >= 2:
        if active and not can_switch and not my_asleep and not my_paralyzed:
            score += 200
        else:
            return -1
    elif energy_count == 1:
        if attach_id == pokemon.energyCards[0].id:
            return -1
        if pokemon.id == Dragapult_ex:
            score += 250
        elif pokemon.id == Dreepy:
            score -= 150
        else:
            score -= 200
        if active:
            score += 200
    else:  # energy_count == 0
        if active:
            if bench_attacker:
                score += 400
        else:
            if pokemon.id == Dragapult_ex:
                score += 150
            elif pokemon.id == Dreepy:
                score += 100
            else:
                score += 50
            if bench_attacker:
                score -= 200
    if no_more_dex and (pokemon.id == Dreepy or pokemon.id == Drakloak):
        score -= 500
    return score
```

**注意:** `can_main_attack`は関数内でグローバル変数のまま参照する（`attach_score()`の元の実装でも
モジュールレベルのグローバル変数`can_main_attack`をそのまま参照していたため、この点は今回の
引数化スコープ外。挙動は変えない）。

次に、元の呼び出し箇所4箇所（593, 595, 730, 826行目）を以下のように置き換える：

593-595行目、変更前:
```python
                    max_score = max(max_score, attach_score(id, pokemon, True))
                ...
                    max_score = max(max_score, attach_score(id, pokemon, False))
```
変更後:
```python
                    max_score = max(max_score, _attach_score(
                        id, pokemon, True,
                        card_table=card_table, can_switch=can_switch, bench_attacker=bench_attacker,
                        no_more_dex=no_more_dex, field_counts=field_counts,
                        my_asleep=my_state.asleep, my_paralyzed=my_state.paralyzed,
                    ))
                ...
                    max_score = max(max_score, _attach_score(
                        id, pokemon, False,
                        card_table=card_table, can_switch=can_switch, bench_attacker=bench_attacker,
                        no_more_dex=no_more_dex, field_counts=field_counts,
                        my_asleep=my_state.asleep, my_paralyzed=my_state.paralyzed,
                    ))
```

730行目、変更前:
```python
                    score = attach_score(context_card_id, card, o.area == AreaType.ACTIVE)
```
変更後:
```python
                    score = _attach_score(
                        context_card_id, card, o.area == AreaType.ACTIVE,
                        card_table=card_table, can_switch=can_switch, bench_attacker=bench_attacker,
                        no_more_dex=no_more_dex, field_counts=field_counts,
                        my_asleep=my_state.asleep, my_paralyzed=my_state.paralyzed,
                    )
```

826行目、変更前:
```python
            score = attach_score(card.id, pokemon, o.inPlayArea == AreaType.ACTIVE)
```
変更後:
```python
            score = _attach_score(
                card.id, pokemon, o.inPlayArea == AreaType.ACTIVE,
                card_table=card_table, can_switch=can_switch, bench_attacker=bench_attacker,
                no_more_dex=no_more_dex, field_counts=field_counts,
                my_asleep=my_state.asleep, my_paralyzed=my_state.paralyzed,
            )
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -k test_attach_score -v`
Expected: PASS

- [ ] **Step 5: リポジトリ全体の回帰確認（既存574件超が1件も壊れていないこと）**

Run: `uv run pytest -q`
Expected: 全件PASS（既存のdragapult関連テストが1件も壊れていないことが、
純粋リファクタリングであることの証拠になる）

- [ ] **Step 6: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "$(cat <<'EOF'
refactor(dragapult): attach_score()をクロージャから引数化した独立関数へ

ロジック変更なしの純粋リファクタリング。検証スクリプトから本番と
同じ関数を直接呼べるようにするための下準備。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: 検証スクリプト用のCardType CSVルックアップ

**Files:**
- Modify: `src/etl/gold.py`
- Test: `tests/test_etl_gold.py`

**Interfaces:**
- Produces: `load_tool_card_ids(csv_path: Path) -> frozenset[int]`（Task 5で使用）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_etl_gold.py`に追記：

```python
def test_load_tool_card_ids_returns_pokemon_tool_ids():
    from etl.gold import load_tool_card_ids

    tool_ids = load_tool_card_ids(CARD_DATA_PATH)
    assert 1159 in tool_ids  # Hero's Cape (Pokémon Tool、feedback_ace_spec_deck_ruleで既知)
    assert 1 not in tool_ids  # Basic {G} Energy はTool ではない
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_etl_gold.py -k test_load_tool_card_ids -v`
Expected: FAIL（`ImportError`）

- [ ] **Step 3: `load_tool_card_ids`を実装する**

`src/etl/gold.py`の`load_card_names`関数の直後に追記：

```python
def load_tool_card_ids(csv_path: Path) -> frozenset:
    """EN_Card_Data.csvから「Pokémon Tool」カテゴリのCard IDだけを集めたfrozensetを返す。

    cg.apiのCardType.TOOLと同じ意味だが、ネイティブライブラリ(cg.sim)を使わず
    CSVだけから判定できるようにする（macOSではall_card_data()が動かないため）。
    """
    type_column = "Stage (Pokémon)/Type (Energy and Trainer)"
    tool_ids = set()
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row[type_column] == "Pokémon Tool":
                tool_ids.add(int(row["Card ID"]))
    return frozenset(tool_ids)
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_etl_gold.py -k test_load_tool_card_ids -v`
Expected: PASS

- [ ] **Step 5: リポジトリ全体の回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add src/etl/gold.py tests/test_etl_gold.py
git commit -m "$(cat <<'EOF'
feat(etl): CSVからPokémon Tool判定用のCard ID集合を読み込む関数を追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: 検証スクリプトの実装

**Files:**
- Create: `scripts/analyze_dragapult_attach_scoring.py`
- Test: `tests/test_analyze_dragapult_attach_scoring.py`

**Interfaces:**
- Consumes: `GameStateTracker`, `load_tool_card_ids`, `build_event_timeline`, `find_player_index`, `load_raw_log`（`etl.gold`）／ `_attach_score`（`dragapult_agent.main`）
- Produces: `field_counts_from_tracker(tracker) -> dict[int, int]`, `is_bench_attacker(tracker, dragapult_ex_id) -> bool`, `evaluate_attach_event(tracker, event, *, card_table, dragapult_ex_id, dreepy_id, drakloak_id) -> dict`（矛盾判定結果を返す純粋関数）, `build_report(battle_log_paths, target_player_name, card_data_csv) -> str`

- [ ] **Step 1: 失敗するテストを書く（純粋関数部分）**

`tests/test_analyze_dragapult_attach_scoring.py`を新規作成：

```python
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cg.api import CardType

import dragapult_agent.main as dm
from etl.gold import GameStateTracker
from analyze_dragapult_attach_scoring import (
    evaluate_attach_event, field_counts_from_tracker, is_bench_attacker,
)

DRAGAPULT_EX = 121
DRAKLOAK = 120
DREEPY = 119
BASIC_FIRE_ENERGY = 2


@dataclass
class _MockCardData:
    cardId: int
    cardType: CardType = CardType.BASIC_ENERGY


@pytest.fixture
def mock_card_table():
    """evaluate_attach_event()にはcard_tableを明示引数で渡す設計のため、
    dm.card_table自体をmonkeypatchする必要はない"""
    return {BASIC_FIRE_ENERGY: _MockCardData(cardId=BASIC_FIRE_ENERGY)}


def _tracker_with_field(active_id, active_serial, bench):
    """bench: list[(card_id, serial, energy_count)]"""
    tracker = GameStateTracker(target_player_index=0)
    tracker.active_serial = active_serial
    tracker.species[active_serial] = active_id
    for card_id, serial, energy in bench:
        tracker.bench_serials.add(serial)
        tracker.species[serial] = card_id
        tracker.energy_count[serial] = energy
    return tracker


def test_field_counts_from_tracker_counts_active_and_bench():
    tracker = _tracker_with_field(DRAGAPULT_EX, 1, [(DREEPY, 2, 0), (DREEPY, 3, 0)])
    counts = field_counts_from_tracker(tracker)
    assert counts[DRAGAPULT_EX] == 1
    assert counts[DREEPY] == 2


def test_is_bench_attacker_true_when_bench_dragapult_ex_has_two_energy():
    tracker = _tracker_with_field(DREEPY, 1, [(DRAGAPULT_EX, 2, 2)])
    assert is_bench_attacker(tracker, DRAGAPULT_EX) is True


def test_is_bench_attacker_false_when_bench_dragapult_ex_has_one_energy():
    tracker = _tracker_with_field(DREEPY, 1, [(DRAGAPULT_EX, 2, 1)])
    assert is_bench_attacker(tracker, DRAGAPULT_EX) is False


def test_evaluate_attach_event_handles_candidate_with_one_energy(mock_card_table):
    """energy_count==1の候補が存在すると_attach_score()内部でpokemon.energyCards[0].idが
    参照される。tracker.energy_cardsを正しく引き継いでいないとAttributeErrorで
    クラッシュする(energy_countをintのみで持つ設計の初期案で実際に踏んだ不具合)"""
    tracker = GameStateTracker(target_player_index=0)
    tracker.active_serial = 1
    tracker.species[1] = DREEPY
    tracker.energy_count[1] = 1
    tracker.energy_cards[1] = [BASIC_FIRE_ENERGY]
    tracker.bench_serials.add(2)
    tracker.species[2] = DREEPY

    event = {
        "type": 11, "playerIndex": 0, "cardId": BASIC_FIRE_ENERGY,
        "serial": 99, "cardIdTarget": DREEPY, "serialTarget": 2,
    }
    result = evaluate_attach_event(tracker, event, card_table=mock_card_table, dragapult_ex_id=DRAGAPULT_EX)
    assert "contradiction" in result


def test_evaluate_attach_event_treats_ready_active_dragapult_as_unable_to_receive_more_energy(mock_card_table):
    """アクティブが既にドラパルトexで2エネ以上(=ファントムダイブ発動可能)なら、
    dm.can_main_attackをここで再計算してTrueにしないと、_attach_score()の
    'if active and can_main_attack: return -1' が発火せず、本来除外されるべき
    アクティブ候補に正のスコアがついて誤って矛盾判定されてしまう"""
    tracker = GameStateTracker(target_player_index=0)
    tracker.active_serial = 1
    tracker.species[1] = DRAGAPULT_EX
    tracker.energy_count[1] = 2
    tracker.bench_serials.add(2)
    tracker.species[2] = DREEPY

    event = {
        "type": 11, "playerIndex": 0, "cardId": BASIC_FIRE_ENERGY,
        "serial": 99, "cardIdTarget": DREEPY, "serialTarget": 2,
    }
    evaluate_attach_event(tracker, event, card_table=mock_card_table, dragapult_ex_id=DRAGAPULT_EX)
    assert dm.can_main_attack is True
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_analyze_dragapult_attach_scoring.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'analyze_dragapult_attach_scoring'`）

- [ ] **Step 3: スクリプトの本体を実装する**

`scripts/analyze_dragapult_attach_scoring.py`を新規作成：

```python
"""ドラパルトex `_attach_score()` ベンチ配分の再検証CLI

前回(2026-07-22)の分析はステップ単位のスナップショットで「今どちらがアクティブか」を
判定しており、1ステップに複数ターン分のイベントが混在しうる問題とSWITCHのフィールド名の
意味の取り違えにより結果が汚染された。本スクリプトはGameStateTrackerでイベントを
1件ずつ再生し、本番と同じ_attach_score()を使って矛盾件数を数え直す。

使い方: uv run python scripts/analyze_dragapult_attach_scoring.py \
    --target-player Kagura_UT data/battle_logs/8720*.json data/battle_logs/8721*.json
"""
import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "data" / "competition" / "sample_submission"))

from unittest.mock import MagicMock  # noqa: E402

sys.modules.setdefault("cg.sim", MagicMock())
sys.modules.setdefault("cg.game", MagicMock())

from cg.api import Card, CardType  # noqa: E402

import dragapult_agent.main as dm  # noqa: E402
from etl.gold import (  # noqa: E402
    GameStateTracker, LOG_TYPE_ATTACH, build_event_timeline,
    find_player_index, load_raw_log, load_tool_card_ids,
)

CARD_DATA_CSV = ROOT / "data" / "competition" / "EN_Card_Data.csv"


def field_counts_from_tracker(tracker: GameStateTracker) -> dict:
    counts = {}
    for card_id in tracker.species.values():
        counts[card_id] = counts.get(card_id, 0) + 1
    return counts


def is_bench_attacker(tracker: GameStateTracker, dragapult_ex_id: int) -> bool:
    for serial in tracker.bench_serials:
        if tracker.species.get(serial) == dragapult_ex_id and tracker.energy_count[serial] >= 2:
            return True
    return False


def _own_candidates(tracker: GameStateTracker) -> list:
    """(serial, is_active)のリストを返す。アクティブ + ベンチ全員が候補"""
    candidates = []
    if tracker.active_serial is not None:
        candidates.append((tracker.active_serial, True))
    for serial in tracker.bench_serials:
        candidates.append((serial, False))
    return candidates


def evaluate_attach_event(tracker: GameStateTracker, event: dict, *, card_table: dict,
                           dragapult_ex_id: int) -> dict:
    """ATTACHイベント時点(適用前)の状態で、実際に選ばれた対象より高スコアの候補が
    存在するかを判定する。can_switchはTrue/False両方で試し、結果が割れる場合は
    'needs_manual_review'をTrueにする。

    dm.can_main_attackはagent()内部でしか更新されないモジュールグローバルなので、
    このスクリプトではagent()を一度も呼ばないため常にFalseのまま(呼び出し忘れではなく
    未設定のまま放置すると、既にファントムダイブが撃てる状態のアクティブを"まだ攻撃不可"と
    誤認し、本来正しいベンチ配分を誤って矛盾と判定してしまう)。そのためtracker状態から
    ここで明示的に再計算して都度セットする。閾値2は`bench_attacker`判定
    (main.py:398 `len(card.energies) >= 2`)と同じ、ファントムダイブの必要エネルギー数。
    """
    target_serial = event["serialTarget"]
    field_counts = field_counts_from_tracker(tracker)
    bench_attacker = is_bench_attacker(tracker, dragapult_ex_id)
    no_more_dex = field_counts.get(dragapult_ex_id, 0) * 2 >= tracker.opponent_prize_remaining
    dm.can_main_attack = (
        tracker.species.get(tracker.active_serial) == dragapult_ex_id
        and tracker.energy_count[tracker.active_serial] >= 2
    )

    class _Pokemon:
        def __init__(self, id, energies, energy_cards):
            self.id = id
            self.energies = energies
            self.energyCards = energy_cards

    def score_for(serial: int, is_active: bool, can_switch: bool) -> int:
        species_id = tracker.species[serial]
        energy_n = tracker.energy_count[serial]
        # pokemon.energyCards[0].idはenergy_count==1分岐で参照されるため、
        # tracker.energy_cards(装着済みエネルギーのcard_id列)から実際のCardを組み立てる。
        # energiesはlen()しか使われないためダミー値で十分
        energy_card_objs = [Card(id=cid, serial=0, playerIndex=0) for cid in tracker.energy_cards[serial]]
        pokemon = _Pokemon(species_id, [0] * energy_n, energy_card_objs)
        return dm._attach_score(
            event["cardId"], pokemon, is_active,
            card_table=card_table, can_switch=can_switch, bench_attacker=bench_attacker,
            no_more_dex=no_more_dex, field_counts=field_counts,
            my_asleep=tracker.asleep, my_paralyzed=tracker.paralyzed,
        )

    results = {}
    for can_switch in (True, False):
        candidates = _own_candidates(tracker)
        scores = {serial: score_for(serial, is_active, can_switch) for serial, is_active in candidates}
        chosen_score = scores[target_serial]
        better = [s for s, sc in scores.items() if sc > chosen_score]
        results[can_switch] = bool(better)

    contradiction_true = results[True]
    contradiction_false = results[False]
    return {
        "contradiction": contradiction_true or contradiction_false,
        "needs_manual_review": contradiction_true != contradiction_false,
    }


class _CardTypeEntry:
    """_attach_score()が参照するのは`.cardType`属性1つだけなので、
    CardData全体を組み立てず最小限のダミーで代用する"""
    def __init__(self, card_type):
        self.cardType = card_type


def _build_local_card_table(tool_card_ids: frozenset) -> dict:
    """全カードIDに対応する必要はなく、_attach_score()内の
    `card_table[attach_id].cardType == CardType.TOOL`という等価比較さえ
    再現できればよいため、Tool判定さえ分かればBASIC_ENERGY扱いで十分。

    dm._build_card_table()は実機(Kaggle)専用のネイティブライブラリ(cg.sim)を
    呼び出すため、macOS上のこのスクリプトからは使えない(呼ぶとクラッシュする)。
    """
    return collections.defaultdict(
        lambda: _CardTypeEntry(CardType.BASIC_ENERGY),
        {cid: _CardTypeEntry(CardType.TOOL) for cid in tool_card_ids},
    )


def build_report(battle_log_paths: list, target_player_name: str) -> str:
    tool_card_ids = load_tool_card_ids(CARD_DATA_CSV)
    local_card_table = _build_local_card_table(tool_card_ids)
    contradictions = []
    manual_review = []
    total_bench_attach = 0

    for log_path in battle_log_paths:
        data = load_raw_log(log_path)
        target_index = find_player_index(data, target_player_name)
        tracker = GameStateTracker(target_player_index=target_index, tool_card_ids=tool_card_ids)
        timeline = build_event_timeline(data, player_index=0)
        for step_index, event in timeline:
            if (event.get("type") == LOG_TYPE_ATTACH
                    and event.get("playerIndex") == target_index
                    and event.get("cardId") not in tool_card_ids
                    and event.get("serialTarget") != tracker.active_serial):
                total_bench_attach += 1
                verdict = evaluate_attach_event(
                    tracker, event, card_table=local_card_table, dragapult_ex_id=dm.Dragapult_ex,
                )
                if verdict["needs_manual_review"]:
                    manual_review.append((log_path.stem, step_index))
                elif verdict["contradiction"]:
                    contradictions.append((log_path.stem, step_index))
            tracker.apply(event)

    lines = [
        "# ドラパルトex ベンチ向けエネルギー装着 再検証レポート",
        "",
        f"検証対象試合数: {len(battle_log_paths)}",
        f"ベンチ向けATTACHイベント総数: {total_bench_attach}",
        f"矛盾件数: {len(contradictions)}",
        f"要目視確認件数(can_switchの値次第で判定が割れる): {len(manual_review)}",
        "",
        "## 矛盾事例",
    ]
    for episode_id, step_index in contradictions:
        lines.append(f"- 試合{episode_id} step={step_index}")
    lines.append("")
    lines.append("## 要目視確認事例")
    for episode_id, step_index in manual_review:
        lines.append(f"- 試合{episode_id} step={step_index}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("battle_logs", nargs="+", type=Path)
    parser.add_argument("--target-player", required=True)
    args = parser.parse_args()
    print(build_report(args.battle_logs, args.target_player))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_analyze_dragapult_attach_scoring.py -v`
Expected: PASS

- [ ] **Step 5: リポジトリ全体の回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 6: コミット**

```bash
git add scripts/analyze_dragapult_attach_scoring.py tests/test_analyze_dragapult_attach_scoring.py
git commit -m "$(cat <<'EOF'
feat(dragapult): attach_score再検証CLIスクリプトを追加

GameStateTrackerと本番のattach_score()を直接使い、ベンチ向け
エネルギー装着イベントの矛盾件数を集計する。can_switchが
ログから完全には復元できないため、True/False両方で判定し
結果が割れる場合は要目視確認として分けて記録する。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: 20戦分の本実行とレポート作成・ユーザー報告

**Files:**
- Create: `docs/analyses/20260722-dragapult-attach-scoring-verified.md`

- [ ] **Step 1: スクリプトを20戦分のログに対して実行する**

Run:
```bash
uv run python scripts/analyze_dragapult_attach_scoring.py \
  --target-player Kagura_UT \
  data/battle_logs/87204277.json data/battle_logs/87204845.json data/battle_logs/87205390.json \
  data/battle_logs/87205929.json data/battle_logs/87206482.json data/battle_logs/87207033.json \
  data/battle_logs/87207578.json data/battle_logs/87208132.json data/battle_logs/87208679.json \
  data/battle_logs/87209220.json data/battle_logs/87209770.json data/battle_logs/87210329.json \
  data/battle_logs/87210886.json data/battle_logs/87211430.json data/battle_logs/87211992.json \
  data/battle_logs/87212533.json data/battle_logs/87213077.json data/battle_logs/87213619.json \
  data/battle_logs/87214153.json data/battle_logs/87214695.json
```

**注記:** `--target-player`の値は実際のログ内`info.Agents`のプレイヤー名と一致させる必要がある。
`docs/superpowers/plans/2026-07-22-dragapult-energy-attach-debug-plan.md`および過去の分析では
「Kagura_UT」で解析していたため同じ値を使うが、実行前に
`python3 -c "import json; print(json.load(open('data/battle_logs/87204277.json'))['info']['Agents'])"`
で実際のプレイヤー名を確認し、異なっていれば正しい名前に差し替える。

- [ ] **Step 2: 出力内容をレポートファイルへ保存する**

Step1の標準出力をそのまま`docs/analyses/20260722-dragapult-attach-scoring-verified.md`へ保存する。
ファイル冒頭に以下の前置きを追記する：

```markdown
**このファイルの位置付け：** 2026-07-22に一度「65件中4件が矛盾」と分析したが、
分析手法自体に致命的なバグ2つ（ステップ内の複数ターン混在／SWITCHのフィールド名の
意味の取り違え）が発覚し全て汚染された（詳細は
`docs/superpowers/plans/2026-07-22-dragapult-energy-attach-debug-plan.md`参照）。
本ファイルは`GameStateTracker`によるイベント再生方式で正しく再検証した結果であり、
前回の`docs/analyses/20260722-dragapult-attach-and-unfair-stamp-review.md`の
ベンチ配分部分を置き換えるものである。

---

```

- [ ] **Step 3: 矛盾事例があれば個別に目視確認する**

矛盾件数が1件以上の場合、各事例について`data/battle_logs/<episode_id>.json`の該当stepを
`python3`で直接読み、`_attach_score()`の計算結果と実際の選択が食い違う理由を特定する
（ATTACH_FROMの候補列挙自体に見落としがある可能性、または真のバグの可能性の両方を検討する）。
特定した内容をレポートファイルの「## 矛盾事例」セクションに追記する。

- [ ] **Step 4: ユーザーへ結果を報告し、次の分岐を確認する**

以下を提示してユーザーに確認する：
- 矛盾件数・要目視確認件数
- 矛盾ゼロの場合：「設計通りと確認できたが、他に確認したい点はあるか」
- 矛盾ありの場合：矛盾事例の内容を提示し、修正に進んでよいか（`superpowers:systematic-debugging`
  → `superpowers:test-driven-development`で単一の仮説から最小修正 → 回帰確認 →
  `scripts/build_dragapult_submission_notebook.py`でnotebook再生成 → 実装サマリー保存、
  という後続フローに進む）

- [ ] **Step 5: コミット**

```bash
git add docs/analyses/20260722-dragapult-attach-scoring-verified.md
git commit -m "$(cat <<'EOF'
docs(dragapult): attach_score再検証結果（20戦・GameStateTracker方式）を追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## 本計画のスコープ外（Task 6完了後にユーザー判断で着手）

矛盾が実際に見つかった場合の「仮説→最小修正→TDD→Kaggle再提出」は、矛盾の具体的な内容が
判明するまで正しい修正内容を書けないため、本計画には含めない。Task 6完了後、ユーザーに
結果を報告し、修正が必要と判断された場合は別途その場で仮説とテストケースを立てて対応する。
