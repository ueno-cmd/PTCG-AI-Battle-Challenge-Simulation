# ディレクトリ構成・ファイル責務

> このファイルは `/starter` コマンドで自動生成・上書きされます。
> 2026-07-20: data/・src/フォルダ再編成に伴い手動更新。

---

## 構成概要

コンペ提出用のポケモンカードゲームAIエージェント開発リポジトリ。
`src/`は実行可能なPythonパッケージのみ、`data/`は用途別に分けたデータ資産、
`notebooks/`はGit非管理のノートブック資産を置く。

---

## ディレクトリ構成

```
src/                        # Pythonパッケージ（Git管理・pythonpath対象）
├── <agent>_agent/          # 各対戦AIエージェント（main.pyにAgentクラス）
├── deck_builder/           # デッキ定義からdeck.csvを生成
└── etl/                    # バトルログの bronze/silver/gold 変換

decks/                      # デッキ定義（カードIDタプルのリスト）
scripts/                    # CLIツール（デッキ生成・ETL実行・分析・ノートブック生成）
tests/                      # pytestテストスイート

notebooks/                  # Git非管理のノートブック資産（*.ipynb）
├── references/             # 競技提供の参考ノートブック
├── experiments/            # 自前生成の実験ノートブック（scripts/build_*.pyが生成）
└── samples/                # 競技提供のサンプルノートブック

data/                       # Git非管理（.gitignoreのdata/*）。コンペ配布データ含むため再配布不可
├── competition/            # 競技配布データ（不変）
│   ├── JP_Card_Data.csv / EN_Card_Data.csv / Card_ID List_*.pdf
│   └── sample_submission/  # 競技公式サンプル（cgシミュレータ本体含む）
├── battle_logs/            # ダウンロードした生バトルログ（JSON）
├── unity-catalog/          # ETLパイプライン成果物（bronze/silver層）
├── experiments/            # 実験ログ・キャリブレーション結果
├── derived/                # スクリプトで再生成可能な自前生成データ
└── submission.tar.gz       # 提出物アーカイブ

output/                     # 実行時生成物（deck.csv出力など、Git非管理）
docs/                       # ドキュメント（要件・実装サマリ・レビュー・steering）
```

---

## 主要ファイル責務

- `src/<agent>_agent/main.py`: 各対戦AIエージェントの意思決定ロジック（`cg`ランタイムから呼ばれる`agent()`関数を実装）
- `src/deck_builder/`: `decks/*.py`のデッキ定義（カード名 or IDのタプル列）から提出用`deck.csv`を生成
- `src/etl/`: `data/battle_logs/`の生JSONを`data/unity-catalog/`のbronze（コピー）→silver（パース済みCSV）→gold（分析用集計）に変換
- `scripts/build_deck.py`: `decks/*.py`を読み`output/`にdeck.csvを出力
- `scripts/etl_battle_log.py`: 単一バトルログをbronze/silverに変換するCLI
- `scripts/merge_card_data.py`: `data/competition/`のEN/JP Card DataをJOINして`data/derived/card_data_merged.csv`を生成
- `scripts/analyze_top10_meta.py`: `data/derived/top10_meta_targets.csv`を読み、対象バトルログを分析してレポートを`output/`に出力
- `scripts/build_*_notebook.py`: `notebooks/references/`の参考ノートブックを元に`notebooks/experiments/`へ実験用ノートブックを生成
- `data/competition/`: 競技運営から配布されたデータ一式。改変しない
- `data/unity-catalog/`: ETLパイプラインの成果物置き場（medallion architecture命名）
