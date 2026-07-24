# ドラパルトex ver7実測ログ3件修正 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ver7バトルログ30戦の実測解析で判明した3件の独立したスコアリングバグ・設計不足（エネルギー種別チェック欠如／スボミー交代優先度過多／カースドボム発動条件の狭さ）を`src/dragapult_agent/main.py`で修正する。

**Architecture:** 既存の`_attach_score()`・`_own_switch_target_score()`・`_cursed_bomb_score()`という3つの独立したテスト可能関数に対する、それぞれ局所的な変更。新規モジュール・新規クラスは作らない。デッキ構成・`TrainerCardPolicy`登録辞書・その他の関数には触れない。

**Tech Stack:** Python, pytest, uv

## Global Constraints

- コードコメントは日本語で書く（CLAUDE.md）
- TDD（Red→Green）で進める。各関数のテストは`tests/test_dragapult_agent.py`の既存スタイル（Given-When-Then・日本語docstringでWHYを明記）を踏襲する
- 各タスクは独立してコミットする（1タスク=1コミット）
- 設計書: `docs/superpowers/specs/2026-07-24-dragapult-ver7-energy-switch-cursedbomb-fix-design.md`

---

### Task 1: `_attach_score()` にエネルギー種別ガードを追加

**Files:**
- Modify: `src/dragapult_agent/main.py:82-92`
- Test: `tests/test_dragapult_agent.py`

**Interfaces:**
- Consumes: なし（既存の`_attach_score()`シグネチャは変更しない）
- Produces: `_attach_score()`の挙動変更のみ。他タスクはこの関数に依存しない

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_dragapult_agent.py`の`test_attach_score_dusknoir_and_dusclops_get_low_priority`（116-128行目）の直後に追記する。

```python
def test_attach_score_dragon_line_rejects_dark_energy():
    """ドラパルト系統(ドラメシヤ/ドロンチ/ドラパルトex)の技コストは炎/超エネルギーのみ。
    悪エネルギーを装着しても無意味なため-1を返す。
    2026-07-24、実測30戦のATTACHイベント検証でドラパルト系統への悪エネルギー
    誤装着30件を確認（_attach_score()にエネルギー種別チェックが無かったため）"""
    card_table = {dm.Basic_Dark_Energy: _MockCardData(cardId=dm.Basic_Dark_Energy)}
    for card_id in (dm.Dreepy, dm.Drakloak, dm.Dragapult_ex):
        pokemon = _MockPokemon(id=card_id)
        score = dm._attach_score(
            dm.Basic_Dark_Energy, pokemon, True,
            card_table=card_table, can_switch=False, bench_attacker=False,
            no_more_dex=False, field_counts=defaultdict(int),
            my_asleep=False, my_paralyzed=False,
        )
        assert score == -1


def test_attach_score_dragon_line_accepts_fire_or_psychic_energy():
    """ドラパルト系統は炎/超エネルギーなら既存の汎用スコアリングがそのまま適用される
    （新規ガードを追加しても既存挙動が変わらないことの回帰確認）"""
    card_table = {
        dm.Basic_Fire_Energy: _MockCardData(cardId=dm.Basic_Fire_Energy),
        dm.Basic_Psychic_Energy: _MockCardData(cardId=dm.Basic_Psychic_Energy),
    }
    pokemon = _MockPokemon(id=dm.Dragapult_ex)
    score = dm._attach_score(
        dm.Basic_Fire_Energy, pokemon, True,
        card_table=card_table, can_switch=False, bench_attacker=True,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    assert score == 20000 + 400


def test_attach_score_munkidori_rejects_fire_or_psychic_energy():
    """マシマシラの特性「アドレナブレイン」は悪エネルギー装着が発動条件のため、
    炎/超エネルギーを装着しても無意味。
    2026-07-24、実測30戦でマシマシラへの炎/超エネルギー誤装着10件を確認"""
    card_table = {
        dm.Basic_Fire_Energy: _MockCardData(cardId=dm.Basic_Fire_Energy),
        dm.Basic_Psychic_Energy: _MockCardData(cardId=dm.Basic_Psychic_Energy),
    }
    pokemon = _MockPokemon(id=dm.Munkidori)
    for energy_id in (dm.Basic_Fire_Energy, dm.Basic_Psychic_Energy):
        score = dm._attach_score(
            energy_id, pokemon, True,
            card_table=card_table, can_switch=False, bench_attacker=False,
            no_more_dex=False, field_counts=defaultdict(int),
            my_asleep=False, my_paralyzed=False,
        )
        assert score == -1


def test_attach_score_munkidori_accepts_dark_energy():
    """マシマシラは悪エネルギーなら既存の汎用スコアリングがそのまま適用される
    （新規ガードを追加しても既存挙動が変わらないことの回帰確認）"""
    card_table = {dm.Basic_Dark_Energy: _MockCardData(cardId=dm.Basic_Dark_Energy)}
    pokemon = _MockPokemon(id=dm.Munkidori)
    score = dm._attach_score(
        dm.Basic_Dark_Energy, pokemon, True,
        card_table=card_table, can_switch=False, bench_attacker=True,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    assert score == 20000 + 400
```

- [ ] **Step 2: テストを実行し、失敗することを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -k "dragon_line or munkidori_rejects or munkidori_accepts" -v`
Expected: `test_attach_score_dragon_line_rejects_dark_energy`と`test_attach_score_munkidori_rejects_fire_or_psychic_energy`がFAIL（実際には-1ではなく通常のスコアが返るため）。`_accepts_`系の2件は既にPASSするはず（まだ既存挙動なので）。

- [ ] **Step 3: 最小限の実装を書く**

`src/dragapult_agent/main.py`の82-92行目を以下に置き換える。

```python
    elif pokemon.id == Yveltal:
        # イベルタルの技コストは悪エネルギーのみ。それ以外は装着しても無意味
        if attach_id != Basic_Dark_Energy:
            return -1
        if active and not can_switch and not my_asleep and not my_paralyzed:
            return 24000
        else:
            return 19000
    elif pokemon.id in (Dreepy, Drakloak, Dragapult_ex) and attach_id not in (Basic_Fire_Energy, Basic_Psychic_Energy):
        # ドラパルト系統の技コストは炎/超エネルギーのみ。悪エネルギー等を誤装着させない
        # (2026-07-24、実測30戦で誤装着30件を確認して追加)
        return -1
    elif pokemon.id == Munkidori and attach_id != Basic_Dark_Energy:
        # マシマシラの特性発動には悪エネルギーの装着が必須。それ以外は無意味
        # (2026-07-24、実測30戦で誤装着10件を確認して追加)
        return -1
    elif pokemon.id == Dusknoir or pokemon.id == Dusclops:
        # カースドボムはエネルギー不要のため、通常はエネルギー投資の優先度を下げる
        return 500
```

- [ ] **Step 4: テストを実行し、成功することを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: 全件PASS（新規4件含む、既存テストに回帰なし）

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "$(cat <<'EOF'
fix(dragapult): _attach_score()にドラパルト系統/マシマシラのエネルギー種別ガードを追加

イベルタルにのみ存在した型チェックが無く、悪エネルギーがドラパルト系統に、
炎/超エネルギーがマシマシラに誤装着されるバグを実測30戦で確認したため修正。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `_own_switch_target_score()` のスボミー優先度を引き下げ

**Files:**
- Modify: `src/dragapult_agent/main.py`（`_own_switch_target_score()`内、`elif card_id == Budew:`の行）
- Test: `tests/test_dragapult_agent.py:151-215`

**Interfaces:**
- Consumes: なし
- Produces: `_own_switch_target_score()`の挙動変更のみ

- [ ] **Step 1: 失敗するテストを書く（既存テストの更新＋新規テスト追加）**

`tests/test_dragapult_agent.py`の`test_own_switch_target_score_dragapult_ex_beats_budew_even_without_bench_attacker`（151-164行目）を以下に置き換える。

```python
def test_own_switch_target_score_dragapult_ex_beats_budew_even_without_bench_attacker():
    """強制入場時のみスボミーへ+100000を与える分岐を削除した後、
    Dragapult_exが常にスボミーより優先されることを確認する回帰テスト。
    2026-07-23、docs/analyses/20260723-dragapult-post-attach-fix-20-games.mdの検証で、
    強制入場時のスボミー優先(旧+100000)が実戦で機能している確証がなく、
    本命アタッカーを出し損ねるリスクの方が明確なため削除した
    （docs/superpowers/specs/2026-07-23-dragapult-forced-switch-budew-priority-design.md）"""
    dragapult_ex_score = dm._own_switch_target_score(
        dm.Dragapult_ex, energy_count=0, bench_attacker=False, opponent_active_is_ex=False)
    budew_score = dm._own_switch_target_score(
        dm.Budew, energy_count=0, bench_attacker=False, opponent_active_is_ex=False)
    assert dragapult_ex_score > budew_score
    assert dragapult_ex_score == 50000
    assert budew_score == 3000
```

同ファイルの`test_own_switch_target_score_budew_is_zero_when_bench_attacker_ready`（167-171行目）はスボミーの数値を直接検証していないため変更不要。その直後に新規テストを追加する。

```python
def test_own_switch_target_score_budew_loses_to_non_ex_attackers():
    """2026-07-24、実測30戦のうち87674403/87675484/87677096の3敗戦試合で、
    ベンチにドラパルトexがおらず相手アクティブが非exの局面で、
    実戦的な非exアタッカー（イベルタル・ファイヤー）が選択肢にあったのに
    スボミー(HP30・攻撃10ダメージのみ)が優先されていたことを確認。
    スボミーの優先度を、非exアタッカーの優先度を下回る値に引き下げる"""
    budew_score = dm._own_switch_target_score(
        dm.Budew, energy_count=0, bench_attacker=False, opponent_active_is_ex=False)
    yveltal_score = dm._own_switch_target_score(
        dm.Yveltal, energy_count=0, bench_attacker=False, opponent_active_is_ex=False)
    moltres_score_vs_non_ex = dm._own_switch_target_score(
        dm.Moltres, energy_count=0, bench_attacker=False, opponent_active_is_ex=False)
    assert budew_score < yveltal_score
    assert budew_score < moltres_score_vs_non_ex
```

- [ ] **Step 2: テストを実行し、失敗することを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -k own_switch_target_score -v`
Expected: `test_own_switch_target_score_dragapult_ex_beats_budew_even_without_bench_attacker`が`assert budew_score == 3000`でFAIL（現状30000のため）。`test_own_switch_target_score_budew_loses_to_non_ex_attackers`も`assert budew_score < yveltal_score`でFAIL（現状30000 > 15000のため）。

- [ ] **Step 3: 最小限の実装を書く**

`src/dragapult_agent/main.py`の`_own_switch_target_score()`内、`elif card_id == Budew:`の行を以下に置き換える。

```python
    elif card_id == Budew:
        # 2026-07-24、実測30戦でイベルタル/ファイヤー等の非exアタッカーより
        # 優先されて敗因になっていたケースを確認したため、非exアタッカー
        # (イベルタル15000・ファイヤー5000/49000)を下回る値に引き下げる
        return 3000 if not bench_attacker else 0
```

- [ ] **Step 4: テストを実行し、成功することを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "$(cat <<'EOF'
fix(dragapult): _own_switch_target_score()のスボミー優先度を非exアタッカー未満に引き下げ

ベンチにドラパルトexがいない場面で、スボミー(30000点)がイベルタル(15000点)や
ファイヤー(5000点)より優先されて実戦的なアタッカーを見送るケースを実測30戦で
3件確認したため、3000点に引き下げた。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `_cursed_bomb_score()` に文鎮化ケースの発動条件を追加

**Files:**
- Modify: `src/dragapult_agent/main.py:224-233`（`_cursed_bomb_score()`本体）
- Modify: `src/dragapult_agent/main.py:1121-1123`（呼び出し元）
- Test: `tests/test_dragapult_agent.py:576-589`

**Interfaces:**
- Consumes: なし
- Produces: `_cursed_bomb_score(opponent_active_id, energy_count, has_other_attacker)`（シグネチャ変更、旧`_cursed_bomb_score(opponent_active_id)`から引数2つ追加）

- [ ] **Step 1: 失敗するテストを書く（既存テストの更新＋新規テスト追加）**

`tests/test_dragapult_agent.py`の576-589行目を以下に置き換える。

```python
def test_cursed_bomb_score_high_when_opponent_active_blocks_direct_damage():
    """相手アクティブがno_damage_dex()該当（イワパレス等、直接攻撃を完全ブロックする
    相手）の時は、カースドボム(自爆技)を積極的に使う。energy_count/has_other_attackerの
    値に関わらず最優先される"""
    assert dm._cursed_bomb_score(
        opponent_active_id=345, energy_count=0, has_other_attacker=False) == 90000  # Crustle
    assert dm._cursed_bomb_score(
        opponent_active_id=345, energy_count=0, has_other_attacker=True) == 90000  # Crustle


def test_cursed_bomb_score_low_for_normal_opponent_with_no_other_attacker():
    """通常の相手（直接攻撃が通る）かつ自分に他の攻撃可能な駒が無い場合、
    本命アタッカーを犠牲にする自爆は避け、温存する"""
    assert dm._cursed_bomb_score(
        opponent_active_id=1, energy_count=0, has_other_attacker=False) == -1


def test_cursed_bomb_score_low_when_no_opponent_active():
    """相手アクティブが存在しない（Noneが渡された）場合も温存する"""
    assert dm._cursed_bomb_score(
        opponent_active_id=None, energy_count=0, has_other_attacker=False) == -1


def test_cursed_bomb_score_dead_weight_case_allows_self_destruct():
    """2026-07-24、実測30戦のうちヨノワール/サマヨールまで進化した21戦全てで
    進化後に一度も攻撃していなかったことを確認（_attach_score()側でエネルギー
    投資を避けているため攻撃手段が無いことが原因）。相手が壁でなくても、
    自分にエネルギー(energy_count==0)が無く、かつ他に攻撃可能な駒がある場合は、
    試合終了まで何もしない「文鎮」になるより自爆してダメカンを置く方が
    価値があると判断し、中程度の優先度で発動を許可する"""
    assert dm._cursed_bomb_score(
        opponent_active_id=1, energy_count=0, has_other_attacker=True) == 20000


def test_cursed_bomb_score_not_dead_weight_when_energy_attached():
    """energy_countが1以上ある場合は文鎮ではない（攻撃できる可能性が残る）ため、
    このケースの対象外とし温存する"""
    assert dm._cursed_bomb_score(
        opponent_active_id=1, energy_count=1, has_other_attacker=True) == -1
```

- [ ] **Step 2: テストを実行し、失敗することを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -k cursed_bomb -v`
Expected: `TypeError: _cursed_bomb_score() missing 2 required positional arguments`等でFAIL（現状シグネチャが`opponent_active_id`のみのため）。

- [ ] **Step 3: 最小限の実装を書く**

`src/dragapult_agent/main.py`の224-233行目（`_cursed_bomb_score()`本体）を以下に置き換える。

```python
def _cursed_bomb_score(opponent_active_id: int | None, energy_count: int, has_other_attacker: bool) -> int:
    """ヨノワール／サマヨールの特性「カースドボム」
    （自分を気絶させ、相手ポケモン1匹にダメカンを直接配置）のスコアを返す。
    「ダメカンの直接配置」は「攻撃ダメージ」ではないため、イワパレスのような
    no_damage_dex()該当の特性ブロックを迂回できる。自爆前提のため、
    相手アクティブが直接攻撃を完全ブロックする相手の時は最優先で発動する。
    それ以外でも、_attach_score()側でエネルギー投資を避けられているため
    このポケモンは攻撃手段を持たず(energy_count==0)、かつ自分の場に
    他の攻撃可能な駒がある(has_other_attacker)場合は、試合終了まで何も
    しない「文鎮」になるより自爆してダメカンを置く方が価値があると判断し、
    中程度の優先度で発動を許可する（2026-07-24、実測30戦中21戦で
    ヨノワール/サマヨール到達後に一度も攻撃しない事例を確認して追加。
    本命アタッカーを犠牲にするリスクを避けるため、他に攻撃札が無い場合は
    発動しない）"""
    if opponent_active_id is not None and no_damage_dex(opponent_active_id):
        return 90000
    if energy_count == 0 and has_other_attacker:
        return 20000
    return -1
```

`src/dragapult_agent/main.py`の1121-1123行目（呼び出し元）を以下に置き換える。

```python
            elif card.id == Dusknoir or card.id == Dusclops:
                opponent_active_id = op_state.active[0].id if op_state.active else None
                score = _cursed_bomb_score(
                    opponent_active_id, len(card.energies), bench_attacker or can_main_attack,
                )
```

- [ ] **Step 4: テストを実行し、成功することを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "$(cat <<'EOF'
fix(dragapult): _cursed_bomb_score()に文鎮化ケースの発動条件を追加

ヨノワール/サマヨールはエネルギー投資を避けられているため攻撃手段を持たず、
相手がイワパレス系でない限り試合終了まで何もしない「文鎮」になっていた
（実測30戦中21戦で進化後に一度も攻撃せず）。エネルギー0かつ他に攻撃可能な
駒がある場合は自爆を許可し、ダメカン設置で価値を出せるようにした。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: 全体テスト実行・提出用notebook再生成・実装サマリー作成

**Files:**
- Create: `docs/implementations/20260724-dragapult-ver7-energy-switch-cursedbomb-fix.md`
- Regenerate: `notebooks/submissions/dragapult_agent_submission.ipynb`（`scripts/build_dragapult_submission_notebook.py`実行の副産物）

**Interfaces:**
- Consumes: Task 1〜3で変更した3関数の最終状態
- Produces: なし（このプランの最終タスク）

- [ ] **Step 1: リポジトリ全体のテストを実行する**

Run: `uv run pytest -q`
Expected: 既存の無関係な失敗・エラー件数（変更前と同数）以外はPASS。Task 1〜3で追加・変更したテストは全てPASSしていること。

- [ ] **Step 2: 提出用notebookを再生成する**

Run: `uv run python scripts/build_dragapult_submission_notebook.py`
Expected: `notebooks/submissions/dragapult_agent_submission.ipynb`が更新される（`git status`で更新日時の変化を確認。`.ipynb`は`.gitignore`対象のためコミット不要）。

- [ ] **Step 3: 実装サマリーを作成する**

`docs/implementations/20260724-dragapult-ver7-energy-switch-cursedbomb-fix.md`を新規作成し、以下を記載する：
- 背景（ver7の30戦実測解析で判明した3件の問題、設計書へのリンク）
- 実装内容（Task 1〜3で変更した3関数の要約）
- テスト結果（`uv run pytest -q`の最終件数）
- 次のアクション（Kaggle再提出はユーザー実施、次回バトルログでの実測検証）

- [ ] **Step 4: コミット**

```bash
git add docs/implementations/20260724-dragapult-ver7-energy-switch-cursedbomb-fix.md
git commit -m "$(cat <<'EOF'
docs(dragapult): ver7実測ログ3件修正の実装サマリーを追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
