# ルカリオexデッキ combat.py切り出し・energy_score無効化考慮修正 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/lucario_agent/main.py`（826行）から意思決定チェーン（エネルギー配分・攻撃プラン計算）を`constants.py`・`combat.py`へ切り出し、その過程で実測確認済みの`energy_score`関連3件の実バグを修正する。

**Architecture:** 3ファイル構成に分割する。`constants.py`はカードID定数のみ（依存なし）。`combat.py`はエネルギー配分・攻撃プラン計算・RETREAT/ATTACKスコアリングを担い、`constants.py`にのみ依存する。`main.py`は両方からimportし、トレーナーズカード判断・エージェント入口を担う。`card_table`（カードメタデータ辞書）は`main.py`のグローバル変数から`combat.py`の各関数へ明示的な引数として渡し、モジュール間の暗黙グローバル共有をなくす。

**Tech Stack:** Python 3.12 / uv / pytest。`cg.api`（Pokémon TCGシミュレータのデータクラス定義、macOSではネイティブ部分`libcg.so`が動作しないためpure Pythonのデータクラスのみ利用）。

## Global Constraints

- macOSでは`cg.sim`のネイティブライブラリが動作しないため、`tests/conftest.py`が`sys.modules['cg.sim']`をモック済み。このモック機構に触れない
- `tests/test_lucario_agent.py`は`import lucario_agent.main as lm`で全ての定数・関数に`lm.X`としてアクセスしている（416箇所）。各タスクで「テストファイルは変更不要」と明記した箇所以外は、既存のテストコードの意図（何を検証しているか）を変えない
- `pyproject.toml`の`[tool.pytest.ini_options]`で`pythonpath = ["src", "data/competition/sample_submission"]`が設定済みのため、`src/lucario_agent/`配下のモジュールは`lucario_agent.xxx`としてimportできる
- 全タスク完了後、`uv run pytest -q`でリポジトリ全体が例外なく全件PASSすること

---

## Task 1: `constants.py`の新設

**Files:**
- Create: `src/lucario_agent/constants.py`
- Modify: `src/lucario_agent/main.py:12-37`
- Test: `tests/test_lucario_agent.py`（変更不要、既存テストの継続PASSで検証）

**Interfaces:**
- Produces: `constants.py`は`Lunatone`, `Solrock`, `Riolu`, `Mega_Lucario_ex`, `Premium_Power_Pro`, `Fighting_Gong`, `Poke_Pad`, `Hero_Cape`, `Boss_Orders`, `Lillie_Determination`, `Gravity_Mountain`, `Nighttime_Mine`, `Basic_Fighting_Energy`, `Rock_Fighting_Energy`, `Ultra_Ball`, `Pokegear`, `Night_Stretcher`, `Judge`, `Hilda`, `Wally_Compassion`, `Ciphermaniac_Codebreaking`, `Ogerpon_ex`, `Crustle`, `Sylveon`, `EX_DAMAGE_NULLIFIER_IDS`（全てint定数、`EX_DAMAGE_NULLIFIER_IDS`のみ`frozenset[int]`）を公開する

- [ ] **Step 1: `constants.py`を新規作成する**

`src/lucario_agent/main.py`の12-37行目（`# ==================== カードID定数 ====================`のコメント行から`EX_DAMAGE_NULLIFIER_IDS = frozenset({Crustle, Sylveon})`まで）と全く同じ内容で、新規ファイルを作成する。

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
Nighttime_Mine        = 1266  # テラスタルポケモンの技コスト+1（両プレイヤー対象）
Basic_Fighting_Energy = 6
Rock_Fighting_Energy  = 20  # ロック闘エネルギー：装着ポケモンは相手の技の"効果"を受けない（Alakazam「ハンドパワー」対策）
Ultra_Ball                 = 1121
Pokegear                   = 1122
Night_Stretcher            = 1097
Judge                      = 1213
Hilda                      = 1225
Wally_Compassion           = 1229
Ciphermaniac_Codebreaking  = 1188
Ogerpon_ex                 = 117
Crustle                     = 345  # 特性「ふしぎな岩の宿」：相手の「ポケモン【ex】」の技ダメージを無効化する壁ポケモン
Sylveon                     = 330  # 特性「Safeguard」：Crustleと同一効果文（相手のポケモンexの技ダメージを無効化）
EX_DAMAGE_NULLIFIER_IDS = frozenset({Crustle, Sylveon})
```

Write先: `/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/src/lucario_agent/constants.py`

- [ ] **Step 2: `main.py`からカードID定数ブロックを削除し、`constants.py`からのimportに置き換える**

`src/lucario_agent/main.py`の以下の部分（1-41行目、importブロックとカードID定数ブロック）：

```python
import os
import random
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass

from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, Option, PlayerState, all_card_data, to_observation_class,
)

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
Nighttime_Mine        = 1266  # テラスタルポケモンの技コスト+1（両プレイヤー対象）
Basic_Fighting_Energy = 6
Rock_Fighting_Energy  = 20  # ロック闘エネルギー：装着ポケモンは相手の技の"効果"を受けない（Alakazam「ハンドパワー」対策）
Ultra_Ball                 = 1121
Pokegear                   = 1122
Night_Stretcher            = 1097
Judge                      = 1213
Hilda                      = 1225
Wally_Compassion           = 1229
Ciphermaniac_Codebreaking  = 1188
Ogerpon_ex                 = 117
Crustle                     = 345  # 特性「ふしぎな岩の宿」：相手の「ポケモン【ex】」の技ダメージを無効化する壁ポケモン
Sylveon                     = 330  # 特性「Safeguard」：Crustleと同一効果文（相手のポケモンexの技ダメージを無効化）
EX_DAMAGE_NULLIFIER_IDS = frozenset({Crustle, Sylveon})

EPSILON = 0.28  # 温存判断時に探索的先出しをする確率
_rng    = random.Random()  # 本番用の実乱数。テストではスタブを注入する
```

を、以下に置き換える：

```python
import os
import random
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass

from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, Option, PlayerState, all_card_data, to_observation_class,
)

from lucario_agent.constants import (
    Lunatone, Solrock, Riolu, Mega_Lucario_ex, Premium_Power_Pro, Fighting_Gong,
    Poke_Pad, Hero_Cape, Boss_Orders, Lillie_Determination, Gravity_Mountain,
    Nighttime_Mine, Basic_Fighting_Energy, Rock_Fighting_Energy, Ultra_Ball,
    Pokegear, Night_Stretcher, Judge, Hilda, Wally_Compassion,
    Ciphermaniac_Codebreaking, Ogerpon_ex, Crustle, Sylveon, EX_DAMAGE_NULLIFIER_IDS,
)

EPSILON = 0.28  # 温存判断時に探索的先出しをする確率
_rng    = random.Random()  # 本番用の実乱数。テストではスタブを注入する
```

（`EPSILON`/`_rng`はTask2で`combat.py`へ移動するまで`main.py`に残す）

- [ ] **Step 3: テスト実行で無変更PASSを確認する**

Run: `uv run pytest -q`
Expected: 全件PASS（テストファイルは一切変更していない。`lm.Lunatone`等は`main.py`が`constants.py`からimportして再exportしているため、`lm.`経由でも変わらずアクセスできる）

- [ ] **Step 4: Commit**

```bash
git add src/lucario_agent/constants.py src/lucario_agent/main.py
git commit -m "refactor(lucario): カードID定数をconstants.pyへ切り出し"
```

---

## Task 2: `combat.py`の新設（AttackPlan・pokemon_score・prize_count・energy_score・攻撃プラン計算の移動）

**Files:**
- Create: `src/lucario_agent/combat.py`
- Modify: `src/lucario_agent/main.py`
- Modify: `tests/test_lucario_agent.py`（`card_table`引数の一括追加、スクリプトで実施）

**Interfaces:**
- Consumes: Task1の`lucario_agent.constants`（`Lunatone`, `Solrock`, `Riolu`, `Mega_Lucario_ex`, `Ogerpon_ex`, `Basic_Fighting_Energy`, `Rock_Fighting_Energy`, `Nighttime_Mine`, `EX_DAMAGE_NULLIFIER_IDS`）
- Produces: `combat.py`は`AttackPlan`（dataclass）、`prize_count(pokemon, card_table) -> int`、`pokemon_score(pokemon, card_table) -> int`、`energy_score(pokemon, active, attacker1, op_active_nullifies_ex=False) -> int`、`_tera_stadium_cost_bonus(pokemon_id, stadium_id, card_table) -> int`、`_calc_attack_damage(attacker_id, base_damage, defender_id, defender_data, card_table) -> int`、`calc_attack_plan(obs, my_state, op_state, state, field_counts, hand_counts, discard_counts, can_switch, can_op_switch, can_use_mega_brave, can_attack, my_prize, card_table, stadium_id=0, rng=None) -> AttackPlan`を公開する

- [ ] **Step 1: `combat.py`を新規作成する**

`/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/src/lucario_agent/combat.py`を以下の内容で作成する（`main.py`の該当箇所を移動し、`card_table`をグローバル参照から明示引数に変更したもの）：

```python
"""ルカリオexエージェントの戦闘意思決定ロジック（エネルギー配分・攻撃プラン計算）"""
import random
from dataclasses import dataclass

from cg.api import EnergyType, Pokemon

from lucario_agent.constants import (
    Lunatone, Solrock, Riolu, Mega_Lucario_ex, Ogerpon_ex,
    Basic_Fighting_Energy, Rock_Fighting_Energy, Nighttime_Mine,
    EX_DAMAGE_NULLIFIER_IDS,
)

EPSILON = 0.28  # 温存判断時に探索的先出しをする確率
_rng    = random.Random()  # 本番用の実乱数。テストではスタブを注入する


@dataclass
class AttackPlan:
    attacker:     int  = -1
    target:       int  = -1
    attack_index: int  = -1
    remain_hp:    int  = -1
    energy:       bool = False


def prize_count(pokemon: Pokemon, card_table: dict) -> int:
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


def pokemon_score(pokemon: Pokemon, card_table: dict) -> int:
    """対象ポケモンの戦術的価値をヒューリスティックに評価する"""
    data  = card_table[pokemon.id]
    score = prize_count(pokemon, card_table) * 1000
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


def energy_score(pokemon: Pokemon, active: bool, attacker1: bool, op_active_nullifies_ex: bool = False) -> int:
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
    elif pokemon.id == Ogerpon_ex:
        if energy_count < 3:
            score += 80
        if attacker1:
            score += 40  # ルカリオ確保済みなら余剰エネルギーをオーガポンexへ
        if op_active_nullifies_ex:
            score += 150  # 相手がex無効化持ちならメガルカリオex系より優先してエネルギーを回す
    return score


def _tera_stadium_cost_bonus(pokemon_id: int, stadium_id: int, card_table: dict) -> int:
    """Nighttime Mine下でテラスタルポケモンが支払う追加コストを返す"""
    if stadium_id == Nighttime_Mine and card_table[pokemon_id].tera:
        return 1
    return 0


def _calc_attack_damage(attacker_id: int, base_damage: int, defender_id: int, defender_data, card_table: dict) -> int:
    """弱点・抵抗力・ex技無効化ポケモンの特性を考慮した実ダメージを1箇所で計算する"""
    damage = base_damage
    attack_ignores_defender_effects = attacker_id == Ogerpon_ex  # ぶちやぶる：相手にかかっている効果を計算しない
    if not attack_ignores_defender_effects:
        if defender_data.weakness == EnergyType.FIGHTING:
            damage *= 2
        elif defender_data.resistance == EnergyType.FIGHTING:
            damage -= 30

    attacker_is_ex = card_table[attacker_id].ex or card_table[attacker_id].megaEx
    defender_nullifies_ex_damage = (
        not attack_ignores_defender_effects  # ぶちやぶるは無効化を貫通するため対象外
        and defender_id in EX_DAMAGE_NULLIFIER_IDS
        and attacker_is_ex
    )
    if defender_nullifies_ex_damage:
        damage = 0  # Crustle/Sylveonの特性：相手のポケモンexの技ダメージを無効化する

    return damage


def calc_attack_plan(
    obs,
    my_state,
    op_state,
    state,
    field_counts,
    hand_counts,
    discard_counts,
    can_switch: bool,
    can_op_switch: bool,
    can_use_mega_brave: bool,
    can_attack: bool,
    my_prize: int,
    card_table: dict,
    stadium_id: int = 0,
    rng: "random.Random | None" = None,
) -> AttackPlan:
    """最適な攻撃プランを計算して返す。

    【メモ・2026-07-17】Mega_Lucario_ex/Solrock/Ogerpon_exのアタッカー候補は
    if/elif連鎖で判定している。2026-07-07にテーブル化リファクタリング
    （アタッカー定義をdataclassのリストに切り出す案）が検討されたが、
    ブレスト中にスコープ確定直後で中断されたまま未着手。今回のTrainerCardPolicy化とは
    別スコープのため対象外とする
    """
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
            elif a == 1:
                break
            elif my_pokemon.id == Solrock:
                if field_counts[Lunatone] >= 1:
                    energy_required = 1
                    base_damage     = 70
            elif my_pokemon.id == Ogerpon_ex:
                energy_required = 3
                base_damage     = 140

            if base_damage <= 0:
                continue

            energy_required += _tera_stadium_cost_bonus(my_pokemon.id, stadium_id, card_table)

            energy_count = len(my_pokemon.energies)
            more_energy  = False
            mega_brave_unavailable_for_current_active = (
                a == 1 and i == 0 and energy_count >= 2 and not can_use_mega_brave
            )
            if mega_brave_unavailable_for_current_active:
                break
            if energy_count < energy_required:
                can_attach_energy_this_turn = (
                    hand_counts[Basic_Fighting_Energy] + hand_counts[Rock_Fighting_Energy] >= 1
                    and not state.energyAttached
                )
                if can_attach_energy_this_turn:
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
                data   = card_table[op_pokemon.id]
                damage = _calc_attack_damage(my_pokemon.id, base_damage, op_pokemon.id, data, card_table)

                prize = 0
                score = pokemon_score(op_pokemon, card_table)
                if op_pokemon.hp <= damage:
                    prize = prize_count(op_pokemon, card_table)
                else:
                    score *= damage / op_pokemon.hp
                score += base_score

                is_mega_brave_choice = my_pokemon.id == Mega_Lucario_ex and a == 1
                if is_mega_brave_choice:
                    base_dmg_normal = _calc_attack_damage(my_pokemon.id, 130, op_pokemon.id, data, card_table)
                    if op_pokemon.hp <= base_dmg_normal:
                        score -= 1000  # 通常攻撃で足りるならメガブレイブは温存
                    elif op_pokemon.hp > damage:
                        active_rng = rng if rng is not None else _rng
                        if active_rng.random() >= EPSILON:
                            score -= 300  # 探索に外れたら温存寄り

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

- [ ] **Step 2: `main.py`から移動元のコードを削除し、`combat.py`からのimportに置き換える**

`src/lucario_agent/main.py`から以下を削除する：
- `# ==================== ターン状態管理 ====================`直後の`AttackPlan`クラス定義（`@dataclass`から`energy: bool = False`まで）。ただし直後の`plan: AttackPlan = AttackPlan()`・`pre_turn: int = 0`・`ability_used: bool = False`・`_reset_turn_state()`関数はそのまま残す
- `prize_count`関数全体
- `pokemon_score`関数全体
- `energy_score`関数全体
- `_tera_stadium_cost_bonus`関数全体
- `_calc_attack_damage`関数全体
- `calc_attack_plan`関数全体

`main.py`冒頭のimportブロックに以下を追加する（Task1で追加した`from lucario_agent.constants import (...)`の直後）：

```python
from lucario_agent.combat import (
    AttackPlan,
    prize_count,
    pokemon_score,
    energy_score,
    _calc_attack_damage,
    calc_attack_plan,
)
```

`main.py`側で`calc_attack_plan`を呼び出している箇所（`agent()`関数内、`plan = calc_attack_plan(...)`）に`card_table=card_table`を追加する：

現状：
```python
        plan = calc_attack_plan(
            obs, my_state, op_state, state,
            field_counts, hand_counts, discard_counts,
            can_switch, can_op_switch, can_use_mega_brave, can_attack,
            my_prize, stadium_id=stadium_id,
        )
```

変更後：
```python
        plan = calc_attack_plan(
            obs, my_state, op_state, state,
            field_counts, hand_counts, discard_counts,
            can_switch, can_op_switch, can_use_mega_brave, can_attack,
            my_prize, card_table=card_table, stadium_id=stadium_id,
        )
```

- [ ] **Step 3: 既存テストの`card_table`引数を一括追加するスクリプトを作成・実行する**

`combat.py`へ移動した5関数（`prize_count`, `pokemon_score`, `_calc_attack_damage`, `_tera_stadium_cost_bonus`, `calc_attack_plan`）に`card_table`引数を追加したため、`tests/test_lucario_agent.py`内の既存呼び出し全46箇所（`calc_attack_plan`18箇所・`_calc_attack_damage`10箇所・`_tera_stadium_cost_bonus`3箇所・`prize_count`5箇所・`pokemon_score`10箇所）に`card_table=lm.card_table`（または位置引数として`lm.card_table`）を追加する必要がある。`mock_card_table`フィクスチャ（`tests/test_lucario_agent.py:27-61`、`autouse=True`）が`monkeypatch.setattr(lm, "card_table", table)`で`lm.card_table`を既にパッチしているため、各テストメソッドの引数に`mock_card_table`を追加する必要はなく、`lm.card_table`を直接参照するだけでよい。

以下のPythonスクリプトを一時ファイルとして作成し、実行する。

`/tmp/patch_card_table_args.py`:
```python
import re

path = "tests/test_lucario_agent.py"
with open(path, encoding="utf-8") as f:
    text = f.read()

# 1. calc_attack_plan: 18箇所、いずれも `my_prize=<数字>,` という行を含む多行呼び出し
text, n1 = re.subn(
    r"(my_prize=\d+,)\n",
    r"\1\n            card_table=lm.card_table,\n",
    text,
)
assert n1 == 18, f"expected 18 calc_attack_plan sites, got {n1}"

# 2. _calc_attack_damage: 10箇所、いずれも単一行呼び出し
text, n2 = re.subn(
    r"lm\._calc_attack_damage\(([^)]*)\)",
    r"lm._calc_attack_damage(\1, card_table=lm.card_table)",
    text,
)
assert n2 == 10, f"expected 10 _calc_attack_damage sites, got {n2}"

# 3. _tera_stadium_cost_bonus: 3箇所、いずれも単一行呼び出し
text, n3 = re.subn(
    r"lm\._tera_stadium_cost_bonus\(([^)]*)\)",
    r"lm._tera_stadium_cost_bonus(\1, card_table=lm.card_table)",
    text,
)
assert n3 == 3, f"expected 3 _tera_stadium_cost_bonus sites, got {n3}"

# 4. prize_count: 5箇所、いずれも単一行呼び出し
text, n4 = re.subn(
    r"lm\.prize_count\(([^)]*)\)",
    r"lm.prize_count(\1, lm.card_table)",
    text,
)
assert n4 == 5, f"expected 5 prize_count sites, got {n4}"

# 5. pokemon_score: 10箇所（5行×2回ずつ）、いずれも単一行呼び出し
text, n5 = re.subn(
    r"lm\.pokemon_score\(([^)]*)\)",
    r"lm.pokemon_score(\1, lm.card_table)",
    text,
)
assert n5 == 10, f"expected 10 pokemon_score sites, got {n5}"

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

print(f"calc_attack_plan={n1} _calc_attack_damage={n2} _tera_stadium_cost_bonus={n3} "
      f"prize_count={n4} pokemon_score={n5}")
```

Run: `uv run python /tmp/patch_card_table_args.py`
Expected: 例外なく`calc_attack_plan=18 _calc_attack_damage=10 _tera_stadium_cost_bonus=3 prize_count=5 pokemon_score=10`と出力される（件数が1つでも一致しなければ`AssertionError`で停止するため、そのまま実行して問題ない）

- [ ] **Step 4: テスト実行で全件PASSを確認する**

Run: `uv run pytest -q`
Expected: 全件PASS。もし特定のテストで`TypeError: ... missing 1 required positional argument: 'card_table'`のようなエラーが出た場合、Step3のスクリプトが対象箇所を正しく書き換えられていない（呼び出し形式が正規表現のパターンと一致しない）ことを意味するため、該当箇所を`grep -n "lm\.関数名("  tests/test_lucario_agent.py`で特定し、`card_table=lm.card_table`（または`lm.card_table`を末尾の位置引数として）手動で追加する

- [ ] **Step 5: 一時スクリプトを削除しCommit**

```bash
rm /tmp/patch_card_table_args.py
git add src/lucario_agent/combat.py src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "refactor(lucario): AttackPlan・pokemon_score・prize_count・energy_score・calc_attack_planをcombat.pyへ切り出し"
```

---

## Task 3: RETREAT/ATTACKスコアリングの関数化・combat.pyへの移動

**Files:**
- Modify: `src/lucario_agent/combat.py`
- Modify: `src/lucario_agent/main.py`
- Test: `tests/test_lucario_agent.py`

**Interfaces:**
- Consumes: Task2の`combat.py`の`AttackPlan`
- Produces: `combat.py`は`_score_retreat_option(current_plan: AttackPlan) -> int`、`_score_attack_option_choice(o, current_plan: AttackPlan) -> int`を追加で公開する

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の624行目付近（`# ==================== Task 6: agent() 統合テスト ====================`というコメントの直前）に、以下のテストクラスを追加する：

```python
class TestScoreRetreatOption:
    """OptionType.RETREAT のスコアリング（_score_retreat_option）のテスト"""

    def test_negative_when_plan_keeps_current_attacker(self):
        assert lm._score_retreat_option(lm.AttackPlan(attacker=0)) == -1

    def test_high_score_when_plan_switches_attacker(self):
        assert lm._score_retreat_option(lm.AttackPlan(attacker=1)) == 2000

    def test_negative_when_no_plan_computed(self):
        """plan未計算時のデフォルト(attacker=-1)でも退却は選ばれない"""
        assert lm._score_retreat_option(lm.AttackPlan()) == -1


class TestScoreAttackOptionChoice:
    """OptionType.ATTACK のスコアリング（_score_attack_option_choice）のテスト"""

    def test_prefers_mega_brave_when_plan_selects_it(self):
        plan = lm.AttackPlan(attack_index=1)
        mega_brave = Option(type=OptionType.ATTACK, attackId=983)
        normal     = Option(type=OptionType.ATTACK, attackId=100)
        assert lm._score_attack_option_choice(mega_brave, plan) > lm._score_attack_option_choice(normal, plan)

    def test_prefers_normal_attack_when_plan_selects_it(self):
        plan = lm.AttackPlan(attack_index=0)
        mega_brave = Option(type=OptionType.ATTACK, attackId=983)
        normal     = Option(type=OptionType.ATTACK, attackId=100)
        assert lm._score_attack_option_choice(normal, plan) > lm._score_attack_option_choice(mega_brave, plan)
```

（`Option`・`OptionType`は`tests/test_lucario_agent.py`の263行目付近で既に`from cg.api import Option, OptionType`としてimport済みのため、追加のimportは不要）

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreRetreatOption tests/test_lucario_agent.py::TestScoreAttackOptionChoice -v`
Expected: FAIL（`AttributeError: module 'lucario_agent.main' has no attribute '_score_retreat_option'`）

- [ ] **Step 3: `combat.py`に2関数を追加する**

`src/lucario_agent/combat.py`の末尾（`calc_attack_plan`関数の後）に以下を追加する：

```python
def _score_retreat_option(current_plan: AttackPlan) -> int:
    """OptionType.RETREAT のスコアを返す"""
    return 2000 if current_plan.attacker >= 1 else -1


def _score_attack_option_choice(o, current_plan: AttackPlan) -> int:
    """OptionType.ATTACK のスコアを返す"""
    score = 1000
    if current_plan.attack_index == 1:
        score += 100 if o.attackId == 983 else 0  # Mega Brave 優先
    else:
        score += 0 if o.attackId == 983 else 100
    return score
```

- [ ] **Step 4: `main.py`から該当ロジックを削除し、`combat.py`の関数呼び出しに置き換える**

`src/lucario_agent/main.py`の`_score_option`関数内、以下の部分：

```python
        case OptionType.RETREAT:
            return 2000 if current_plan.attacker >= 1 else -1
        case OptionType.ATTACK:
            score = 1000
            if current_plan.attack_index == 1:
                score += 100 if o.attackId == 983 else 0  # Mega Brave 優先
            else:
                score += 0 if o.attackId == 983 else 100
            return score
```

を、以下に置き換える：

```python
        case OptionType.RETREAT:
            return _score_retreat_option(current_plan)
        case OptionType.ATTACK:
            return _score_attack_option_choice(o, current_plan)
```

`main.py`冒頭の`from lucario_agent.combat import (...)`ブロックに`_score_retreat_option`・`_score_attack_option_choice`を追加する：

```python
from lucario_agent.combat import (
    AttackPlan,
    prize_count,
    pokemon_score,
    energy_score,
    _calc_attack_damage,
    calc_attack_plan,
    _score_retreat_option,
    _score_attack_option_choice,
)
```

- [ ] **Step 5: テストを実行し、成功を確認する**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 6: Commit**

```bash
git add src/lucario_agent/combat.py src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "refactor(lucario): RETREAT/ATTACKスコアリングを関数化しcombat.pyへ移動"
```

---

## Task 4: `energy_score`関連3件の実バグ修正

**Files:**
- Modify: `src/lucario_agent/combat.py`
- Modify: `src/lucario_agent/main.py`
- Test: `tests/test_lucario_agent.py`

**Interfaces:**
- Consumes: Task2の`combat.py`の`energy_score`
- Produces: `energy_score`のシグネチャ・呼び出し方は変更しない（内部ロジックのみ修正）

### 4-1. `energy_score`のMega_Lucario_ex/Riolu分岐への減点追加

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`TestEnergyScoreOgerponEx`クラス（162-188行目）の直後に、以下のテストクラスを追加する：

```python
class TestEnergyScoreNullifierPenaltyForLucarioLine:
    """energy_scoreのMega_Lucario_ex/Riolu分岐に、相手がex無効化持ちのときの減点があることを確認するテスト
    （Ogerpon_exには+150ボーナスがあるのに対応する減点が無かった実バグの回帰テスト）"""

    def test_mega_lucario_ex_penalised_when_op_active_nullifies_ex(self):
        p = make_pokemon(id=lm.Mega_Lucario_ex, energies=[])
        without_flag = lm.energy_score(p, False, False, op_active_nullifies_ex=False)
        with_flag    = lm.energy_score(p, False, False, op_active_nullifies_ex=True)
        assert with_flag < without_flag

    def test_riolu_penalised_when_op_active_nullifies_ex(self):
        p = make_pokemon(id=lm.Riolu, energies=[])
        without_flag = lm.energy_score(p, False, False, op_active_nullifies_ex=False)
        with_flag    = lm.energy_score(p, False, False, op_active_nullifies_ex=True)
        assert with_flag < without_flag

    def test_solrock_beats_mega_lucario_ex_when_op_active_nullifies_ex(self):
        """相手がex無効化持ちのとき、ソルロック(ex無効化されない非exアタッカー)が
        ベンチのメガルカリオex(ex無効化される)より優先される（実ログ86898758で
        確認された実バグの回帰テスト：メガルカリオexへエネルギーが偏り続けていた）"""
        solrock = make_pokemon(id=lm.Solrock, energies=[])
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[])
        solrock_score = lm.energy_score(solrock, False, False, op_active_nullifies_ex=True)
        lucario_score = lm.energy_score(lucario, False, False, op_active_nullifies_ex=True)
        assert solrock_score > lucario_score
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestEnergyScoreNullifierPenaltyForLucarioLine -v`
Expected: 3件ともFAIL（`with_flag < without_flag`が成り立たず`8101 == 8101`のような等号になる、または`solrock_score(8020) > lucario_score(8101)`が成り立たない）

- [ ] **Step 3: `energy_score`のMega_Lucario_ex/Riolu分岐に減点を追加する**

`src/lucario_agent/combat.py`の`energy_score`関数内、以下の部分：

```python
    elif pokemon.id in (Riolu, Mega_Lucario_ex):
        if pokemon.id == Mega_Lucario_ex:
            score += 1
        if energy_count < 2:
            score += 100
        if attacker1:
            score -= 50
```

を、以下に置き換える：

```python
    elif pokemon.id in (Riolu, Mega_Lucario_ex):
        if pokemon.id == Mega_Lucario_ex:
            score += 1
        if energy_count < 2:
            score += 100
        if attacker1:
            score -= 50
        if op_active_nullifies_ex:
            score -= 150  # 相手がex無効化持ちならOgerpon_ex/Solrockへ道を譲る
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestEnergyScoreNullifierPenaltyForLucarioLine tests/test_lucario_agent.py::TestEnergyScoreOgerponEx tests/test_lucario_agent.py::TestEnergyScore -v`
Expected: 全件PASS（既存の`TestEnergyScoreOgerponEx`・`TestEnergyScore`も回帰なくPASSすること）

- [ ] **Step 5: Commit**

```bash
git add src/lucario_agent/combat.py tests/test_lucario_agent.py
git commit -m "fix(lucario): energy_scoreのMega_Lucario_ex/Riolu分岐に相手ex無効化持ち時の減点を追加"
```

### 4-2. `_score_card_option`のATTACH_FROMケースの転送漏れ修正

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_lucario_agent.py`の`class TestLunaCycleAbilityScore:`（1174行目付近、Task4-1で追加したクラスの後にずれる）の直前に、以下のテストクラスを追加する：

```python
class TestScoreCardOptionAttachFrom:
    """SelectContext.ATTACH_FROM のスコアリング（_score_card_option）で
    op_active_nullifies_exが正しくenergy_scoreへ転送されることを確認するテスト"""

    def _score(self, pokemon, op_active_nullifies_ex):
        obs = MagicMock()
        my_state = make_player_state(bench=[pokemon])
        obs.current.players = [my_state, make_player_state()]
        option = Option(type=OptionType.CARD, area=lm.AreaType.BENCH, index=0, playerIndex=0)
        return lm._score_card_option(
            obs, option, context=lm.SelectContext.ATTACH_FROM, my_index=0,
            state=_make_state(), my_state=my_state,
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), attacker1=False,
            current_plan=lm.AttackPlan(), ability_used_flag=False,
            op_active_nullifies_ex=op_active_nullifies_ex,
        )

    def test_ogerpon_ex_gets_nullify_bonus_via_attach_from(self):
        """ATTACH_FROM経由でop_active_nullifies_exが転送され、
        オーガポンexのスコアが相手ex無効化持ち時に上がることを確認する
        （転送漏れの実バグの回帰テスト）"""
        ogerpon = make_pokemon(id=lm.Ogerpon_ex, energies=[])
        without_flag = self._score(ogerpon, op_active_nullifies_ex=False)
        with_flag    = self._score(ogerpon, op_active_nullifies_ex=True)
        assert with_flag > without_flag
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreCardOptionAttachFrom -v`
Expected: FAIL（`with_flag > without_flag`が成り立たず、両方とも同じ値になる。現状のATTACH_FROMケースは`op_active_nullifies_ex`引数を無視しているため）

- [ ] **Step 3: `_score_card_option`のATTACH_FROMケースを修正する**

`src/lucario_agent/main.py`の`_score_card_option`関数内、以下の部分：

```python
        case SelectContext.ATTACH_FROM:
            return energy_score(card, o.area == AreaType.ACTIVE, attacker1)
```

を、以下に置き換える：

```python
        case SelectContext.ATTACH_FROM:
            return energy_score(card, o.area == AreaType.ACTIVE, attacker1, op_active_nullifies_ex)
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreCardOptionAttachFrom -v`
Expected: PASS

Run: `uv run pytest -q`
Expected: 全件PASS（回帰確認）

- [ ] **Step 5: Commit**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "fix(lucario): ATTACH_FROMケースのop_active_nullifies_ex転送漏れを修正"
```

### 4-3. `_score_attach_option`のRock_Fighting_Energy無条件+500ボーナスの抑制

- [ ] **Step 1: 失敗するテストを書く**

Task4-2で追加した`TestScoreCardOptionAttachFrom`クラスの直後に、以下のテストクラスを追加する：

```python
class TestScoreAttachOptionRockFightingEnergy:
    """_score_attach_optionのRock_Fighting_Energy「アクティブ優先+500」ボーナスが、
    相手がex無効化持ち・対象がexのときは抑制されることを確認するテスト"""

    def _score(self, pokemon, op_active_nullifies_ex):
        obs = MagicMock()
        rock_energy_card = Card(id=lm.Rock_Fighting_Energy, serial=1, playerIndex=0)
        my_state = make_player_state(active_pokemon=pokemon, hand=[rock_energy_card])
        obs.current.players = [my_state, make_player_state()]
        option = Option(
            type=OptionType.ATTACH, area=lm.AreaType.HAND, index=0,
            inPlayArea=lm.AreaType.ACTIVE, inPlayIndex=0,
        )
        return lm._score_attach_option(
            obs, option, my_index=0, current_plan=lm.AttackPlan(),
            attacker1=False, op_active_nullifies_ex=op_active_nullifies_ex,
        )

    def test_bonus_suppressed_for_ex_attacker_when_op_active_nullifies_ex(self):
        """相手がex無効化持ちのとき、ex系アタッカー(メガルカリオex)への
        +500ボーナスが抑制される（実バグの回帰テスト）"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[])
        baseline = lm.energy_score(lucario, True, False, op_active_nullifies_ex=True)
        attach_score = self._score(lucario, op_active_nullifies_ex=True)
        assert attach_score == baseline

    def test_bonus_still_applies_when_op_active_nullifies_ex_is_false(self):
        """相手がex無効化持ちでなければ、ex系アタッカーにも+500ボーナスが
        従来通り付与される（回帰確認）"""
        lucario = make_pokemon(id=lm.Mega_Lucario_ex, energies=[])
        baseline = lm.energy_score(lucario, True, False, op_active_nullifies_ex=False)
        attach_score = self._score(lucario, op_active_nullifies_ex=False)
        assert attach_score == baseline + 500

    def test_bonus_still_applies_for_non_ex_attacker_even_when_nullifier_present(self):
        """対象が非ex(ソルロック)なら、相手がex無効化持ちでも+500ボーナスは
        維持される（回帰確認）"""
        solrock = make_pokemon(id=lm.Solrock, energies=[])
        baseline = lm.energy_score(solrock, True, False, op_active_nullifies_ex=True)
        attach_score = self._score(solrock, op_active_nullifies_ex=True)
        assert attach_score == baseline + 500
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreAttachOptionRockFightingEnergy -v`
Expected: `test_bonus_suppressed_for_ex_attacker_when_op_active_nullifies_ex`のみFAIL（`attach_score`が`baseline`ではなく`baseline + 500`になっているため）。他の2件は現状のコードでも既にPASSする（回帰確認用のため）

- [ ] **Step 3: `_score_attach_option`のRock_Fighting_Energyボーナスを条件付けする**

`src/lucario_agent/main.py`の`_score_attach_option`関数内、以下の部分：

```python
    if card.id == Rock_Fighting_Energy and o.inPlayArea == AreaType.ACTIVE:
        # Alakazam「ハンドパワー」はアクティブのポケモンのみを狙うため、
        # そのときアクティブの子を優先的に守る
        score += 500
```

を、以下に置き換える：

```python
    if card.id == Rock_Fighting_Energy and o.inPlayArea == AreaType.ACTIVE:
        # Alakazam「ハンドパワー」はアクティブのポケモンのみを狙うため、
        # そのときアクティブの子を優先的に守る。ただし相手がex無効化持ちで
        # 対象がexなら、この優先度がOgerpon_exへの優先度連動を上書きしてしまうため抑制する
        attacker_is_ex = card_table[pokemon.id].ex or card_table[pokemon.id].megaEx
        if not (op_active_nullifies_ex and attacker_is_ex):
            score += 500
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_lucario_agent.py::TestScoreAttachOptionRockFightingEnergy -v`
Expected: 全件PASS

Run: `uv run pytest -q`
Expected: 全件PASS（回帰確認）

- [ ] **Step 5: Commit**

```bash
git add src/lucario_agent/main.py tests/test_lucario_agent.py
git commit -m "fix(lucario): Rock_Fighting_Energyの無条件+500ボーナスをex無効化対面では抑制"
```

---

## Task 5: `EN_Card_Data.csv`とのエネルギー条件突き合わせテストの新設

**Files:**
- Create: `tests/test_lucario_attacker_energy_consistency.py`

**Interfaces:**
- Consumes: `data/competition/EN_Card_Data.csv`（列: `Card ID`, `Move Name`, `Cost`, `Damage`）
- Produces: なし（テストのみ、他タスクへの依存なし）

- [ ] **Step 1: テストファイルを新規作成する**

`/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/tests/test_lucario_attacker_energy_consistency.py`を以下の内容で作成する：

```python
"""combat.pyのcalc_attack_planが使う手打ちのエネルギー要求・ダメージ値を、
data/competition/EN_Card_Data.csvのカード原文と突き合わせるテスト。

libcg.so（macOSで動作しない）を経由せず、手元のCSVだけで検証できる。
このテストは今回の修正の正しさを保証するものではなく、将来
all_attack()/CSVベースのテーブル化に着手する際、新実装が現行の
手打ち値と同じ結果を再現できているかの回帰テストとして転用することを狙いとする。
"""
import csv
from pathlib import Path

import pytest

CSV_PATH = Path(__file__).parent.parent / "data" / "competition" / "EN_Card_Data.csv"


def _count_energy_symbols(cost: str) -> int:
    """Cost文字列（例: "{F}●●"）内のエネルギー記号数を数える。
    "{X}"ブロック1つ・"●"1文字がそれぞれ1エネルギーに相当する"""
    return cost.count("{") + cost.count("●")


def _load_moves() -> dict:
    """(Card ID, Move Name) -> {"energy": int, "damage": int} の辞書を作る。
    [Ability]/[Tera]接頭辞の行（技ではなく特性等）は除外する"""
    moves = {}
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            move_name = row["Move Name"]
            cost = row["Cost"]
            if move_name in ("n/a", "") or cost in ("n/a", ""):
                continue
            if move_name.startswith("[Ability]") or move_name.startswith("[Tera]"):
                continue
            damage_str = row["Damage"]
            damage = int(damage_str) if damage_str not in ("n/a", "") else 0
            moves[(int(row["Card ID"]), move_name)] = {
                "energy": _count_energy_symbols(cost),
                "damage": damage,
            }
    return moves


MOVES = _load_moves()


@pytest.mark.parametrize("card_id,move_name,expected_energy,expected_damage", [
    (678, "Aura Jab", 1, 130),    # Mega Lucario ex 通常技（combat.py: energy_required=1, base_damage=130）
    (678, "Mega Brave", 2, 270),  # Mega Lucario ex メガブレイブ（combat.py: energy_required=2, base_damage=270）
    (676, "Cosmic Beam", 1, 70),  # Solrock（combat.py: energy_required=1, base_damage=70）
    (117, "Demolish", 3, 140),    # Cornerstone Mask Ogerpon ex（combat.py: energy_required=3, base_damage=140）
])
def test_calc_attack_plan_hardcoded_values_match_card_data(card_id, move_name, expected_energy, expected_damage):
    move = MOVES[(card_id, move_name)]
    assert move["energy"] == expected_energy, (
        f"{move_name}(ID{card_id}): combat.pyの手打ちエネルギー要求={expected_energy} "
        f"だがEN_Card_Data.csvの実際の値は{move['energy']}"
    )
    assert move["damage"] == expected_damage, (
        f"{move_name}(ID{card_id}): combat.pyの手打ちダメージ={expected_damage} "
        f"だがEN_Card_Data.csvの実際の値は{move['damage']}"
    )
```

- [ ] **Step 2: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_lucario_attacker_energy_consistency.py -v`
Expected: 4件ともPASS（`data/competition/EN_Card_Data.csv`の実データが`combat.py`の手打ち値と一致することを確認済み：Aura Jab={F}/130、Mega Brave={F}{F}/270、Cosmic Beam={F}/70、Demolish={F}●●/140）

- [ ] **Step 3: Commit**

```bash
git add tests/test_lucario_attacker_energy_consistency.py
git commit -m "test(lucario): calc_attack_planの手打ちエネルギー値とEN_Card_Data.csvの突き合わせテストを追加"
```

---

## Task 6: 提出用ビルドスクリプトの新設

**Files:**
- Create: `scripts/build_lucario_submission_main.py`
- Create: `tests/test_build_lucario_submission_main.py`

**Interfaces:**
- Consumes: Task1〜4完了後の`src/lucario_agent/constants.py`・`combat.py`・`main.py`
- Produces: なし（スクリプトは標準出力またはファイルへ結合済みソースを出力するのみ）

- [ ] **Step 1: 失敗するテストを書く**

`/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/tests/test_build_lucario_submission_main.py`を以下の内容で作成する：

```python
"""scripts/build_lucario_submission_main.py が正しく単一ファイルを生成することを確認するテスト"""
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "build_lucario_submission_main.py"


def _run_build() -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, check=True, cwd=ROOT,
    )
    return result.stdout


def test_build_output_contains_agent_function():
    combined = _run_build()
    assert "def agent(" in combined


def test_build_output_has_no_syntax_errors():
    combined = _run_build()
    ast.parse(combined)  # SyntaxErrorなら例外を投げてテスト失敗になる


def test_build_output_has_no_internal_package_imports():
    """結合後は lucario_agent.* への相対importが残っていてはいけない
    （提出先には lucario_agent パッケージ自体が存在しないため）"""
    combined = _run_build()
    assert "from lucario_agent" not in combined
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_build_lucario_submission_main.py -v`
Expected: FAIL（`scripts/build_lucario_submission_main.py`が存在しないため`FileNotFoundError`または`subprocess`のエラー）

- [ ] **Step 3: ビルドスクリプトを作成する**

`/Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation/scripts/build_lucario_submission_main.py`を以下の内容で作成する：

```python
"""ルカリオexエージェントのKaggle提出用main.pyを生成するビルドスクリプト。

src/lucario_agent/constants.py + combat.py + main.py の内容を結合し、
lucario_agent内部の相対import文（結合後は不要になる）を除去した単一ファイルを
標準出力（または --out 指定時はファイル）へ出力する。

main.py/combat.py/constants.pyを直接編集した後はこのスクリプトを再実行し、
出力をKaggleノートブックの %%writefile main.py セルへコピペすること
（手動での複数ファイル辻褄合わせによるタイポ混入リスクを減らす狙い）。

Usage: uv run python scripts/build_lucario_submission_main.py [--out PATH]
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PACKAGE_DIR = ROOT / "src" / "lucario_agent"

# 結合順（依存関係の順）：constants → combat → main
SOURCE_FILES = ["constants.py", "combat.py", "main.py"]

# lucario_agent内部の相対import文（結合後は不要になるため除去）
INTERNAL_IMPORT_RE = re.compile(
    r"^from lucario_agent\.(constants|combat) import \([^)]*\)\n",
    re.MULTILINE,
)


def build() -> str:
    parts = []
    for filename in SOURCE_FILES:
        path = PACKAGE_DIR / filename
        source = path.read_text(encoding="utf-8")
        source = INTERNAL_IMPORT_RE.sub("", source)
        parts.append(f"# {'=' * 20} {filename} {'=' * 20}\n{source}")
    return "\n\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None, help="出力先ファイル（省略時は標準出力）")
    args = parser.parse_args()

    combined = build()

    if "def agent(" not in combined:
        print("エラー: 結合後のソースに agent() が含まれていません", file=sys.stderr)
        sys.exit(1)

    if args.out:
        args.out.write_text(combined, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(combined)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_build_lucario_submission_main.py -v`
Expected: 全件PASS

- [ ] **Step 5: 生成物を目視確認する**

Run: `uv run python scripts/build_lucario_submission_main.py | head -60`
Expected: `constants.py`の内容（カードID定数）から始まり、`combat.py`・`main.py`の内容が順に連結された出力が表示される。`from lucario_agent`という文字列が出力中に含まれないこと

- [ ] **Step 6: Commit**

```bash
git add scripts/build_lucario_submission_main.py tests/test_build_lucario_submission_main.py
git commit -m "feat(lucario): Kaggle提出用main.py生成ビルドスクリプトを追加"
```

---

## 完了確認

全タスク完了後、以下を実行してリポジトリ全体の健全性を最終確認する。

Run: `uv run pytest -q`
Expected: 全件PASS（新規追加分含め、リポジトリ全体で回帰なし）

Run: `uv run python scripts/build_lucario_submission_main.py --out /tmp/lucario_submission_main.py && python3 -c "import ast; ast.parse(open('/tmp/lucario_submission_main.py').read()); print('OK')"`
Expected: `OK`（構文エラーなくコンパイル可能な単一ファイルが生成される）

この後の提出フロー（Kaggleノートブックの`%%writefile main.py`セルへのコピペ、`deck.csv`アップロード、再提出）はユーザー側で実施する。
