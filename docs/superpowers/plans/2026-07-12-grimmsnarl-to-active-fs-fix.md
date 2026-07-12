# grimmsnarl_agent TO_ACTIVE の fs 引数渡し忘れ修正 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/grimmsnarl_agent/main.py:374` の `TO_ACTIVE` コンテキスト（自分のポケモンをバトル場に出す選択）で `_score_own_switch_target(card)` に必須引数 `fs` を渡し忘れているバグを修正し、既存の失敗テスト3件を回復させる。

**Architecture:** 2026-07-07のCrustle対策改修（コミット `c80e057`）で `_score_own_switch_target(card, fs)` と署名変更した際、`SWITCH` コンテキスト側（365行目）は追従修正されたが `TO_ACTIVE` 側（374行目）だけ漏れた。呼び出し1箇所に `fs` を渡すだけの最小修正。`agent()` には例外処理が無いため、このバグは「自分のアクティブがきぜつして交代先を選ぶ場面」（ほぼ毎試合発生）で必ず `TypeError` を起こす実害のあるバグ。

**Tech Stack:** Python 3.12 / uv / pytest

## Global Constraints

- 修正は `src/grimmsnarl_agent/main.py` の374行目のみ。他のロジック・スコア値には一切手を入れない
- 新規テストは書かない。既存の失敗テスト3件（`tests/test_grimmsnarl_agent.py::TestScoreCardOption` の
  `test_to_active_own_pokemon_still_prefers_grimmsnarl` /
  `test_to_active_support_only_pokemon_deprioritized_even_with_higher_hp` /
  `test_to_active_prefers_higher_hp_among_non_grimmsnarl_attackers`）が
  そのまま回帰テストとして機能する（TDDの「失敗するテストが先にある」状態が既に成立している）
- デッキ本体（`decks/grimmsnarl_20260701.py`）は変更しないため、`output/` 用CSV再生成は不要
- Kaggle提出用ノートブック（`src/grimmsnarl_agent.ipynb`、.gitignore対象）への転記はユーザーが実施する（本計画のスコープ外）

---

### Task 1: TO_ACTIVE の `_score_own_switch_target` 呼び出しに `fs` を渡す

**Files:**
- Modify: `src/grimmsnarl_agent/main.py:374`
- Test: `tests/test_grimmsnarl_agent.py`（既存、変更しない）

**Interfaces:**
- Consumes: `_score_own_switch_target(card: "Pokemon", fs: FieldState) -> int`（`main.py:325` 定義済み）
- Produces: なし（挙動修正のみ。`TO_ACTIVE` で自分のポケモンを選ぶ際のスコアが `SWITCH` と同じ基準になる）

- [ ] **Step 1: 失敗するテストが失敗することを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -q`
Expected: `3 failed, 85 passed`（失敗3件はいずれも `TypeError: _score_own_switch_target() missing 1 required positional argument: 'fs'`）

- [ ] **Step 2: 修正を入れる**

`src/grimmsnarl_agent/main.py` の374行目を修正する：

```python
# 修正前
            return _score_own_switch_target(card)

# 修正後
            return _score_own_switch_target(card, fs)
```

- [ ] **Step 3: テストが通ることを確認する**

Run: `uv run pytest tests/test_grimmsnarl_agent.py -q`
Expected: `88 passed`（失敗0件）

- [ ] **Step 4: リポジトリ全体の回帰確認**

Run: `uv run pytest -q`
Expected: 全件PASS（2026-07-09時点で289件＋grimmsnarl 3件回復。他デッキのテストに影響なし）

- [ ] **Step 5: コミット**

```bash
git add src/grimmsnarl_agent/main.py docs/superpowers/plans/2026-07-12-grimmsnarl-to-active-fs-fix.md
git commit -m "fix: TO_ACTIVEで_score_own_switch_targetにfsを渡し忘れてクラッシュするバグを修正

c80e057のCrustle対策でfs引数が必須になった際、SWITCH側のみ追従して
TO_ACTIVE側の呼び出しが漏れていた。自分のアクティブがきぜつして
交代先を選ぶ場面で毎回TypeErrorになる実害バグ。既存の失敗テスト3件が
回帰テストとして回復したことを確認。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
