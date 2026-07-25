# ドラパルトex 所感a・b修正 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 実測20戦ログ調査で確定した2件のバグ（所感a「無駄なエネルギー消費→にげる」の主因、所感b「ドロンチ在場中の無駄なベンチ手張り」）を修正する。

**Architecture:** `src/dragapult_agent/main.py`内2箇所への局所的な変更。(1)`agent()`内のベタ書き変数`do_switch`を新規関数`_should_switch()`へ抽出しBudew節にエネルギー未投資条件を追加、(2)既存の`_attach_score()`の`energy_count==0`分岐にアクティブ側の種族ボーナスを追加。どちらも既存のテスト可能な純粋関数パターン（`_attach_score()`・`_own_switch_target_score()`と同じ形）に揃える。

**Tech Stack:** Python 3.11+, pytest, uv（`uv run pytest`でテスト実行）

## Global Constraints

- 設計書: `docs/superpowers/specs/2026-07-25-dragapult-wasted-attach-switch-fix-design.md`
- 修正対象は所感a・bの**主因のみ**（RETREATスコアリング自体、`_attach_score()`の+400ボーナス、所感c/d/eは対象外）
- 既存テストスイート（現時点704件PASS）を壊さないこと
- コードコメントは日本語

---

### Task 1: `_should_switch()`新規関数の追加とテスト

**Files:**
- Modify: `src/dragapult_agent/main.py`（`_own_switch_target_score()`の直後、195行目と198行目の`def _evolve_score(`の間に新規関数を挿入）
- Test: `tests/test_dragapult_agent.py`（末尾に新規テストブロックを追加）

**Interfaces:**
- Produces: `_should_switch(can_main_attack: bool, bench_attacker: bool, active_id: int, active_energy_count: int, budew_in_field: bool, turn: int) -> bool`（Task 2で`agent()`から呼ばれる）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_dragapult_agent.py`の末尾（716行目の後）に以下を追記する:

```python
def test_should_switch_true_when_bench_attacker_ready_regardless_of_energy():
    """bench_attackerが真なら、アクティブのエネルギー投資額やBudewの有無に関わらず
    交代を検討する（既存挙動を維持）"""
    assert dm._should_switch(
        can_main_attack=False, bench_attacker=True, active_id=dm.Drakloak,
        active_energy_count=2, budew_in_field=False, turn=5,
    ) is True


def test_should_switch_budew_clause_fires_only_when_active_has_no_energy():
    """Budew節は、アクティブに既にエネルギー投資がある場合は発火しない
    （2026-07-25実測20戦で12戦・16件、装着直後の交代でエネルギーが
    無駄になる問題への対応。docs/analyses/20260725-dragapult-ver8-5symptoms-investigation.md）"""
    assert dm._should_switch(
        can_main_attack=False, bench_attacker=False, active_id=dm.Drakloak,
        active_energy_count=0, budew_in_field=True, turn=2,
    ) is True
    assert dm._should_switch(
        can_main_attack=False, bench_attacker=False, active_id=dm.Drakloak,
        active_energy_count=1, budew_in_field=True, turn=2,
    ) is False


def test_should_switch_false_when_can_main_attack():
    """このターン攻撃できるなら交代を検討しない"""
    assert dm._should_switch(
        can_main_attack=True, bench_attacker=True, active_id=dm.Drakloak,
        active_energy_count=0, budew_in_field=True, turn=5,
    ) is False


def test_should_switch_budew_clause_requires_budew_in_field_and_turn_2_plus():
    """Budew節は、Budewが場におらず、またはturn<2なら発火しない"""
    assert dm._should_switch(
        can_main_attack=False, bench_attacker=False, active_id=dm.Drakloak,
        active_energy_count=0, budew_in_field=False, turn=5,
    ) is False
    assert dm._should_switch(
        can_main_attack=False, bench_attacker=False, active_id=dm.Drakloak,
        active_energy_count=0, budew_in_field=True, turn=1,
    ) is False


def test_should_switch_budew_clause_does_not_fire_when_active_is_budew():
    """アクティブ自身がBudewなら、Budew節での交代は不要（既存挙動を維持）"""
    assert dm._should_switch(
        can_main_attack=False, bench_attacker=False, active_id=dm.Budew,
        active_energy_count=0, budew_in_field=True, turn=5,
    ) is False
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -k test_should_switch -v`
Expected: FAIL（`AttributeError: module 'dragapult_agent.main' has no attribute '_should_switch'`）

- [ ] **Step 3: 最小限の実装を書く**

`src/dragapult_agent/main.py`の195行目（`_own_switch_target_score()`の`return 0`の後、空行2つを挟んで198行目`def _evolve_score(`の前）に以下を挿入する:

```python
def _should_switch(
    can_main_attack: bool, bench_attacker: bool, active_id: int,
    active_energy_count: int, budew_in_field: bool, turn: int,
) -> bool:
    """RETREAT(にげる)を検討すべきかを返す。
    bench_attacker: ベンチに攻撃準備済み(2エネ以上)のドラパルトexがいるか
    budew_in_field: 自分の場にスボミー(Budew)が存在するか（アクティブ・ベンチ問わず）
    Budew節は、アクティブにまだエネルギー投資が無い場合のみ発火させる
    （エネルギー装着直後の交代で投資が無駄になる問題への対応。2026-07-25実測20戦で
    12戦・16件確認。docs/analyses/20260725-dragapult-ver8-5symptoms-investigation.md）"""
    if can_main_attack:
        return False
    if bench_attacker:
        return True
    return active_id != Budew and budew_in_field and turn >= 2 and active_energy_count == 0
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -k test_should_switch -v`
Expected: PASS（5件全て）

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "$(cat <<'EOF'
feat(dragapult): _should_switch()を新規追加しBudew節にエネルギー未投資条件を追加

無駄なエネルギー消費→にげる(所感a)の主因であるdo_switchのBudew節を、
アクティブが未投資(energy_count==0)の時だけ発火するよう関数抽出して限定。
まだagent()からは呼ばれておらず、既存挙動に影響なし。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `agent()`内の`do_switch`を`_should_switch()`呼び出しに置き換え

**Files:**
- Modify: `src/dragapult_agent/main.py:965`付近

**Interfaces:**
- Consumes: `_should_switch(can_main_attack, bench_attacker, active_id, active_energy_count, budew_in_field, turn) -> bool`（Task 1で追加済み）

- [ ] **Step 1: 現状のコードを確認する**

`src/dragapult_agent/main.py`で以下の行を探す（`no_draw`定義の直後）:

```python
    no_draw = (my_state.deckCount <= 8)  # Whether to restrict actions that reduce the deck
    do_switch = (not can_main_attack and (bench_attacker or (active_id != Budew and field_counts[Budew] >= 1 and state.turn >= 2)))
```

- [ ] **Step 2: 置き換える**

上記2行目（`do_switch = ...`）を以下に置き換える:

```python
    active_energy_count = len(my_state.active[0].energies) if my_state.active else 0
    do_switch = _should_switch(
        can_main_attack, bench_attacker, active_id, active_energy_count,
        field_counts[Budew] >= 1, state.turn,
    )
```

- [ ] **Step 3: 全体テストスイートを実行し回帰がないことを確認する**

Run: `uv run pytest tests/ -v`
Expected: PASS（既存704件 + Task1で追加した5件 = 709件、失敗0件。既存テストで`do_switch`を直接参照するものは無いため、既存テストの結果は変化しない想定）

- [ ] **Step 4: コミット**

```bash
git add src/dragapult_agent/main.py
git commit -m "$(cat <<'EOF'
fix(dragapult): agent()のdo_switchを_should_switch()呼び出しに置き換え

無駄なエネルギー消費→にげる(所感a)の主因を修正。Budew節がアクティブの
エネルギー投資額を無視して交代を促していた問題を解消(20戦中12戦・16件で
確認、うち15件がBudew節起因)。bench_attacker分岐の既存挙動は変更なし。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `_attach_score()`の`energy_count==0`分岐にアクティブ側種族ボーナスを追加

**Files:**
- Modify: `src/dragapult_agent/main.py:125-137`
- Modify: `tests/test_dragapult_agent.py:24-34`（既存テストの期待値更新）
- Test: `tests/test_dragapult_agent.py`（新規テスト追加）

**Interfaces:**
- Consumes: なし（既存の`_attach_score()`シグネチャは変更しない）

- [ ] **Step 1: 既存テストを新しい期待値に更新し、新規の失敗するテストを書く**

`tests/test_dragapult_agent.py`の`test_attach_score_active_gets_priority_when_bench_attacker_ready_and_zero_energy`（24-34行目）を以下に置き換える（Dragapult_exの種族ボーナス+150が新たに加算されるため期待値が変わる）:

```python
def test_attach_score_active_gets_priority_when_bench_attacker_ready_and_zero_energy():
    """energy_count=0・active=True・bench_attackerありなら、種族ボーナス(+150)と
    bench_attackerボーナス(+400)の両方が加算される。
    2026-07-25修正前はアクティブ側に種族ボーナスが無く、bench_attacker=Falseの
    場面でベンチが常に勝つ非対称バグがあった(所感b、docs/analyses/20260725-dragapult-ver8-5symptoms-investigation.md)"""
    card_table = {dm.Basic_Fire_Energy: _MockCardData(cardId=dm.Basic_Fire_Energy)}
    pokemon = _MockPokemon(id=dm.Dragapult_ex)
    score = dm._attach_score(
        dm.Basic_Fire_Energy, pokemon, True,
        card_table=card_table, can_switch=False, bench_attacker=True,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    assert score == 20000 + 150 + 400
```

続けて、`tests/test_dragapult_agent.py`の末尾（Task 1で追加した`test_should_switch_*`群の後）に以下を追記する:

```python
def test_attach_score_active_drakloak_beats_bench_dreepy_when_no_bench_attacker_ready():
    """所感bの再現ケース：bench_attacker=Falseの場面で、アクティブの
    未攻撃可Drakloak(energy_count=0)は、種族優先度がより低いベンチのDreepy
    (energy_count=0)より高いスコアを得るべき（2026-07-25修正前は種族ボーナスの
    非対称でベンチが常に勝っていた）"""
    card_table = {dm.Basic_Psychic_Energy: _MockCardData(cardId=dm.Basic_Psychic_Energy)}
    active_drakloak = _MockPokemon(id=dm.Drakloak)
    bench_dreepy = _MockPokemon(id=dm.Dreepy)

    active_score = dm._attach_score(
        dm.Basic_Psychic_Energy, active_drakloak, True,
        card_table=card_table, can_switch=False, bench_attacker=False,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    bench_score = dm._attach_score(
        dm.Basic_Psychic_Energy, bench_dreepy, False,
        card_table=card_table, can_switch=False, bench_attacker=False,
        no_more_dex=False, field_counts=defaultdict(int),
        my_asleep=False, my_paralyzed=False,
    )
    assert active_score > bench_score


def test_attach_score_active_energy_zero_species_bonus_matches_bench():
    """energy_count==0の種族ボーナスは、active/bench問わず同じ値
    （Dragapult_ex +150 / Dreepy +100 / それ以外 +50）であるべき
    （bench_attackerによる加減点は別途アクティブ/ベンチで異なる）"""
    card_table = {dm.Basic_Psychic_Energy: _MockCardData(cardId=dm.Basic_Psychic_Energy)}
    for card_id, bonus in ((dm.Dragapult_ex, 150), (dm.Dreepy, 100), (dm.Drakloak, 50)):
        active_pokemon = _MockPokemon(id=card_id)
        active_score = dm._attach_score(
            dm.Basic_Psychic_Energy, active_pokemon, True,
            card_table=card_table, can_switch=False, bench_attacker=False,
            no_more_dex=False, field_counts=defaultdict(int),
            my_asleep=False, my_paralyzed=False,
        )
        assert active_score == 20000 + bonus, f"card_id={card_id}"
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -k "test_attach_score_active_gets_priority_when_bench_attacker_ready_and_zero_energy or test_attach_score_active_drakloak_beats_bench_dreepy_when_no_bench_attacker_ready or test_attach_score_active_energy_zero_species_bonus_matches_bench" -v`
Expected: FAIL（3件とも。既存テストは`20000+400=20400`を期待するが実際は`20000+400=20400`のまま変わらず一致してしまう可能性があるため、必ず新しい期待値`20000+150+400=20550`に書き換えた後で実行し、現行実装(修正前)では`20400`が返り`20550`との不一致でFAILすることを確認する）

- [ ] **Step 3: 最小限の実装を書く**

`src/dragapult_agent/main.py`の125-137行目（`else:  # energy_count == 0`のブロック全体）を以下に置き換える:

```python
    else:  # energy_count == 0
        if pokemon.id == Dragapult_ex:
            score += 150
        elif pokemon.id == Dreepy:
            score += 100
        else:
            score += 50
        if active:
            if bench_attacker:
                score += 400
        else:
            if bench_attacker:
                score -= 200
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -v`
Expected: PASS（全件）

- [ ] **Step 5: コミット**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "$(cat <<'EOF'
fix(dragapult): _attach_score()のenergy_count==0分岐にアクティブ側種族ボーナスを追加

ドロンチ在場中の無駄なベンチ手張り(所感b)を修正。ベンチ側にのみ種族
ボーナス(+150/+100/+50)があり、アクティブ側には無い非対称のため、
bench_attacker=Falseの場面でベンチが常に勝ってしまい、アクティブの
未攻撃可ドロンチを差し置いて無関係なベンチへエネルギーが流れていた
問題を解消(20戦中8戦・9件で確認)。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: 全体回帰確認と提出用notebook再生成

**Files:**
- Modify: なし（検証と成果物再生成のみ）
- Create: `notebooks/submissions/dragapult_agent_submission.ipynb`（再生成、gitignore対象のため未コミット）

**Interfaces:**
- Consumes: Task 1〜3で完了した全変更

- [ ] **Step 1: リポジトリ全体のテストを実行する**

Run: `uv run pytest tests/ -v`
Expected: PASS（全件。Task 2実行時点から新たな失敗が増えていないこと。既知の無関係な失敗/エラーがある場合はTask開始前の`git stash`等で事前にベースラインを確認しておくこと）

- [ ] **Step 2: 提出用notebookを再生成する**

Run: `uv run python scripts/build_dragapult_submission_notebook.py`
Expected: `notebooks/submissions/dragapult_agent_submission.ipynb`が新しいタイムスタンプで再生成される（`_should_switch`関数と、更新後の`_attach_score()`のenergy_count==0分岐を含むこと）

- [ ] **Step 3: 生成結果を軽く確認する**

Run: `grep -n "_should_switch\|def _attach_score" notebooks/submissions/dragapult_agent_submission.ipynb`
Expected: `_should_switch`と`_attach_score`の両方がヒットする

- [ ] **Step 4: 実装サマリーを保存する**

`docs/implementations/20260725-dragapult-wasted-attach-switch-fix.md`を作成し、以下を記載する:
- 対象バグ（所感a主因・所感b）と対応するコミットハッシュ
- 変更したファイル・関数一覧
- テスト結果（PASS件数）
- 未実装のまま残した項目（所感aの副因4件、RETREATスコアリング自体、所感c/d/e）
- フォローアップ：Kaggle再提出後の新規ログで所感a・bの解消状況を再確認する旨（設計書のフォローアップ節を踏襲）

```bash
git add docs/implementations/20260725-dragapult-wasted-attach-switch-fix.md
git commit -m "$(cat <<'EOF'
docs(dragapult): 所感a/b修正の実装サマリーを追加

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage**：設計書の修正1(`_should_switch()`)・修正2(`_attach_score()`)・テスト方針・フォローアップの4点すべてに対応するタスクがある（Task1-2, Task3, Task1&3のテスト, Task4のdocsで明記）。
- **既存テストへの影響**：`test_attach_score_active_gets_priority_when_bench_attacker_ready_and_zero_energy`が唯一の要更新テストであることをコード確認済み（`grep`で`do_switch`/`RETREAT`/`_should_switch`を含む既存テストが無いことを確認済み、他に`energy_count==0`かつ`active=True`の期待値を固定するテストは無し）。
- **型・シグネチャの一貫性**：`_should_switch()`の引数名・型はTask1定義とTask2呼び出しで一致させている。
