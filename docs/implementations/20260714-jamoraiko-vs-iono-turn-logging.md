# ジャモライコ vs イオナサンプル校正実験：手番選択ログ出力機能 実装サマリー

## 背景

ジャモライコエージェント（タケルライコex軸）にOptionType.CARDのスコアリング機能を追加した直後、Kaggle上での200試合校正実験で勝率が3/200（0.015）のまま変化しなかった。単体テスト451件は全てPASSしているが、対戦全体を通した実際の動作は検証できていない。

原因を切り分けるため、校正ノートブックが対戦中の手番選択（OptionType/SelectContext/提示された選択肢/選択結果/盤面スナップショット/イベントログ）を詳細に記録する機能を追加した。この実装により、負け試合の深掘り調査が可能になる。

## 実装内容

### 全体設計
- `scripts/build_jamoraiko_vs_iono_notebook.py`にcg非依存の純粋関数群を追加
- 既存200試合本体のロジックは変更せず、**最初の10試合のみ**手番選択ログを記録
- 生成ノートブック内で`inspect.getsource()`を使ってPython関数をセルに埋め込み

### Task 1: 列挙型の名前引きマップ + compact_option/compact_log_entry（コミット: de35681）

追加したコンポーネント：
- `SELECT_TYPE_NAMES: dict[int, str]` — SelectType列挙型の名前マップ（11種類）
- `SELECT_CONTEXT_NAMES: dict[int, str]` — SelectContext列挙型の名前マップ（49種類）
- `compact_option(option: dict) -> dict` — 選択肢dictからNoneフィールドを除去
- `compact_log_entry(log: dict) -> dict` — イベントログdictからNoneフィールドを除去

テスト追加: 5件（TestEnumNameMaps: 2件、TestCompactOption: 2件、TestCompactLogEntry: 1件）

### Task 2: board_snapshot（盤面スナップショット抽出）（コミット: 923ffff）

追加したコンポーネント：
- `_pokemon_summary(pokemon: dict | None) -> dict | None` — ポケモンからid/hp/maxHp/energyCountのみ抽出
- `board_snapshot(state: dict, my_index: int) -> dict` — 両者のアクティブ/ベンチの情報を簡潔に抽出

設計: obs["current"]["players"]から自分・相手の別に、アクティブなポケモン・ベンチポケモンの必要フィールドのみ抽出
テスト追加: 3件（TestBoardSnapshot: 3件、空スロット対応を含む）

### Task 3: build_turn_log_entry（1手番分のログレコード組み立て）（コミット: 0dc36d5）

追加したコンポーネント：
- `build_turn_log_entry(obs: dict, selected: list[int], game_index: int, step: int, agent_name: str) -> dict` — 1手番分のレコード組み立て

出力フィールド：
- game_index/step/turn/player_index/agent（識別情報）
- select_type/select_type_name/select_context/select_context_name（手番の種類）
- options（提示された全選択肢の圧縮版）
- selected_indices/selected_options（実際に選ばれた選択肢）
- board（その時の盤面スナップショット）
- logs_since_last（前回の選択から現在までのイベントログ）

テスト追加: 6件（TestBuildTurnLogEntry: 6件、未知の列挙型値のフォールバック対応を含む）

### Task 4: ハーネス/校正実験への配線 + ノートブック生成（コミット: e948af9）

`scripts/build_jamoraiko_vs_iono_notebook.py`の変更：

**HARNESS_CODE（play_game関数）:**
- `turn_log_sink: list | None`引数を追加（ログリストが渡された場合のみ記録）
- `agent_a_name`/`agent_b_name`引数を追加（ログ内のエージェント識別用）
- 各手番で`build_turn_log_entry()`を呼んでログリストに追記

**CALIBRATION_CODE（run_series関数）:**
- `LOG_FIRST_N = 10`定数を追加
- `log_first_n`パラメータを追加（デフォルト0）
- 最初のlog_first_n試合のみ`turn_log_sink`付きで`play_game`を呼び出し
- 座席交代（先手/後手の入れ替え）に合わせて、エージェント名を正しく反映
- 2つ目の戻り値として`turn_log_games`（ログ記録済みゲームのリスト）を返却

**新規セル：**
- `turn-log-helpers`セル：SELECT_TYPE_NAMES/SELECT_CONTEXT_NAMESとcompact_*/board_snapshot/build_turn_log_entryの関数定義を埋め込み
- `save-turn-log`セル：`jamoraiko_vs_iono_turn_log.json`に手番選択ログを保存

**ノートブック全セル構成（13セル）:**
1. calibration-note（MD）— 実験の目的説明
2-3. 参考ノートブックからのコピーセル（標準import/cgランタイム起動）
4. deck-load — デッキ定数の定義
5. agent-sources — エージェントソースコードの埋め込み
6. load-helper — パッチ適用関数等のヘルパーコード
7. agent-load — デッキ読み込みパッチ適用 & エージェント読み込み
8. turn-log-helpers（新規） — 手番ログ用純粋関数群
9. battle-harness — play_game関数とMAX_STEPS定数
10. calibration-run — run_series関数実行（200試合/10試合ログ）
11. save-results — 既存の勝率結果ファイル保存
12. save-turn-log（新規） — 手番選択ログのJSON保存
13. plot-curve — 結果グラフプロット

テスト追加: 6件（TestMainBuildsNotebookWithTurnLogging: 6件、セル構文検証・配線検証・セル順序検証を含む）

## テスト結果

### 追加テスト数：20件
- Task 1: 5件（SELECT_TYPE_NAMES/SELECT_CONTEXT_NAMES/compact_option/compact_log_entry）
- Task 2: 3件（_pokemon_summary/board_snapshot、空スロット/相対参照対応）
- Task 3: 6件（build_turn_log_entry、列挙型ラベリング・フォールバック・フィールド検証）
- Task 4: 6件（ノートブック全体構文・セル内容・セル順序検証）

### テスト実行結果
```
uv run pytest -q
471 passed in 0.60s
```

既存テスト（451件）+ 新規テスト（20件）= **総計471件、全PASS**
（回帰なし。既存の単体テスト/統合テスト全て正常動作）

## 出力ファイルスキーマ

生成ノートブクがKaggle上で実行されると、`/kaggle/working/jamoraiko_vs_iono_turn_log.json`に以下の構造でログが保存される：

```json
{
  "num_games_logged": 10,
  "games": [
    {
      "game_index": 0,
      "seat_first": "jamoraiko",
      "result": 1,
      "turns": [
        {
          "game_index": 0,
          "step": 3,
          "turn": 2,
          "player_index": 0,
          "agent": "jamoraiko",
          "select_type": 1,
          "select_type_name": "CARD",
          "select_context": 3,
          "select_context_name": "SWITCH",
          "options": [
            {"type": 3, "area": 5, "index": 0, "playerIndex": 0, "cardId": 63},
            {"type": 3, "area": 5, "index": 1, "playerIndex": 0, "cardId": 71}
          ],
          "selected_indices": [1],
          "selected_options": [
            {"type": 3, "area": 5, "index": 1, "playerIndex": 0, "cardId": 71}
          ],
          "board": {
            "mine": {
              "active": [{"id": 63, "hp": 90, "maxHp": 190, "energyCount": 2}],
              "bench": [{"id": 71, "hp": 130, "maxHp": 130, "energyCount": 1}]
            },
            "opponent": {
              "active": [{"id": 269, "hp": 150, "maxHp": 190, "energyCount": 3}],
              "bench": []
            }
          },
          "logs_since_last": [
            {"type": 16, "playerIndex": 0, "cardId": 63, "value": -30}
          ]
        }
      ]
    }
  ]
}
```

スキーマの特徴：
- `result`: jamoraiko視点の勝敗（+1/勝ち、-1/負け、0/引き分け・打ち切り）
- `select_type_name`/`select_context_name`: int値に加えたラベル（int値は将来の列挙型拡張に対応）
- `logs_since_last`: 前の選択からこの選択提示までに発生したゲームイベント（ダメージ・交代・効果等）
- `options`: 提示された全選択肢（「本来選べたはずの選択肢が提示されていたか」を後から検証可能）
- `board`: 常に最新の盤面状態（turns配列内の時系列で盤面遷移を追える）

## 未検証事項（Kaggle実行が必要）

- [ ] ノートブックがKaggle上で実際に正常に実行され、200試合の勝率測定と並行して最初の10試合のログが生成されること
- [ ] 生成されたJSONファイルのフォーマットが正確で、パースが正常に行えること
- [ ] 10試合分のログファイルサイズが実用的な範囲に収まること（想定: 数MB程度）
- [ ] 座席交代の処理が正しく反映され、game_index奇数時のエージェント名が期待通りに逆転していること

## 次のステップ

1. ユーザーがKaggle上でノートブック（`src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`）を実行
2. 結果ファイルをダウンロード（`jamoraiko_vs_iono_results.json`と`jamoraiko_vs_iono_turn_log.json`）
3. `jamoraiko_vs_iono_turn_log.json`を分析ノートブック等で解析
4. 負け試合（result=-1）を中心に、turn-by-turnの選択判断・盤面遷移・イベントログを検証
5. 「なぜ勝率が0.015のままなのか」の原因を特定
6. 必要に応じてジャモライコエージェントのロジック修正 → テスト追加 → 再実験

## 関連ドキュメント

- 設計書: `docs/superpowers/specs/2026-07-14-jamoraiko-vs-iono-turn-logging-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-14-jamoraiko-vs-iono-turn-logging.md`
- ビルドスクリプト: `scripts/build_jamoraiko_vs_iono_notebook.py`
- テストコード: `tests/test_jamoraiko_vs_iono_notebook_build.py`
