# ドラパルトex 強制入場時スボミー優先ロジック削除 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KOによる強制入場時（`SelectContext.TO_ACTIVE`/`SETUP_ACTIVE_POKEMON`）にスボミーを
特別優先する分岐を削除し、自発的な交代（`SelectContext.SWITCH`）と同じ基準に統一する。

**Architecture:** `src/dragapult_agent/main.py`の巨大な`agent()`関数内にベタ書きされている
「自分のポケモンをアクティブへ送る候補」のスコアリングを、`_attach_score()`・
`_boss_orders_score()`と同じパターンで独立関数`_own_switch_target_score()`として切り出し、
単体テスト可能にした上で、その関数内でスボミーの強制入場優先(+100000)を削除する。

**Tech Stack:** Python 3.12 / pytest / uv

## Global Constraints

- 対象は`src/dragapult_agent/main.py`の`o.playerIndex == my_index`分岐のみ（設計書
  `docs/superpowers/specs/2026-07-23-dragapult-forced-switch-budew-priority-design.md`参照）
- `SelectContext.SWITCH`でのスボミー+30000自体、ニャースex/フェザンディピティex/ラティアスex
  の優先ロジック、`_attach_score()`側のスボミー扱いは変更しない
- デッキ本体（`decks/dragapult_20260721.py`）は変更しない
- 全体テスト（`uv run pytest -q`）がPASSすること

---

### Task 1: `_own_switch_target_score()`の切り出しとスボミー強制優先の削除

**Files:**
- Modify: `src/dragapult_agent/main.py:136`（`_boss_orders_score()`の直後、`class AttackPlan:`の直前に新規関数を挿入）
- Modify: `src/dragapult_agent/main.py:687-714`（`agent()`内の呼び出し箇所を新関数呼び出しに置換）
- Test: `tests/test_dragapult_agent.py`（末尾に追加）

**Interfaces:**
- Produces: `_own_switch_target_score(card_id: int, energy_count: int, bench_attacker: bool) -> int`
  （`dm._own_switch_target_score`としてテストから呼び出す）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_dragapult_agent.py`の末尾（107行目の後）に以下を追記する。

```python


def test_own_switch_target_score_dragapult_ex_beats_budew_even_without_bench_attacker():
    """強制入場時のみスボミーへ+100000を与える分岐を削除した後、
    Dragapult_exが常にスボミーより優先されることを確認する回帰テスト。
    2026-07-23、docs/analyses/20260723-dragapult-post-attach-fix-20-games.mdの検証で、
    強制入場時のスボミー優先(旧+100000)が実戦で機能している確証がなく、
    本命アタッカーを出し損ねるリスクの方が明確なため削除した
    （docs/superpowers/specs/2026-07-23-dragapult-forced-switch-budew-priority-design.md）"""
    dragapult_ex_score = dm._own_switch_target_score(dm.Dragapult_ex, energy_count=0, bench_attacker=False)
    budew_score = dm._own_switch_target_score(dm.Budew, energy_count=0, bench_attacker=False)
    assert dragapult_ex_score > budew_score
    assert dragapult_ex_score == 50000
    assert budew_score == 30000


def test_own_switch_target_score_budew_is_zero_when_bench_attacker_ready():
    """既にベンチに攻撃可能な控えがいる場合、スボミーの優先度は0点になる
    （SelectContext.SWITCHでの既存挙動を維持）"""
    assert dm._own_switch_target_score(dm.Budew, energy_count=0, bench_attacker=True) == 0


def test_own_switch_target_score_existing_priorities_unchanged():
    """Dreepy/Drakloak/フェザンディピティex/ニャースex/未知カードの
    既存優先度が変わっていないことの回帰確認"""
    assert dm._own_switch_target_score(dm.Dreepy, energy_count=0, bench_attacker=False) == 10000
    assert dm._own_switch_target_score(dm.Drakloak, energy_count=1, bench_attacker=False) == 20000
    assert dm._own_switch_target_score(dm.Drakloak, energy_count=0, bench_attacker=False) == -10000
    assert dm._own_switch_target_score(dm.Fezandipiti_ex, energy_count=0, bench_attacker=False) == -1000
    assert dm._own_switch_target_score(dm.Meowth_ex, energy_count=0, bench_attacker=False) == -2000
    assert dm._own_switch_target_score(999999, energy_count=0, bench_attacker=False) == 0
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -k own_switch_target_score -v`
Expected: FAIL（`AttributeError: module 'dragapult_agent.main' has no attribute '_own_switch_target_score'`）

- [ ] **Step 3: `_own_switch_target_score()`を実装する**

`src/dragapult_agent/main.py`の136行目（`_boss_orders_score()`の`return 0`の後、
空行2つを挟んで`class AttackPlan:`の直前）に以下を挿入する。

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

- [ ] **Step 4: 新関数のテストが通ることを確認する**

Run: `uv run pytest tests/test_dragapult_agent.py -k own_switch_target_score -v`
Expected: PASS（3件）

- [ ] **Step 5: `agent()`内の呼び出し箇所を新関数呼び出しに置換する**

`src/dragapult_agent/main.py`の687-714行目（現状は以下の内容）を

```python
                if (context == SelectContext.SWITCH
                    or context == SelectContext.TO_ACTIVE
                    or context == SelectContext.SETUP_ACTIVE_POKEMON):
                    # Selection of the Pokémon to send to the Active Spot
                    if o.playerIndex == my_index:
                        if card.id == Dreepy:
                            score += 10000
                        elif card.id == Drakloak:
                            if energy_count >= 1:
                                score += 20000
                            else:
                                score -= 10000
                        elif card.id == Dragapult_ex:
                            score += 50000
                        elif card.id == Budew:
                            if context != SelectContext.SWITCH:
                                score += 100000
                            elif not bench_attacker:
                                score += 30000
                        elif card.id == Fezandipiti_ex:
                            score -= 1000
                        elif card.id == Meowth_ex:
                            score -= 2000
                    else:
                        if plan_a.attack == o.index + 1:
                            score += 100000
                    score += energy_count * 1000
                    score += hp
```

次のように置き換える。

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

- [ ] **Step 6: リポジトリ全体のテストを実行し、回帰がないことを確認する**

Run: `uv run pytest -q`
Expected: 全件PASS（既存テスト件数 + 今回追加した3件）

- [ ] **Step 7: コミットする**

```bash
git add src/dragapult_agent/main.py tests/test_dragapult_agent.py
git commit -m "$(cat <<'EOF'
fix(dragapult): 強制入場時のスボミー優先ロジックを削除

KO後の強制入場でスボミーへ+100000を与える分岐が、実戦では同じ
ターン中に自分から交代させてしまい特性発動の意図と矛盾する上、
本命アタッカー(Dragapult_ex)を出し損ね逆転機会を逃すリスクが
あったため削除。_own_switch_target_score()として切り出しテスト可能にした。

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## 実装後のフォローアップ（このプランのスコープ外）

- 提出用notebook（`scripts/build_dragapult_submission_main.py`・
  `scripts/build_dragapult_submission_notebook.py`）の再生成とKaggle再提出はユーザー側で実施
- `docs/implementations/20260723-dragapult-forced-switch-budew-priority.md`への実装サマリー保存
- Kaggle再提出後、次回バトルログ取得時に、強制入場時に本命アタッカーが選ばれるようになったかを実測確認
