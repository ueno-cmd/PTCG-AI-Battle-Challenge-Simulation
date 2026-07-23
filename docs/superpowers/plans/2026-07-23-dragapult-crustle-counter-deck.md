# ドラパルトex イワパレス対策デッキ 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `decks/dragapult_20260721.py`のドラパルトexデッキを、実際のジムバトル環境で
確認されたイワパレス(Crustle)対策構成に全面差し替えし、`src/dragapult_agent/main.py`に
新規カードのスコアリングロジックを追加する。

**Architecture:** 既存の`main.py`（`agent()`関数中心の1ファイル構成、`hand_score()`
クロージャ・`_attach_score()`・`_own_switch_target_score()`・`TrainerCardPolicy`
登録辞書の4つの主要な判断ポイント）に、新規カードの分岐を既存パターンに沿って追加する。
新規ファイルは作成しない。

**Tech Stack:** Python 3.12、pytest、`cg.api`（Kaggle公式シミュレータAPI）。

## Global Constraints

- 設計書: `docs/superpowers/specs/2026-07-23-dragapult-crustle-counter-deck-design.md`
  （矛盾が生じた場合はこちらを正とする）
- コードコメントは日本語で書く（CLAUDE.md）
- if/elif連鎖に新規分岐を追加する際、独立した`if`文で連鎖を分断しない
  （2026-07-23のアカマツ(Crispin)スコアリングバグの再発防止。
  `docs/analyses/20260723-dragapult-main-if-else-audit.md`参照）
- 新規サポート/スタジアム（ヒカリ・メイのはげまし・ジャミングタワー）は
  `TrainerCardPolicy`（ABC＋登録辞書）パターンに乗せ、`agent()`内に
  カードID分岐を新規追加しない
- 各タスク完了時点でリポジトリ全体のテストスイートが引き続きPASSすること
- `hand_score()`は`agent()`内のクロージャであり、`_build_card_table()`が
  ネイティブライブラリ（macOSでは動作しない、[[project_battle_log_parser]]参照）を
  呼び出すため、`agent()`をエンドツーエンドで駆動する単体テストはこの開発環境では
  書けない。既存コードの前例（Dreepy/Budew等のhand_score()分岐にも専用テストが
  存在しない）に倣い、`hand_score()`自体の新規分岐は直接テストしない。一方、
  `_attach_score()`・`_own_switch_target_score()`・`_crispin_score()`・
  `_boss_orders_score()`のように独立関数として切り出し済み/切り出し可能な
  ロジックは、既存パターンに倣い必ずTDDで実装する
- マシマシラの特性「アドレナブレイン」の詳細な対象選択（自分のどのポケモンから
  ダメカンを移すか等）は、実際のSelectContext形状が実戦ログでまだ確認できていない
  ため、発動条件（ABILITY選択時のゲーティング）のみを実装し、それ以降の対象選択は
  既存の汎用ロジックに委ねる（設計書のテスト戦略節参照）

---

## ファイル構成

| ファイル | 責務 | 変更種別 |
|---|---|---|
| `decks/dragapult_20260721.py` | 60枚のデッキリスト定義 | 全面差し替え |
| `src/dragapult_agent/constants.py` | カードID定数 | 追加・削除 |
| `src/dragapult_agent/main.py` | エージェント本体（スコアリングロジック） | 追加・削除 |
| `tests/test_dragapult_agent.py` | 単体テスト | 追加・削除・更新 |
| `scripts/build_dragapult_submission_notebook.py` | 提出用notebook生成 | 変更なし（再実行のみ） |

---

## Task 1: 新規カード定数の追加とデッキリスト差し替え

**Files:**
- Modify: `src/dragapult_agent/constants.py`
- Modify: `decks/dragapult_20260721.py`
- Test: `tests/test_dragapult_agent.py`（デッキ検証テストを新規追加）

**Interfaces:**
- Produces: `Munkidori`, `Duskull`, `Dusclops`, `Dusknoir`, `Moltres`, `Yveltal`,
  `Dawn`, `Rosas_Encouragement`, `Jamming_Tower`, `Basic_Dark_Energy`（いずれも`int`定数）

この段階では既存カード（`Latias_ex`等）の定数・ロジックはまだ削除しない
（Task 2で削除するまでは、新デッキに存在しないカードを参照する既存ロジックが
単に使われなくなるだけで、importエラーは起きない）。

- [ ] **Step 1: 新規カード定数を追加**

`src/dragapult_agent/constants.py`の末尾に追記する：

```python
Munkidori               = 112   # マシマシラ（JP名）
Duskull                 = 131   # ヨマワル（JP名）
Dusclops                = 132   # サマヨール（JP名）
Dusknoir                = 133   # ヨノワール（JP名、カースドボムの主役）
Moltres                 = 791   # ファイヤー（JP名）
Yveltal                 = 689   # イベルタル
Dawn                    = 1231  # ヒカリ（JP名）
Rosas_Encouragement     = 1240  # メイのはげまし（JP名）
Jamming_Tower           = 1246  # ジャミングタワー（JP名）
Basic_Dark_Energy       = 7
```

- [ ] **Step 2: デッキリストを新構成に差し替え**

`decks/dragapult_20260721.py`を以下の内容に全面差し替える：

```python
# ドラパルトexデッキ定義（2026-07-23 イワパレス対策版）
# 実際のジムバトル環境で確認されたイワパレス(Crustle)対策デッキを移植。
# 設計書: docs/superpowers/specs/2026-07-23-dragapult-crustle-counter-deck-design.md

DECK = [
    (2, 3),      # Basic Fire Energy
    (5, 3),      # Basic Psychic Energy
    (7, 2),      # Basic Dark Energy
    (112, 1),    # Munkidori (マシマシラ)
    (119, 4),    # Dreepy
    (120, 4),    # Drakloak
    (121, 3),    # Dragapult ex
    (131, 2),    # Duskull (ヨマワル)
    (132, 1),    # Dusclops (サマヨール)
    (133, 1),    # Dusknoir (ヨノワール)
    (140, 1),    # Fezandipiti ex
    (235, 1),    # Budew
    (689, 1),    # Yveltal
    (791, 1),    # Moltres (ファイヤー)
    (1071, 1),   # Meowth ex
    (1079, 2),   # Rare Candy
    (1080, 1),   # Unfair Stamp (ACE SPEC)
    (1086, 4),   # Buddy-Buddy Poffin
    (1097, 2),   # Night Stretcher
    (1121, 4),   # Ultra Ball
    (1152, 4),   # Poke Pad
    (1182, 4),   # Boss's Orders
    (1198, 3),   # Crispin
    (1227, 4),   # Lillie's Determination
    (1231, 1),   # Dawn (ヒカリ)
    (1240, 1),   # Rosa's Encouragement (メイのはげまし)
    (1246, 1),   # Jamming Tower
]
```

- [ ] **Step 3: デッキ合計枚数とACE SPEC制限を検証するテストを新規作成**

`tests/test_dragapult_agent.py`の末尾に追記：

```python
import importlib.util
from pathlib import Path


def _load_deck_module():
    deck_path = Path(__file__).resolve().parents[1] / "decks" / "dragapult_20260721.py"
    spec = importlib.util.spec_from_file_location("dragapult_deck", deck_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deck_totals_exactly_sixty_cards():
    deck_module = _load_deck_module()
    assert sum(count for _, count in deck_module.DECK) == 60


def test_deck_has_no_duplicate_card_ids():
    deck_module = _load_deck_module()
    card_ids = [card_id for card_id, _ in deck_module.DECK]
    assert len(card_ids) == len(set(card_ids))


def test_deck_ace_spec_limit_is_one():
    """ACE SPECカード(Unfair_Stamp)は1枚制限を遵守する"""
    deck_module = _load_deck_module()
    counts = dict(deck_module.DECK)
    assert counts[dm.Unfair_Stamp] == 1
```

- [ ] **Step 4: テストを実行して全てPASSすることを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "test_deck_"`
Expected: 3件PASS

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/constants.py decks/dragapult_20260721.py tests/test_dragapult_agent.py
git commit -m "feat(dragapult): イワパレス対策デッキの新規カード定数とデッキリストを追加"
```

---

## Task 2: 除外カードの既存ロジック削除

**Files:**
- Modify: `src/dragapult_agent/constants.py`
- Modify: `src/dragapult_agent/main.py`
- Modify: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: Task 1で追加した新規デッキリスト（`Latias_ex`等がデッキに含まれない）
- Produces: `constants.py`から`Latias_ex`, `Crushing_Hammer`, `Lucky_Helmet`,
  `Team_Rocket_Watchtower`, `Brock_Scouting`が削除された状態

除外対象：ラティアスex・クラッシングハンマー・ラッキーヘルメット・
ロケット団の見張り搭・ブロックの探索。フェザンディピティexは対象外（変更なし）。

- [ ] **Step 1: 削除対象を参照する既存テストを先に整理**

`tests/test_dragapult_agent.py`から以下を削除する：
- `test_unfair_stamp_and_crushing_hammer_registered`関数まるごと
- `test_team_rocket_watchtower_policy_plays_when_stadium_already_set`関数まるごと
- `test_team_rocket_watchtower_policy_plays_on_turn_one_even_without_stadium`関数まるごと
- `test_team_rocket_watchtower_policy_holds_otherwise`関数まるごと
- `test_rare_candy_and_team_rocket_watchtower_registered`関数まるごと

`test_unfair_stamp_and_crushing_hammer_registered`の代わりに以下を追加：

```python
def test_unfair_stamp_registered():
    assert dm._score_play_trainer_card(dm.Unfair_Stamp, _make_ctx()) == 15000
```

`test_rare_candy_and_team_rocket_watchtower_registered`の代わりに以下を追加：

```python
def test_rare_candy_registered():
    assert dm._score_play_trainer_card(dm.Rare_Candy, _make_ctx(no_more_dex=False)) == 75000
```

`test_no_draw_gated_cards_registered`から、`dm.Brock_Scouting`を使う以下のブロック
のみを削除する（同関数内の他のassertは残す）：

```python
    assert dm._score_play_trainer_card(
        dm.Brock_Scouting, _make_ctx(card_id=dm.Brock_Scouting, use_support=dm.Brock_Scouting)
    ) == 35000
```

`test_trainer_card_policies_cover_exactly_the_migrated_card_set`の`expected`集合を
以下に更新する：

```python
def test_trainer_card_policies_cover_exactly_the_migrated_card_set():
    """現行TRAINER_CARD_POLICIESに登録されているカードと過不足なく一致することを保証する"""
    expected = {
        dm.Rare_Candy, dm.Unfair_Stamp, dm.Night_Stretcher,
        dm.Boss_Orders, dm.Lillie_Determination,
        dm.Buddy_Buddy_Poffin, dm.Ultra_Ball, dm.Poke_Pad, dm.Crispin,
    }
    assert set(dm.TRAINER_CARD_POLICIES.keys()) == expected
```

- [ ] **Step 2: テストを実行して失敗することを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "trainer_card_policies_cover"`
Expected: FAIL（`TRAINER_CARD_POLICIES`にまだ`Crushing_Hammer`等が残っているため集合不一致）

- [ ] **Step 3: main.pyから除外カードの参照を削除**

`src/dragapult_agent/main.py`のimport文から`Latias_ex`, `Lucky_Helmet`,
`Team_Rocket_Watchtower`, `Brock_Scouting`, `Crushing_Hammer`を削除：

```python
from dragapult_agent.constants import (
    Dreepy, Drakloak, Dragapult_ex, Fezandipiti_ex, Budew,
    Meowth_ex, Rare_Candy, Unfair_Stamp, Buddy_Buddy_Poffin, Night_Stretcher,
    Ultra_Ball, Poke_Pad, Boss_Orders, Crispin,
    Lillie_Determination,
    Basic_Fire_Energy, Basic_Psychic_Energy,
)
```

`_attach_score()`内の以下の行：

```python
    elif pokemon.id == Meowth_ex or pokemon.id == Fezandipiti_ex or pokemon.id == Latias_ex:
```

を以下に変更：

```python
    elif pokemon.id == Meowth_ex or pokemon.id == Fezandipiti_ex:
```

`hand_score()`クロージャ内から以下の5つのブロックを削除：

```python
        elif id == Latias_ex:
            if active_id == Fezandipiti_ex or active_id == Meowth_ex or active_id == Dreepy:
                if field_counts[Drakloak] + field_counts[Dragapult_ex] == 0:
                    score = 28000
                else:
                    score = 15000
            else:
                score = 10
```

```python
        elif id == Crushing_Hammer:
            score = 20
```

```python
        elif id == Lucky_Helmet:
            score = 15
```

```python
        elif id == Brock_Scouting:
            if not ignore_count or support_count == 0:
                if state.turn == 2 and field_counts[Budew] + field_counts[Latias_ex] == 0:
                    score = 50000
                else:
                    score = 30000
```

```python
        elif id == Team_Rocket_Watchtower:
            if stadium_id != 0 and stadium_id != Team_Rocket_Watchtower:
                score = 4000
```

`OptionType.PLAY`分岐から以下のブロックを削除：

```python
            elif card.id == Latias_ex:
                if active_id != Drakloak and active_id != Dragapult_ex:
                    score = 51000
                else:
                    score = -1
```

`TeamRocketWatchtowerPolicy`クラス定義をまるごと削除：

```python
class TeamRocketWatchtowerPolicy(TrainerCardPolicy):
    """スタジアムが既に何か設置済み、または1ターン目なら設置する"""
    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        if ctx.stadium_id > 0 or ctx.state.turn == 1:
            return 80000
        return -1
```

`TRAINER_CARD_POLICIES`辞書から以下の3行を削除：

```python
    Crushing_Hammer: FixedScorePolicy(40000),
    Team_Rocket_Watchtower: TeamRocketWatchtowerPolicy(),
    Brock_Scouting: SupporterSelectedPolicy(35000, no_draw_gate=True),
```

- [ ] **Step 4: テストを実行して全てPASSすることを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: 全件PASS

- [ ] **Step 5: constants.pyから除外カードの定数を削除**

`src/dragapult_agent/constants.py`から以下の5行を削除：

```python
Latias_ex               = 184
```
```python
Crushing_Hammer         = 1120
```
```python
Lucky_Helmet            = 1156
```
```python
Brock_Scouting          = 1210  # タケシのスカウト（JP名）
```
```python
Team_Rocket_Watchtower  = 1256
```

- [ ] **Step 6: テストを再実行して全てPASSすることを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: 全件PASS（constants.py削除後もimportエラーが起きないことを確認）

- [ ] **Step 7: コミット**

```bash
git add src/dragapult_agent/constants.py src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "refactor(dragapult): 除外カード(ラティアスex等5種)の既存ロジックを削除"
```

---

## Task 3: 新規ポケモンのhand_score()追加

**Files:**
- Modify: `src/dragapult_agent/main.py`

**Interfaces:**
- Consumes: Task 1の`Munkidori`, `Duskull`, `Dusclops`, `Dusknoir`, `Moltres`,
  `Yveltal`定数
- Produces: `can_evolve_yomawaru`, `can_evolve_samayouru`（`agent()`内のローカル変数）

`hand_score()`は`agent()`内のクロージャで、既存のDreepy/Drakloak/Budew等の分岐にも
専用の単体テストは存在しない（Global Constraints参照）。このタスクでは新規分岐の
実装のみを行い、既存の全体テストスイートで回帰がないことを確認する。

- [ ] **Step 1: 進化ライン追跡フラグの初期化・更新ロジックを追加**

`main.py`の`agent()`内、以下の初期化ブロック：

```python
    active_id = 0
    bench_attacker = False
    can_evolve_dreepy = False
    evolve_dreepy_count = 0
    can_evolve_drakloak = False
    damage = 200
```

を以下に変更（`can_evolve_yomawaru`・`can_evolve_samayouru`を追加）：

```python
    active_id = 0
    bench_attacker = False
    can_evolve_dreepy = False
    evolve_dreepy_count = 0
    can_evolve_drakloak = False
    can_evolve_yomawaru = False
    can_evolve_samayouru = False
    damage = 200
```

続く`for card in my_state.active:`ループ内：

```python
        if not card.appearThisTurn:
            if card.id == Dreepy:
                can_evolve_dreepy = True
                evolve_dreepy_count += 1
            elif card.id == Drakloak:
                can_evolve_drakloak = True
```

を以下に変更：

```python
        if not card.appearThisTurn:
            if card.id == Dreepy:
                can_evolve_dreepy = True
                evolve_dreepy_count += 1
            elif card.id == Drakloak:
                can_evolve_drakloak = True
            elif card.id == Duskull:
                can_evolve_yomawaru = True
            elif card.id == Dusclops:
                can_evolve_samayouru = True
```

続く`for card in my_state.bench:`ループ内も同様に変更：

```python
        if not card.appearThisTurn:
            if card.id == Dreepy:
                can_evolve_dreepy = True
                evolve_dreepy_count += 1
            elif card.id == Drakloak:
                can_evolve_drakloak = True
```

を以下に変更：

```python
        if not card.appearThisTurn:
            if card.id == Dreepy:
                can_evolve_dreepy = True
                evolve_dreepy_count += 1
            elif card.id == Drakloak:
                can_evolve_drakloak = True
            elif card.id == Duskull:
                can_evolve_yomawaru = True
            elif card.id == Dusclops:
                can_evolve_samayouru = True
```

- [ ] **Step 2: hand_score()に新規ポケモンの分岐を追加**

`hand_score()`内、`elif id == Budew:`ブロックの直後に以下を追加：

```python
        elif id == Duskull:
            if field_counts[id] + field_counts[Dusclops] + field_counts[Dusknoir] >= 1:
                score = 1000
            else:
                score = 15000
        elif id == Dusclops:
            if can_evolve_yomawaru and field_counts[Dusclops] + field_counts[Dusknoir] == 0:
                score = 16000
            else:
                score = 1000
        elif id == Dusknoir:
            if can_evolve_samayouru and field_counts[Dusknoir] == 0:
                score = 17000
            else:
                score = 1000
        elif id == Munkidori:
            if field_counts[id] == 0:
                score = 12000
            else:
                score = 500
        elif id == Moltres:
            if field_counts[id] == 0:
                score = 12000
            else:
                score = 500
        elif id == Yveltal:
            if field_counts[id] == 0:
                score = 13000
            else:
                score = 500
```

- [ ] **Step 3: リポジトリ全体のテストを実行し回帰がないことを確認**

Run: `uv run pytest`
Expected: 既存の既知の失敗（無関係な既知の失敗10件・エラー12件、
`docs/implementations/20260723-dragapult-trainer-card-policy-migration.md`
時点の記録と同数）以外は全てPASS。新規追加した分岐によるImportError・SyntaxError
が無いことを確認する

- [ ] **Step 4: コミット**

```bash
git add src/dragapult_agent/main.py
git commit -m "feat(dragapult): 新規ポケモン6種(ヨマワル系統/マシマシラ/ファイヤー/イベルタル)のhand_score()を追加"
```

---

## Task 4: 新規たねポケモンのPLAY dispatch追加

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: Task 3の`field_counts`（既存の`agent()`内変数、変更なし）

対象：ヨマワル(Duskull)・マシマシラ(Munkidori)・ファイヤー(Moltres)・
イベルタル(Yveltal)。いずれも「たね」ポケモンで、`OptionType.PLAY`で
手札から場に出す。サマヨール(Dusclops)・ヨノワール(Dusknoir)は
1進化/2進化のため`OptionType.EVOLVE`経由（Task 5）でPLAY分岐は不要。

- [ ] **Step 1: PLAY dispatchに新規分岐を追加**

`main.py`の`OptionType.PLAY`分岐内、`elif card.id == Budew:`ブロックの直後に
以下を追加：

```python
            elif card.id == Duskull:
                if field_counts[Duskull] + field_counts[Dusclops] + field_counts[Dusknoir] == 0:
                    score = 51000
                else:
                    score = -1
            elif card.id == Munkidori:
                if field_counts[Munkidori] == 0:
                    score = 51000
                else:
                    score = -1
            elif card.id == Moltres:
                if field_counts[Moltres] == 0:
                    score = 51000
                else:
                    score = -1
            elif card.id == Yveltal:
                if field_counts[Yveltal] == 0:
                    score = 51000
                else:
                    score = -1
```

- [ ] **Step 2: 新規Pokemonカードがトレーナー扱いされないことを確認するテストを追加**

`tests/test_dragapult_agent.py`に追記：

```python
def test_new_basic_pokemon_are_not_registered_as_trainer_cards():
    """Duskull/Munkidori/Moltres/YveltalはPokemonカードのため、
    TrainerCardPolicyには登録されない（agent()内の専用PLAY分岐で処理される）"""
    for card_id in (dm.Duskull, dm.Munkidori, dm.Moltres, dm.Yveltal):
        assert card_id not in dm.TRAINER_CARD_POLICIES
```

- [ ] **Step 3: テストを実行して通ることを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "test_new_basic_pokemon"`
Expected: PASS

- [ ] **Step 4: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "feat(dragapult): 新規たねポケモン4種のPLAY dispatchを追加"
```

---

## Task 5: EVOLVE dispatch拡張（`_evolve_score()`の切り出し）

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: Task 1の`Duskull`, `Dusclops`定数
- Produces: `_evolve_score(pre_evolution_id: int, energy_count: int,
  dragapult_ex_field_count: int, opponent_prize_count: int) -> int`
  （新規独立関数。`_own_switch_target_score()`と同じ切り出しパターン）

既存の`OptionType.EVOLVE`分岐はagent()内にベタ書きされておりテストできない。
新規カード（ヨマワル→サマヨール）の優先度をTDDで実装するため、既存の
Dreepy/Drakloak→Dragapult_exロジックも含めて独立関数に切り出す
（`_own_switch_target_score()`が同じ理由で既に切り出し済みの前例に倣う）。

- [ ] **Step 1: 失敗するテストを先に書く**

`tests/test_dragapult_agent.py`に追記：

```python
def test_evolve_score_dreepy_to_drakloak():
    """Dreepy(たね)の進化(→Drakloak)は既存通り+30000の加点"""
    assert dm._evolve_score(
        dm.Dreepy, energy_count=0, dragapult_ex_field_count=0, opponent_prize_count=6,
    ) == 30000


def test_evolve_score_duskull_to_dusclops():
    """Duskull(ヨマワル)の進化(→サマヨール)は専用の+25000加点"""
    assert dm._evolve_score(
        dm.Duskull, energy_count=0, dragapult_ex_field_count=0, opponent_prize_count=6,
    ) == 25000


def test_evolve_score_dusclops_to_dusknoir():
    """Dusclops(サマヨール)の進化(→ヨノワール)は専用の+60000加点"""
    assert dm._evolve_score(
        dm.Dusclops, energy_count=0, dragapult_ex_field_count=0, opponent_prize_count=6,
    ) == 60000


def test_evolve_score_drakloak_to_dragapult_ex_default_fallback():
    """Duskull/Dusclops/Dreepy以外(=Drakloak→Dragapult_ex)は既存通り+70000の加点"""
    assert dm._evolve_score(
        dm.Drakloak, energy_count=0, dragapult_ex_field_count=0, opponent_prize_count=6,
    ) == 70000


def test_evolve_score_drakloak_to_dragapult_ex_suppressed_when_enough_on_field():
    """ドラパルトexが既に2体以上場にいる場合は既存通り-1で見送る"""
    assert dm._evolve_score(
        dm.Drakloak, energy_count=0, dragapult_ex_field_count=2, opponent_prize_count=6,
    ) == -1


def test_evolve_score_adds_energy_count_bonus():
    """既存通り、進化元のエネルギー数がそのまま加点される"""
    assert dm._evolve_score(
        dm.Dreepy, energy_count=2, dragapult_ex_field_count=0, opponent_prize_count=6,
    ) == 30002
```

- [ ] **Step 2: テストを実行して失敗することを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "evolve_score"`
Expected: FAIL（`AttributeError: module 'dragapult_agent.main' has no attribute '_evolve_score'`）

- [ ] **Step 3: `_evolve_score()`を実装し、`_own_switch_target_score()`の直後に追加**

```python
def _evolve_score(
    pre_evolution_id: int, energy_count: int, dragapult_ex_field_count: int,
    opponent_prize_count: int,
) -> int:
    """OptionType.EVOLVEのスコアを返す（進化元ポケモンのエネルギー数は
    呼び出し側で加算済みの前提ではなく、この関数内で加算する）。
    既存のDreepy→Drakloak・Drakloak→Dragapult_exの優先度は維持しつつ、
    新規のDuskull(ヨマワル)→Dusclops(サマヨール)・
    Dusclops(サマヨール)→Dusknoir(ヨノワール)の優先度を追加する。
    ドラパルトライン優先の設計方針（設計書参照）に基づき、ヨマワル系統の
    加点はドラパルトライン（Dreepy=30000、フォールバックのDrakloak=70000）
    よりやや低く設定している"""
    score = energy_count
    if pre_evolution_id == Dreepy:
        return score + 30000
    elif pre_evolution_id == Duskull:
        return score + 25000
    elif pre_evolution_id == Dusclops:
        return score + 60000
    elif (dragapult_ex_field_count >= 2
          or (dragapult_ex_field_count == 1 and opponent_prize_count <= 2)):
        return -1
    else:
        return score + 70000
```

- [ ] **Step 4: テストを実行してPASSすることを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "evolve_score"`
Expected: 6件PASS

- [ ] **Step 5: `OptionType.EVOLVE`分岐から`_evolve_score()`を呼び出す**

`main.py`の`OptionType.EVOLVE`分岐：

```python
        elif o.type == OptionType.EVOLVE:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            score += len(pokemon.energies)
            if pokemon.id == Dreepy:
                score += 30000
            elif field_counts[Dragapult_ex] >= 2 or (field_counts[Dragapult_ex] == 1 and len(op_state.prize) <= 2):
                score = -1
            else:
                score += 70000
```

を以下に変更：

```python
        elif o.type == OptionType.EVOLVE:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            score = _evolve_score(
                pokemon.id, len(pokemon.energies), field_counts[Dragapult_ex], len(op_state.prize),
            )
```

- [ ] **Step 6: リポジトリ全体のテストを実行**

Run: `uv run pytest`
Expected: 既存の既知の失敗以外は全てPASS

- [ ] **Step 7: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "refactor(dragapult): EVOLVE dispatchを_evolve_score()へ切り出し、ヨマワル系統の優先度を追加"
```

---

## Task 6: ヨマワルの特性「むかえにいく」ロジック

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: Task 1の`Duskull`定数、既存の`discard_counts`（`agent()`内変数、変更なし）
- Produces: `_fetch_from_discard_score(discard_count: int, bench_space: int) -> int`
  （新規独立関数）

デッキ内はヨマワル2・サマヨール1・ヨノワール1の計4枚のみ。主目的はハイパーボール等で
手札から直接トラッシュされたヨマワルの回収とし、トラッシュに回収対象がない、
またはベンチに空きがない場合は使う意味がない。

- [ ] **Step 1: 失敗するテストを先に書く**

```python
def test_fetch_from_discard_score_high_when_target_available():
    """トラッシュにヨマワルがあり、ベンチにも空きがあれば積極的に使う"""
    assert dm._fetch_from_discard_score(discard_count=1, bench_space=2) == 42000


def test_fetch_from_discard_score_low_when_discard_empty():
    """トラッシュに回収対象のヨマワルが無ければ使う意味がない"""
    assert dm._fetch_from_discard_score(discard_count=0, bench_space=2) == -1


def test_fetch_from_discard_score_low_when_bench_full():
    """ベンチに空きが無ければ戻す先が無く使う意味がない"""
    assert dm._fetch_from_discard_score(discard_count=1, bench_space=0) == -1
```

- [ ] **Step 2: テストを実行して失敗することを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "fetch_from_discard"`
Expected: FAIL

- [ ] **Step 3: `_fetch_from_discard_score()`を実装**

`main.py`の`_evolve_score()`関数の直後に追加：

```python
def _fetch_from_discard_score(discard_count: int, bench_space: int) -> int:
    """ヨマワルの特性「むかえにいく」（トラッシュから最大3枚のヨマワルをベンチに戻す）
    のスコアを返す。デッキ内はヨマワル2・サマヨール1・ヨノワール1の計4枚のみのため、
    主目的はハイパーボール等で手札から直接トラッシュされたヨマワルの回収。
    トラッシュに回収対象がなければ、または自分のベンチに空きがなければ
    使う意味がない（docs/superpowers/specs/2026-07-23-dragapult-crustle-counter-deck-design.md）"""
    if discard_count <= 0 or bench_space <= 0:
        return -1
    return 42000
```

- [ ] **Step 4: テストを実行してPASSすることを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "fetch_from_discard"`
Expected: 3件PASS

- [ ] **Step 5: `OptionType.ABILITY`分岐から呼び出す**

`main.py`の`OptionType.ABILITY`分岐：

```python
        elif o.type == OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if no_draw:
                score = -1
            elif card.id == 1267:  # Lumiose City
                score = 1
            else:
                score = 40000
```

を以下に変更：

```python
        elif o.type == OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if no_draw:
                score = -1
            elif card.id == 1267:  # Lumiose City
                score = 1
            elif card.id == Duskull:
                bench_space = my_state.benchMax - len(my_state.bench)
                score = _fetch_from_discard_score(discard_counts[Duskull], bench_space)
            else:
                score = 40000
```

- [ ] **Step 6: リポジトリ全体のテストを実行**

Run: `uv run pytest`
Expected: 既存の既知の失敗以外は全てPASS

- [ ] **Step 7: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "feat(dragapult): ヨマワルの特性「むかえにいく」発動条件を追加"
```

---

## Task 7: カースドボム（ヨノワール／サマヨール）のABILITY判断ロジック

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: 既存の`no_damage_dex(id: int) -> bool`関数（`main.py:327`付近、変更なし）
- Produces: `_cursed_bomb_score(opponent_active_id: int | None) -> int`（新規独立関数）

「ダメカンの直接配置」は「攻撃ダメージ」ではないため、イワパレスの特性
（exの**攻撃ダメージ**のみを防ぐ）を迂回できる。自爆前提のため、相手アクティブが
`no_damage_dex()`該当（直接攻撃が完全ブロックされる相手）の時のみ発動する。

- [ ] **Step 1: 失敗するテストを先に書く**

```python
def test_cursed_bomb_score_high_when_opponent_active_blocks_direct_damage():
    """相手アクティブがno_damage_dex()該当（イワパレス等、直接攻撃を完全ブロックする
    相手）の時は、カースドボム(自爆技)を積極的に使う"""
    assert dm._cursed_bomb_score(opponent_active_id=345) == 90000  # Crustle


def test_cursed_bomb_score_low_for_normal_opponent():
    """通常の相手（直接攻撃が通る）には温存し、自爆技は使わない"""
    assert dm._cursed_bomb_score(opponent_active_id=1) == -1


def test_cursed_bomb_score_low_when_no_opponent_active():
    """相手アクティブが存在しない（Noneが渡された）場合も温存する"""
    assert dm._cursed_bomb_score(opponent_active_id=None) == -1
```

- [ ] **Step 2: テストを実行して失敗することを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "cursed_bomb"`
Expected: FAIL（`AttributeError: module 'dragapult_agent.main' has no attribute '_cursed_bomb_score'`）

- [ ] **Step 3: `_cursed_bomb_score()`を実装**

`main.py`の`_fetch_from_discard_score()`関数の直後に追加：

```python
def _cursed_bomb_score(opponent_active_id: int | None) -> int:
    """ヨノワール／サマヨールの特性「カースドボム」
    （自分を気絶させ、相手ポケモン1匹にダメカンを直接配置）のスコアを返す。
    「ダメカンの直接配置」は「攻撃ダメージ」ではないため、イワパレスのような
    no_damage_dex()該当の特性ブロックを迂回できる。自爆前提のため、
    相手アクティブが直接攻撃を完全ブロックする相手の時のみ発動する
    （docs/superpowers/specs/2026-07-23-dragapult-crustle-counter-deck-design.md）"""
    if opponent_active_id is not None and no_damage_dex(opponent_active_id):
        return 90000
    return -1
```

- [ ] **Step 4: テストを実行してPASSすることを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "cursed_bomb"`
Expected: 3件PASS

- [ ] **Step 5: `OptionType.ABILITY`分岐から`_cursed_bomb_score()`を呼び出す**

`main.py`の`OptionType.ABILITY`分岐（Task 6で変更済みのもの）：

```python
            elif card.id == Duskull:
                bench_space = my_state.benchMax - len(my_state.bench)
                score = _fetch_from_discard_score(discard_counts[Duskull], bench_space)
            else:
                score = 40000
```

を以下に変更：

```python
            elif card.id == Duskull:
                bench_space = my_state.benchMax - len(my_state.bench)
                score = _fetch_from_discard_score(discard_counts[Duskull], bench_space)
            elif card.id == Dusknoir or card.id == Dusclops:
                opponent_active_id = op_state.active[0].id if op_state.active else None
                score = _cursed_bomb_score(opponent_active_id)
            else:
                score = 40000
```

- [ ] **Step 6: リポジトリ全体のテストを実行**

Run: `uv run pytest`
Expected: 既存の既知の失敗以外は全てPASS

- [ ] **Step 7: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "feat(dragapult): ヨノワール/サマヨールのカースドボム発動条件を追加"
```

---

## Task 8: マシマシラのアビリティ発動条件ロジック

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: 既存の`no_damage_dex()`関数
- Produces: `_adrena_brain_score(opponent_active_id: int | None) -> int`（新規独立関数）

マシマシラの特性「アドレナブレイン」（悪エネルギー装着時、自分の場のポケモン1匹の
ダメカン最大3個を相手のポケモン1匹に移し替え。自爆なし・毎ターン使用可）も、
カースドボムと同じ理由でイワパレスの特性を迂回できる。今回は発動条件
（ABILITY選択時のゲーティング）のみを実装し、「瀕死の相手ポケモンを確実にKOできる
場合」「自分側HPが40以下にならない」等の追加ガードは、実際のSelectContext形状が
実戦ログでまだ確認できていないため次回以降に持ち越す（Global Constraints参照）。

- [ ] **Step 1: 失敗するテストを先に書く**

```python
def test_adrena_brain_score_high_when_opponent_active_blocks_direct_damage():
    assert dm._adrena_brain_score(opponent_active_id=345) == 85000  # Crustle


def test_adrena_brain_score_low_for_normal_opponent():
    assert dm._adrena_brain_score(opponent_active_id=1) == -1


def test_adrena_brain_score_low_when_no_opponent_active():
    assert dm._adrena_brain_score(opponent_active_id=None) == -1
```

- [ ] **Step 2: テストを実行して失敗することを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "adrena_brain"`
Expected: FAIL

- [ ] **Step 3: `_adrena_brain_score()`を実装**

`main.py`の`_cursed_bomb_score()`関数の直後に追加：

```python
def _adrena_brain_score(opponent_active_id: int | None) -> int:
    """マシマシラの特性「アドレナブレイン」
    （悪エネルギー装着時、自分の場のポケモン1匹のダメカン最大3個を
    相手のポケモン1匹に移し替え。自爆なし・毎ターン使用可）のスコアを返す。
    カースドボムと同じ理由（ダメカンの直接配置は攻撃ダメージではないため）で
    イワパレスの特性を迂回できる。発動条件のみを実装し、対象選択（どのポケモンの
    ダメカンを何個移すか）は既存の汎用ロジックに委ねる（次回以降のログ検証待ち）"""
    if opponent_active_id is not None and no_damage_dex(opponent_active_id):
        return 85000
    return -1
```

- [ ] **Step 4: テストを実行してPASSすることを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "adrena_brain"`
Expected: 3件PASS

- [ ] **Step 5: `OptionType.ABILITY`分岐に統合**

`main.py`の`OptionType.ABILITY`分岐（Task 7で変更済みのもの）：

```python
            elif card.id == Dusknoir or card.id == Dusclops:
                opponent_active_id = op_state.active[0].id if op_state.active else None
                score = _cursed_bomb_score(opponent_active_id)
            else:
                score = 40000
```

を以下に変更：

```python
            elif card.id == Dusknoir or card.id == Dusclops:
                opponent_active_id = op_state.active[0].id if op_state.active else None
                score = _cursed_bomb_score(opponent_active_id)
            elif card.id == Munkidori:
                opponent_active_id = op_state.active[0].id if op_state.active else None
                score = _adrena_brain_score(opponent_active_id)
            else:
                score = 40000
```

- [ ] **Step 6: リポジトリ全体のテストを実行**

Run: `uv run pytest`
Expected: 既存の既知の失敗以外は全てPASS

- [ ] **Step 7: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "feat(dragapult): マシマシラのアドレナブレイン発動条件を追加"
```

---

## Task 9: `_attach_score()`統合（イベルタル優先・ヨノワール/サマヨール低優先度・悪エネルギー対応）

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: Task 1の`Yveltal`, `Dusknoir`, `Dusclops`, `Basic_Dark_Energy`定数

- [ ] **Step 1: 失敗するテストを先に書く**

```python
def test_attach_score_yveltal_prioritizes_dark_energy_when_active():
    """イベルタルは悪エネルギー装着の最優先先。アクティブかつ攻撃可能状態なら高スコア"""
    card_table = {dm.Basic_Dark_Energy: _MockCardData(cardId=dm.Basic_Dark_Energy)}
    pokemon = _MockPokemon(id=dm.Yveltal)
    score = dm._attach_score(
        dm.Basic_Dark_Energy, pokemon, True,
        card_table=card_table, can_switch=False, bench_attacker=False,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    assert score == 24000


def test_attach_score_yveltal_rejects_non_dark_energy():
    """イベルタルの技コストは悪エネルギーのみのため、炎/超エネルギーは無意味"""
    card_table = {dm.Basic_Fire_Energy: _MockCardData(cardId=dm.Basic_Fire_Energy)}
    pokemon = _MockPokemon(id=dm.Yveltal)
    score = dm._attach_score(
        dm.Basic_Fire_Energy, pokemon, True,
        card_table=card_table, can_switch=False, bench_attacker=False,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    assert score == -1


def test_attach_score_dusknoir_and_dusclops_get_low_priority():
    """カースドボムはエネルギー不要のため、ヨノワール/サマヨールへの
    エネルギー投資は低優先度に留める"""
    card_table = {dm.Basic_Psychic_Energy: _MockCardData(cardId=dm.Basic_Psychic_Energy)}
    for card_id in (dm.Dusknoir, dm.Dusclops):
        pokemon = _MockPokemon(id=card_id)
        score = dm._attach_score(
            dm.Basic_Psychic_Energy, pokemon, False,
            card_table=card_table, can_switch=False, bench_attacker=False,
            no_more_dex=False, field_counts=defaultdict(int),
            my_asleep=False, my_paralyzed=False,
        )
        assert score == 500
```

- [ ] **Step 2: テストを実行して失敗することを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "yveltal or dusknoir_and_dusclops"`
Expected: FAIL（イベルタル/ヨノワール/サマヨール分岐が存在せず、既存の汎用ロジックに
フォールバックして期待値と異なるスコアが返るため）

- [ ] **Step 3: `_attach_score()`に分岐を追加**

`main.py`の`_attach_score()`関数：

```python
    # Attach energy
    if pokemon.id == Budew:
        return -1
    elif pokemon.id == Meowth_ex or pokemon.id == Fezandipiti_ex:
        if active and not can_switch and not my_asleep and not my_paralyzed:
            if bench_attacker or field_counts[Budew] >= 1:
                return 22000
            else:
                return 18000
        else:
            return -1
```

を以下に変更（`Yveltal`と`Dusknoir`/`Dusclops`の分岐を追加）：

```python
    # Attach energy
    if pokemon.id == Budew:
        return -1
    elif pokemon.id == Meowth_ex or pokemon.id == Fezandipiti_ex:
        if active and not can_switch and not my_asleep and not my_paralyzed:
            if bench_attacker or field_counts[Budew] >= 1:
                return 22000
            else:
                return 18000
        else:
            return -1
    elif pokemon.id == Yveltal:
        # イベルタルの技コストは悪エネルギーのみ。それ以外は装着しても無意味
        if attach_id != Basic_Dark_Energy:
            return -1
        if active and not can_switch and not my_asleep and not my_paralyzed:
            return 24000
        else:
            return 19000
    elif pokemon.id == Dusknoir or pokemon.id == Dusclops:
        # カースドボムはエネルギー不要のため、通常はエネルギー投資の優先度を下げる
        return 500
```

`hand_score()`内の以下の行：

```python
        elif id == Basic_Fire_Energy or id == Basic_Psychic_Energy:
```

を以下に変更：

```python
        elif id == Basic_Fire_Energy or id == Basic_Psychic_Energy or id == Basic_Dark_Energy:
```

- [ ] **Step 4: テストを実行してPASSすることを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "yveltal or dusknoir_and_dusclops"`
Expected: 3件PASS

- [ ] **Step 5: リポジトリ全体のテストを実行**

Run: `uv run pytest`
Expected: 既存の既知の失敗以外は全てPASS

- [ ] **Step 6: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "feat(dragapult): _attach_score()にイベルタル優先/ヨノワール・サマヨール低優先度を統合"
```

---

## Task 10: `_own_switch_target_score()`統合（ファイヤー・イベルタル・ヨノワール）

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: Task 1の`Moltres`, `Yveltal`, `Dusknoir`定数
- Produces: `_own_switch_target_score(card_id, energy_count, bench_attacker,
  opponent_active_is_ex)`（**シグネチャ変更**：第4引数`opponent_active_is_ex: bool`
  を新規追加。既存の呼び出し元（`agent()`本体・既存テスト）は全て更新が必要）

- [ ] **Step 1: 既存テストをシグネチャ変更に合わせて更新**

`tests/test_dragapult_agent.py`内、`_own_switch_target_score`を呼んでいる
既存4関数を以下のように更新する（第4引数`opponent_active_is_ex`を明示的に渡す）：

```python
def test_own_switch_target_score_dragapult_ex_beats_budew_even_without_bench_attacker():
    dragapult_ex_score = dm._own_switch_target_score(
        dm.Dragapult_ex, energy_count=0, bench_attacker=False, opponent_active_is_ex=False)
    budew_score = dm._own_switch_target_score(
        dm.Budew, energy_count=0, bench_attacker=False, opponent_active_is_ex=False)
    assert dragapult_ex_score > budew_score
    assert dragapult_ex_score == 50000
    assert budew_score == 30000


def test_own_switch_target_score_budew_is_zero_when_bench_attacker_ready():
    assert dm._own_switch_target_score(
        dm.Budew, energy_count=0, bench_attacker=True, opponent_active_is_ex=False) == 0


def test_own_switch_target_score_existing_priorities_unchanged():
    assert dm._own_switch_target_score(
        dm.Dreepy, energy_count=0, bench_attacker=False, opponent_active_is_ex=False) == 10000
    assert dm._own_switch_target_score(
        dm.Drakloak, energy_count=1, bench_attacker=False, opponent_active_is_ex=False) == 20000
    assert dm._own_switch_target_score(
        dm.Drakloak, energy_count=0, bench_attacker=False, opponent_active_is_ex=False) == -10000
    assert dm._own_switch_target_score(
        dm.Fezandipiti_ex, energy_count=0, bench_attacker=False, opponent_active_is_ex=False) == -1000
    assert dm._own_switch_target_score(
        dm.Meowth_ex, energy_count=0, bench_attacker=False, opponent_active_is_ex=False) == -2000
    assert dm._own_switch_target_score(
        999999, energy_count=0, bench_attacker=False, opponent_active_is_ex=False) == 0
```

- [ ] **Step 2: 新規ポケモンの分岐を検証する失敗テストを追加**

```python
def test_own_switch_target_score_moltres_prioritized_when_opponent_active_is_ex():
    """相手アクティブがexの時のみドラパルトexと同等の高優先度、それ以外は低優先度"""
    high = dm._own_switch_target_score(
        dm.Moltres, energy_count=0, bench_attacker=False, opponent_active_is_ex=True)
    low = dm._own_switch_target_score(
        dm.Moltres, energy_count=0, bench_attacker=False, opponent_active_is_ex=False)
    assert high == 49000
    assert low == 5000
    assert high > low


def test_own_switch_target_score_yveltal_is_mid_priority():
    """イベルタルはドラパルトexより低い中程度の優先度（主力が倒れた際のつなぎ）"""
    yveltal_score = dm._own_switch_target_score(
        dm.Yveltal, energy_count=0, bench_attacker=False, opponent_active_is_ex=False)
    dragapult_ex_score = dm._own_switch_target_score(
        dm.Dragapult_ex, energy_count=0, bench_attacker=False, opponent_active_is_ex=False)
    assert 0 < yveltal_score < dragapult_ex_score
    assert yveltal_score == 15000


def test_own_switch_target_score_dusknoir_is_low_priority():
    """貴重な1枚をカースドボム抜きで晒すと丸損なため、低優先度"""
    assert dm._own_switch_target_score(
        dm.Dusknoir, energy_count=0, bench_attacker=False, opponent_active_is_ex=False) < 0
```

- [ ] **Step 3: テストを実行して失敗することを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "own_switch_target"`
Expected: FAIL（シグネチャ不一致の`TypeError`、および新規ポケモン分岐が
未実装のため0が返り期待値と不一致）

- [ ] **Step 4: `_own_switch_target_score()`のシグネチャと分岐を更新**

`main.py`の`_own_switch_target_score()`関数：

```python
def _own_switch_target_score(card_id: int, energy_count: int, bench_attacker: bool) -> int:
    """SelectContext.SWITCH/TO_ACTIVE/SETUP_ACTIVE_POKEMON共通で、
    自分のポケモンをアクティブへ送る候補への優先度スコアを返す
    （hp・energy_count*1000の共通加点は呼び出し側で加算する）。
    強制入場時のみスボミーを特別優先していた分岐は、実戦で効果が
    機能している確証がなく、本命アタッカーを出し損ねるリスクの方が
    明確なため削除した（2026-07-23、docs/analyses/20260723-dragapult-post-attach-fix-20-games.md参照）。"""
    if card_id == Dreepy:
        return 10000
    elif card_id == Drakloak:
        return 20000 if energy_count >= 1 else -10000
    elif card_id == Dragapult_ex:
        return 50000
    elif card_id == Budew:
        return 30000 if not bench_attacker else 0
    elif card_id == Fezandipiti_ex:
        return -1000
    elif card_id == Meowth_ex:
        return -2000
    return 0
```

を以下に変更：

```python
def _own_switch_target_score(
    card_id: int, energy_count: int, bench_attacker: bool, opponent_active_is_ex: bool,
) -> int:
    """SelectContext.SWITCH/TO_ACTIVE/SETUP_ACTIVE_POKEMON共通で、
    自分のポケモンをアクティブへ送る候補への優先度スコアを返す
    （hp・energy_count*1000の共通加点は呼び出し側で加算する）。
    強制入場時のみスボミーを特別優先していた分岐は、実戦で効果が
    機能している確証がなく、本命アタッカーを出し損ねるリスクの方が
    明確なため削除した（2026-07-23、docs/analyses/20260723-dragapult-post-attach-fix-20-games.md参照）。
    ファイヤーは相手アクティブがexの時のみドラパルトexと同等の優先度
    （非ex攻撃で110ダメージを狙えるため）、イベルタルは主力が倒れた際の
    つなぎとして中程度の優先度、ヨノワールは貴重な1枚をカースドボム抜きで
    晒すと丸損なため低優先度とする
    （docs/superpowers/specs/2026-07-23-dragapult-crustle-counter-deck-design.md）"""
    if card_id == Dreepy:
        return 10000
    elif card_id == Drakloak:
        return 20000 if energy_count >= 1 else -10000
    elif card_id == Dragapult_ex:
        return 50000
    elif card_id == Budew:
        return 30000 if not bench_attacker else 0
    elif card_id == Fezandipiti_ex:
        return -1000
    elif card_id == Meowth_ex:
        return -2000
    elif card_id == Moltres:
        return 49000 if opponent_active_is_ex else 5000
    elif card_id == Yveltal:
        return 15000
    elif card_id == Dusknoir:
        return -500
    return 0
```

- [ ] **Step 5: 呼び出し元を更新**

`main.py`の`OptionType.CARD`分岐内、`SelectContext.SWITCH`等の処理：

```python
                if (context == SelectContext.SWITCH
                    or context == SelectContext.TO_ACTIVE
                    or context == SelectContext.SETUP_ACTIVE_POKEMON):
                    # Selection of the Pokémon to send to the Active Spot
                    if o.playerIndex == my_index:
                        score += _own_switch_target_score(card.id, energy_count, bench_attacker)
                    else:
                        if plan_a.attack == o.index + 1:
                            score += 100000
                    score += energy_count * 1000
                    score += hp
```

を以下に変更：

```python
                if (context == SelectContext.SWITCH
                    or context == SelectContext.TO_ACTIVE
                    or context == SelectContext.SETUP_ACTIVE_POKEMON):
                    # Selection of the Pokémon to send to the Active Spot
                    if o.playerIndex == my_index:
                        opponent_active_is_ex = (
                            len(op_state.active) > 0 and op_state.active[0] is not None
                            and card_table[op_state.active[0].id].ex
                        )
                        score += _own_switch_target_score(
                            card.id, energy_count, bench_attacker, opponent_active_is_ex)
                    else:
                        if plan_a.attack == o.index + 1:
                            score += 100000
                    score += energy_count * 1000
                    score += hp
```

- [ ] **Step 6: テストを実行してPASSすることを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "own_switch_target"`
Expected: 全件PASS

- [ ] **Step 7: リポジトリ全体のテストを実行**

Run: `uv run pytest`
Expected: 既存の既知の失敗以外は全てPASS

- [ ] **Step 8: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "feat(dragapult): _own_switch_target_score()にファイヤー/イベルタル/ヨノワールを統合"
```

---

## Task 11: `TrainerCardPolicy`登録（ヒカリ・メイのはげまし・ジャミングタワー）

**Files:**
- Modify: `src/dragapult_agent/main.py`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: Task 1の`Dawn`, `Rosas_Encouragement`, `Jamming_Tower`定数、
  既存の`SupporterSelectedPolicy`クラス（変更なし）
- Produces: 新規`JammingTowerPolicy`クラス

ヒカリ・メイのはげましはサポートカードのため、既存の`SupporterSelectedPolicy`
（`use_support`と一致した場合のみ得点する仕組み。1ターン1枚のサポート制限を守る
ための既存メカニズム）をそのまま再利用する。ジャミングタワーはスタジアムのため、
`TeamRocketWatchtowerPolicy`（Task 2で削除済み）と同様の専用クラスを新設する。

- [ ] **Step 1: 失敗するテストを先に書く**

```python
def test_jamming_tower_policy_plays_when_no_own_stadium():
    policy = dm.JammingTowerPolicy()
    ctx = _make_ctx(stadium_id=0)
    assert policy.play_score(ctx) == 30000


def test_jamming_tower_policy_holds_when_already_active():
    policy = dm.JammingTowerPolicy()
    ctx = _make_ctx(stadium_id=dm.Jamming_Tower)
    assert policy.play_score(ctx) == -1


def test_jamming_tower_policy_replays_over_opponent_stadium():
    """相手のスタジアムが設置済みでも、ジャミングタワー(自分のもの)ではないので
    常時採用の方針通りプレイする"""
    policy = dm.JammingTowerPolicy()
    ctx = _make_ctx(stadium_id=999999)
    assert policy.play_score(ctx) == 30000


def test_dawn_and_rosas_encouragement_and_jamming_tower_registered():
    assert dm._score_play_trainer_card(
        dm.Dawn, _make_ctx(card_id=dm.Dawn, use_support=dm.Dawn)
    ) == 22000
    assert dm._score_play_trainer_card(
        dm.Rosas_Encouragement,
        _make_ctx(card_id=dm.Rosas_Encouragement, use_support=dm.Rosas_Encouragement)
    ) == 21000
    assert dm._score_play_trainer_card(
        dm.Jamming_Tower, _make_ctx(stadium_id=0)
    ) == 30000


def test_trainer_card_policies_cover_updated_card_set():
    """Task 2の更新に、ヒカリ・メイのはげまし・ジャミングタワーを追加した最終集合と一致すること"""
    expected = {
        dm.Rare_Candy, dm.Unfair_Stamp, dm.Night_Stretcher,
        dm.Boss_Orders, dm.Lillie_Determination,
        dm.Buddy_Buddy_Poffin, dm.Ultra_Ball, dm.Poke_Pad, dm.Crispin,
        dm.Dawn, dm.Rosas_Encouragement, dm.Jamming_Tower,
    }
    assert set(dm.TRAINER_CARD_POLICIES.keys()) == expected
```

（このテストを追加する際、Task 2で更新した
`test_trainer_card_policies_cover_exactly_the_migrated_card_set`は削除し、
上記`test_trainer_card_policies_cover_updated_card_set`に置き換える）

- [ ] **Step 2: テストを実行して失敗することを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v -k "jamming_tower or dawn_and_rosas"`
Expected: FAIL

- [ ] **Step 3: `hand_score()`にヒカリ・メイのはげまし・ジャミングタワーの分岐を追加**

`hand_score()`内、`elif id == Lillie_Determination:`ブロックの直後に追加：

```python
        elif id == Dawn:
            score = 22000
        elif id == Rosas_Encouragement:
            score = 21000 if prize_diff < 0 else UNNECESSARY
        elif id == Jamming_Tower:
            score = 8000
```

- [ ] **Step 4: `JammingTowerPolicy`クラスを新設し登録**

`main.py`の`PokePadPolicy`クラス定義の直後に追加：

```python
class JammingTowerPolicy(TrainerCardPolicy):
    """両者の「どうぐ」を無効化するスタジアム。自デッキはツールカードを
    採用していないため実質相手のみ不利化する。常時採用する方針とし、
    既に自分のジャミングタワーが場にある場合のみ見送る"""
    def play_score(self, ctx: PlayTrainerCardContext) -> int:
        if ctx.stadium_id == Jamming_Tower:
            return -1
        return 30000
```

`TRAINER_CARD_POLICIES`辞書に以下を追加：

```python
    Dawn: SupporterSelectedPolicy(22000),
    Rosas_Encouragement: SupporterSelectedPolicy(21000),
    Jamming_Tower: JammingTowerPolicy(),
```

- [ ] **Step 5: テストを実行してPASSすることを確認**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: 全件PASS

- [ ] **Step 6: リポジトリ全体のテストを実行**

Run: `uv run pytest`
Expected: 既存の既知の失敗以外は全てPASS

- [ ] **Step 7: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "feat(dragapult): ヒカリ/メイのはげまし/ジャミングタワーをTrainerCardPolicyへ登録"
```

---

## Task 12: 提出用notebook再生成・全体テスト実行・実装サマリー作成

**Files:**
- Modify: `notebooks/submissions/dragapult_agent_submission.ipynb`（ビルド成果物、再生成のみ）
- Create: `docs/implementations/20260723-dragapult-crustle-counter-deck.md`

**Interfaces:**
- Consumes: Task 1〜11の全ての変更

- [ ] **Step 1: 提出用notebookを再生成**

Run: `uv run python scripts/build_dragapult_submission_notebook.py`
Expected: `notebooks/submissions/dragapult_agent_submission.ipynb`が更新される
（`*.ipynb`は`.gitignore`方針でビルド成果物として未コミット）

- [ ] **Step 2: 再生成されたnotebookに新規カード定数・ロジックが含まれていることを目視確認**

Run: `grep -c "Duskull\|Dusclops\|Dusknoir\|Munkidori\|Moltres\|Yveltal\|Dawn\|Rosas_Encouragement\|Jamming_Tower" notebooks/submissions/dragapult_agent_submission.ipynb`
Expected: 0より大きい件数

- [ ] **Step 3: リポジトリ全体のテストスイートを実行し、既存の既知の失敗以外が全てPASSすることを最終確認**

Run: `uv run pytest`
Expected: 新規追加分（Task 1〜11で追加したテスト全て）を含めて全てPASS
（既存の無関係な既知の失敗・エラーのみ変化なし）

- [ ] **Step 4: 実装サマリーを作成**

`docs/implementations/20260723-dragapult-crustle-counter-deck.md`を新規作成し、
以下を含める：
- 変更の背景（レーティング300急落・イワパレス構造的弱点）
- デッキ構成の変更点（除外5種・新規9種）
- 新規実装したロジック一覧（むかえにいく・カースドボム・アドレナブレイン発動条件、
  `_evolve_score()`切り出し、`_attach_score()`/`_own_switch_target_score()`統合、
  TrainerCardPolicy登録）
- 未検証・次回持ち越しの項目（マシマシラの対象選択詳細、Rare Candyと
  ヨマワル系統の相互作用、Hikari/EVOLVE分岐の実戦ログ検証）
- テスト結果（PASS件数）

- [ ] **Step 5: コミット**

```bash
git add docs/implementations/20260723-dragapult-crustle-counter-deck.md
git commit -m "docs(dragapult): イワパレス対策デッキの実装サマリーを追加"
```

---

## 実装後の残課題（意図的にスコープ外）

- マシマシラの特性「アドレナブレイン」の対象選択詳細（自分のどのポケモンから
  ダメカンを移すか、HP40ガード等）は実戦ログでの検証後に精緻化する
- ヒカリの実際のSelectContext形状（`TO_HAND`経由で汎用的に処理されると想定して
  いるが未検証）が意図通りhand_score()の値を使って優先順位付けされているか
- Rare CandyとヨマワルNSamayouru/Dusknoirラインの相互作用（現行の
  `RareCandyPolicy`はドラパルトex専用の`no_more_dex`ゲートのみ）
- **`bench_attacker`フラグが現状`Dragapult_ex`の準備状況のみ判定しており
  （`field_counts[Dragapult_ex]と energies>=2`の組み合わせのみ）、ファイヤーが
  ベンチで攻撃準備完了している状況を拾えない可能性がある。この場合、
  `_own_switch_target_score()`でファイヤーが高優先度と評価されても、
  `OptionType.RETREAT`分岐の`do_switch`判定（`bench_attacker`依存）が
  先に交代自体を却下してしまい、実際には交代が起きない懸念がある。
  `bench_attacker`は`_attach_score()`・`hand_score()`・スボミーの
  switch_target優先度等、既存の多数箇所で参照されている共有フラグのため、
  安易な定義拡張は副作用が大きい。次回、実戦ログで「相手アクティブがexの時に
  ファイヤーへ交代できているか」を確認し、必要なら別フラグの新設を検討する**
- Kaggle再提出後の勝率実測検証（[[project_battle_log_parser]]の手法）
