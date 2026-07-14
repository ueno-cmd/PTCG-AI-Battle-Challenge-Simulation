# ジャモライコ vs イオナサンプル 校正実験：手番選択ログ出力機能 設計書

## 背景・目的

`src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`（`scripts/build_jamoraiko_vs_iono_notebook.py`が生成）で、ジャモライコエージェントに`OptionType.CARD`のスコアリングを追加（2026-07-13、テスト451件全PASS）した後も、Kaggle上での200試合校正実験の勝率は0.015のまま変化しなかった（旧: 3/200勝 → 新: 3/200勝）。

単体テストは個々の関数が正しく動作することしか検証できず、対戦全体を通して実際にどう機能しているかは検証できていない。校正ノートブックは現状、勝敗と経過時間しか記録しておらず、対戦中の手番選択の中身が一切わからないため、これ以上の原因切り分けができない状態にある。

本設計は、校正ノートブックに**対戦中の手番選択ログ**（どのOptionType/SelectContextで、どんな選択肢の中からどれを選んだか、その時の盤面はどうだったか）を出力する機能を追加し、負け試合の深掘り調査を可能にすることを目的とする。

## 全体アーキテクチャ

既存の200試合本体実行はそのまま維持し、そのうち**最初の10試合だけ**詳細ログを併せて記録する。試合を2回走らせ直すような無駄は作らない。

`scripts/build_jamoraiko_vs_iono_notebook.py` に、ログ変換用の**純粋関数群**を新規追加する（`cg`ライブラリに依存しない、プレーンなdict操作のみ）：

- `compact_option(option: dict) -> dict` — Noneフィールドを除いた選択肢の圧縮表現
- `compact_log_entry(log: dict) -> dict` — 同様にLogイベント（`obs["logs"]`）の圧縮表現
- `board_snapshot(state: dict, my_index: int) -> dict` — 両者のアクティブ/ベンチの id・hp・maxHp・energyCount のみ抽出
- `build_turn_log_entry(obs, selected, game_index, step, agent_name) -> dict` — 上記を組み合わせて1手番分のレコードを組み立てる
- `OptionType`/`SelectContext` の名前引き用の静的dict（`data/cg/api.py`の現行定義から生成、可読性用のラベル付けのみに使い、値自体は生のintも必ず残す）

これらは既存の`load_agent_module`と同じパターンで**ローカルでも純粋なPythonロジックとして単体テスト可能**にし、`inspect.getsource()`でノートブックのセルに埋め込む（cg依存のハーネス部分と分離する）。

ノートブック内の`play_game`関数（`HARNESS_CODE`）に`turn_log_sink: list | None`と`agent_a_name`/`agent_b_name`引数を追加し、渡された場合のみ各手番で`build_turn_log_entry`を呼んでリストに追記する。引数を渡さなければ現行と完全に同じ挙動を維持する。

`run_series`（`CALIBRATION_CODE`）は`log_first_n=10`のデフォルト値を持ち、`i < log_first_n`の試合だけ`turn_log_sink`付きで`play_game`を呼び出し、ログを収集する。座席交代（`i % 2`による先手後手の入れ替え）に合わせて、そのゲームで実際に`player_index=0`を担当しているのがジャモライコかイオナサンプルかを正しく`agent_a_name`/`agent_b_name`に反映する。

結果は既存の`jamoraiko_vs_iono_results.json`とは別ファイル `jamoraiko_vs_iono_turn_log.json` として `/kaggle/working` に保存する新規セルを追加する。

## データ形式

`jamoraiko_vs_iono_turn_log.json` の構造：

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

ポイント：

- `result`はそのゲームの`jamoraiko`視点の勝敗（既存`run_series`と同じ+1/-1/0）
- `select_type_name`/`select_context_name`はint値に加えたラベルで、値自体（`select_type`/`select_context`）は必ず両方残す（列挙型が将来拡張されてもデータは失われない）
- `logs_since_last`は`obs["logs"]`（前回の選択からその選択が提示されるまでに起きたイベント：ダメージ・移動・交代など）をそのまま圧縮したもの。これで盤面の推移を後から追える
- `options`には提示された全選択肢を含める（「本来選べたはずの選択肢がそもそも提示されていたか」まで検証できるようにするため）

## 変更ファイル

`scripts/build_jamoraiko_vs_iono_notebook.py`：

- 純粋関数群（`compact_option`/`compact_log_entry`/`board_snapshot`/`build_turn_log_entry`）と静的な名前引きdict（`OPTION_TYPE_NAMES`/`SELECT_CONTEXT_NAMES`）を新規追加
- `HARNESS_CODE`（`play_game`関数）に`turn_log_sink`/`agent_a_name`/`agent_b_name`引数を追加
- `CALIBRATION_CODE`（`run_series`）に`log_first_n=10`パラメータと、対応するログ収集ロジックを追加
- 新規セル`SAVE_LOG_CODE`（`jamoraiko_vs_iono_turn_log.json`書き出し）を追加
- `main()`内のセル組み立てに、上記の純粋関数群を埋め込むセル（`inspect.getsource()`利用）を追加
- `NOTE_MD`に新しい出力ファイルの説明を追記

## テスト方針

`tests/test_jamoraiko_vs_iono_notebook_build.py`に追加（cg非依存でローカル実行可能）：

- `compact_option`/`compact_log_entry`：Noneフィールドが除去されること、値があるフィールドは保持されることを固定
- `board_snapshot`：dictフィクスチャ（active/bench含む）から正しくid/hp/maxHp/energyCountを抽出すること、activeが空リスト（きぜつ直後など）でも壊れないこと
- `build_turn_log_entry`：SWITCH場面を模したフィクスチャobsで、`selected_indices`から正しく`selected_options`が解決されること、`select_type_name`/`select_context_name`が正しくラベル付けされること、未知のint値でも`"?"`等にフォールバックしクラッシュしないこと
- 既存の`TestJamoraikoDeckExpansion`等の回帰テストは無変更のまま維持

**ローカルで検証できない範囲**（Kaggle実測待ち）：

- 実際に生成されたノートブックが10試合分のログを正しく書き出せるか
- ファイルサイズが実用的な範囲に収まるか（想定：数MB程度。大きすぎる場合はstep数上限や試合数を絞る調整を次回検討する）

## スコープ外（今回はやらないこと）

- 200試合全体のログ化（ファイル肥大化のため見送り。まずは10試合で十分な情報が得られるか確認する）
- `obs["select"]["deck"]`（山札から選ぶ効果で見えているカード一覧）のログ化（今回のCARD実装漏れ調査には必須ではないため見送り。必要になれば追加検討）
- ログの自動分析・可視化（本設計はログ出力までがスコープ。分析は次のステップでログを見ながら判断する）
