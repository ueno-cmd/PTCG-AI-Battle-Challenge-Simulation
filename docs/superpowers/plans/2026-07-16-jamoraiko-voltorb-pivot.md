# ジャモライコ ビリリダマ軸ピボット Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ジャモライコデッキからタケルライコex・基本闘エネルギーを完全に抜き、ナンジャモのビリリダマ（チェインボルト）を主軸にしたデッキへピボットし、それに伴い死んだコードとなる「タケルライコex専用ロジック」を削除、「エネルギーつけかえ」の運用目的をハラバリーex/タイカイデンへのエネルギー集中に作り直す。

**Architecture:** 単一ファイル `src/jamoraiko_agent/main.py` に対する段階的リファクタ。①攻撃プラン計算まわり（FieldState/Attacker/ATTACKERSテーブル/POKEMON_LINES/calc_attack_plan）→②EnergyPolicyクラスの作り直し→③残存する闘エネルギー分岐・定数の最終削除、の3段階に分け、各段階の終わりに必ず `uv run pytest -q` で全PASSを確認する。デッキ定義ファイル `decks/jamoraiko_20260713.py` の変更は独立した最初のタスクとして先行させる。

**Tech Stack:** Python 3.12 / uv / pytest / dataclasses

## Global Constraints

- 各タスク終了時、`uv run pytest -q` でリポジトリ全体が全PASSであること（途中経過で壊れたままにしない）
- コードコメント・docstringは日本語で書く（既存方針）
- ワークスペース分離は git worktree ではなく通常のfeatureブランチを使う（[[feedback_no_worktree_preference]]）
- 設計書 `docs/superpowers/specs/2026-07-16-jamoraiko-voltorb-pivot-design.md` の内容と矛盾しないこと

---

### Task 1: デッキ変更（タケルライコex撤去・ビリリダマ増量）

**Files:**
- Modify: `decks/jamoraiko_20260713.py`
- Modify: `tests/test_jamoraiko_deck.py`
- Modify: `tests/test_jamoraiko_agent.py:15-20`（`TestAgentDeckSelection`）

**Interfaces:**
- Consumes: なし（このタスクは独立して着手できる）
- Produces: `decks.jamoraiko_20260713.DECK`（タケルライコex/基本闘エネルギー0枚、ビリリダマ3枚、基本雷エネルギー15枚）。Task 2以降はこのDECKの内容を前提にしない（`main.py`のロジック変更はDECKの定数と直接連動しないため）

- [ ] **Step 1: デッキ定義を変更する**

`decks/jamoraiko_20260713.py` の内容を以下に置き換える。

```python
# ジャモライコデッキ定義（さくさくさん7/9ジムバトル優勝レシピを移植）
# ナンジャモ系ポケモン（雷）+ ビリリダマのチェインボルトを主軸にした構成
# （2026-07-16改修：タケルライコex・基本闘エネルギーへの依存を解消し、
#  ビリリダマのチェインボルトに軸足を移した）

DECK = [
    (268, 3),    # ナンジャモのズピカ (Iono's Tadbulb)
    (269, 3),    # ナンジャモのハラバリーex (Iono's Bellibolt ex)
    (270, 3),    # ナンジャモのカイデン (Iono's Wattrel)
    (271, 3),    # ナンジャモのタイカイデン (Iono's Kilowattrel)
    (265, 3),    # ナンジャモのビリリダマ (Iono's Voltorb)
    (1121, 4),   # ハイパーボール (Ultra Ball)
    (1086, 4),   # なかよしポフィン (Buddy-Buddy Poffin)
    (1118, 2),   # エネルギー回収 (Energy Retrieval)
    (1097, 3),   # 夜のタンカ (Night Stretcher)
    (1116, 2),   # エネルギーつけかえ (Energy Switch)
    (1123, 2),   # ポケモンいれかえ (Switch)
    (1110, 1),   # つりざおMAX (Max Rod, ACE SPEC)
    (1227, 3),   # リーリエの決心 (Lillie's Determination)
    (1233, 4),   # カナリィ (Canari)
    (1182, 2),   # ボスの指令 (Boss's Orders)
    (1254, 3),   # ハッコウシティ (Levincia)
    (4, 15),     # 基本{雷}エネルギー
]
```

- [ ] **Step 2: デッキテストを更新する**

`tests/test_jamoraiko_deck.py` の内容を以下に置き換える。

```python
from decks.jamoraiko_20260713 import DECK

ENERGY_IDS = {4}  # Basic {L} Energy
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
    assert counts[268] == 3    # ズピカ
    assert counts[269] == 3    # ハラバリーex
    assert counts[270] == 3    # カイデン
    assert counts[271] == 3    # タイカイデン
    assert counts[265] == 3    # ビリリダマ
    assert 63 not in counts    # タケルライコexは不採用


def test_trainer_counts():
    counts = dict(DECK)
    assert counts[1121] == 4   # ハイパーボール
    assert counts[1086] == 4   # なかよしポフィン
    assert counts[1118] == 2   # エネルギー回収
    assert counts[1097] == 3   # 夜のタンカ
    assert counts[1116] == 2   # エネルギーつけかえ
    assert counts[1123] == 2   # ポケモンいれかえ
    assert counts[1110] == 1   # つりざおMAX
    assert counts[1227] == 3   # リーリエの決心
    assert counts[1233] == 4   # カナリィ
    assert counts[1182] == 2   # ボスの指令
    assert counts[1254] == 3   # ハッコウシティ


def test_energy_counts():
    counts = dict(DECK)
    assert counts[4] == 15  # 基本雷エネルギー
    assert 6 not in counts  # 基本闘エネルギーは不採用
```

- [ ] **Step 3: `TestAgentDeckSelection`のデッキ先頭カード期待値を更新する**

`tests/test_jamoraiko_agent.py:15-20` を以下に置き換える（DECKの先頭がタケルライコex(63)からズピカ(268)に変わるため）。

```python
class TestAgentDeckSelection:
    def test_agent_returns_deck_when_select_is_none(self):
        obs_dict = {"select": None, "logs": [], "current": None, "search_begin_input": None}
        result = jm.agent(obs_dict)
        assert len(result) == 60
        assert result[0] == 268  # ナンジャモのズピカ が先頭
```

- [ ] **Step 4: テスト実行**

```bash
uv run pytest tests/test_jamoraiko_deck.py tests/test_jamoraiko_agent.py -v
```

Expected: `test_jamoraiko_deck.py` の全テストPASS。`test_jamoraiko_agent.py`は現時点で他の箇所（タケルライコex関連ロジック）がまだ残っているため、Task 1が触れていないテスト（`TestCollectFieldState`等）はそのままPASSし続けることを確認する。`TestAgentDeckSelection::test_agent_returns_deck_when_select_is_none`はPASSすること。

- [ ] **Step 5: コミット**

```bash
git add decks/jamoraiko_20260713.py tests/test_jamoraiko_deck.py tests/test_jamoraiko_agent.py
git commit -m "feat: ジャモライコデッキからタケルライコex・基本闘エネルギーを撤去しビリリダマを増量"
```

---

### Task 2: 攻撃ロジック簡略化（タケルライコex撤去に伴う死んだコードの削除）

**Files:**
- Modify: `src/jamoraiko_agent/main.py`
- Modify: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: Task 1で変更済みの `decks/jamoraiko_20260713.py`（このタスクでは直接参照しないが、`_load_deck`のフォールバック先として存在する）
- Produces: `FieldState`（`own_board_basic_energy_total`/`active_fighting_energy_count`フィールドなし）、`Attacker`（`is_utility`/`requires_fighting`フィールドなし）、簡略化された`ATTACKERS`/`POKEMON_LINES`/`calc_attack_plan`/`_is_attack_ready(card_id, energy_count)`（`fighting_count`引数なし）。Task 3・Task 4はこれらのシグネチャを前提にする

- [ ] **Step 1: `FieldState`から闘エネルギー関連フィールドを削除する**

`src/jamoraiko_agent/main.py`の`FieldState`定義（58-68行目付近）を以下に置き換える。

```python
@dataclass
class FieldState:
    field_counts: defaultdict
    hand_counts: defaultdict
    discard_counts: defaultdict
    iono_lightning_on_board: int
    active_energy_count: int
    hand_has_basic_lightning_energy: bool = False
```

- [ ] **Step 2: `_collect_field_state`を更新する**

同ファイルの`_collect_field_state`関数（71-117行目付近）を以下に置き換える。

```python
def _collect_field_state(my_state) -> FieldState:
    """バトル場・ベンチ・手札・捨て山のカード枚数と、
    チェインボルトのダメージ計算に必要な雷エネルギー集計を返す。"""
    field_counts   = defaultdict(int)
    hand_counts    = defaultdict(int)
    discard_counts = defaultdict(int)
    iono_lightning_on_board = 0
    active_energy_count = 0

    active = my_state.active[0] if my_state.active else None

    for card in my_state.active + my_state.bench:
        if card is None:
            continue
        field_counts[card.id] += 1
        lightning = card.energies.count(EnergyType.LIGHTNING)
        if card.id in IONO_POKEMON_IDS:
            iono_lightning_on_board += lightning

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
        active_energy_count=active_energy_count,
        hand_has_basic_lightning_energy=hand_counts[Basic_Lightning_Energy] > 0,
    )
```

- [ ] **Step 3: `Attacker`から`is_utility`/`requires_fighting`を削除し、`ATTACKERS`テーブルからタケルライコexの2技を削除する**

`Attacker`データクラス（121-129行目付近）を以下に置き換える。

```python
@dataclass(frozen=True)
class Attacker:
    id: int
    attack_name: str
    energy_required: int
    damage_fn: Callable[[FieldState], int]
    locks_next_turn: bool = False
```

`ATTACKERS`テーブル（132-143行目付近）を以下に置き換える。

```python
ATTACKERS: list[Attacker] = [
    Attacker(id=Iono_Voltorb, attack_name="Voltaic Chain", energy_required=2,
             damage_fn=lambda fs: 20 + 20 * fs.iono_lightning_on_board),
    Attacker(id=Iono_Bellibolt_ex, attack_name="Thunderous Bolt", energy_required=4,
             damage_fn=lambda fs: 230, locks_next_turn=True),
    Attacker(id=Iono_Kilowattrel, attack_name="Mach Bolt", energy_required=3,
             damage_fn=lambda fs: 70),
]
```

- [ ] **Step 4: `POKEMON_LINES`からタケルライコexを削除し、ビリリダマの`max_field_copies`を3に変更する**

`POKEMON_LINES`（155-162行目付近）を以下に置き換える。

```python
POKEMON_LINES: dict[int, PokemonLine] = {
    Iono_Voltorb:      PokemonLine(id=Iono_Voltorb, max_field_copies=3, setup_active_priority=300),
    Iono_Tadbulb:      PokemonLine(id=Iono_Tadbulb, max_field_copies=1, setup_active_priority=50),
    Iono_Bellibolt_ex: PokemonLine(id=Iono_Bellibolt_ex, pre_evo_id=Iono_Tadbulb, max_field_copies=1),
    Iono_Wattrel:      PokemonLine(id=Iono_Wattrel, max_field_copies=1, setup_active_priority=50),
    Iono_Kilowattrel:  PokemonLine(id=Iono_Kilowattrel, pre_evo_id=Iono_Wattrel, max_field_copies=1),
}
```

- [ ] **Step 5: `calc_attack_plan`を簡略化する**

`calc_attack_plan`関数（174-226行目付近）を以下に置き換える。

```python
def calc_attack_plan(my_active: "Pokemon | None", op_active_hp: int,
                      fs: FieldState, my_state) -> AttackPlan:
    """アクティブなポケモンについて、テーブル上の候補技から最適な1つを選ぶ。

    優先順位：
    1. 確定KOできる技があれば最優先
    2. 確定KOがなければ最大ダメージを選ぶが、次ターン技封じの技は減点評価
    """
    if my_active is None:
        return AttackPlan()

    candidates = []
    for atk in ATTACKERS:
        if atk.id != my_active.id:
            continue
        if fs.active_energy_count < atk.energy_required:
            continue
        damage = atk.damage_fn(fs)
        is_lethal = damage >= op_active_hp
        candidates.append((atk, damage, is_lethal))

    if not candidates:
        return AttackPlan()

    lethal = [c for c in candidates if c[2]]
    if lethal:
        # 現在のATTACKERSテーブルでは同一ポケモンが複数の技エントリを持つことはないため、
        # 複数のlethal候補から選別するロジックは不要。先頭を採用すれば十分
        chosen = lethal[0]
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

- [ ] **Step 6: `_is_attack_ready`と`_score_switch_target`から`fighting_count`を削除する**

`_is_attack_ready`関数（510-520行目付近）を以下に置き換える。

```python
def _is_attack_ready(card_id: int, energy_count: int) -> bool:
    """このポケモンが今すぐ攻撃可能な技を持つか（ATTACKERSテーブルの再利用）"""
    for atk in ATTACKERS:
        if atk.id != card_id:
            continue
        if energy_count < atk.energy_required:
            continue
        return True
    return False
```

`_score_switch_target`関数（523-542行目付近）を以下に置き換える。

```python
def _score_switch_target(card, o, my_index: int, plan: AttackPlan) -> int:
    """OptionType.CARD / SelectContext.SWITCH・TO_ACTIVE のスコアを返す"""
    if not isinstance(card, Pokemon):
        # 当該コンテキストは仕様上Pokemonしか提示されないが、
        # 想定外のCard型が来た場合にcard.hp/card.energies参照でAttributeError落ちしないための防御
        # （grimmsnarl_agentのisinstanceガードと同じスタイル）
        return 0
    if o.playerIndex != my_index:
        # ボスの指令：現在の攻撃プラン(plan.damage)で確定KOできるベンチを最優先、次に低HP
        score = -card.hp
        if plan.attacker_id != -1 and plan.damage >= card.hp:
            score += 100000
        return score
    # 自分の交代先／強制昇格先
    energy_count = len(card.energies)
    score = energy_count * 10
    if _is_attack_ready(card.id, energy_count):
        score += 5000
    return score
```

- [ ] **Step 7: `_score_search_candidate`から闘エネルギー分岐を削除する（`FieldState`のフィールド削除に伴う必須修正）**

`_score_search_candidate`関数（545-564行目付近）を以下に置き換える。

```python
def _score_search_candidate(card_id: int, fs: FieldState) -> int:
    """OptionType.CARD / SelectContext.TO_HAND・TO_BENCH のスコアを返す"""
    line = POKEMON_LINES.get(card_id)
    if line is not None:
        owned = fs.field_counts[card_id] + fs.hand_counts[card_id]
        if owned >= line.max_field_copies:
            return -1000  # もう十分
        score = 300
        if line.pre_evo_id is not None and fs.field_counts[line.pre_evo_id] == 0:
            score -= 200  # 進化前が場にいないなら優先度を下げる
        return score
    if card_id == Basic_Lightning_Energy:
        return 150
    return 0
```

（`Basic_Fighting_Energy`分岐はここでは削除するが、定数`Basic_Fighting_Energy`自体はTask 4で他の参照箇所と一緒に削除する）

- [ ] **Step 8: テストファイルを更新する（`_fs`ヘルパー・関連テストの一括修正）**

`tests/test_jamoraiko_agent.py`に対し、以下の箇所をそれぞれ置き換える。

(a) `mock_attack_table`フィクスチャ（76-86行目付近）からタケルライコexの技を削除：

```python
@pytest.fixture(autouse=True)
def mock_attack_table(monkeypatch):
    table = {
        1001: MockAttack(attackId=1001, name="Voltaic Chain"),
        1002: MockAttack(attackId=1002, name="Thunderous Bolt"),
        1003: MockAttack(attackId=1003, name="Mach Bolt"),
    }
    monkeypatch.setattr(jm, "attack_table", table)
    return table
```

(b) `TestCollectFieldState`（23-63行目付近）から`test_own_board_basic_energy_total_counts_lightning_and_fighting`を削除する（他の5テストはそのまま残す）：

```python
class TestCollectFieldState:
    def test_iono_lightning_on_board_counts_only_iono_pokemon(self):
        voltorb = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])       # 雷2
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4])  # 雷3
        non_iono = make_pokemon(id=999, energies=[4, 4, 4, 4])            # 対象外のはずが混入しないことを確認
        my_state = make_player_state(active_pokemon=voltorb, bench=[bellibolt, non_iono])
        fs = jm._collect_field_state(my_state)
        assert fs.iono_lightning_on_board == 5

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

    def test_hand_has_basic_lightning_energy_true_when_present(self):
        energy_card = make_pokemon(id=jm.Basic_Lightning_Energy)
        my_state = make_player_state(hand=[energy_card])
        fs = jm._collect_field_state(my_state)
        assert fs.hand_has_basic_lightning_energy is True

    def test_hand_has_basic_lightning_energy_false_when_absent(self):
        canari = make_pokemon(id=jm.Canari)
        my_state = make_player_state(hand=[canari])
        fs = jm._collect_field_state(my_state)
        assert fs.hand_has_basic_lightning_energy is False
```

(c) `TestCalcAttackPlan`（124行目付近〜）を以下に置き換える（`_fs`ヘルパー修正＋タケルライコex関連6テスト削除、4テストのみ残す）：

```python
class TestCalcAttackPlan:
    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            active_energy_count=0,
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

    def test_thunderous_bolt_penalised_when_not_lethal(self):
        """確定KOでない場合、次ターン技封じのサンダーボルトより他技を優先する"""
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])
        fs = self._fs(active_energy_count=4, iono_lightning_on_board=4)
        my_state = make_player_state(active_pokemon=bellibolt, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(bellibolt, op_active_hp=9999, fs=fs, my_state=my_state)
        # サンダーボルト(230)一択のはずだが、ペナルティが付いていても他に選択肢がないので選ばれる
        assert plan.attacker_id == jm.Iono_Bellibolt_ex

    def test_no_active_pokemon_returns_empty_plan(self):
        fs = self._fs()
        my_state = make_player_state(active_pokemon=None, deck_count=40, prize_count=6)
        plan = jm.calc_attack_plan(None, op_active_hp=100, fs=fs, my_state=my_state)
        assert plan.attacker_id == -1
```

(d) `TestDeckSafety`（371行目付近〜）から`test_burst_roar_blocked_when_deck_thin`を削除し、`_fs`ヘルパーを修正：

```python
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

    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            active_energy_count=0,
        )
        base.update(overrides)
        return jm.FieldState(**base)
```

(e) `TestAgentEndToEnd.test_agent_selects_card_option_for_setup_active_pokemon`（557行目付近）内の`hand`定義を以下に置き換える（タケルライコexを削除済みのため、比較対象をズピカに差し替え）：

```python
        hand = [
            Card(id=jm.Iono_Tadbulb, serial=1, playerIndex=0),  # ズピカ：50点（低スコア）
            Card(id=jm.Iono_Voltorb, serial=2, playerIndex=0),  # ビリリダマ：300点（高スコア、期待される選択肢）
        ]
```

(f) `TestScoreSetupActive`（590行目付近）を以下に置き換える：

```python
class TestScoreSetupActive:
    def test_voltorb_outranks_tadbulb(self):
        assert jm._score_setup_active(jm.Iono_Voltorb) > jm._score_setup_active(jm.Iono_Tadbulb)

    def test_unknown_card_defaults_to_zero(self):
        assert jm._score_setup_active(999999) == 0
```

(g) `TestIsAttackReady`（601行目付近）を以下に置き換える：

```python
class TestIsAttackReady:
    def test_voltorb_ready_with_2_energy(self):
        assert jm._is_attack_ready(jm.Iono_Voltorb, energy_count=2) is True

    def test_voltorb_not_ready_with_1_energy(self):
        assert jm._is_attack_ready(jm.Iono_Voltorb, energy_count=1) is False

    def test_bellibolt_ex_ready_with_4_energy(self):
        assert jm._is_attack_ready(jm.Iono_Bellibolt_ex, energy_count=4) is True

    def test_bellibolt_ex_not_ready_with_3_energy(self):
        assert jm._is_attack_ready(jm.Iono_Bellibolt_ex, energy_count=3) is False

    def test_unknown_card_is_never_ready(self):
        assert jm._is_attack_ready(999999, energy_count=10) is False
```

(h) `TestScoreSearchCandidate`（667行目付近）を以下に置き換える（`_fs`ヘルパー修正・上限3枚への更新・闘エネルギー分岐テスト削除）：

```python
class TestScoreSearchCandidate:
    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            active_energy_count=0,
        )
        base.update(overrides)
        return jm.FieldState(**base)

    def test_pokemon_below_cap_scores_positive(self):
        fs = self._fs()
        assert jm._score_search_candidate(jm.Iono_Voltorb, fs) > 0

    def test_pokemon_at_cap_is_deprioritised(self):
        fs = self._fs(field_counts=defaultdict(int, {jm.Iono_Voltorb: 3}))
        assert jm._score_search_candidate(jm.Iono_Voltorb, fs) < 0

    def test_evolution_deprioritised_when_pre_evo_absent(self):
        fs_no_pre_evo = self._fs()
        fs_with_pre_evo = self._fs(field_counts=defaultdict(int, {jm.Iono_Tadbulb: 1}))
        score_absent = jm._score_search_candidate(jm.Iono_Bellibolt_ex, fs_no_pre_evo)
        score_present = jm._score_search_candidate(jm.Iono_Bellibolt_ex, fs_with_pre_evo)
        assert score_present > score_absent

    def test_lightning_energy_has_base_priority(self):
        fs = self._fs()
        assert jm._score_search_candidate(jm.Basic_Lightning_Energy, fs) == 150

    def test_unknown_card_defaults_to_zero(self):
        fs = self._fs()
        assert jm._score_search_candidate(999999, fs) == 0
```

(i) `TestScoreDiscardCandidate`の`_fs`ヘルパーと`test_surplus_pokemon_is_safe_to_discard`（712行目付近）を以下に置き換える（このタスクではビリリダマの上限が3枚に変わったことへの対応のみ行い、`Basic_Fighting_Energy`関連テストはTask 4まで残す）：

```python
class TestScoreDiscardCandidate:
    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            active_energy_count=0,
        )
        base.update(overrides)
        return jm.FieldState(**base)

    def test_surplus_pokemon_is_safe_to_discard(self):
        fs = self._fs(hand_counts=defaultdict(int, {jm.Iono_Voltorb: 4}))  # 上限3を超過
        assert jm._score_discard_candidate(jm.Iono_Voltorb, fs) > 0

    def test_needed_pokemon_is_protected(self):
        fs = self._fs()
        assert jm._score_discard_candidate(jm.Iono_Voltorb, fs) < 0

    def test_key_supporter_is_protected(self):
        fs = self._fs()
        assert jm._score_discard_candidate(jm.Boss_Orders, fs) < 0

    def test_fighting_energy_is_protected(self):
        fs = self._fs()
        assert jm._score_discard_candidate(jm.Basic_Fighting_Energy, fs) < 0

    def test_surplus_lightning_energy_is_safe_to_discard(self):
        fs = self._fs(hand_counts=defaultdict(int, {jm.Basic_Lightning_Energy: 3}))
        assert jm._score_discard_candidate(jm.Basic_Lightning_Energy, fs) > 0

    def test_generic_card_gets_small_positive_score(self):
        fs = self._fs()
        assert jm._score_discard_candidate(999999, fs) == 10
```

(j) `TestScoreOptionKilowattrelAbility`の`_fs`ヘルパー（876行目付近）を以下に置き換える：

```python
class TestScoreOptionKilowattrelAbility:
    def _fs(self, **overrides):
        base = dict(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            active_energy_count=0, hand_has_basic_lightning_energy=False,
        )
        base.update(overrides)
        return jm.FieldState(**base)
```

（このクラス内の2つのテストメソッド本体は変更不要）

(k) `TestScoreOptionEnergyCardType.test_routes_energy_card_type_through_dispatcher`（923行目付近）内の`FieldState`構築を以下に置き換える（このクラス自体はTask 3で削除するが、Task 2終了時点でも壊れないようにする）：

```python
        fs = jm.FieldState(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), iono_lightning_on_board=0,
            active_energy_count=0,
        )
```

- [ ] **Step 9: テスト実行**

```bash
uv run pytest tests/test_jamoraiko_agent.py -v
```

Expected: 全てPASS（`TestEnergyPolicy`・`TestScoreAttachOption`・`TestScoreDiscardCandidate`の一部・`TestScoreCardOptionDispatch`の一部・`TestScoreEnergyCardOptionDispatch`・`TestScoreOptionEnergyCardType`はまだタケルライコex参照コードが残っているが、このタスクで削除した箇所とは無関係なので影響を受けない）

```bash
uv run pytest -q
```

Expected: リポジトリ全体で全PASS

- [ ] **Step 10: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "refactor: ジャモライコの攻撃プラン計算からタケルライコex専用ロジックを削除"
```

---

### Task 3: EnergyPolicyの作り直し（ハラバリーex/タイカイデンへのエネルギー集中）

**Files:**
- Modify: `src/jamoraiko_agent/main.py`
- Modify: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: Task 2で確定した`SURPLUS_THRESHOLD = {Iono_Bellibolt_ex: 4, Iono_Kilowattrel: 3}`（変更なし）、`get_card`関数
- Produces: `EnergyPolicy.needs_lightning(my_state)`（アクティブのハラバリーex/タイカイデンが閾値未満かを返す）、`EnergyPolicy.switch_destination_score(card)`（`SURPLUS_THRESHOLD`ベースで一般化）、`EnergyPolicy.switch_source_score(obs, o, my_index)`（タケルライコex特殊分岐なし）。Task 4はこれらのシグネチャが変わらないことを前提にする

- [ ] **Step 1: `EnergyPolicy`クラスを作り直す**

`src/jamoraiko_agent/main.py`の`EnergyPolicy`クラス全体（230-326行目付近）を以下に置き換える。

```python
class EnergyPolicy:
    """雷エネルギーの手張り優先度と、エネルギーつけかえによる
    ハラバリーex/タイカイデンへのエネルギー集中を1箇所に集約する。
    OptionType.ATTACH / PLAY / ENERGY_CARD という複数のSelectContextに
    またがるロジックをここに閉じ込め、散逸を防ぐ。
    """

    SURPLUS_THRESHOLD = {
        Iono_Bellibolt_ex: 4,  # Thunderous Boltのenergy_required（ATTACKERSテーブルより）
        Iono_Kilowattrel: 3,   # Mach Boltのenergy_required（ATTACKERSテーブルより）
    }

    def attach_priority(self, pokemon: Pokemon, active: bool) -> int:
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

    def find_surplus_source(self, my_state) -> "Pokemon | None":
        """エネルギーつけかえの供給元にできる、自分自身の攻撃必要本数に
        既に届いているナンジャモポケモンを1体返す（無ければNone）。"""
        for card in my_state.active + my_state.bench:
            if card is None:
                continue
            threshold = self.SURPLUS_THRESHOLD.get(card.id)
            if threshold is None:
                continue
            lightning_count = card.energies.count(EnergyType.LIGHTNING)
            if lightning_count >= threshold:
                return card
        return None

    def needs_lightning(self, my_state) -> bool:
        """アクティブのハラバリーex/タイカイデンが、自身の攻撃必要本数に届いていないか"""
        active = my_state.active[0] if my_state.active else None
        if active is None:
            return False
        threshold = self.SURPLUS_THRESHOLD.get(active.id)
        if threshold is None:
            return False
        return active.energies.count(EnergyType.LIGHTNING) < threshold

    def play_score(self, my_state) -> int:
        """OptionType.PLAY（エネルギーつけかえを使うか）のスコアを返す"""
        if self.needs_lightning(my_state) and self.find_surplus_source(my_state) is not None:
            return 7500  # アクティブが攻撃必要本数未満で、ベンチに余剰供給元がある時のみ高優先
        return 200

    def switch_destination_score(self, card) -> int:
        """SelectContext.ATTACH_FROM（エネルギーつけかえで付け直す先のポケモン）のスコアを返す"""
        if not isinstance(card, Pokemon):
            return 0
        threshold = self.SURPLUS_THRESHOLD.get(card.id)
        if threshold is None:
            return 0
        lightning_count = card.energies.count(EnergyType.LIGHTNING)
        return 500 if lightning_count < threshold else -500

    def switch_source_score(self, obs, o, my_index: int) -> int:
        """SelectContext.SWITCH_ENERGY_CARD（エネルギーつけかえで動かす元の
        エネルギーカードを選ぶ）のスコアを返す"""
        card = get_card(obs, o.area, o.index, o.playerIndex)
        if not isinstance(card, Pokemon):
            return 0
        threshold = self.SURPLUS_THRESHOLD.get(card.id)
        if threshold is None:
            return 0
        lightning_count = card.energies.count(EnergyType.LIGHTNING)
        return 500 if lightning_count >= threshold else -500
```

- [ ] **Step 2: `_score_energy_card_option`から`DISCARD_ENERGY_CARD`ケースを削除する**

`_score_energy_card_option`関数（602-610行目付近）を以下に置き換える。

```python
def _score_energy_card_option(obs, o, context, my_index: int) -> int:
    """OptionType.ENERGY_CARD のスコアをコンテキスト別に返す。
    DISCARD_ENERGY_CARD（エネルギー破棄でダメージ増加）はデッキ内に該当する技が
    存在しないため未対応（case _ の0点に自然にフォールバックする）"""
    match context:
        case SelectContext.SWITCH_ENERGY_CARD:
            return ENERGY_POLICY.switch_source_score(obs, o, my_index)
        case _:
            return 0
```

- [ ] **Step 3: `TestEnergyPolicy`を作り直す**

`tests/test_jamoraiko_agent.py`の`TestEnergyPolicy`クラス全体（242-352行目付近）を以下に置き換える。

```python
class TestEnergyPolicy:
    def test_active_slot_gets_bonus(self):
        p = make_pokemon(id=jm.Iono_Voltorb, energies=[])
        assert jm.ENERGY_POLICY.attach_priority(p, True) > jm.ENERGY_POLICY.attach_priority(p, False)

    def test_voltorb_prioritised_below_2_energy(self):
        no_e  = make_pokemon(id=jm.Iono_Voltorb, energies=[])
        two_e = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])
        assert jm.ENERGY_POLICY.attach_priority(no_e, False) > jm.ENERGY_POLICY.attach_priority(two_e, False)

    def test_bellibolt_ex_prioritised_below_4_energy(self):
        low  = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4])
        full = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])
        assert jm.ENERGY_POLICY.attach_priority(low, False) > jm.ENERGY_POLICY.attach_priority(full, False)

    def test_kilowattrel_prioritised_below_3_energy(self):
        low  = make_pokemon(id=jm.Iono_Kilowattrel, energies=[4])
        full = make_pokemon(id=jm.Iono_Kilowattrel, energies=[4, 4, 4])
        assert jm.ENERGY_POLICY.attach_priority(low, False) > jm.ENERGY_POLICY.attach_priority(full, False)

    def test_find_surplus_source_returns_bellibolt_ex_when_surplus_lightning(self):
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])  # 雷4=閾値到達
        my_state = make_player_state(active_pokemon=None, bench=[bellibolt])
        assert jm.ENERGY_POLICY.find_surplus_source(my_state) is bellibolt

    def test_find_surplus_source_returns_none_when_below_threshold(self):
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4])  # 雷3=閾値未満
        my_state = make_player_state(active_pokemon=None, bench=[bellibolt])
        assert jm.ENERGY_POLICY.find_surplus_source(my_state) is None

    def test_find_surplus_source_ignores_unrelated_pokemon(self):
        voltorb = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4, 4, 4, 4])
        my_state = make_player_state(active_pokemon=voltorb, bench=[])
        assert jm.ENERGY_POLICY.find_surplus_source(my_state) is None

    def test_needs_lightning_true_when_active_bellibolt_ex_below_threshold(self):
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4])  # 雷2<4
        my_state = make_player_state(active_pokemon=bellibolt, bench=[])
        assert jm.ENERGY_POLICY.needs_lightning(my_state) is True

    def test_needs_lightning_false_when_active_bellibolt_ex_at_threshold(self):
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])  # 雷4=閾値到達
        my_state = make_player_state(active_pokemon=bellibolt, bench=[])
        assert jm.ENERGY_POLICY.needs_lightning(my_state) is False

    def test_needs_lightning_false_when_active_not_in_threshold_table(self):
        voltorb = make_pokemon(id=jm.Iono_Voltorb, energies=[])
        my_state = make_player_state(active_pokemon=voltorb, bench=[])
        assert jm.ENERGY_POLICY.needs_lightning(my_state) is False

    def test_needs_lightning_false_when_no_active_pokemon(self):
        my_state = make_player_state(active_pokemon=None, bench=[])
        assert jm.ENERGY_POLICY.needs_lightning(my_state) is False

    def test_switch_source_score_prefers_surplus_bench_pokemon(self):
        from cg.api import Option

        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])  # 雷4=余剰あり
        my_state = make_player_state(active_pokemon=None, bench=[bellibolt])
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.BENCH, index=0, playerIndex=0, energyIndex=0)
        assert jm.ENERGY_POLICY.switch_source_score(obs, o, my_index=0) == 500

    def test_switch_source_score_penalises_non_surplus_bench_pokemon(self):
        from cg.api import Option

        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4])  # 雷1=余剰なし
        my_state = make_player_state(active_pokemon=None, bench=[bellibolt])
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.BENCH, index=0, playerIndex=0, energyIndex=0)
        assert jm.ENERGY_POLICY.switch_source_score(obs, o, my_index=0) == -500

    def test_switch_source_score_neutral_for_unrelated_pokemon(self):
        from cg.api import Option

        voltorb = make_pokemon(id=jm.Iono_Voltorb, energies=[4, 4])
        my_state = make_player_state(active_pokemon=None, bench=[voltorb])
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.BENCH, index=0, playerIndex=0, energyIndex=0)
        assert jm.ENERGY_POLICY.switch_source_score(obs, o, my_index=0) == 0

    def test_switch_source_score_returns_zero_when_card_missing(self):
        from cg.api import Option

        my_state = make_player_state(active_pokemon=None, bench=[])
        my_state.active = [None]
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.ACTIVE, index=0, playerIndex=0, energyIndex=0)
        assert jm.ENERGY_POLICY.switch_source_score(obs, o, my_index=0) == 0

    def test_switch_destination_score_prefers_pokemon_below_threshold(self):
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4])  # 雷2<4
        assert jm.ENERGY_POLICY.switch_destination_score(bellibolt) == 500

    def test_switch_destination_score_penalises_pokemon_at_threshold(self):
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])  # 雷4=閾値到達
        assert jm.ENERGY_POLICY.switch_destination_score(bellibolt) == -500

    def test_switch_destination_score_neutral_for_unrelated_pokemon(self):
        voltorb = make_pokemon(id=jm.Iono_Voltorb, energies=[])
        assert jm.ENERGY_POLICY.switch_destination_score(voltorb) == 0

    def test_switch_destination_score_zero_for_non_pokemon(self):
        from cg.api import Card

        non_pokemon = Card(id=999, serial=1, playerIndex=0)
        assert jm.ENERGY_POLICY.switch_destination_score(non_pokemon) == 0
```

- [ ] **Step 4: `TestTrainerCardPolicies.test_energy_switch_policy_delegates_to_energy_policy`を更新する**

`tests/test_jamoraiko_agent.py`内の該当テスト（443-449行目付近）を以下に置き換える。

```python
    def test_energy_switch_policy_delegates_to_energy_policy(self):
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4])  # 雷2<4=必要
        kilowattrel = make_pokemon(id=jm.Iono_Kilowattrel, energies=[4, 4, 4])  # 供給可能
        my_state = make_player_state(active_pokemon=bellibolt, bench=[kilowattrel])
        ctx = jm.PlayScoringContext(obs=None, o=None, my_index=0, fs=None, my_state=my_state, plan=jm.AttackPlan())
        policy = jm.EnergySwitchPolicy()
        assert policy.play_score(ctx) == jm.ENERGY_POLICY.play_score(my_state)
```

- [ ] **Step 5: `TestScorePlayOption`のエネルギーつけかえ関連2テストを更新する**

`tests/test_jamoraiko_agent.py`内の該当テスト（498-525行目付近）を以下に置き換える。

```python
    def test_energy_switch_scores_high_when_active_needs_lightning_and_source_exists(self, mock_card_table):
        mock_card_table[jm.Energy_Switch] = MockCardData(cardId=jm.Energy_Switch, cardType=CardType.ITEM)
        energy_switch = make_pokemon(id=jm.Energy_Switch)
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4])  # 雷2<4=必要
        kilowattrel = make_pokemon(id=jm.Iono_Kilowattrel, energies=[4, 4, 4])  # 雷3=供給可能
        my_state = make_player_state(
            active_pokemon=bellibolt, bench=[kilowattrel],
            hand=[energy_switch], deck_count=40, prize_count=6,
        )
        obs, o = self._make_obs_with_hand_card(jm.Energy_Switch, my_state)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_play_option(obs, o, my_index=0, fs=fs, my_state=my_state, plan=plan)
        assert score >= 7000

    def test_energy_switch_scores_low_when_no_source_available(self, mock_card_table):
        mock_card_table[jm.Energy_Switch] = MockCardData(cardId=jm.Energy_Switch, cardType=CardType.ITEM)
        energy_switch = make_pokemon(id=jm.Energy_Switch)
        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4])  # 雷2<4=必要
        my_state = make_player_state(
            active_pokemon=bellibolt, bench=[],
            hand=[energy_switch], deck_count=40, prize_count=6,
        )
        obs, o = self._make_obs_with_hand_card(jm.Energy_Switch, my_state)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score = jm._score_play_option(obs, o, my_index=0, fs=fs, my_state=my_state, plan=plan)
        assert score < 7000
```

- [ ] **Step 6: `TestScoreCardOptionDispatch`のATTACH_FROMテストを更新する**

`tests/test_jamoraiko_agent.py`内の`test_dispatches_attach_from_prefers_raging_bolt_ex_needing_lightning`（832-846行目付近）を以下に置き換える。

```python
    def test_dispatches_attach_from_prefers_pokemon_needing_lightning(self):
        from cg.api import Option, SelectContext

        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4])  # 雷2<4=まだ必要
        kilowattrel = make_pokemon(id=jm.Iono_Kilowattrel, energies=[4, 4, 4])  # 雷3=閾値到達済み
        my_state = make_player_state(active_pokemon=bellibolt, bench=[kilowattrel])
        obs = MagicMock()
        obs.current.players = [my_state]
        o_bellibolt = Option(type=OptionType.CARD, area=AreaType.ACTIVE, index=0, playerIndex=0)
        o_kilowattrel = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        fs = jm._collect_field_state(my_state)
        plan = jm.AttackPlan()
        score_bellibolt = jm._score_card_option(obs, o_bellibolt, SelectContext.ATTACH_FROM, my_index=0, fs=fs, plan=plan)
        score_kilowattrel = jm._score_card_option(obs, o_kilowattrel, SelectContext.ATTACH_FROM, my_index=0, fs=fs, plan=plan)
        assert score_bellibolt > score_kilowattrel
```

- [ ] **Step 7: `DISCARD_ENERGY_CARD`関連テストを削除・置き換える**

`tests/test_jamoraiko_agent.py`の`TestScoreEnergyCardOptionDispatch`クラス（849-874行目付近）を以下に置き換える（`test_dispatches_discard_energy_card`を削除し、代わりに「意図的に0点にフォールバックすること」を検証するテストを追加）。

```python
class TestScoreEnergyCardOptionDispatch:
    def test_dispatches_switch_energy_card(self):
        from cg.api import Option, SelectContext

        bellibolt = make_pokemon(id=jm.Iono_Bellibolt_ex, energies=[4, 4, 4, 4])
        my_state = make_player_state(active_pokemon=None, bench=[bellibolt])
        obs = MagicMock()
        obs.current.players = [my_state]
        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.BENCH, index=0, playerIndex=0, energyIndex=0)
        score = jm._score_energy_card_option(obs, o, SelectContext.SWITCH_ENERGY_CARD, my_index=0)
        assert score == jm.ENERGY_POLICY.switch_source_score(obs, o, my_index=0)

    def test_discard_energy_card_context_defaults_to_zero(self):
        """きょくらいごう撤去に伴いDISCARD_ENERGY_CARDは未対応になった。
        意図的にcase _の0点へフォールバックすることを明示的に検証する"""
        from cg.api import Option, SelectContext

        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.ACTIVE, index=0, playerIndex=0, energyIndex=0)
        score = jm._score_energy_card_option(obs=MagicMock(), o=o, context=SelectContext.DISCARD_ENERGY_CARD, my_index=0)
        assert score == 0

    def test_unknown_context_defaults_to_zero(self):
        from cg.api import Option, SelectContext

        o = Option(type=OptionType.ENERGY_CARD, area=AreaType.ACTIVE, index=0, playerIndex=0, energyIndex=0)
        score = jm._score_energy_card_option(obs=MagicMock(), o=o, context=SelectContext.MAIN, my_index=0)
        assert score == 0
```

- [ ] **Step 8: `TestScoreOptionEnergyCardType`クラスを削除する**

`tests/test_jamoraiko_agent.py`末尾の`TestScoreOptionEnergyCardType`クラス（923-939行目付近）を削除する（ファイル末尾のクラスなので、クラス定義ごと削除して良い）。

- [ ] **Step 9: テスト実行**

```bash
uv run pytest tests/test_jamoraiko_agent.py -v
uv run pytest -q
```

Expected: 全てPASS

- [ ] **Step 10: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "refactor: EnergyPolicyをハラバリーex/タイカイデンへのエネルギー集中用に作り直す"
```

---

### Task 4: 残存する闘エネルギー分岐・定数の最終クリーンアップ

**Files:**
- Modify: `src/jamoraiko_agent/main.py`
- Modify: `tests/test_jamoraiko_agent.py`

**Interfaces:**
- Consumes: Task 2・Task 3で確定した全ての関数シグネチャ（変更なし）
- Produces: `Raging_Bolt_ex`/`Basic_Fighting_Energy`定数が完全に消えた`main.py`。以降のタスクなし（Task 5は回帰確認のみ）

- [ ] **Step 1: `_score_attach_option`から闘エネルギー分岐を削除する**

`src/jamoraiko_agent/main.py`の`_score_attach_option`関数（331-344行目付近）を以下に置き換える。

```python
def _score_attach_option(obs, o, my_index: int) -> int:
    """OptionType.ATTACH のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
    if pokemon is None or card is None:
        return 0
    if card.id == Basic_Lightning_Energy:
        return ENERGY_POLICY.attach_priority(pokemon, o.inPlayArea == AreaType.ACTIVE)
    return 0
```

- [ ] **Step 2: `_score_discard_candidate`から闘エネルギー分岐を削除する**

`_score_discard_candidate`関数（567-579行目付近）を以下に置き換える。

```python
def _score_discard_candidate(card_id: int, fs: FieldState) -> int:
    """OptionType.CARD / SelectContext.DISCARD のスコアを返す"""
    line = POKEMON_LINES.get(card_id)
    if line is not None:
        owned = fs.field_counts[card_id] + fs.hand_counts[card_id]
        return 50 if owned > line.max_field_copies else -300
    if card_id == Basic_Lightning_Energy:
        return 30 if fs.hand_counts[Basic_Lightning_Energy] >= 3 else -50
    if card_id in (Boss_Orders, Lillie_Determination, Max_Rod):
        return -200  # キーカード・ACE SPECは温存
    return 10
```

- [ ] **Step 3: 定数`Raging_Bolt_ex`と`Basic_Fighting_Energy`を削除する**

ファイル冒頭のカードID定数定義（13-32行目付近）から以下の2行を削除する。

削除前：
```python
Raging_Bolt_ex          = 63    # タケルライコex
Iono_Voltorb            = 265   # ナンジャモのビリリダマ
```
（`Raging_Bolt_ex`の行のみ削除。`Iono_Voltorb`は残す）

削除前：
```python
Basic_Lightning_Energy      = 4
Basic_Fighting_Energy       = 6
```
削除後：
```python
Basic_Lightning_Energy      = 4
```

- [ ] **Step 4: `mock_card_table`フィクスチャから該当エントリを削除する**

`tests/test_jamoraiko_agent.py`の`mock_card_table`フィクスチャ（97-121行目付近）を以下に置き換える。

```python
@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    table = {
        jm.Iono_Voltorb:            MockCardData(cardId=jm.Iono_Voltorb),
        jm.Iono_Tadbulb:            MockCardData(cardId=jm.Iono_Tadbulb),
        jm.Iono_Bellibolt_ex:       MockCardData(cardId=jm.Iono_Bellibolt_ex),
        jm.Iono_Wattrel:            MockCardData(cardId=jm.Iono_Wattrel),
        jm.Iono_Kilowattrel:        MockCardData(cardId=jm.Iono_Kilowattrel),
        jm.Buddy_Buddy_Poffin:      MockCardData(cardId=jm.Buddy_Buddy_Poffin, cardType=CardType.ITEM),
        jm.Night_Stretcher:         MockCardData(cardId=jm.Night_Stretcher, cardType=CardType.ITEM),
        jm.Max_Rod:                 MockCardData(cardId=jm.Max_Rod, cardType=CardType.ITEM),
        jm.Energy_Retrieval:        MockCardData(cardId=jm.Energy_Retrieval, cardType=CardType.ITEM),
        jm.Energy_Switch:            MockCardData(cardId=jm.Energy_Switch, cardType=CardType.ITEM),
        jm.Ultra_Ball:               MockCardData(cardId=jm.Ultra_Ball, cardType=CardType.ITEM),
        jm.Switch:                   MockCardData(cardId=jm.Switch, cardType=CardType.ITEM),
        jm.Boss_Orders:               MockCardData(cardId=jm.Boss_Orders, cardType=CardType.SUPPORTER),
        jm.Lillie_Determination:       MockCardData(cardId=jm.Lillie_Determination, cardType=CardType.SUPPORTER),
        jm.Canari:                     MockCardData(cardId=jm.Canari, cardType=CardType.SUPPORTER),
        jm.Levincia:                   MockCardData(cardId=jm.Levincia, cardType=CardType.STADIUM),
        jm.Basic_Lightning_Energy:      MockCardData(cardId=jm.Basic_Lightning_Energy, cardType=CardType.BASIC_ENERGY),
    }
    monkeypatch.setattr(jm, "card_table", table)
    return table
```

- [ ] **Step 5: `TestScoreAttachOption`クラスを削除する**

`tests/test_jamoraiko_agent.py`の`TestScoreAttachOption`クラス（355-368行目付近、`test_fighting_energy_prioritises_raging_bolt_ex_without_fighting`のみを含むクラス）をクラスごと削除する。

- [ ] **Step 6: `TestScoreDiscardCandidate.test_fighting_energy_is_protected`を削除する**

`tests/test_jamoraiko_agent.py`の`TestScoreDiscardCandidate`クラス（Task 2で更新済み）から以下のメソッドを削除する。

```python
    def test_fighting_energy_is_protected(self):
        fs = self._fs()
        assert jm._score_discard_candidate(jm.Basic_Fighting_Energy, fs) < 0
```

- [ ] **Step 7: テスト実行**

```bash
uv run pytest tests/test_jamoraiko_agent.py -v
```

Expected: 全てPASS。特に`grep -n "Raging_Bolt_ex\|Basic_Fighting_Energy" tests/test_jamoraiko_agent.py src/jamoraiko_agent/main.py`がヒットしないことを確認する。

```bash
uv run pytest -q
```

Expected: リポジトリ全体で全PASS

- [ ] **Step 8: コミット**

```bash
git add src/jamoraiko_agent/main.py tests/test_jamoraiko_agent.py
git commit -m "refactor: ジャモライコからタケルライコex・基本闘エネルギーの残存参照を完全に削除"
```

---

### Task 5: 全体回帰確認・実装サマリー作成

**Files:**
- Create: `docs/implementations/20260716-jamoraiko-voltorb-pivot.md`

**Interfaces:**
- Consumes: Task 1〜4の全ての変更
- Produces: 実装サマリードキュメント（CLAUDE.mdフェーズ4の完了条件）

- [ ] **Step 1: リポジトリ全体のテストを実行し、件数を記録する**

```bash
uv run pytest -q
```

Expected: 全PASS。実行結果のテスト総数を記録する（Task実行前の507件から、削除分・追加分を差し引きした件数になるはず）

- [ ] **Step 2: `Raging_Bolt_ex`・`Basic_Fighting_Energy`の参照が完全に消えたことを確認する**

```bash
grep -rn "Raging_Bolt_ex\|Basic_Fighting_Energy" src/jamoraiko_agent/ decks/jamoraiko_20260713.py tests/test_jamoraiko_agent.py tests/test_jamoraiko_deck.py
```

Expected: 何もヒットしない（終了コード1）

- [ ] **Step 3: デッキ枚数を最終確認する**

```bash
uv run python -c "
from decks.jamoraiko_20260713 import DECK
print('合計枚数:', sum(c for _, c in DECK))
print(dict(DECK))
"
```

Expected: 合計60枚。`{265: 3, 4: 15}`を含み、`63`（タケルライコex）・`6`（基本闘エネルギー）が存在しないこと

- [ ] **Step 4: 実装サマリーを作成する**

`docs/implementations/20260716-jamoraiko-voltorb-pivot.md`を作成する。

```markdown
# ジャモライコ ビリリダマ軸ピボット 実装サマリー

## 背景

2026-07-14までの校正ノートブック実測で、ジャモライコの勝率は複数回の改修を経ても2〜4.5%で頭打ちだった。根本原因は「きょくらいごう」（タケルライコex）が要求する雷1闘1のうち、基本闘エネルギーが60枚中3枚しかなく構造的に揃わないことと判明。ユーザー判断により、タケルライコex・闘エネルギー依存を解消し、ナンジャモのビリリダマの「チェインボルト」（闘エネルギー不要・場全体の雷エネルギー数でダメージが決まる技）を主軸に据える方向へピボットした。

## 変更内容

### デッキ変更（`decks/jamoraiko_20260713.py`）

| カード | 変更前 | 変更後 |
|---|---|---|
| タケルライコex (63) | 2枚 | 0枚 |
| ナンジャモのビリリダマ (265) | 1枚 | 3枚 |
| 基本闘エネルギー (6) | 3枚 | 0枚 |
| 基本雷エネルギー (4) | 12枚 | 15枚 |

### コード変更（`src/jamoraiko_agent/main.py`）

- タケルライコex専用の死んだコードを削除：`FieldState.own_board_basic_energy_total`/`active_fighting_energy_count`、`Attacker.requires_fighting`/`is_utility`、`ATTACKERS`テーブルの2技（Bellowing Thunder/Burst Roar）、`POKEMON_LINES`のタケルライコexエントリ、`calc_attack_plan`内の関連分岐、`_score_attach_option`/`_score_search_candidate`/`_score_discard_candidate`の闘エネルギー分岐、`_score_energy_card_option`のDISCARD_ENERGY_CARDケース
- `POKEMON_LINES`のビリリダマ`max_field_copies`を2→3に変更（3枚採用に合わせる）
- `EnergyPolicy`クラスを「タケルライコexへのエネルギー集中」から「アクティブのハラバリーex(4エネ必要)/タイカイデン(3エネ必要)が攻撃可能本数に届いていない時、ベンチの余剰供給元から回す」ロジックに作り直し

## テスト

- `tests/test_jamoraiko_deck.py`：デッキ内容変更に合わせて全面更新
- `tests/test_jamoraiko_agent.py`：タケルライコex関連テストを削除・置き換え、EnergyPolicy再設計に伴うテストを新規作成
- `uv run pytest -q`でリポジトリ全体が全PASSであることを確認済み

## 未検証事項（次回以降）

- ビリリダマ軸への変更が実際に勝率を改善するかは、校正ノートブックの再ビルド・Kaggle実行でのみ確認できる（本タスクのスコープ外、ユーザー側で別途実施）
- カイデン（id=270）がATTACKERSテーブルに未登録の件は既知の軽微なロジック穴として引き続き別件で持ち越し
```

- [ ] **Step 5: コミット**

```bash
git add docs/implementations/20260716-jamoraiko-voltorb-pivot.md
git commit -m "docs: ジャモライコ ビリリダマ軸ピボットの実装サマリーを追加"
```
