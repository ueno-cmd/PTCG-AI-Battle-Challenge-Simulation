# オーロンゲ（グリムスナールex）デッキ改修 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `decks/grimmsnarl_20260701.py` のデッキ構成を、デッキアウト対策・進化事故対策を反映した新60枚構成に更新し、テストとデッキCSVを整合させる。

**Architecture:** デッキ定義ファイル（`DECK: list[tuple[int, int]]`）を書き換え、それに対応する`tests/test_grimmsnarl_deck.py`のアサーションを更新する。エージェントロジック（`src/grimmsnarl_agent/main.py`）は変更しない（スコープ外）。

**Tech Stack:** Python 3.12 / uv / pytest

## Global Constraints

- デッキは必ず合計60枚（設計書: `docs/superpowers/specs/2026-07-02-grimmsnarl-deck-revision-design.md`）
- エネルギー以外のカードは1種4枚まで（`card_id != 7`）
- ACE SPECカードは合計1枚まで（本改修では Secret Box, ID 1092 のみ）
- `src/grimmsnarl_agent/main.py` は変更しない（デッキ構成のみが今回のスコープ）
- 全コメントは日本語（CLAUDE.md準拠）

---

## Task 1: デッキテストを新構成向けに更新する（TDD: 先にテストを直す）

**Files:**
- Modify: `tests/test_grimmsnarl_deck.py`

**Interfaces:**
- Consumes: `decks.grimmsnarl_20260701.DECK`（`list[tuple[int, int]]`、現時点ではまだ旧構成のまま）
- Produces: なし（テストファイルのみ）

- [ ] **Step 1: `tests/test_grimmsnarl_deck.py` を以下の内容に置き換える**

```python
from decks.grimmsnarl_20260701 import DECK

ENERGY_IDS = {7}  # Basic {D} Energy
ACE_SPEC_IDS = {1092}  # Secret Box（data/EN_Card_Data.csv で Rule: ACE SPEC）


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
    assert 112 in ids, "Munkidori が不在"
    assert 104 in ids, "Froslass が不在"
    assert 689 in ids, "Yveltal が不在"


def test_removed_pokemon_absent():
    ids = {card_id for card_id, _ in DECK}
    assert 649 not in ids, "Marnie's Morpeko は今回の改修で削除されたはず"
    assert 66 not in ids, "Dudunsparce は今回の改修で削除されたはず"
    assert 305 not in ids, "Dunsparce は今回の改修で削除されたはず"


def test_energy_count():
    darkness = sum(c for i, c in DECK if i == 7)
    assert darkness == 12


def test_ace_spec_does_not_exceed_1_copy():
    for card_id, count in DECK:
        if card_id in ACE_SPEC_IDS:
            assert count <= 1, f"ACE SPECカード {card_id} が {count} 枚（上限1枚）"


def test_ace_spec_card_is_secret_box():
    secret_box_count = sum(c for i, c in DECK if i == 1092)
    assert secret_box_count == 1, "Secret Box が1枚採用されているはず"
    hero_cape_count = sum(c for i, c in DECK if i == 1159)
    assert hero_cape_count == 0, "Hero's Cape は今回の改修で削除されたはず（ACE SPECをSecret Boxに統合）"


def test_no_duplicate_card_id_entries():
    ids = [card_id for card_id, _ in DECK]
    assert len(ids) == len(set(ids)), "同じcard_idが複数タプルに分かれている"


def test_boss_orders_count():
    count = sum(c for i, c in DECK if i == 1182)
    assert count == 3


def test_energy_recycler_removed():
    count = sum(c for i, c in DECK if i == 1139)
    assert count == 0, "Energy Recycler は今回の改修で削除されたはず"
```

- [ ] **Step 2: 現時点（旧デッキのまま）でテストを実行し、狙った箇所が失敗することを確認する**

Run: `cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation && uv run pytest tests/test_grimmsnarl_deck.py -v`

Expected: 以下5件がFAIL、残りはPASS
- `test_key_pokemon_present`（104, 689が旧デッキに無い）
- `test_removed_pokemon_absent`（649, 66, 305が旧デッキに残っている）
- `test_ace_spec_card_is_secret_box`（旧デッキはSecret Box非採用・Hero's Cape採用中）
- `test_boss_orders_count`（旧デッキは2枚）
- `test_energy_recycler_removed`（旧デッキは2枚）

- [ ] **Step 3: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add tests/test_grimmsnarl_deck.py
git commit -m "test: オーロンゲデッキ改修に向けてテストを新構成向けに更新（Red状態）"
```

---

## Task 2: デッキ定義ファイルを新構成に更新する

**Files:**
- Modify: `decks/grimmsnarl_20260701.py`

**Interfaces:**
- Consumes: なし
- Produces: `DECK: list[tuple[int, int]]`（Task 1のテストが検証する）

- [ ] **Step 1: `decks/grimmsnarl_20260701.py` を以下の内容に置き換える**

```python
# マリィのグリムスナールex デッキ（20260702改修）
# 設計書: docs/superpowers/specs/2026-07-02-grimmsnarl-deck-revision-design.md
# 背景: LBスコアが700→500に下落。負けログ5件の解析でデッキアウト負け・進化事故負けが
#       判明したため、山札消費の大きいカードを整理し進化ラインを厚くした。
#       あわせてカードショップ大会リスト（本大会ルールとは異なる環境）を参考に
#       トールボックス要素（特性ポケモン群）を導入。

DECK = [
    # --- ポケモン: 20体 ---
    (646,  3),   # Marnie's Impidimp（進化元・Filchで初動ドロー・70HP）
    (647,  2),   # Marnie's Morgrem（進化中継・Rare Candy未引き時の保険を強化）
    (648,  3),   # Marnie's Grimmsnarl ex（メインアタッカー）
    (860,  2),   # Snorunt（Froslassの進化元）
    (104,  2),   # Froslass（特性: 毎ターン全特性持ちポケモンに1ダメカン。攻撃は使わない前提）
    (112,  3),   # Munkidori（Adrena-Brainでダメカン移動。Froslassの副産物ダメカンを転嫁）
    (235,  1),   # Budew（相手のグッズ使用を1ターン封じる）
    (343,  1),   # Shaymin（特性: 自分のルール無しベンチポケモンへのダメージを無効化）
    (122,  1),   # Tatsugiri（特性: バトル場にいる間、山札上6枚からサポートを回収）
    (689,  1),   # Yveltal（わしづかみ：相手を次の番にげられなくする。ガチグマの代替）
    (858,  1),   # Psyduck（特性: 自傷前提の特性を封じる）

    # --- トレーナーズ: 28枚 ---
    (1152, 4),   # Poké Pad（ポケモンサーチ）
    (1079, 3),   # Rare Candy（Impidimp→Grimmsnarl ex 一気進化）
    (1086, 2),   # Buddy-Buddy Poffin（低HP基本ポケモンをベンチ展開）
    (1097, 2),   # Night Stretcher（トラッシュ回収・山札を減らさない）
    (1227, 4),   # Lillie's Determination（手札リフレッシュ）
    (1182, 3),   # Boss's Orders（ベンチの弱ったポケモンを強制的にバトル場へ・KOを補助）
    (1259, 3),   # Spikemuth Gym（毎ターンMarnie's系サーチ）
    (1116, 2),   # Energy Switch（基本エネルギーの付け替え）
    (1092, 1),   # Secret Box（ACE SPEC・手札3枚トラッシュでグッズ/どうぐ/サポートをサーチ）
    (1174, 1),   # Air Balloon（にげるためのエネルギーを2個軽減）
    (1219, 3),   # Team Rocket's Petrel（トレーナーズ全般をサーチ）

    # --- エネルギー: 12枚 ---
    (7,   12),   # Basic {D} Energy
]
```

- [ ] **Step 2: テストを実行し全件PASSすることを確認する**

Run: `cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation && uv run pytest tests/test_grimmsnarl_deck.py -v`

Expected: 全10件PASS

- [ ] **Step 3: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add decks/grimmsnarl_20260701.py
git commit -m "feat: オーロンゲデッキをデッキアウト対策・進化事故対策構成に改修"
```

---

## Task 3: 既存テストスイート全体への影響確認とデッキCSVの再生成

**Files:**
- なし（生成物: `output/deck_YYYYMMDD_HHMMSS.csv`。`output/`はgitignore対象のためコミット不要）

**Interfaces:**
- Consumes: `decks/grimmsnarl_20260701.py` の `DECK`（Task 2で更新済み）
- Produces: `output/deck_YYYYMMDD_HHMMSS.csv`（Kaggleへの手動アップロード用）

- [ ] **Step 1: リポジトリ全体のテストを実行し、他デッキ・エージェントに影響が無いことを確認する**

Run: `cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation && uv run pytest -v`

Expected: 全件PASS（`tests/test_grimmsnarl_deck.py`以外のテストは今回の変更と無関係のため、全て既存通りPASSするはず）

- [ ] **Step 2: デッキCSVを再生成する**

Run: `cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation && uv run python scripts/build_deck.py decks/grimmsnarl_20260701.py`

Expected: `✓ (ID: xxx) × n [ID直接指定]` が20+28+12=39行分（タプル数分）出力され、末尾に `合計: 60 枚` と `出力: .../output/deck_YYYYMMDD_HHMMSS.csv` が表示される

- [ ] **Step 3: 生成されたCSVの行数が60行であることを確認する**

Run: `wc -l output/deck_*.csv | tail -1`（直前に生成した最新ファイルを目視で特定して確認してもよい）

Expected: `60`

---

## Task 4: 実装サマリーを保存する

**Files:**
- Create: `docs/implementations/20260702-grimmsnarl-deck-revision.md`

**Interfaces:**
- Consumes: Task 1〜3の結果
- Produces: なし（ドキュメントのみ）

- [ ] **Step 1: 実装サマリーを作成する**

```markdown
# 実装サマリー：オーロンゲ（グリムスナールex）デッキ改修

**実装日：** 2026-07-02
**関連設計書：** `docs/superpowers/specs/2026-07-02-grimmsnarl-deck-revision-design.md`

## 背景

LBスコアが700から500へ下落し連勝できない状態だった。負けバトルログ5件
（83101226, 83110611, 83141570, 83169077, 83173685）を解析した結果、
デッキアウト負け（35ターン戦でダメージ優勢だったが山札切れ）と
進化事故負け（13ターン戦で1回も攻撃できず敗北）の2パターンが判明した。

## 変更内容

### デッキ（`decks/grimmsnarl_20260701.py`）
- ポケモン: Morpeko/Dudunsparce/Dunsparceを削除し、Froslass・Snorunt・Munkidori増量・
  Budew・Shaymin・Tatsugiri・Yveltal・Psyduckを新規採用（20体、旧構成から総入れ替え）
- トレーナーズ: Dawn・Xerosic's Machinations・Energy Recyclerを削除、
  Rare Candy/Buddy-Buddy Poffin/Night Stretcherを減量、
  Boss's Orders 2→3、Energy Switch・Air Balloon・Team Rocket's Petrelを新規採用（28枚）
- ACE SPEC: Hero's Cape → Secret Box に変更
- エネルギー: Basic {D} Energy 12枚（変更なし）

参考情報として、カードショップ大会（本大会ルールとは別環境）で使用されていた
オーロンゲデッキのリストをユーザーから受領し、カードプール収録カードのみを
採用した。プール未収録の「スペシャルレッドカード」「ムク」（ZA環境限定）は不採用。
「ガチグマ」は闘エネルギー依存で本デッキ（闇単色）では機能しないためユーザー判断で
不採用とし、闇エネルギーで機能する「イベルタル」に差し替えた。

### テスト（`tests/test_grimmsnarl_deck.py`）
- 削除カード（Morpeko/Dudunsparce/Dunsparce/Energy Recycler/Hero's Cape）の
  不在を検証するテストを追加
- Boss's Orders枚数・ACE SPEC種別のアサーションを新構成に合わせて更新

## テスト結果

- `tests/test_grimmsnarl_deck.py`: 10件全てPASS
- リポジトリ全体のテストスイート: 全件PASS（既存の他デッキ・エージェントへの影響なし）

## 未対応・次回持ち越し

- Kaggle再提出後のスコア変化確認（本改修のスコープ外）
- 超高速デッキ（Mega Lucario ex、アラカザム）との相性問題は今回未対応
  （デッキ構成のみでは解決しきれない範囲と判断）
- 「15-30-15」比率から外れたトールボックス構成による事故率増加リスクは
  ユーザー確認済みの既知のトレードオフ
```

- [ ] **Step 2: コミットする**

```bash
cd /Users/t-ueno/Developer/PTCG-AI-Battle-Challenge-Simulation
git add docs/implementations/20260702-grimmsnarl-deck-revision.md
git commit -m "docs: オーロンゲデッキ改修の実装サマリーを追加"
```
