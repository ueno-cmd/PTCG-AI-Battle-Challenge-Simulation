# アカマツ(Crispin)スコアリング死角バグ修正 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/dragapult_agent/main.py`の`hand_score()`内、アカマツ(Crispin)のスコアリングで発見された「if文がelifになっておらず、山札のエネルギー枯渇時の低評価(10点)が常に上書きされて死んでいる」バグを、既存の`_attach_score`/`_boss_orders_score`/`_own_switch_target_score`と同じパターン（独立関数への抽出＋直接テスト）で修正する。

**Architecture:** アカマツのスコア計算ロジックを`_crispin_score()`という独立関数として`main.py`内に切り出し、`hand_score()`からはその関数を呼ぶだけにする。抽出時にif文の構造をelifチェーンに直し、バグを修正する。合わせて、同種の「siblingなifによる意図しない上書き」が`main.py`の他箇所に潜んでいないかを機械的に監査し、証跡を文書として残す。

**Tech Stack:** Python, pytest, 既存の`cg.api`型定義

## Global Constraints

- コードコメントは日本語で書く（変数名・関数名は英語）
- 既存の630件超のテストを一件も壊さない
- TDD（テスト→失敗確認→最小実装→成功確認）を厳守する
- YAGNI：バグ修正の範囲を超えたリファクタや機能追加はしない
- 修正後、提出用notebook生成スクリプトを再実行する（`scripts/build_dragapult_submission_notebook.py`）

---

## Task 1: main.pyのif/elif構造の全体監査（証跡を文書化）

ユーザーから「アカマツ以外にも同種の意図的でないバグが潜んでいないか、if/elseのガイドライン遵守状況を全体チェックすべき」との指摘があった。これに応え、`src/dragapult_agent/main.py`全909行の全ての条件分岐ブロックを機械的に見直し、「siblingなif文（elifであるべきなのに独立したifになっている）によって、先に代入したscoreが意図せず上書きされる」パターンが他に無いかを検証し、結果を証跡として保存する。

**Files:**
- Create: `docs/analyses/20260723-dragapult-main-if-else-audit.md`

**Interfaces:**
- 後続タスクへの影響なし（純粋な調査・文書化タスク）

- [ ] **Step 1: main.py内の全条件分岐ブロックを関数単位で棚卸しする**

以下の観点でチェックする：
1. `if A: score = X` の直後に、`elif`ではなく独立した`if B: score = Y else: score = Z`が続いていないか（続いていれば、Aが真の場合でもXが必ず上書きされ、Aの分岐が死ぬ）
2. 複合代入（`+=`/`-=`）による意図的な合成、または`return`文による早期リターンなど、上書きが安全な設計は問題なしとする
3. `_attach_score`（main.py:47-118）、`hand_score`内の各カード分岐（main.py:508-657）、`main_option_proc`（main.py:297-392）、`agent()`メイン処理（main.py:394-908）の4ブロックを対象とする

以下の結果を`docs/analyses/20260723-dragapult-main-if-else-audit.md`に保存する（実際に確認した内容をそのまま書く）：

```markdown
# main.py if/elif構造 全体監査（2026-07-23）

## 経緯
アカマツ(Crispin)のhand_scoreで、`if`が`elif`になっておらず低評価(10点)の分岐が
常に上書きされて死んでいるバグが発見された(main.py:604-611)。同種のバグが
他に潜んでいないか、ユーザー指摘によりmain.py全体を監査した。

## 監査対象と結論

### `_attach_score`（main.py:47-118）
- Budew/Meowth_ex/Fezandipiti_ex/Latias_exの分岐は全てreturn文で終わるため、
  後続の`if active and can_main_attack: return -1`（line 79）が誤って実行される
  ことはない（先行するreturnにより到達しない）。問題なし。
- `energy_count>=2/==1/==0`のif/elif/elseチェーン（line 82-115）は正しくelifで
  分岐しており、siblingなif問題は無い。
- 末尾の`if no_more_dex and (...): score -= 500`（line 116-117）は`-=`による
  意図的な合成であり、上書きバグではない。問題なし。

### `hand_score`内の各カード分岐（main.py:508-657）
- Crispin（line 604-611）：**バグ確認**。2つ目の`if`が`elif`になっておらず、
  1つ目の`if`で設定した`score=10`が常に上書きされる。本計画のTask 2で修正。
- Dreepy/Drakloak/Dragapult_ex/Fezandipiti_ex/Latias_ex/Budew/Meowth_ex/
  Rare_Candy/Unfair_Stamp/Buddy_Buddy_Poffin/Night_Stretcher/Crushing_Hammer/
  Ultra_Ball/Poke_Pad/Lucky_Helmet/Boss_Orders/Brock_Scouting/
  Lillie_Determination/Team_Rocket_Watchtower/Basic_Fire_Energy/
  Basic_Psychic_Energyの各分岐を個別に確認。全てif/elif/elseの正しいチェーン、
  または`+=`/`-=`による意図的な合成、もしくは単一のif/elseで構成されており、
  Crispinと同種の「siblingなifによる無条件上書き」は見つからなかった。
- 末尾の`if not ignore_count and hand_counts[id] > 0: ... score -= 100 (等)`
  （line 650-656）は`-=`による意図的な合成であり、上書きバグではない。

### `main_option_proc`（main.py:297-392）
- line 313-319のoptionループ内`if/elif`、line 333-348の逆算アルゴリズム
  （`continue`によるガード付き）、line 352-392のプラン選択スコア計算、
  いずれもsiblingなif上書き問題は見当たらなかった。

### `agent()`メイン処理（main.py:394-908）
- `OptionType`ごとの`elif`チェーン（line 692-895）を全て確認。
  `SelectContext.TO_BENCH`/`TO_HAND`のアカマツ専用の逆転スコアリング
  （line 726-728, `if effect_card_id == Crispin: score = 100000 - hand_score(...)`）
  や、`DAMAGE_COUNTER`系の`no_damage_counter`による無条件上書き
  （line 760-761, `score = -1`）は、いずれも「特定条件下でスコアを
  意図的に上書きする」設計であり、siblingなif由来の偶発的なバグではない。
  他に同種のバグは見つからなかった。

## 結論
main.py全体で確認されたsiblingなif上書きバグは、アカマツ(Crispin)の
hand_score（line 604-611）の1件のみ。他の条件分岐は、elifチェーンによる
正しい排他分岐か、`+=`/`-=`・`return`による意図的な合成/早期終了パターンで
構成されており、追加のバグは発見されなかった。
```

- [ ] **Step 2: コミット**

```bash
git add docs/analyses/20260723-dragapult-main-if-else-audit.md
git commit -m "docs(dragapult): main.pyのif/elif構造全体監査結果を追加"
```

---

## Task 2: `_crispin_score()`関数抽出とバグ修正（TDD）

**Files:**
- Modify: `src/dragapult_agent/main.py:604-611`（Crispinのhand_score分岐）
- Modify: `src/dragapult_agent/main.py`（`_own_switch_target_score`定義の直後、138-157行目あたりに`_crispin_score`を新規追加）
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Produces: `_crispin_score(*, deck_counts: dict, can_main_attack: bool, bench_attacker: bool, field_counts: dict) -> int`
  - `deck_counts[Basic_Fire_Energy] == 0 or deck_counts[Basic_Psychic_Energy] == 0` → `10`
  - 上記以外で`not can_main_attack and not bench_attacker and field_counts[Dragapult_ex] >= 1` → `55000`
  - それ以外 → `25000`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_dragapult_agent.py`の末尾（`test_own_switch_target_score_existing_priorities_unchanged`関数の後）に追記：

```python
def test_crispin_score_low_when_fire_energy_exhausted_in_deck():
    """アカマツは山札から「ちがうタイプの基本エネルギーを2枚まで」探す効果のため、
    炎エネルギーが山札に0枚だと2種探せず効果が弱まる。この場合は他の状況に関わらず
    低評価(10点)であるべき。修正前は`if`が`elif`になっておらず、この分岐が
    直後のif/elseで無条件に上書きされ死んでいた（main.py:604-611）"""
    deck_counts = defaultdict(int, {dm.Basic_Fire_Energy: 0, dm.Basic_Psychic_Energy: 4})
    field_counts = defaultdict(int, {dm.Dragapult_ex: 1})
    score = dm._crispin_score(
        deck_counts=deck_counts, can_main_attack=False, bench_attacker=False,
        field_counts=field_counts,
    )
    assert score == 10


def test_crispin_score_low_when_psychic_energy_exhausted_in_deck():
    """炎エネルギー側と対称に、超エネルギーが山札に0枚の場合も低評価(10点)"""
    deck_counts = defaultdict(int, {dm.Basic_Fire_Energy: 4, dm.Basic_Psychic_Energy: 0})
    field_counts = defaultdict(int, {dm.Dragapult_ex: 1})
    score = dm._crispin_score(
        deck_counts=deck_counts, can_main_attack=False, bench_attacker=False,
        field_counts=field_counts,
    )
    assert score == 10


def test_crispin_score_high_priority_when_energy_available_and_dragapult_ex_needs_it():
    """両タイプが山札に残っており、かつドラパルトexが場にいるのに攻撃準備が
    整っていない（本命技も控えの攻撃可能個体も無い）場合は最優先(55000点)"""
    deck_counts = defaultdict(int, {dm.Basic_Fire_Energy: 2, dm.Basic_Psychic_Energy: 2})
    field_counts = defaultdict(int, {dm.Dragapult_ex: 1})
    score = dm._crispin_score(
        deck_counts=deck_counts, can_main_attack=False, bench_attacker=False,
        field_counts=field_counts,
    )
    assert score == 55000


def test_crispin_score_default_priority_when_already_attack_ready():
    """両タイプが山札に残っていても、既に本命技が撃てる状態なら通常優先度(25000点)"""
    deck_counts = defaultdict(int, {dm.Basic_Fire_Energy: 2, dm.Basic_Psychic_Energy: 2})
    field_counts = defaultdict(int, {dm.Dragapult_ex: 1})
    score = dm._crispin_score(
        deck_counts=deck_counts, can_main_attack=True, bench_attacker=False,
        field_counts=field_counts,
    )
    assert score == 25000
```

- [ ] **Step 2: テストを実行し、失敗を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -k crispin_score -v`
Expected: `AttributeError: module 'dragapult_agent.main' has no attribute '_crispin_score'` で4件ともFAIL（既存の`_attach_score`等と同じ「未実装による失敗」であることを確認する）

- [ ] **Step 3: `_crispin_score()`を実装する**

`src/dragapult_agent/main.py`の`_own_switch_target_score`関数の定義末尾（現在の157行目、`return 0`の直後）に新規関数を追加：

```python
def _crispin_score(
    *,
    deck_counts: dict,
    can_main_attack: bool,
    bench_attacker: bool,
    field_counts: dict,
) -> int:
    """アカマツ(Crispin)のスコアを返す。
    「自分の山札から、それぞれちがうタイプの基本エネルギーを2枚まで選び、
    1枚を手札に、残りを自分のポケモンに付ける」効果のため、炎・超いずれかの
    基本エネルギーが山札に0枚だと2種を探せず効果が弱まる。修正前はこの
    低評価分岐がelifではなく独立したifだったため、直後のif/elseで無条件に
    上書きされ常に死んでいた（2026-07-23発見、docs/analyses/20260723-dragapult-main-if-else-audit.md参照）。
    """
    if deck_counts[Basic_Fire_Energy] == 0 or deck_counts[Basic_Psychic_Energy] == 0:
        return 10
    if not can_main_attack and not bench_attacker and field_counts[Dragapult_ex] >= 1:
        return 55000
    return 25000
```

続けて、`hand_score()`内のCrispin分岐（現在のmain.py:604-611）を書き換える：

修正前：
```python
        elif id == Crispin:
            if not ignore_count or support_count == 0:
                if deck_counts[Basic_Fire_Energy] == 0 or deck_counts[Basic_Psychic_Energy] == 0:
                    score = 10
                if not can_main_attack and not bench_attacker and field_counts[Dragapult_ex] >= 1:
                    score = 55000
                else:
                    score = 25000
```

修正後：
```python
        elif id == Crispin:
            if not ignore_count or support_count == 0:
                score = _crispin_score(
                    deck_counts=deck_counts, can_main_attack=can_main_attack,
                    bench_attacker=bench_attacker, field_counts=field_counts,
                )
```

- [ ] **Step 4: テストを実行し、成功を確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -k crispin_score -v`
Expected: 4件ともPASS

- [ ] **Step 5: dragapult_agent関連の全テストを実行し、既存挙動を壊していないことを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: 全件PASS（既存のCrispin以外のテストも含め回帰なし）

- [ ] **Step 6: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "fix(dragapult): アカマツのスコアリングでelif不備によるデッドコードを修正"
```

---

## Task 3: リポジトリ全体のテスト実行・提出用notebook再生成・実装サマリー保存

**Files:**
- Modify: `notebooks/submissions/dragapult_agent_submission.ipynb`（スクリプトにより再生成、直接編集しない）
- Create: `docs/implementations/20260723-dragapult-crispin-score-fix.md`

**Interfaces:**
- 後続タスクなし（本計画の最終タスク）

- [ ] **Step 1: リポジトリ全体のテストを実行する**

Run: `uv run pytest`
Expected: 全件PASS（既存630件超 + 本計画で追加した4件）

- [ ] **Step 2: 提出用notebook生成スクリプトを再実行する**

Run: `uv run python scripts/build_dragapult_submission_notebook.py`
Expected: `notebooks/submissions/dragapult_agent_submission.ipynb`が更新され、`_crispin_score`を含み旧`if deck_counts[Basic_Fire_Energy] == 0 or ... score = 10`の直後に無条件`if`が続く旧構造を含まないことを確認する

- [ ] **Step 3: 実装サマリーを保存する**

`docs/implementations/20260723-dragapult-crispin-score-fix.md`を作成し、以下を記載する：
- 発見の経緯（デッキ・戦略レビュー中に発見、ユーザーからの「if/elseガイドライン全体チェック」指摘）
- バグの内容（Crispinのhand_scoreでif/elifの構造ミスにより低評価分岐が常に上書きされていた）
- 監査結果（他に同種バグは無かったこと、`docs/analyses/20260723-dragapult-main-if-else-audit.md`参照）
- 修正内容（`_crispin_score()`への抽出とelif化）
- テスト結果（追加4件 + 既存全件PASS）
- 次のアクション（Kaggle再提出後の新規ログでの実測は本バグ単体の影響が小さいため優先度は次回のRL調査後）

- [ ] **Step 4: コミット**

```bash
git add docs/implementations/20260723-dragapult-crispin-score-fix.md notebooks/submissions/dragapult_agent_submission.ipynb
git commit -m "docs(dragapult): アカマツスコアリング修正の実装サマリーを追加、提出用notebookを再生成"
```

---

## 完了後の報告

全タスク完了後、ユーザーに以下を報告する：
- 修正内容とテスト結果のサマリー
- `superpowers:requesting-code-review`によるコードレビュー依頼が必要か確認する
- mainブランチへのマージ・pushのタイミングはユーザー判断（[[project_ptcg_backlog]]の運用判断事項に準拠）
