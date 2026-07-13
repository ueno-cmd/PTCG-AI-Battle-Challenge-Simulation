# ジャモライコ vs イオナサンプル 校正ノートブック 実装サマリー

- 実装日：2026-07-13
- 目的：ジャモライコエージェント（`src/jamoraiko_agent/main.py`）が、現行のイオナ/ナンジャモサンプル（LB 600〜877）に対して勝率で上回るかを、Kaggle Notebook上の自己対戦（200試合）で確認するための校正ノートブックを生成する
- 設計書：`docs/superpowers/specs/2026-07-13-jamoraiko-vs-iono-calibration-design.md`
- 実装計画：`docs/superpowers/plans/2026-07-13-jamoraiko-vs-iono-calibration.md`

## 実装したファイル一覧

| ファイル | 役割 |
| --- | --- |
| `scripts/build_jamoraiko_vs_iono_notebook.py` | ノートブック生成スクリプト（参考ノートブックからcgランタイム起動セルをコピーし、両エージェント本体・両デッキ定数・対戦ハーネス等を合成してノートブックJSONを書き出す） |
| `tests/test_jamoraiko_vs_iono_notebook_build.py` | 生成スクリプトの検証テスト（セル数・埋め込みマーカーの存在確認など） |

（Task 1で実装・レビュー承認・コミット済み。本タスクではビルドスクリプトの実行と生成物の検証のみを行った。）

## テスト件数

- Task 1で追加した新規テスト：`tests/test_jamoraiko_vs_iono_notebook_build.py` の**8件**
- リポジトリ全体：`uv run pytest -q` → **408件 → 416件**（回帰なし。今回も416件PASSを再確認済み）
- Task 1のレビューでImportant指摘1件があり、修正済み：`load_helper_src`を`load_agent_module`関数のロジックの手動転記文字列にしていたため、両者が乖離してもテストは通り続けるサイレントバグの温床になっていた。`inspect.getsource(load_agent_module)`から動的生成する方式に変更し、テスト対象の関数とノートブックに埋め込まれる関数が構造的に一致することを保証した（コミット`5037fb4`）。

## ノートブックの生成・検証結果

### Step 1: ビルドスクリプト実行

```
$ uv run python scripts/build_jamoraiko_vs_iono_notebook.py
wrote src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb with 11 cells
```

計画時の実測値（note1 + コピー2 + deck-load + agent-sources + load-helper + agent-load + battle-harness + calibration-run + save-results + plot-curve = 11セル）と完全一致。

### Step 2: 内容検証

以下のワンライナーで、生成されたノートブック内の主要マーカーが全て存在することを確認した。

```
$ uv run python -c "
import json
nb = json.loads(open('src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb').read())
print('cell count:', len(nb['cells']))
srcs = {c['id']: c['source'] for c in nb['cells'] if c['cell_type'] == 'code'}
assert 'JAMORAIKO_SOURCE' in srcs['agent-sources']
assert 'IONO_SOURCE' in srcs['agent-sources']
assert '%%writefile' not in srcs['agent-sources']
assert 'JAMORAIKO_DECK' in srcs['deck-load']
assert 'IONO_DECK' in srcs['deck-load']
assert 'load_agent_module' in srcs['load-helper']
assert 'battle_start' in srcs['battle-harness']
assert 'GAMES = 200' in srcs['calibration-run']
print('OK: all expected markers present')
"
cell count: 11
OK: all expected markers present
```

エラーなく終了し、期待マーカー（両エージェントのソース埋め込み、`%%writefile`未混入、両デッキの定数埋め込み、名前空間分離ヘルパー、対戦ハーネス、200試合の実行設定）が全て確認できた。

なお、`src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`自体は`.gitignore`対象のためコミットしていない（生成手順は本ドキュメントとビルドスクリプトから再現可能）。

## Kaggle上での実行手順

1. Kaggle Notebookに`src/rl_experiments/jamoraiko_vs_iono_experiment.ipynb`をアップロードする
2. **Add Inputでジャモライコのdeck.csvデータセットのみアタッチすればよい**（イオナサンプルのデッキ・エージェント本体はいずれもビルド時にコード内へ埋め込まれているため、追加データセットは不要）
3. ノートブックを実行し、200試合の累積勝率推移と`jamoraiko_vs_iono_results.json`（`/kaggle/working`）を確認する

なお、ジャモライコのデッキデータセット（`output/deck_jamoraiko_20260713.csv`相当）のKaggleへのアップロード作業は、ユーザーが別途進めている最中である。本タスクの範囲はローカルでのノートブック生成・検証までであり、Kaggle上でのアップロード完了・実行はユーザー作業として引き継ぐ。

## 次のステップ（ユーザー判断で別途実施）

- ジャモライコのdeck.csvデータセットをKaggleにアップロードし、本ノートブックをAdd Input経由で実行する
- 200試合の実行結果（累積勝率）を確認し、イオナサンプルに対して優位かどうかを判断する
- 実際の勝率次第で、チューニング対象の洗い出しに進むかどうかを判断する（設計書のスコープ外事項）
- 負け試合の盤面ログ保存・質的分析（今回は勝率のみ測定。必要になれば別途追加）

設計書: `docs/superpowers/specs/2026-07-13-jamoraiko-vs-iono-calibration-design.md`
