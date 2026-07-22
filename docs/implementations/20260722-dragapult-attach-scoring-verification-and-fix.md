# ドラパルトex エネルギー配分バグ 検証・修正 実装サマリー

## 背景

ユーザーから「バトル場ではなくベンチのポケモンにエネルギーが配分されている」という所感の検証依頼があり、`docs/superpowers/specs/2026-07-22-dragapult-attach-scoring-verification-design.md`・`docs/superpowers/plans/2026-07-22-dragapult-attach-scoring-verification.md`に基づき、実データ検証ツールを新規実装した。

## 実装内容

1. `src/etl/gold.py`に`GameStateTracker`クラスを追加。生ログのイベントを1件ずつ再生し、スナップショットに頼らず盤面（アクティブ/ベンチ・エネルギー数・装着済みカードID列・状態異常・相手残りサイド枚数）を追跡する
2. `src/dragapult_agent/main.py`の`attach_score()`をクロージャから独立関数`_attach_score()`へ引数化（純粋リファクタリング）
3. `scripts/analyze_dragapult_attach_scoring.py`を新規実装。20戦の実ログを`GameStateTracker`で再生し、本番の`_attach_score()`を使って「実際に選ばれたベンチ対象より高スコアの候補が存在するか」を検証する
4. 実データ本実行を通し、検証ツール自体に5件の重大な欠落を発見・修正（PLAYイベント未対応・イベント読み込みチャンネル固定・相手プライズ判定・クリスピン効果の分岐未考慮・クリスピン検出ヒューリスティックの欠陥）

## 検証結果

20戦・77件のベンチ向けエネルギー装着イベント中、**4件が`_attach_score()`のロジックと実際の選択の矛盾**、6件が`can_switch`値不明のため判定保留（詳細: `docs/analyses/20260722-dragapult-attach-scoring-verified.md`）。

**最終ブランチレビューで重要な指摘**：決定論的なargmaxエージェントが自身のスコアリングと矛盾する選択をログに残すことは、通常は状態再現の誤りかコードバージョンのズレを意味する。この指摘を受け、コントローラーが直接（サブエージェントを介さず）以下を検証：
- `_attach_score()`のロジックは、ログ生成時（2026-07-21提出）から本セッションの純粋リファクタリング以外に変更されていないことをgit履歴で確認
- 4件のうち代表事例（試合87208679 step=82）について、対象ポケモンの系譜を最初のドローから全イベント遡って追跡し、エネルギー数の再現に誤りがないことを確認

## 修正内容

3件の矛盾に共通するパターンとして、`_attach_score()`のenergy_count==1分岐が、ドラパルトex・ドレディア以外の種族（Drakloak等）への追加装着に一律-200点のペナルティを課しており、energy_count==0分岐の+50点（新規着手）より常に不利になっていた。これにより「1エネルギー投資済みの個体を2エネルギー（攻撃可能）まで伸ばす」より「新規個体への着手」を常に優先してしまう非対称設計になっていた。

`src/dragapult_agent/main.py`の該当分岐（-200 → +50）を修正し、TDDでテスト（`tests/test_dragapult_agent.py::test_attach_score_topping_up_non_priority_bench_pokemon_is_not_worse_than_fresh`）を追加。リポジトリ全体630件PASS確認済み。

**残タスク（意図的にスコープ外）**：クリスピン自動装着時のドラパルトex+200ボーナスに関する1件（試合87208679 step=130）は今回未対応。実機シミュレータ（cg.sim）がmacOSで動かないため、この修正が実際のゲームエンジン上で意図通りに機能するかは、Kaggle再提出後の新規バトルログでのみ確認可能。

## 提出用notebook

`scripts/build_dragapult_submission_main.py`・`scripts/build_dragapult_submission_notebook.py`を再実行し、`notebooks/submissions/dragapult_agent_submission.ipynb`に修正を反映済み（Kaggleへのアップロードはユーザーが実施）。
