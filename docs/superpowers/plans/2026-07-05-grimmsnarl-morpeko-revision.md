# グリムスナールexデッキ 第3次改修（モルペコ再導入）実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `decks/grimmsnarl_20260701.py` にイワパレス対策の非exアタッカー「マリィのモルペコ(649)」を再導入し、自傷ダメージ・展開遅延の原因だったユキワラシ(860)/ユキメノコ(104)/マシマシラ(112)を撤去、展開速度対策のギーマの一手(1230)・チェレン(1224)を新規採用する。あわせて`src/grimmsnarl_agent/main.py`を新カード構成に追従させる。

**Architecture:** デッキ定義ファイルの構成変更（Task 1）→ 削除カード（Froslass/Munkidori）の定数・ロジック撤去とFieldStateのベンチ追跡フィールドをMarnie's Morpeko用に置き換え（Task 2）→ Marnie's Morpekoへのエネルギー配分・攻撃スコアリングを機能ごとに2タスクに分割（Task 3〜4）→ ベンチ選択優先度の追従（Task 5）→ 新規トレーナーズ2種のPLAYスコアリングを1タスクずつ追加（Task 6〜7）→ 全体回帰確認とデッキCSV生成、実装サマリー作成（Task 8）。設計書は`docs/superpowers/specs/2026-07-05-grimmsnarl-morpeko-revision-design.md`。

**Tech Stack:** Python 3.12 / uv / pytest

## Global Constraints

- デッキは必ず合計60枚（ポケモン16体・トレーナーズ32枚・エネルギー12枚の内訳を維持）
- エネルギー以外のカードは1種4枚まで
- ACE SPECカード（Secret Box, ID 1092）は合計1枚まで（今回変更なし）
- 全コメント・ドキュメントは日本語（CLAUDE.md準拠）
- 各タスク終了時に`uv run pytest -q`で回帰なしを確認してからコミットする
- macOSの`sed -i`はバックアップ拡張子引数が必須のため`sed -i ''`の形で使う

---

## Task 1: デッキ構成をモルペコ再導入後の座組に更新する

**Files:**
- Modify: `tests/test_grimmsnarl_deck.py`
- Modify: `decks/grimmsnarl_20260701.py`

**Interfaces:**
- Consumes: `decks.grimmsnarl_20260701.DECK`（`list[tuple[int, int]]`）
- Produces: 新DECK構成（後続タスクのエージェントロジックが前提とするカードID: `649`=マリィのモルペコ3枚、`1230`=ギーマの一手2枚、`1224`=チェレン1枚。`860`/`104`/`112`は不在になる）

- [ ] **Step 1: `tests/test_grimmsnarl_deck.py`の`test_key_pokemon_present`を編集する**

現状:

```python
def test_key_pokemon_present():
    ids = {card_id for card_id, _ in DECK}
    assert 646 in ids, "Marnie's Impidimp が不在"
    assert 647 in ids, "Marnie's Morgrem が不在"
    assert 648 in ids, "Marnie's Grimmsnarl ex が不在"
    assert 112 in ids, "Munkidori が不在"
    assert 104 in ids, "Froslass が不在"
    assert 689 in ids, "Yveltal が不在"
```

変更後:

```python
def test_key_pokemon_present():
    ids = {card_id for card_id, _ in DECK}
    assert 646 in ids, "Marnie's Impidimp が不在"
    assert 647 in ids, "Marnie's Morgrem が不在"
    assert 648 in ids, "Marnie's Grimmsnarl ex が不在"
    assert 649 in ids, "Marnie's Morpeko が不在"
    assert 689 in ids, "Yveltal が不在"
```

- [ ] **Step 2: 同ファイルの`test_removed_pokemon_absent`を編集する（モルペコは今回再導入するため「削除されたはず」の対象から外す）**

現状:

```python
def test_removed_pokemon_absent():
    ids = {card_id for card_id, _ in DECK}
    assert 649 not in ids, "Marnie's Morpeko は今回の改修で削除されたはず"
    assert 66 not in ids, "Dudunsparce は今回の改修で削除されたはず"
    assert 305 not in ids, "Dunsparce は今回の改修で削除されたはず"
```

変更後:

```python
def test_removed_pokemon_absent():
    ids = {card_id for card_id, _ in DECK}
    assert 66 not in ids, "Dudunsparce は今回の改修で削除されたはず"
    assert 305 not in ids, "Dunsparce は今回の改修で削除されたはず"
```

- [ ] **Step 3: 同ファイルの末尾に以下のテストを追加する**

```python
def test_phase3_removed_pokemon_absent():
    ids = {card_id for card_id, _ in DECK}
    assert 860 not in ids, "Snorunt(ユキワラシ) は第3次改修で削除されたはず"
    assert 104 not in ids, "Froslass(ユキメノコ) は第3次改修で削除されたはず"
    assert 112 not in ids, "Munkidori(マシマシラ) は第3次改修で削除されたはず"


def test_morpeko_count():
    count = sum(c for i, c in DECK if i == 649)
    assert count == 3, "マリィのモルペコ(649)は3枚採用のはず"


def test_buddy_buddy_poffin_count_increased():
    count = sum(c for i, c in DECK if i == 1086)
    assert count == 3, "Buddy-Buddy Poffin(1086)は第3次改修で3枚に増量されたはず"


def test_grimsley_move_count():
    count = sum(c for i, c in DECK if i == 1230)
    assert count == 2, "ギーマの一手(1230)は2枚採用のはず"


def test_cheren_count():
    count = sum(c for i, c in DECK if i == 1224)
    assert count == 1, "チェレン(1224)は1枚採用のはず"
```

- [ ] **Step 4: テストが失敗することを確認する**

Run: `uv run pytest tests/test_grimmsnarl_deck.py -v -k "key_pokemon_present or phase3_removed or morpeko_count or buddy_buddy_poffin_count_increased or grimsley_move_count or cheren_count"`
Expected: `test_key_pokemon_present`（649がまだ不在）、`test_phase3_removed_pokemon_absent`（860/104/112がまだ存在）、`test_morpeko_count`（0枚）、`test_buddy_buddy_poffin_count_increased`（まだ2枚）、`test_grimsley_move_count`（0枚）、`test_cheren_count`（0枚）が全てFAIL

- [ ] **Step 5: `decks/grimmsnarl_20260701.py`を編集する**

ファイル冒頭のコメント（1〜9行目）に以下を追記する:

```python
# 第3次改修（2026-07-05）: イワパレス（特性「しんぴのいしやど」で相手ex技を無効化）への
#   対抗策として非exアタッカーのマリィのモルペコ(649)を再導入。あわせて自傷ダメージ・
#   展開遅延の原因だったユキワラシ(860)/ユキメノコ(104)/マシマシラ(112)を撤去し、
#   展開速度対策のギーマの一手(1230)・チェレン(1224)を新規採用。
#   設計書: docs/superpowers/specs/2026-07-05-grimmsnarl-morpeko-revision-design.md
```

`DECK`定義全体を以下に置き換える:

```python
DECK = [
    # --- ポケモン: 16体 ---
    (646,  3),   # Marnie's Impidimp（進化元・Filchで初動ドロー・70HP）
    (647,  2),   # Marnie's Morgrem（進化中継・Rare Candy未引き時の保険を強化）
    (648,  3),   # Marnie's Grimmsnarl ex（メインアタッカー）
    (649,  3),   # Marnie's Morpeko（非exアタッカー。スパイキーホイール：20+悪エネ×40。
                 #                  イワパレスの特性「しんぴのいしやど」（exの技を受けない）を回避する要）
    (343,  1),   # Shaymin（特性: 自分のルール無しベンチポケモンへのダメージを無効化）
    (689,  2),   # Yveltal（わしづかみ：相手を次の番にげられなくする。ガチグマの代替）
    (140,  2),   # Fezandipiti ex（キチキギスex。210HP高耐久・悪エネで実際に攻撃可能。
                 #                特性「さかてにとる」はバトル場条件なしで安全に発動）

    # --- トレーナーズ: 32枚 ---
    (1152, 4),   # Poké Pad（ポケモンサーチ）
    (1079, 3),   # Rare Candy（Impidimp→Grimmsnarl ex 一気進化）
    (1086, 3),   # Buddy-Buddy Poffin（低HP基本ポケモンをベンチ展開）
    (1097, 2),   # Night Stretcher（トラッシュ回収・山札を減らさない）
    (1227, 4),   # Lillie's Determination（手札リフレッシュ）
    (1182, 3),   # Boss's Orders（ベンチの弱ったポケモンを強制的にバトル場へ・KOを補助）
    (1259, 3),   # Spikemuth Gym（毎ターンMarnie's系サーチ）
    (1116, 2),   # Energy Switch（基本エネルギーの付け替え）
    (1092, 1),   # Secret Box（ACE SPEC・手札3枚トラッシュでグッズ/どうぐ/サポートをサーチ）
    (1174, 1),   # Air Balloon（にげるためのエネルギーを2個軽減）
    (1219, 3),   # Team Rocket's Petrel（トレーナーズ全般をサーチ）
    (1230, 2),   # Grimsley's Move（ギーマの一手。山札上7枚から悪ポケモン1体をベンチに出す。展開速度対策）
    (1224, 1),   # Cheren（チェレン。山札3枚ドロー。相手非干渉の安全牌）

    # --- エネルギー: 12枚 ---
    (7,   12),   # Basic {D} Energy
]
```

- [ ] **Step 6: テストが通ることを確認する**

Run: `uv run pytest tests/test_grimmsnarl_deck.py -v`
Expected: 全件PASS

- [ ] **Step 7: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add decks/grimmsnarl_20260701.py tests/test_grimmsnarl_deck.py
git commit -m "$(cat <<'EOF'
feat: グリムスナールexデッキにマリィのモルペコを再導入

イワパレス（相手exの技を無効化する特性）への対抗策として非exアタッカーの
マリィのモルペコ(649)を3枚採用。自傷ダメージ・展開遅延の原因だった
ユキワラシ/ユキメノコ/マシマシラを撤去し、Buddy-Buddy Poffin増量と
ギーマの一手・チェレンの新規採用で展開速度を補強する。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Froslass/Munkidoriを撤去しFieldStateのベンチ追跡をMarnie's Morpeko用に置き換える

**Files:**
- Modify: `src/grimmsnarl_agent/main.py`（定数・`SUPPORT_ONLY_IDS`・`FieldState`・`_collect_field_state`・`_score_play`・`_score_attach`・`_score_card_option`・`ABILITY`分岐）
- Modify: `tests/test_grimmsnarl_agent.py`

**Interfaces:**
- Consumes: なし
- Produces: `gm.Marnie_Morpeko = 649`（Task 3〜5で使用）、`gm.Grimsley_Move = 1230`・`gm.Cheren = 1224`（Task 6〜7で使用）、`FieldState.morpeko_bench_idx` / `FieldState.morpeko_energy_count`（Task 3〜5が前提とするフィールド）。`gm.Munkidori`/`gm.Froslass`/`FieldState.munkidori_bench_idx`は以後存在しない

この変更は「Munkidori/Froslassの完全撤去」と「FieldStateのベンチ追跡フィールドのリネーム（`munkidori_bench_idx`→`morpeko_bench_idx`）」が同一データクラスに対する不可分な変更のため、新しい振る舞いのテストではなくリファクタリングとして扱う（main.py編集→テスト追従→全体確認の順で進める）。

- [ ] **Step 1: `src/grimmsnarl_agent/main.py`の定数ブロック（11〜30行目付近）を編集する**

現状:

```python
# ==================== カードID定数 ====================
# 20260702改修：Morpeko/Dudunsparce/Dunsparce/Dawn/Xerosic's Machinations/
# Energy Recycler/Hero's Capeはデッキから削除済みのため定数ごと削除。
# 代わりにTeam Rocket's Petrelを追加（docs/superpowers/specs/2026-07-02-grimmsnarl-deck-revision-design.md）
# フェーズB改修（2026-07-03）：Budew/Tatsugiri/Psyduckはデッキから削除済みのため定数ごと削除。
# 代わりにFezandipiti_exを追加（docs/superpowers/specs/2026-07-03-grimmsnarl-deck-revision-phase-b-design.md）
Impidimp       = 646
Morgrem        = 647
Grimmsnarl_ex  = 648
Munkidori      = 112
Froslass       = 104
Shaymin        = 343
Yveltal        = 689
Fezandipiti_ex = 140

# 特性が「場にいれば無条件で発動」する専用要員。バトル場に出す前提のカードではないため、
# SWITCH/TO_ACTIVEでは他に選択肢がある限り選ばれないよう明確に減点する。
# Munkidoriは特性発動にエネルギー要求があり攻撃も可能なため対象外。
# Fezandipiti_exは210HPの実戦アタッカーであり特性もバトル場条件なしのため対象外。
SUPPORT_ONLY_IDS = {Froslass, Shaymin}
```

変更後:

```python
# ==================== カードID定数 ====================
# 20260702改修：Morpeko/Dudunsparce/Dunsparce/Dawn/Xerosic's Machinations/
# Energy Recycler/Hero's Capeはデッキから削除済みのため定数ごと削除。
# 代わりにTeam Rocket's Petrelを追加（docs/superpowers/specs/2026-07-02-grimmsnarl-deck-revision-design.md）
# フェーズB改修（2026-07-03）：Budew/Tatsugiri/Psyduckはデッキから削除済みのため定数ごと削除。
# 代わりにFezandipiti_exを追加（docs/superpowers/specs/2026-07-03-grimmsnarl-deck-revision-phase-b-design.md）
# 第3次改修（2026-07-05）：Froslass/Snorunt/Munkidoriはデッキから削除済みのため定数ごと削除。
# 代わりにMarnie_Morpeko/Grimsley_Move/Cherenを追加
# （docs/superpowers/specs/2026-07-05-grimmsnarl-morpeko-revision-design.md）
Impidimp       = 646
Morgrem        = 647
Grimmsnarl_ex  = 648
Shaymin        = 343
Yveltal        = 689
Fezandipiti_ex = 140
Marnie_Morpeko = 649
Grimsley_Move  = 1230
Cheren         = 1224

# 特性が「場にいれば無条件で発動」する専用要員。バトル場に出す前提のカードではないため、
# SWITCH/TO_ACTIVEでは他に選択肢がある限り選ばれないよう明確に減点する。
# Fezandipiti_exは210HPの実戦アタッカーであり特性もバトル場条件なしのため対象外。
# Marnie_Morpekoは非exアタッカー（スパイキーホイール）であり対象外。
SUPPORT_ONLY_IDS = {Shaymin}
```

- [ ] **Step 2: `FieldState`データクラス定義を編集する**

現状:

```python
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
```

変更後:

```python
@dataclass
class FieldState:
    """毎ターン計算されるフィールド状態"""
    field_counts:            defaultdict
    hand_counts:             defaultdict
    discard_counts:          defaultdict
    grimmsnarl_active:       bool
    grimmsnarl_energy_count: int
    impidimp_bench_idx:      int
    morpeko_bench_idx:       int
    morpeko_energy_count:    int
    rare_candy_in_hand:      bool
    my_active_hp:            int
    op_active_hp:            int
    op_bench_hp:             list
```

- [ ] **Step 3: `_collect_field_state`関数を編集する**

現状:

```python
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
        if card is None:
            continue
        hand_counts[card.id] += 1

    for card in my_state.discard:
        if card is None:
            continue
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
```

変更後:

```python
def _collect_field_state(my_state, op_state) -> FieldState:
    """バトル場・ベンチ・手札・トラッシュから行動判断に必要な状態を収集する"""
    field_counts   = defaultdict(int)
    hand_counts    = defaultdict(int)
    discard_counts = defaultdict(int)

    grimmsnarl_active       = False
    grimmsnarl_energy_count = 0
    impidimp_bench_idx      = -1
    morpeko_bench_idx       = -1
    morpeko_energy_count    = 0
    my_active_hp            = 0

    for card in my_state.active:
        if card is None:
            continue
        field_counts[card.id] += 1
        my_active_hp = card.hp
        if card.id == Grimmsnarl_ex:
            grimmsnarl_active       = True
            grimmsnarl_energy_count = len(card.energies)
        elif card.id == Marnie_Morpeko:
            morpeko_energy_count = len(card.energies)

    for i, card in enumerate(my_state.bench):
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id == Impidimp and impidimp_bench_idx == -1:
            impidimp_bench_idx = i
        elif card.id == Marnie_Morpeko and morpeko_bench_idx == -1:
            morpeko_bench_idx = i

    for card in my_state.hand:
        if card is None:
            continue
        hand_counts[card.id] += 1

    for card in my_state.discard:
        if card is None:
            continue
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
        morpeko_bench_idx=morpeko_bench_idx,
        morpeko_energy_count=morpeko_energy_count,
        rare_candy_in_hand=rare_candy_in_hand,
        my_active_hp=my_active_hp,
        op_active_hp=op_active_hp,
        op_bench_hp=op_bench_hp,
    )
```

- [ ] **Step 4: `_score_play`内のBuddy_Buddy_Poffin判定を編集する（FieldStateのフィールド名変更に追従）**

現状:

```python
    if card_id == Buddy_Buddy_Poffin:
        needs_bench = fs.impidimp_bench_idx == -1 or fs.munkidori_bench_idx == -1
        return 8000 if needs_bench else 2000
```

変更後:

```python
    if card_id == Buddy_Buddy_Poffin:
        needs_bench = fs.impidimp_bench_idx == -1 or fs.morpeko_bench_idx == -1
        return 8000 if needs_bench else 2000
```

- [ ] **Step 5: `_score_attach`からMunkidori分岐を削除する**

現状:

```python
        if pokemon.id == Fezandipiti_ex and energy_count < 3 and grimmsnarl_ready_or_absent:
            # クルーエルアローの実際のコストは無色3（本デッキは全て悪エネルギーのため
            # 悪3枚で支払える）
            return 5000 - energy_count * 500
        if pokemon.id == Munkidori and energy_count == 0 and grimmsnarl_ready_or_absent:
            # アドレナブレインはエネルギー1枚で発動する
            return 4000
        return -1
    return 3000
```

変更後:

```python
        if pokemon.id == Fezandipiti_ex and energy_count < 3 and grimmsnarl_ready_or_absent:
            # クルーエルアローの実際のコストは無色3（本デッキは全て悪エネルギーのため
            # 悪3枚で支払える）
            return 5000 - energy_count * 500
        return -1
    return 3000
```

- [ ] **Step 6: `_score_card_option`の`TO_BENCH | TO_HAND`分岐からMunkidori分岐を削除する**

現状:

```python
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
```

変更後:

```python
        case SelectContext.TO_BENCH | SelectContext.TO_HAND:
            if not isinstance(card, Pokemon):
                return 10
            if card.id == Grimmsnarl_ex:
                return 100 if fs.field_counts[Grimmsnarl_ex] == 0 else 10
            if card.id == Impidimp:
                return 60 if fs.field_counts[Impidimp] < 2 else 20
            return 10
```

- [ ] **Step 7: `agent()`内`OptionType.ABILITY`分岐を編集する**

現状:

```python
                    score = 2500 if card.id in (Munkidori, Fezandipiti_ex) else 1200
```

変更後:

```python
                    score = 2500 if card.id == Fezandipiti_ex else 1200
```

- [ ] **Step 8: `tests/test_grimmsnarl_agent.py`の`mock_card_table`フィクスチャからMunkidoriの行を削除する**

現状:

```python
        gm.Munkidori:       MockCardData(cardId=gm.Munkidori, attacks=[9104]),
```
↓ この行を削除

- [ ] **Step 9: `munkidori_bench_idx`を`morpeko_bench_idx`にリネームする（sedで一括置換）**

Run:
```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
sed -i '' 's/munkidori_bench_idx/morpeko_bench_idx/g' tests/test_grimmsnarl_agent.py
```
Expected: 出力なし（サイレント成功）。ファイル内の`munkidori_bench_idx`が全て`morpeko_bench_idx`に置き換わる

- [ ] **Step 10: リネーム後、`FieldState`の生コンストラクタ呼び出し8箇所に`morpeko_energy_count=0,`を追加する（sedで一括置換）**

Run:
```bash
sed -i '' 's/morpeko_bench_idx=-1,/morpeko_bench_idx=-1, morpeko_energy_count=0,/g' tests/test_grimmsnarl_agent.py
```
Expected: 出力なし。`morpeko_bench_idx=-1,`パターンを持つ8箇所（`_make_fs`系ヘルパーのデフォルト辞書2箇所＋`FieldState(...)`生コンストラクタ6箇所）にのみ`morpeko_energy_count=0,`が追加される。`assert fs.morpeko_bench_idx == 0`（アサーション行）と`self._make_fs(impidimp_bench_idx=0, morpeko_bench_idx=1)`（ヘルパー呼び出しでの上書き）はパターンが一致しないため変更されない

- [ ] **Step 11: `TestCollectFieldState.test_munkidori_bench_detected`を`test_morpeko_bench_detected`にリネームし、Marnie_Morpekoを使うよう書き換える**

現状（Step 9のsed適用後）:

```python
    def test_munkidori_bench_detected(self):
        munkidori = make_pokemon(id=gm.Munkidori, energies=[7])
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex),
            bench=[munkidori],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.morpeko_bench_idx == 0
```

変更後:

```python
    def test_morpeko_bench_detected(self):
        morpeko = make_pokemon(id=gm.Marnie_Morpeko, energies=[7])
        my_ps = make_player_state(
            active_pokemon=make_pokemon(id=gm.Grimmsnarl_ex),
            bench=[morpeko],
        )
        op_ps = make_player_state(active_pokemon=make_pokemon(id=1, hp=200))
        fs = gm._collect_field_state(my_ps, op_ps)
        assert fs.morpeko_bench_idx == 0
```

- [ ] **Step 12: `TestScoreAttach`クラスからMunkidori専用テスト3件を削除する**

以下の3メソッドを削除する（Munkidoriが存在しなくなるため、対応するモルペコ向けテストはTask 3で追加する）:

```python
    def test_basic_d_energy_to_munkidori_allowed_when_grimmsnarl_attack_ready(self):
        """グリムスナールexがシャドーバレット分（2エネ）を確保済みなら、余剰エネルギーをマシマシラに貼れること"""
        munkidori = make_pokemon(id=gm.Munkidori, energies=[])
        fs = self._make_fs_with_grimmsnarl_energy(2)
        score = gm._score_attach(munkidori, AreaType.BENCH, gm.Basic_D_Energy, fs)
        assert score > 0

    def test_basic_d_energy_to_munkidori_denied_when_grimmsnarl_not_attack_ready(self):
        """グリムスナールexがまだ攻撃可能エネルギー未確保なら、マシマシラへの分配は認めないこと"""
        munkidori = make_pokemon(id=gm.Munkidori, energies=[])
        fs = self._make_fs_with_grimmsnarl_energy(0)
        assert gm._score_attach(munkidori, AreaType.BENCH, gm.Basic_D_Energy, fs) == -1

    def test_basic_d_energy_to_munkidori_denied_when_already_has_energy(self):
        """マシマシラのアドレナブレインはエネルギー1枚で発動するため、2枚目以降は不要"""
        munkidori = make_pokemon(id=gm.Munkidori, energies=[7])
        fs = self._make_fs_with_grimmsnarl_energy(2)
        assert gm._score_attach(munkidori, AreaType.BENCH, gm.Basic_D_Energy, fs) == -1
```

- [ ] **Step 13: `TestScoreCardOption`クラスから`test_switch_munkidori_not_penalized_like_support_only_pokemon`を削除する**

```python
    def test_switch_munkidori_not_penalized_like_support_only_pokemon(self):
        """マシマシラは特性にエネルギー要求があり攻撃も可能なため、特性専用ポケモンほど減点されないこと"""
        shaymin   = make_pokemon(id=gm.Shaymin, hp=100)
        munkidori = make_pokemon(id=gm.Munkidori, hp=100)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), bench=[shaymin, munkidori])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs()
        o_shaymin   = Option(type=OptionType.CARD, area=AreaType.BENCH, index=0, playerIndex=0)
        o_munkidori = Option(type=OptionType.CARD, area=AreaType.BENCH, index=1, playerIndex=0)
        score_shaymin   = gm._score_card_option(obs, o_shaymin, SelectContext.SWITCH, 0, fs, defaultdict(int))
        score_munkidori = gm._score_card_option(obs, o_munkidori, SelectContext.SWITCH, 0, fs, defaultdict(int))
        assert score_munkidori > score_shaymin
```
↓ このメソッド全体を削除

- [ ] **Step 14: `TestAgent`クラスから`test_ability_fires_before_non_lethal_attack`を削除する（Munkidoriの`ABILITY`優先度テスト。Fezandipiti_ex版は残す）**

```python
    def test_ability_fires_before_non_lethal_attack(self):
        """アビリティ（Munkidori）は無償で使えるため、確定KOでない攻撃より優先して
        毎ターン使用されること（Adrena-Brainの仕様意図の挙動保証）"""
        munkidori = make_pokemon(id=gm.Munkidori, energies=[7])
        grimmsnarl = make_pokemon(id=gm.Grimmsnarl_ex, hp=300, max_hp=320, energies=[7, 7])
        my_ps = make_player_state(active_pokemon=grimmsnarl, bench=[munkidori])
        # op_state を指定しない場合、make_main_obs のデフォルトは hp=200（>180、非確定KO）
        options = [
            Option(type=OptionType.ABILITY, area=AreaType.BENCH, index=0),
            Option(type=OptionType.ATTACK, attackId=9102),  # Shadow_Bullet_ID (mocked)、非確定KO
        ]
        obs_dict = make_main_obs(my_state=my_ps, options=options)
        result = gm.agent(obs_dict)
        assert options[result[0]].type == OptionType.ABILITY
```
↓ このメソッド全体を削除

- [ ] **Step 15: リポジトリ全体のテストを実行し回帰がないことを確認する**

Run: `uv run pytest -q`
Expected: 全件PASS（`gm.Munkidori`/`gm.Froslass`/`FieldState.munkidori_bench_idx`への残存参照があればここでエラーになるはずだが、Step 1〜14で洗い出し済み）

- [ ] **Step 16: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "$(cat <<'EOF'
refactor: Froslass/Munkidoriを撤去しベンチ追跡をMarnie's Morpeko用に置き換え

デッキから撤去したFroslass/Munkidoriの定数・スコアリング分岐を削除。
FieldStateのmunkidori_bench_idxをmorpeko_bench_idxにリネームし、
モルペコの装着エネルギー数を追跡するmorpeko_energy_countを新規追加。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Marnie's Morpekoへのエネルギー配分ロジックを追加する

**Files:**
- Modify: `src/grimmsnarl_agent/main.py`（`_score_attach`）
- Modify: `tests/test_grimmsnarl_agent.py`（`TestScoreAttach`クラスにテスト追加）

**Interfaces:**
- Consumes: `gm.Marnie_Morpeko`（Task 2で追加済み）、`FieldState.grimmsnarl_energy_count`（既存）
- Produces: `_score_attach(pokemon, area, card_id, fs)` がMarnie's Morpekoを認識するようになる（Task 4の攻撃判断が前提とする「モルペコにエネルギーが配分され得る」という挙動）

- [ ] **Step 1: `tests/test_grimmsnarl_agent.py`の`TestScoreAttach`クラス末尾に以下のテストを追加する**

```python
    def test_basic_d_energy_to_morpeko_allowed_when_grimmsnarl_attack_ready(self):
        """グリムスナールexがシャドーバレット分（2エネ）を確保済みなら、余剰エネルギーをモルペコに貼れること"""
        morpeko = make_pokemon(id=gm.Marnie_Morpeko, energies=[])
        fs = self._make_fs_with_grimmsnarl_energy(2)
        score = gm._score_attach(morpeko, AreaType.BENCH, gm.Basic_D_Energy, fs)
        assert score > 0

    def test_basic_d_energy_to_morpeko_denied_when_grimmsnarl_not_attack_ready(self):
        """グリムスナールexがまだ攻撃可能エネルギー未確保なら、モルペコへの分配は認めないこと"""
        morpeko = make_pokemon(id=gm.Marnie_Morpeko, energies=[])
        fs = self._make_fs_with_grimmsnarl_energy(0)
        assert gm._score_attach(morpeko, AreaType.BENCH, gm.Basic_D_Energy, fs) == -1

    def test_basic_d_energy_to_morpeko_still_positive_with_many_energies(self):
        """スパイキーホイールは装着エネルギー数に応じてダメージが際限なく伸びるため、
        Fezandipiti_exの3枚上限とは異なり、複数枚ついていても配分を認め続けること"""
        morpeko = make_pokemon(id=gm.Marnie_Morpeko, energies=[7, 7, 7, 7])
        fs = self._make_fs_with_grimmsnarl_energy(2)
        assert gm._score_attach(morpeko, AreaType.BENCH, gm.Basic_D_Energy, fs) > 0

    def test_morpeko_energy_priority_lower_than_grimmsnarl(self):
        """モルペコへの配分スコアは、グリムスナールex本体への配分スコアを上回らないこと
        （メインアタッカーの攻撃を絶対に阻害しない既存方針の維持）"""
        grimmsnarl_low = make_pokemon(id=gm.Grimmsnarl_ex, energies=[])
        morpeko        = make_pokemon(id=gm.Marnie_Morpeko, energies=[])
        fs = self._make_fs_with_grimmsnarl_energy(2)
        score_grimmsnarl = gm._score_attach(grimmsnarl_low, AreaType.ACTIVE, gm.Basic_D_Energy, fs)
        score_morpeko    = gm._score_attach(morpeko, AreaType.BENCH, gm.Basic_D_Energy, fs)
        assert score_grimmsnarl > score_morpeko

    def test_basic_d_energy_to_morpeko_allowed_when_grimmsnarl_absent_from_field(self):
        """グリムスナールexが場に不在（きぜつ等）でも、モルペコへのエネルギー配分を
        止めないこと（次善アタッカーが最も必要な場面であるため）"""
        morpeko = make_pokemon(id=gm.Marnie_Morpeko, energies=[])
        fs = gm.FieldState(
            field_counts=defaultdict(int), hand_counts=defaultdict(int),
            discard_counts=defaultdict(int), grimmsnarl_active=False,
            grimmsnarl_energy_count=0, impidimp_bench_idx=-1,
            morpeko_bench_idx=-1, morpeko_energy_count=0, rare_candy_in_hand=False,
            my_active_hp=200, op_active_hp=200, op_bench_hp=[],
        )
        score = gm._score_attach(morpeko, AreaType.ACTIVE, gm.Basic_D_Energy, fs)
        assert score > 0
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k morpeko`
Expected: 上記5件がFAIL（`_score_attach`はまだMarnie's Morpekoを認識せず、常に`-1`を返すため。`test_morpeko_bench_detected`は既にTask 2でPASS済みなので対象外）

- [ ] **Step 3: `src/grimmsnarl_agent/main.py`の`_score_attach`を編集する**

現状:

```python
        if pokemon.id == Fezandipiti_ex and energy_count < 3 and grimmsnarl_ready_or_absent:
            # クルーエルアローの実際のコストは無色3（本デッキは全て悪エネルギーのため
            # 悪3枚で支払える）
            return 5000 - energy_count * 500
        return -1
    return 3000
```

変更後:

```python
        if pokemon.id == Fezandipiti_ex and energy_count < 3 and grimmsnarl_ready_or_absent:
            # クルーエルアローの実際のコストは無色3（本デッキは全て悪エネルギーのため
            # 悪3枚で支払える）
            return 5000 - energy_count * 500
        if pokemon.id == Marnie_Morpeko and grimmsnarl_ready_or_absent:
            # スパイキーホイールは装着した悪エネルギー数に比例して際限なくダメージが伸びる
            # （20+悪エネルギー×40）ため上限を設けず、グリムスナールexの攻撃分確保後は
            # 積極的に投資する
            return 4500 - energy_count * 200
        return -1
    return 3000
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k morpeko`
Expected: 全件PASS

- [ ] **Step 5: リポジトリ全体のテストを実行し回帰がないことを確認する**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 6: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "$(cat <<'EOF'
feat: マリィのモルペコへの基本エネルギー配分ロジックを追加

グリムスナールexの攻撃分（2エネ）確保後、余剰の基本エネルギーを
モルペコ（スパイキーホイール：20+悪エネ×40、上限なし）にも配分できるようにする。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: モルペコのスパイキーホイール攻撃スコアリングを追加する

**Files:**
- Modify: `src/grimmsnarl_agent/main.py`（`_build_card_table`, `Shadow_Bullet_ID`宣言部, `_score_attack`）
- Modify: `tests/test_grimmsnarl_agent.py`（`mock_card_table`フィクスチャ、`TestScoreAttack`クラス）

**Interfaces:**
- Consumes: `gm.Marnie_Morpeko`（Task 2）、`FieldState.morpeko_energy_count`（Task 2）、`FieldState.op_active_hp`（既存）
- Produces: `gm.Spiky_Wheel_ID`（実行時に`_build_card_table()`が設定。テストでは`Shadow_Bullet_ID`/`Cruel_Arrow_ID`と同様に直接monkeypatchする）

- [ ] **Step 1: `tests/test_grimmsnarl_agent.py`冒頭の`mock_card_table`フィクスチャを編集する**

現状:

```python
@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    table = {
        gm.Impidimp:        MockCardData(cardId=gm.Impidimp, attacks=[9101]),
        gm.Morgrem:         MockCardData(cardId=gm.Morgrem, stage1=True, attacks=[9101]),
        gm.Grimmsnarl_ex:   MockCardData(cardId=gm.Grimmsnarl_ex, stage2=True, ex=True, attacks=[9102]),
        gm.Fezandipiti_ex:  MockCardData(cardId=gm.Fezandipiti_ex, ex=True, attacks=[9105]),
        gm.Rare_Candy:      MockCardData(cardId=gm.Rare_Candy, cardType=CardType.ITEM),
        gm.Buddy_Buddy_Poffin: MockCardData(cardId=gm.Buddy_Buddy_Poffin, cardType=CardType.ITEM),
        gm.Lillie_Determination: MockCardData(cardId=gm.Lillie_Determination, cardType=CardType.SUPPORTER),
        gm.Team_Rocket_Petrel: MockCardData(cardId=gm.Team_Rocket_Petrel, cardType=CardType.SUPPORTER),
        gm.Basic_D_Energy:  MockCardData(cardId=gm.Basic_D_Energy, cardType=CardType.BASIC_ENERGY),
    }
    monkeypatch.setattr(gm, "card_table", table)
    monkeypatch.setattr(gm, "Shadow_Bullet_ID", 9102)
    monkeypatch.setattr(gm, "Cruel_Arrow_ID", 9105)
    return table
```

変更後:

```python
@pytest.fixture(autouse=True)
def mock_card_table(monkeypatch):
    table = {
        gm.Impidimp:        MockCardData(cardId=gm.Impidimp, attacks=[9101]),
        gm.Morgrem:         MockCardData(cardId=gm.Morgrem, stage1=True, attacks=[9101]),
        gm.Grimmsnarl_ex:   MockCardData(cardId=gm.Grimmsnarl_ex, stage2=True, ex=True, attacks=[9102]),
        gm.Fezandipiti_ex:  MockCardData(cardId=gm.Fezandipiti_ex, ex=True, attacks=[9105]),
        gm.Marnie_Morpeko:  MockCardData(cardId=gm.Marnie_Morpeko, attacks=[9106]),
        gm.Rare_Candy:      MockCardData(cardId=gm.Rare_Candy, cardType=CardType.ITEM),
        gm.Buddy_Buddy_Poffin: MockCardData(cardId=gm.Buddy_Buddy_Poffin, cardType=CardType.ITEM),
        gm.Lillie_Determination: MockCardData(cardId=gm.Lillie_Determination, cardType=CardType.SUPPORTER),
        gm.Team_Rocket_Petrel: MockCardData(cardId=gm.Team_Rocket_Petrel, cardType=CardType.SUPPORTER),
        gm.Basic_D_Energy:  MockCardData(cardId=gm.Basic_D_Energy, cardType=CardType.BASIC_ENERGY),
    }
    monkeypatch.setattr(gm, "card_table", table)
    monkeypatch.setattr(gm, "Shadow_Bullet_ID", 9102)
    monkeypatch.setattr(gm, "Cruel_Arrow_ID", 9105)
    monkeypatch.setattr(gm, "Spiky_Wheel_ID", 9106)
    return table
```

- [ ] **Step 2: `TestScoreAttack`クラス末尾に以下のテストを追加する**

```python
    def test_spiky_wheel_non_lethal_score(self):
        fs = self._make_fs(op_hp=300)
        assert gm._score_attack(9106, fs) == 2000  # Spiky_Wheel_ID (mocked)、エネ0枚(20ダメ)では確定KOでない

    def test_spiky_wheel_lethal_scores_higher_than_non_lethal(self):
        """装着エネルギー数によるダメージ（20+40×枚数）が相手HP以上（確定KO）なら、
        非確定KO時よりスコアが高くなること"""
        fs_lethal = self._make_fs(op_hp=100)
        fs_lethal.morpeko_energy_count = 2  # 20+40*2=100ダメ、ちょうど確定KO
        fs_non_lethal = self._make_fs(op_hp=300)
        fs_non_lethal.morpeko_energy_count = 2
        assert gm._score_attack(9106, fs_lethal) > gm._score_attack(9106, fs_non_lethal)

    def test_spiky_wheel_lethal_scores_higher_than_retreat(self):
        fs = self._make_fs(op_hp=100)
        fs.morpeko_energy_count = 2
        assert gm._score_attack(9106, fs) == 5000
        assert gm._score_attack(9106, fs) > 3000  # RETREATのスコア（agent()内でインライン計算）
```

- [ ] **Step 3: テストが失敗することを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k spiky_wheel`
Expected: 3件すべてFAIL（`_score_attack`は`9106`を未知の攻撃として扱い、常にデフォルトの`1000`を返すため）

- [ ] **Step 4: `src/grimmsnarl_agent/main.py`のアタックID宣言部と`_build_card_table`を編集する**

現状:

```python
# ==================== アタックID（_build_card_table で設定）====================
Shadow_Bullet_ID: int = 0
Cruel_Arrow_ID: int = 0

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築し、攻撃IDも設定する"""
    global card_table, Shadow_Bullet_ID, Cruel_Arrow_ID
    if not card_table:
        card_table       = {c.cardId: c for c in all_card_data()}
        grimmsnarl_data  = card_table[Grimmsnarl_ex]
        Shadow_Bullet_ID = grimmsnarl_data.attacks[0]  # Shadow Bullet
        fezandipiti_data = card_table[Fezandipiti_ex]
        Cruel_Arrow_ID   = fezandipiti_data.attacks[0]  # Cruel Arrow
    return card_table
```

変更後:

```python
# ==================== アタックID（_build_card_table で設定）====================
Shadow_Bullet_ID: int = 0
Cruel_Arrow_ID: int = 0
Spiky_Wheel_ID: int = 0

# ==================== カードメタデータ（遅延初期化）====================
card_table: dict = {}


def _build_card_table() -> dict:
    """card_table を初回のみ構築し、攻撃IDも設定する"""
    global card_table, Shadow_Bullet_ID, Cruel_Arrow_ID, Spiky_Wheel_ID
    if not card_table:
        card_table       = {c.cardId: c for c in all_card_data()}
        grimmsnarl_data  = card_table[Grimmsnarl_ex]
        Shadow_Bullet_ID = grimmsnarl_data.attacks[0]  # Shadow Bullet
        fezandipiti_data = card_table[Fezandipiti_ex]
        Cruel_Arrow_ID   = fezandipiti_data.attacks[0]  # Cruel Arrow
        morpeko_data     = card_table[Marnie_Morpeko]
        Spiky_Wheel_ID   = morpeko_data.attacks[0]  # Spiky Wheel
    return card_table
```

- [ ] **Step 5: `_score_attack`を編集する**

現状:

```python
CRUEL_ARROW_DAMAGE = 100  # クルーエルアローの与ダメージ（相手1匹を選んで攻撃・ベンチも弱点抵抗力無視で狙える）


def _score_attack(attack_id: int, fs: FieldState) -> int:
    """ATTACK コンテキスト：ワザ選択スコア"""
    if attack_id == Shadow_Bullet_ID:
        # 相手バトルポケモンのHPがSHADOW_BULLET_DAMAGE以下ならShadow Bulletで確実にKOできる
        # （きぜつ確定）ので、RETREATの3000点より高くして撤退より攻撃を優先する
        return 5000 if fs.op_active_hp <= SHADOW_BULLET_DAMAGE else 2000
    if attack_id == Cruel_Arrow_ID:
        # クルーエルアローは相手1匹（バトル場・ベンチ問わず）を選んで攻撃できるため、
        # どちらかにCRUEL_ARROW_DAMAGE以下の確定KO対象がいれば優先する
        op_hps = [fs.op_active_hp, *fs.op_bench_hp]
        return 5000 if any(hp <= CRUEL_ARROW_DAMAGE for hp in op_hps) else 2000
    return 1000
```

変更後:

```python
CRUEL_ARROW_DAMAGE = 100  # クルーエルアローの与ダメージ（相手1匹を選んで攻撃・ベンチも弱点抵抗力無視で狙える）
SPIKY_WHEEL_BASE_DAMAGE       = 20  # スパイキーホイールの基礎ダメージ
SPIKY_WHEEL_DAMAGE_PER_ENERGY = 40  # 装着した悪エネルギー1枚ごとの追加ダメージ


def _score_attack(attack_id: int, fs: FieldState) -> int:
    """ATTACK コンテキスト：ワザ選択スコア"""
    if attack_id == Shadow_Bullet_ID:
        # 相手バトルポケモンのHPがSHADOW_BULLET_DAMAGE以下ならShadow Bulletで確実にKOできる
        # （きぜつ確定）ので、RETREATの3000点より高くして撤退より攻撃を優先する
        return 5000 if fs.op_active_hp <= SHADOW_BULLET_DAMAGE else 2000
    if attack_id == Cruel_Arrow_ID:
        # クルーエルアローは相手1匹（バトル場・ベンチ問わず）を選んで攻撃できるため、
        # どちらかにCRUEL_ARROW_DAMAGE以下の確定KO対象がいれば優先する
        op_hps = [fs.op_active_hp, *fs.op_bench_hp]
        return 5000 if any(hp <= CRUEL_ARROW_DAMAGE for hp in op_hps) else 2000
    if attack_id == Spiky_Wheel_ID:
        # 装着した悪エネルギー数に応じてダメージが伸びるため、都度ダメージを計算し
        # 確定KOできるかを判定する
        damage = SPIKY_WHEEL_BASE_DAMAGE + fs.morpeko_energy_count * SPIKY_WHEEL_DAMAGE_PER_ENERGY
        return 5000 if damage >= fs.op_active_hp else 2000
    return 1000
```

- [ ] **Step 6: テストが通ることを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k spiky_wheel`
Expected: 3件すべてPASS

- [ ] **Step 7: リポジトリ全体のテストを実行し回帰がないことを確認する**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 8: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "$(cat <<'EOF'
feat: モルペコのスパイキーホイール攻撃スコアリングを追加

Shadow_Bullet_ID/Cruel_Arrow_IDと同じパターンでSpiky_Wheel_IDを
card_tableから取得。装着した悪エネルギー数に応じたダメージ（20+40×枚数）を
都度計算し、確定KOなら優先するスコアリングを追加する。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: モルペコのベンチ配置優先度を追加する

**Files:**
- Modify: `src/grimmsnarl_agent/main.py`（`_score_card_option`の`TO_BENCH | TO_HAND`分岐）
- Modify: `tests/test_grimmsnarl_agent.py`（`TestScoreCardOption`クラスにテスト追加）

**Interfaces:**
- Consumes: `gm.Marnie_Morpeko`（Task 2）、`FieldState.morpeko_bench_idx`（Task 2）
- Produces: なし（`_score_card_option`の`TO_BENCH`/`TO_HAND`挙動のみ）

Poké Pad・ギーマの一手（Task 6）などで複数のポケモン候補から選ぶ場面で、モルペコが未展開なら優先的にベンチへ出す判断を追加する。

- [ ] **Step 1: `tests/test_grimmsnarl_agent.py`の`TestScoreCardOption`クラスに、`test_to_bench_grimmsnarl_low_when_already_in_play`の直後として以下のテストを追加する**

```python
    def test_to_bench_morpeko_high_when_none_in_play(self):
        morpeko = make_pokemon(id=gm.Marnie_Morpeko)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), hand=[morpeko])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs(morpeko_bench_idx=-1)
        o = Option(type=OptionType.CARD, area=AreaType.HAND, index=0, playerIndex=0)
        score = gm._score_card_option(obs, o, SelectContext.TO_BENCH, 0, fs, defaultdict(int))
        assert score == 40

    def test_to_bench_morpeko_low_when_already_in_play(self):
        morpeko = make_pokemon(id=gm.Marnie_Morpeko)
        my_ps = make_player_state(active_pokemon=make_pokemon(id=1), hand=[morpeko])
        op_ps = make_player_state(active_pokemon=make_pokemon(id=2, hp=200))
        obs = self._make_obs(my_ps, op_ps)
        fs = self._make_fs(morpeko_bench_idx=0)
        o = Option(type=OptionType.CARD, area=AreaType.HAND, index=0, playerIndex=0)
        score = gm._score_card_option(obs, o, SelectContext.TO_BENCH, 0, fs, defaultdict(int))
        assert score == 10
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k "to_bench_morpeko"`
Expected: 2件すべてFAIL（`TO_BENCH | TO_HAND`分岐はまだMarnie_Morpekoを認識せず、常にデフォルトの`10`を返すため。`test_to_bench_morpeko_high_when_none_in_play`は`40`を期待するのでFAIL、`test_to_bench_morpeko_low_when_already_in_play`は偶然`10`と一致するためPASSしてしまう可能性があるが、実装意図を明確にするため両方とも明示的にテストする）

- [ ] **Step 3: `src/grimmsnarl_agent/main.py`の`_score_card_option`内`TO_BENCH | TO_HAND`分岐を編集する**

現状:

```python
        case SelectContext.TO_BENCH | SelectContext.TO_HAND:
            if not isinstance(card, Pokemon):
                return 10
            if card.id == Grimmsnarl_ex:
                return 100 if fs.field_counts[Grimmsnarl_ex] == 0 else 10
            if card.id == Impidimp:
                return 60 if fs.field_counts[Impidimp] < 2 else 20
            return 10
```

変更後:

```python
        case SelectContext.TO_BENCH | SelectContext.TO_HAND:
            if not isinstance(card, Pokemon):
                return 10
            if card.id == Grimmsnarl_ex:
                return 100 if fs.field_counts[Grimmsnarl_ex] == 0 else 10
            if card.id == Impidimp:
                return 60 if fs.field_counts[Impidimp] < 2 else 20
            if card.id == Marnie_Morpeko:
                return 40 if fs.morpeko_bench_idx == -1 else 10
            return 10
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k "to_bench_morpeko"`
Expected: 2件すべてPASS

- [ ] **Step 5: リポジトリ全体のテストを実行し回帰がないことを確認する**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 6: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "$(cat <<'EOF'
feat: モルペコが未展開ならベンチ配置を優先するロジックを追加

Poké Padやギーマの一手で複数のポケモン候補から選ぶ場面で、
モルペコがまだ場にいなければ優先的にベンチへ出すようにする。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: ギーマの一手（Grimsley's Move）のPLAYスコアリングを追加する

**Files:**
- Modify: `src/grimmsnarl_agent/main.py`（`_score_play`）
- Modify: `tests/test_grimmsnarl_agent.py`（`TestScorePlay`クラスにテスト追加）

**Interfaces:**
- Consumes: `gm.Grimsley_Move`（Task 2）、`FieldState.impidimp_bench_idx` / `FieldState.morpeko_bench_idx`（既存）
- Produces: なし（`_score_play`の挙動のみ）

- [ ] **Step 1: `tests/test_grimmsnarl_agent.py`の`TestScorePlay`クラスに、`test_buddy_buddy_poffin_low_when_bench_targets_present`の直後として以下のテストを追加する**

```python
    def test_grimsley_move_high_when_bench_targets_missing(self):
        fs = self._make_fs()
        assert gm._score_play(gm.Grimsley_Move, fs, prize_count=6) == 7800

    def test_grimsley_move_low_when_bench_targets_present(self):
        fs = self._make_fs(impidimp_bench_idx=0, morpeko_bench_idx=1)
        assert gm._score_play(gm.Grimsley_Move, fs, prize_count=6) == 1500
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k grimsley_move`
Expected: 2件すべてFAIL（`_score_play`はまだ`Grimsley_Move`を認識せず、常にデフォルトの`1000`を返すため）

- [ ] **Step 3: `src/grimmsnarl_agent/main.py`の`_score_play`を編集する**

現状:

```python
    if card_id == Buddy_Buddy_Poffin:
        needs_bench = fs.impidimp_bench_idx == -1 or fs.morpeko_bench_idx == -1
        return 8000 if needs_bench else 2000
    if card_id == Team_Rocket_Petrel:
```

変更後:

```python
    if card_id == Buddy_Buddy_Poffin:
        needs_bench = fs.impidimp_bench_idx == -1 or fs.morpeko_bench_idx == -1
        return 8000 if needs_bench else 2000
    if card_id == Grimsley_Move:
        # 山札上7枚から悪ポケモン1体をベンチに出す。本デッキは悪タイプ密度が高く
        # ヒット率が良好なため、ベンチが手薄な間はBuddy-Buddy Poffinに次ぐ優先度にする
        needs_bench = fs.impidimp_bench_idx == -1 or fs.morpeko_bench_idx == -1
        return 7800 if needs_bench else 1500
    if card_id == Team_Rocket_Petrel:
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k grimsley_move`
Expected: 2件すべてPASS

- [ ] **Step 5: リポジトリ全体のテストを実行し回帰がないことを確認する**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 6: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "$(cat <<'EOF'
feat: ギーマの一手のPLAYスコアリングを追加

ベンチが手薄な間はBuddy-Buddy Poffinに次ぐ優先度で使用し、
展開速度の底上げに寄与させる。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: チェレン（Cheren）のPLAYスコアリングを追加する

**Files:**
- Modify: `src/grimmsnarl_agent/main.py`（`_score_play`）
- Modify: `tests/test_grimmsnarl_agent.py`（`TestScorePlay`クラスにテスト追加）

**Interfaces:**
- Consumes: `gm.Cheren`（Task 2）
- Produces: なし（`_score_play`の挙動のみ）

- [ ] **Step 1: `tests/test_grimmsnarl_agent.py`の`TestScorePlay`クラスに、`test_unhandled_card_returns_default`の直前として以下のテストを追加する**

```python
    def test_cheren_score(self):
        """チェレンは条件なしの単純ドロー（3枚）のため、常に固定スコアを返すこと"""
        fs = self._make_fs()
        assert gm._score_play(gm.Cheren, fs, prize_count=6) == 2200
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k cheren`
Expected: FAIL（`_score_play`はまだ`Cheren`を認識せず、デフォルトの`1000`を返すため）

- [ ] **Step 3: `src/grimmsnarl_agent/main.py`の`_score_play`を編集する**

現状:

```python
    if card_id == Night_Stretcher:
        return 2000
    if card_id == Boss_Orders:
```

変更後:

```python
    if card_id == Night_Stretcher:
        return 2000
    if card_id == Cheren:
        # 条件なしの単純ドロー（3枚）。相手に非干渉で腐り札化リスクもない安全牌として
        # 一定の優先度を与える
        return 2200
    if card_id == Boss_Orders:
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -v -k cheren`
Expected: PASS

- [ ] **Step 5: リポジトリ全体のテストを実行し回帰がないことを確認する**

Run: `uv run pytest -q`
Expected: 全件PASS

- [ ] **Step 6: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add src/grimmsnarl_agent/main.py tests/test_grimmsnarl_agent.py
git commit -m "$(cat <<'EOF'
feat: チェレンのPLAYスコアリングを追加

条件なしの単純ドロー(3枚)として、状況依存カードが手詰まりの際の
安全な代替札の優先度を設定する。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: 全体回帰確認とデッキCSV生成、実装サマリー作成

**Files:**
- Create: `docs/implementations/20260705-grimmsnarl-morpeko-revision.md`

**Interfaces:**
- Consumes: Task 1〜7の全変更
- Produces: なし（ドキュメントのみ）

- [ ] **Step 1: リポジトリ全体のテストスイートを実行する**

Run: `uv run pytest -q`
Expected: 全件PASS（回帰なし）

- [ ] **Step 2: デッキCSVを生成する**

Run:
```bash
uv run python -c "
from decks.grimmsnarl_20260701 import DECK
import datetime
rows = []
for card_id, count in DECK:
    rows.extend([str(card_id)] * count)
assert len(rows) == 60
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
path = f'output/deck_{ts}.csv'
with open(path, 'w') as f:
    f.write('\n'.join(rows))
print(path)
"
```
Expected: `output/deck_YYYYMMDD_HHMMSS.csv` が生成され、パスが標準出力に表示される（Kaggleへのアップロードはユーザーが手動で実施）

- [ ] **Step 3: 実装サマリーを作成する**

`docs/implementations/20260705-grimmsnarl-morpeko-revision.md`を以下の内容で作成する:

```markdown
# 実装サマリー：グリムスナールexデッキ 第3次改修（モルペコ再導入）

**実装日：** 2026-07-05
**関連設計書：** `docs/superpowers/specs/2026-07-05-grimmsnarl-morpeko-revision-design.md`

## 背景

イワパレス（特性「しんぴのいしやど」：相手の「ポケモン【ex】」からの技ダメージを
受けない）に対して、現行デッキのアタッカー（グリムスナールex・キチキギスex）が
両方exのため、ダメージを与える手段が実質存在しないことが判明した。あわせて、
ユキワラシ・ユキメノコ（Froslass）ラインが自傷ダメージ（特性「いてつくとばり」は
自分・相手両方の特性持ちポケモンにダメカンを乗せる）と展開遅延の原因になっており、
キチキギスexとオーロンゲexが同時気絶する事故が過去にあったため、あわせて整理した。

## 変更内容

### デッキ（`decks/grimmsnarl_20260701.py`）
- ユキワラシ(860)/ユキメノコ(104)/マシマシラ(112)を削除（合計7枚）
- マリィのモルペコ(649)を3枚新規採用（非exアタッカー。スパイキーホイール：
  20+装着悪エネルギー×40、上限なし）
- Buddy-Buddy Poffin(1086)を2→3枚に増量
- ギーマの一手(1230)を2枚、チェレン(1224)を1枚新規採用（展開速度対策）
- ポケモン20体→16体、トレーナーズ28枚→32枚（エネルギー12枚は変更なし）

### エージェントロジック（`src/grimmsnarl_agent/main.py`）
- 削除カード（Froslass/Munkidori）の定数・`SUPPORT_ONLY_IDS`・スコアリング分岐
  （`_score_attach`のMunkidori分岐、`ABILITY`のMunkidori優先度、`TO_BENCH | TO_HAND`の
  Munkidori分岐）を削除
- `FieldState.munkidori_bench_idx`を`morpeko_bench_idx`にリネームし、モルペコの
  装着エネルギー数を追跡する`morpeko_energy_count`を新規追加
- `_score_attach`：グリムスナールexの攻撃分（2エネ）確保後、余剰の基本エネルギーを
  モルペコにも配分できるよう追加（Fezandipiti_exと異なり上限を設けない）
- `_score_attack`：`Spiky_Wheel_ID`を`Shadow_Bullet_ID`/`Cruel_Arrow_ID`と同じパターンで
  `_build_card_table()`から取得し、装着エネルギー数から都度ダメージを計算して
  確定KOなら優先するスコアリングを追加
- `TO_BENCH | TO_HAND`：モルペコが未展開なら優先的にベンチへ出す判断を追加
- `_score_play`：ギーマの一手（ベンチが手薄なら優先）とチェレン（条件なしの安全牌）の
  PLAYスコアリングを追加

## テスト結果

- `tests/test_grimmsnarl_deck.py`：新構成向けテスト追加、全件PASS
- `tests/test_grimmsnarl_agent.py`：モルペコのエネルギー配分・攻撃スコアリング・
  ベンチ配置優先度、ギーマの一手・チェレンのPLAYスコアリングのテストを追加。
  削除カード参照（`gm.Munkidori`/`gm.Froslass`）は完全に除去
- リポジトリ全体：`uv run pytest -q` で全件PASS（回帰なし）

## 未対応・次回持ち越し

- モルペコ専用のRETREAT（撤退）判断ロジックは今回未対応（70HPと低耐久だが、
  既存のRETREATロジックはグリムスナールex専用のまま）
- 特性発動（パンクアップ）でモルペコに悪エネルギーを集中配分する際のカード選択
  （`ATTACH_FROM`等の文脈）への専用スコアリングは未対応。現状は通常のATTACHの
  エネルギー装着（Task 3）でのみモルペコへの配分を評価している
- 超高速デッキ（Mega Lucario ex、アラカザム）との相性問題は今回未対応
- 他デッキへの同種横展開は未着手
- Kaggle再提出後のLBスコア変化確認（本改修のスコープ外、ユーザーが手動で実施）
```

- [ ] **Step 4: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add docs/implementations/20260705-grimmsnarl-morpeko-revision.md
git commit -m "$(cat <<'EOF'
docs: グリムスナールexデッキ第3次改修（モルペコ再導入）の実装サマリーを追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
