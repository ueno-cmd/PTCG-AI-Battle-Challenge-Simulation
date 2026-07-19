# data/・src/ フォルダ体系的整理 設計書

## 背景・目的

`data/`と`src/`が種類の異なるファイルの混在で散らかっていた。

- `data/`直下に「競技配布データ」「ETLパイプライン成果物」「生バトルログ」「実験ログ」「自前生成の派生CSV」「提出物」がフラットに並び、加えて未使用ファイル（重複ディレクトリ、コード未参照の一時解析ファイル、孤立ファイル）が混在していた。
- `src/`直下にPythonパッケージ（各エージェント、`deck_builder`、`etl`）と、Git非管理のノートブック群（`rl_experiments`/`rl_references`/`sample_notebook`、計20個弱）が混在していた。`src/`は`pyproject.toml`の`pythonpath`が指す純粋なインポート対象ディレクトリであるべきだが、実態は参照資料・実験ノートブックの置き場にもなっていた。

これらを用途別に整理し、あわせて`docs/steering/repo-structure.md`（現状ほぼ空のテンプレート）に実際の構成を反映させ、今後ステアリングファイルと実態が食い違わないようにする。

## 現状分析で判明した事実

- `data/`は`.gitignore`の`data/*`によりGit管理外（「コンペ配布データ（再配布不可）」）。
- `src/**/*.ipynb`も`.gitignore`の`*.ipynb`によりGit管理外。つまりノートブック群は元々パッケージコードとは別カテゴリの資産。
- `data/cg/`は`data/sample_submission/cg/`と完全に同一内容（`diff`で差分なし。`.pyc`と`cg.dll`の有無を除く）。`pyproject.toml`の`pythonpath`は`sample_submission`側のみを参照しており、`data/cg/`はコードから未参照。
- `data/tmp_iono_analysis/`（94MB）はコードから一切参照されていない。`data/unity-catalog/`と同じ構造（bronze/silver）を持つ、統合済みの古い一時解析の残骸。
- `data/deck.csv`はコードから未参照。2026-06-21付の設計書にのみ言及が残る孤立ファイル。
- `data/jamoraiko_vs_iono_results.json`・`data/jamoraiko_vs_iono_turn_log.json`は`scripts/build_jamoraiko_vs_iono_notebook.py`が生成するKaggleノートブックのセルが`/kaggle/working`に出力するファイルを手動でダウンロード配置したもの。ローカルコードからの参照はなく、移動してもコード修正は不要。

## 新しいディレクトリ構成

### `data/`

```
data/
├── competition/                      # 競技配布データ（不変・再配布不可）
│   ├── JP_Card_Data.csv
│   ├── EN_Card_Data.csv
│   ├── Card_ID List_JP.pdf
│   ├── Card_ID List_EN.pdf
│   └── sample_submission/
├── battle_logs/                      # 現状維持（生バトルログ）
├── unity-catalog/                    # 現状維持（ETLパイプラインのbronze/silver成果物）
├── experiments/
│   ├── （既存ファイルそのまま）
│   └── jamoraiko_vs_iono/
│       ├── results.json              # 旧 jamoraiko_vs_iono_results.json
│       └── turn_log.json             # 旧 jamoraiko_vs_iono_turn_log.json
├── derived/                          # スクリプトで再生成可能な自前生成データ
│   ├── card_data_merged.csv
│   └── top10_meta_targets.csv
└── submission.tar.gz
```

### `src/` と `notebooks/`

```
src/                                  # Pythonパッケージのみ
├── cinderace_starmie_agent/
├── decidueye_agent/
├── deck_builder/
├── etl/
├── grimmsnarl_agent/
├── jamoraiko_agent/
├── lucario_agent/
└── mascarnage_agent/

notebooks/                            # 新設。Git非管理のノートブック資産
├── references/                       # 旧 src/rl_references（競技提供の参考ノートブック、5個）
├── experiments/                      # 旧 src/rl_experiments（自前生成の実験ノートブック、5個）
└── samples/                          # 旧 src/sample_notebook（競技サンプルノートブック、10個）
```

## 削除対象

- `data/cg/`（`data/competition/sample_submission/cg/`と完全重複）
- `data/tmp_iono_analysis/`（94MB、コード未参照の古い一時解析）
- `data/deck.csv`（コード未参照の孤立ファイル）
- `.DS_Store`（`data/`・`src/`直下の各1個）
- 全`__pycache__`ディレクトリ（自動再生成されるキャッシュ）

実施直前に対象ファイル一覧を再提示し、最終確認を取ってから削除する。

## 追従修正が必要なコード箇所

### `data/competition/`移動に伴うパス更新

| ファイル | 変更内容 |
|---|---|
| `pyproject.toml` | `pythonpath`の`"data/sample_submission"` → `"data/competition/sample_submission"` |
| `scripts/analyze_grimmsnarl_stall_metrics.py` | `sys.path.insert`のパスを`data/competition/sample_submission`に更新 |
| `scripts/build_deck.py` | `CARD_CSV`を`data/competition/EN_Card_Data.csv`に更新 |
| `scripts/merge_card_data.py` | `EN_CSV`/`JP_CSV`を`data/competition/`配下に、`OUT_CSV`を`data/derived/card_data_merged.csv`に更新 |
| `scripts/analyze_top10_meta.py` | デフォルトの`top10_meta_targets.csv`パスを`data/derived/`に、`EN_Card_Data.csv`パスを`data/competition/`に更新 |
| `tests/test_analyze_top10_meta.py` | `EN_Card_Data.csv`参照パスを`data/competition/`配下に更新（3箇所） |
| `tests/test_etl_gold.py` | `CARD_DATA_PATH`を`data/competition/EN_Card_Data.csv`に更新 |

`battle_logs/`・`unity-catalog/`は場所を変えないため、これらを参照する箇所は変更不要。

### `notebooks/`移動に伴うパス更新

| ファイル | 変更内容 |
|---|---|
| `scripts/build_lucario_selfcheck_notebook.py` | `REF_NB`（`notebooks/references/...`）・`DST`（`notebooks/experiments/...`）を更新 |
| `scripts/build_grimmsnarl_feature_ab_notebook.py` | 同上 |
| `scripts/build_jamoraiko_vs_iono_notebook.py` | `REF_NB`・`IONO_NB`（`notebooks/samples/...`）・`DST`、およびコメント2箇所を更新 |
| `scripts/build_grimmsnarl_calibration_notebook.py` | `REF_NB`・`DST`を更新 |

## ステアリングファイルの更新

`docs/steering/repo-structure.md`は現状テンプレートのままで実態を反映していない。再編成後の`data/`・`src/`・`notebooks/`・`scripts/`・`decks/`・`tests/`・`docs/`・`output/`の構成と各ディレクトリの責務を記載し、今後の突合ズレを防ぐ。

## 検証方法

- `uv run pytest`で全テストがパスすることを確認する（パス変更ミスは機械的に検出される）
- 再編成後のディレクトリツリーを目視確認する
- 削除対象は実施前に一覧を再提示し、ユーザーの最終確認を得る

## スコープ外

- `scripts/`・`decks/`・`tests/`・`output/`ディレクトリ自体の再編成は対象外（現状で用途別に分かれており問題なし）
- `data/unity-catalog/`・`data/battle_logs/`のディレクトリ名変更は対象外（コード内で機能している名称のため、リスクを避けて維持）
