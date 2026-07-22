# ドラパルトex `attach_score()` ベンチ配分バグ調査：再検証設計書

## 背景

前回セッション（2026-07-22）でユーザーから「バトル場ではなくベンチのポケモンにエネルギーが配分されている」という所感の検証依頼を受け、20戦分のバトルログ（`data/battle_logs/87204277.json`〜`87214695.json`）から65件のベンチ向けATTACHイベントを分析した。しかし分析手法自体に致命的なバグ（詳細は`docs/superpowers/plans/2026-07-22-dragapult-energy-attach-debug-plan.md`参照）が見つかり、65件全ての分類結果が汚染された。本設計書は、この再検証をゼロから正しくやり直すための計画である。

**ゴール（ユーザー指定）：** 「バトル場ではなくベンチのポケモンにエネルギーが配分される」という所感が実際のロジックのバグなのかを確定させ、**バグがあれば修正した上でKaggleへ再提出する**。ゴールに到達するまで（矛盾ゼロで確定した場合も含め）このタスクを完了させる。

## 前回判明した2つのバグ（再検証不要・確定事項）

1. **1つの観測ステップ（`data["steps"][i]`）に複数ターン分のログイベントが混在しうる。** ステップ単位のスナップショット（`observation.current`）で「その瞬間どちらがアクティブか」を判定する手法は、同じステップ内に複数ターンのイベントが含まれる場合に誤判定する。
2. **`LogType.SWITCH`（type=8）のフィールド名が意味と逆。** `cardIdActive`/`serialActive`は実際には「アクティブから退場する（＝ベンチへ行く）」ポケモンを指し、`cardIdBench`/`serialBench`は「ベンチから登場する（＝アクティブになる）」ポケモンを指す。

これにより「スナップショットで“今どちらがアクティブか”を判定する」手法は全面的に不採用とし、生イベントを順番に再生するインクリメンタル方式に切り替える。

## アーキテクチャ

```
src/etl/gold.py
  └─ GameStateTracker（新規クラス）
       内部状態: active_serial, bench_serials(set), species[serial],
                 energy_count[serial], asleep[serial], paralyzed[serial]
       apply(event) でイベント1件ずつ状態を更新する（スナップショット参照ゼロ）
       対応イベント:
         - MOVE_CARD(6): 手札/デッキ→ACTIVE/BENCHへの新規登場、ACTIVE/BENCH→DISCARDでの離脱
         - SWITCH(8): 上記バグ②を踏まえ正しい方向（cardIdActive=退場側/cardIdBench=登場側）で反映
         - ATTACH(11): serialTargetのエネルギー数を+1
         - EVOLVE(12): serialTarget(進化前)の位置・エネルギー数・状態異常をserial(進化後)へ引き継ぎ、種族IDを更新
         - ASLEEP(19)/PARALYZED(20): isRecoverフラグに応じてasleep/paralyzedを更新
       初期状態: data["steps"][0]のスナップショット（SETUP相当）から構築する
                （複数ターン混在の余地がないため、ここのみスナップショット使用を許容）

src/dragapult_agent/main.py
  └─ attach_score()をクロージャから独立関数へ引数化する（ロジック変更なし・純粋リファクタリング）
       引数: attach_id, pokemon, active, card_table, can_switch, bench_attacker,
             no_more_dex, field_counts, my_state（の必要フィールドのみ）
       agent()本体からは従来通り既存の変数を渡して呼ぶだけで、挙動は一切変えない

scripts/analyze_dragapult_attach_scoring.py（新規、既存scripts/analyze_*.pyと同じCLI形式）
  └─ 20戦のログをGameStateTrackerで再生し、ベンチ向けATTACHイベント全件について
     引数化したattach_score()を実際の候補（アクティブ1体+ベンチ全体）に対して呼び、
     矛盾件数を集計してレポート出力する
```

## 「矛盾」の判定基準とcan_switchの扱い

**矛盾の定義：** あるATTACHイベント時点で実際に場にいた自分のポケモン全員（アクティブ1体＋ベンチ全員）を候補として`attach_score()`を計算し、実際に選ばれた対象（ベンチのいずれか）より高いスコアを持つ候補（多くの場合アクティブ）が存在すること。

**can_switchの不確実性：** `can_switch`（このターン交代済みか、逃げエネが足りないか等）はゲームエンジンが選択肢を提示する瞬間にしか分からない値で、ログイベントのみからは100%正確に再現できない（交代コスト判定などゲームルールの主要部分の再実装が必要になり、スコープを大きく超える）。そのため`can_switch`はTrue/False両方で計算し：
- 判定（矛盾あり/なし）がどちらの値でも変わらない場合 → そのまま確定
- 判定がcan_switchの値次第で変わる場合 → 自動判定せず「要目視確認」として個別に記録する

`asleep`/`paralyzed`は`ASLEEP`(19)/`PARALYZED`(20)イベントから正確に追跡できるため、この2つは近似ではなく正確な値を使う。

## テスト方針（TDD）

- `GameStateTracker`：MOVE_CARD/SWITCH（フィールド名の意味が逆な点を含む）/ATTACH/EVOLVE/ASLEEP/PARALYZEDそれぞれの単体テストを`tests/test_etl_gold.py`に追加。既存フィクスチャ`data/battle_logs/84580427.json`を使った結合テスト（試合全体を再生し、既知の特定時点のアクティブ/ベンチ構成と一致するか）も追加する
- `attach_score()`の引数化：既存の`tests/test_dragapult_agent.py`のテストが1件も壊れないことを確認する純粋リファクタリング。新規テストは引数化後のシグネチャに対する最小限のもののみ追加

## 検証スクリプトの出力

`docs/analyses/20260722-dragapult-attach-scoring-verified.md`（新規）に以下を記載する：
- 65件（または再集計後の総数）の再判定結果
- 矛盾件数、can_switch要確認件数
- 各矛盾事例の試合ID・ステップ番号・具体的な候補スコア比較

このファイルは前回の汚染された分析（`docs/analyses/20260722-dragapult-attach-and-unfair-stamp-review.md`のベンチ配分部分）を置き換えるものであることを冒頭に明記する。

## 後続フロー

- **矛盾ゼロの場合：** 「ベンチへの配分は設計通り」と結論できるが、ユーザーの元々の所感を尊重し、検証結果をユーザーに提示して追加の確認・修正が不要か確認してから完了とする（自動的に「バグなし」で打ち切らない）
- **矛盾ありの場合：** 個別事例を読み、単一の仮説を立てる → `superpowers:test-driven-development`で失敗するテストを先に書く → 最小限のコード修正 → `uv run pytest -q`でリポジトリ全体の回帰確認 → `scripts/build_dragapult_submission_notebook.py`でKaggle提出用notebookを再生成 → 実装サマリーを`docs/implementations/`に保存する
- Kaggleへの実際のアップロード操作自体はユーザーが実施する

## スコープ外（本タスクでは扱わない）

- ボスの指令の使用率検証（引いたのに使わない2戦の深掘り）は別タスク（`project_ptcg_backlog`に記載済み）
- 進化失敗3/20戦の深掘りはサンプル不足のため保留のまま
- `attach_score()`以外の関数（`hand_score()`等）の引数化リファクタリングは対象外
