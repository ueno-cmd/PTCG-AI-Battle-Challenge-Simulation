# ドラパルトex 強制入場時スボミー優先ロジック削除 実装サマリー

## 背景

`docs/analyses/20260723-dragapult-post-attach-fix-20-games.md`の20戦検証で、KOによる強制入場時
（`SelectContext.TO_ACTIVE`/`SETUP_ACTIVE_POKEMON`）にスボミー（Budew）を優先する旧ロジック
（+100000点）が、実戦では①同じターン中に自分から交代させてしまい特性発動の意図と矛盾し、
②唯一検証できた1件では相手のアイテム使用を実際には阻止できていなかったことを確認した。
一方で、この優先処理により本命アタッカー（Dragapult_ex）を出し損ね、逆転のチャンスを逃す
リスクは明確だった。ユーザー判断により、強制入場時のスボミー優先を完全に削除した。

- 設計書: `docs/superpowers/specs/2026-07-23-dragapult-forced-switch-budew-priority-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-23-dragapult-forced-switch-budew-priority.md`

## 実施内容

`src/dragapult_agent/main.py`の`agent()`内にベタ書きされていた「アクティブへ送るポケモンの
選択」スコアリングのうち、自分のポケモンを選ぶ側の分岐を`_own_switch_target_score()`として
新規関数に切り出した（`_attach_score()`・`_boss_orders_score()`と同じ、テスト容易性のための
関数抽出パターン）。

```python
def _own_switch_target_score(card_id: int, energy_count: int, bench_attacker: bool) -> int:
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

スボミーのスコアは、旧コードの`SelectContext.SWITCH`（自発的な交代）時の基準
（`bench_attacker`が無ければ+30000、あれば0）に統一され、`context != SelectContext.SWITCH`
（強制入場）時のみ+100000を与えていた特別扱いは削除された。`context`パラメータ自体も
不要になったため関数シグネチャから除外した。

呼び出し側は次の1行に置き換わった。

```python
if o.playerIndex == my_index:
    score += _own_switch_target_score(card.id, energy_count, bench_attacker)
```

## テスト

`tests/test_dragapult_agent.py`に3件追加（TDD、RED→GREENで確認済み）：
- `test_own_switch_target_score_dragapult_ex_beats_budew_even_without_bench_attacker`：
  強制入場相当の条件でもDragapult_ex(50000)がスボミー(30000)を常に上回ることの回帰テスト
- `test_own_switch_target_score_budew_is_zero_when_bench_attacker_ready`：
  既にベンチに攻撃可能な控えがいる場合はスボミーが0点になること
- `test_own_switch_target_score_existing_priorities_unchanged`：
  Dreepy/Drakloak/フェザンディピティex/ニャースex/未知カードの既存スコアが不変であること

リポジトリ全体 `uv run pytest -q` で **633件全てPASS**（既存630件＋新規3件、回帰なし）。

## レビュー結果

subagent-driven-developmentでTask 1（本タスクのみの単一タスク計画）を実施。
- タスクレビュー：Critical/Important無し、Approved
- 最終ブランチ全体レビュー：Ready to merge = Yes、Critical/Important無し
- Minor指摘1件（強制入場+bench_attacker=Trueの組み合わせを明示検証するテストはないが、
  `context`に依存しない実装のため設計通り・対応不要）

`feature/dragapult-forced-switch-budew-priority`ブランチで実装し、mainへFast-forwardマージ済み
（コミット`b07c46d`）。push未実施。

## スコープ外（今後のフォローアップ）

- 提出用notebook（`scripts/build_dragapult_submission_main.py`・
  `scripts/build_dragapult_submission_notebook.py`）の再生成とKaggle再提出はユーザー側で実施。
  **この修正はnotebookを再生成してKaggleへ再提出するまで競技結果には反映されない**
- Kaggle再提出後、次回バトルログ取得時に、強制入場時に本命アタッカーが選ばれるようになったかを実測確認
- `docs/analyses/20260723-dragapult-post-attach-fix-20-games.md`に残る別課題
  （87492541 step=153の新規矛盾パターン、クリスピン+200ボーナスの妥当性）は別タスクとして持ち越し
