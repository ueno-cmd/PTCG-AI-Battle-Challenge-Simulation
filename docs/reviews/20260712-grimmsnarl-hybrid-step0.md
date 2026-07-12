# レビュー結果: グリムスナールex ハイブリッドチューニング ステップ0（校正実験）

- 日付: 2026-07-12
- ブランチ: feature/grimmsnarl-hybrid-step0（589d1ae..6013031、2コミット）
- 設計書: `docs/superpowers/specs/2026-07-12-grimmsnarl-hybrid-tuning-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-12-grimmsnarl-hybrid-step0-calibration.md`
- レビュー体制: タスク単位レビュー×2（サブエージェント）＋最終ブランチ全体レビュー（Opusモデル）

## 最終判定

**Ready to merge = Yes**（Critical/Important無し。持ち越しMinor 4件は全てブロック不要と判定）

## 検証サマリー（レビュアーが実測で確認）

| 観点 | 結果 |
|---|---|
| 全体テスト `uv run pytest -q` | 295 passed（計画の期待値どおり） |
| 挙動不変性（等価リファクタリング） | リテラル→辞書参照の1対1置換のみ。デフォルト値8個が手書き現行値と完全一致。`_score_attach` の場合分け構造・ゲート条件・閾値は不変 |
| 設計書との整合 | 8キー／globパターン／200試合×2系列／チェックポイント／設定B（grimmsnarl_base⇔morpeko_base入替）全て一致 |
| ノートブック生成の冪等性 | 再実行してもバイト一致。9セル構成。gitignore対象であることを確認 |
| Kaggle動作見込み | 高い（play_gameハーネスが参考NBの実績コードとバイト一致、agent()シグネチャ一致、main.py埋め込みは定義のみで副作用なし、battle_startのデッキ焼き込み仕様と整合） |

## Minor指摘（全て対応不要・記録のみ）

1. `TestTunableWeights._make_fs` が既存 `TestScoreAttach._make_fs` とほぼ重複（brief由来。将来テストヘルパー共通化の余地）
2. 参考NBからコピーしたimportセルに校正実験と無関係なevo_search用定数（GENERATIONS等）が残留（逐語コピー仕様由来、未参照のデッドコードで無害）
3. `from cg.game import ...` がコピーセルとハーネスセルで重複（冪等・無害）
4. ノートブック `metadata.papermill` に参考NBの過去実行タイムスタンプ（2026-06-18）が残留（化粧上の残骸、実行に影響なし）
5. （最終レビュー新規発見・低リスク）main.py の `agent()` は `obs.select is None` 時にディスクの deck.csv を読むが、ノートブックの自己対戦では battle_start がデッキを焼き込むため select-None は発生せず実害なし。将来ハーネス方式を変える場合の注意点として記録

## 次のアクション

1. `src/rl_experiments/grimmsnarl_calibration_experiment.ipynb` をKaggleへアップロードし、
   `deck_20260705_185905.csv` を含むデータセット＋公式コンペデータをAdd Inputでアタッチして実行（ユーザー）
2. 確認ポイント：①A vs Bの勝率が何試合目から一貫して60%を超えるか、②A vs Aが50%付近に収束するか、
   ③1試合あたりの実行時間
3. 結果（`calibration_results.json`・実行ログ）を持ち帰り、ステップ1（本番チューニング）の
   試合数・世代数を決定する
