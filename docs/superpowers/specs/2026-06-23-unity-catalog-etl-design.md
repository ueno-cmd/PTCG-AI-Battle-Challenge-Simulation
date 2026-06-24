# Unity Catalog ETL 設計書

作成日: 2026-06-23

---

## 概要

バトルログの生JSONをメダリオンアーキテクチャ（Bronze / Silver）に従って整理・変換するETLパイプライン。
既存の `data/battle_logs/` を一次保管として維持しつつ、`data/unity-catalog/` にコピー・パース済みファイルを配置する。

---

## フォルダ構成

```
data/
├── battle_logs/                        # 一次保管（既存・変更なし）
│   └── 81344455.json
└── unity-catalog/                      # メダリオン層（新規作成）
    ├── bronze_81344455.json            # 生データのコピー
    ├── silver_summary_81344455.csv     # 試合サマリー（1試合1行）
    └── silver_turns_81344455.csv       # ターン詳細（1ステップ×2エージェント）
```

---

## CLIインターフェース

```bash
python scripts/etl_battle_log.py data/battle_logs/81344455.json
```

- 引数: `battle_logs/` 内のJSONファイルパス（1ファイル指定）
- 出力: `data/unity-catalog/` に bronze + silver 2ファイルを生成

---

## 処理フロー

```
battle_logs/<id>.json
        │
        ├─[コピー]──→ unity-catalog/bronze_<id>.json
        │
        └─[パース]──→ unity-catalog/silver_summary_<id>.csv
                   └→ unity-catalog/silver_turns_<id>.csv
```

---

## silver_summary カラム定義

1試合1行のサマリーCSV。

| カラム名 | 型 | 内容 |
|---|---|---|
| episode_id | int | 試合ID（JSONの `info.EpisodeId`） |
| player0_name | str | プレイヤー0の名前（`info.Agents[0].Name`） |
| player1_name | str | プレイヤー1の名前（`info.Agents[1].Name`） |
| winner_index | int | 勝者のagent index（`rewards` の最大値のindex） |
| winner_name | str | 勝者の名前 |
| total_steps | int | 総ステップ数（`len(steps)`） |

---

## silver_turns カラム定義

1ステップ × 2エージェント = 2行/step のターン詳細CSV。

| カラム名 | 型 | 内容 |
|---|---|---|
| episode_id | int | 試合ID |
| step | int | ステップ番号（`observation.step`） |
| agent_index | int | エージェントindex（0 or 1） |
| action | str | 選択した行動リスト（JSON文字列） |
| reward | float | そのステップの報酬 |
| status | str | ACTIVE / DONE |
| logs_count | int | ログイベント数（`len(observation.logs)`） |

---

## スコープ外

- Gold層（集計・分析用テーブル）の作成
- 複数ファイルの一括処理（バッチ実行）
- バリデーション・エラーリカバリーの高度化
