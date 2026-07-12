# 校正ノートブックのグラフをplotly化する計画（ミニ改修）

**Goal:** 校正実験ノートブックの累積勝率グラフをmatplotlibからplotlyに置き換え、日本語の凡例・タイトルが豆腐（□）にならないようにする。

**背景:** 影武者カウント版のグラフ凡例は日本語（「A(手書き・影武者計測) vs B(壊した設定)」等）だが、Kaggleのmatplotlibは日本語フォントを持たないため文字化けする。plotlyはブラウザフォント描画のため日本語がそのまま表示され、Kaggleに標準搭載されている。

**Scope:** `scripts/build_grimmsnarl_calibration_notebook.py` の `PLOT_CODE` 定数のみ。描画内容は従来と同じ（2系列の累積勝率の折れ線＋50%/60%の水平基準線）。タイトル・軸ラベルも日本語化する。ゲームロジック・保存データ・テスト対象コード（SHADOW_CODE等）には触れない。

**実行方式:** インライン実行（描画セルのみの変更で、既存テスト303件と冪等性チェックで担保できるため）。ユーザー承認済み（2026-07-12）。

## タスク

- [ ] `PLOT_CODE` をplotly（`plotly.graph_objects`）版に書き換える
- [ ] `uv run python scripts/build_grimmsnarl_calibration_notebook.py` でノートブック再生成（10セルのまま）
- [ ] 2回生成してshasum一致（冪等性）を確認
- [ ] `uv run pytest -q` で303件パスを確認
- [ ] ビルドスクリプトと本計画をコミット

## 検証

| 項目 | 方法 |
|---|---|
| 生成の冪等性・セル数 | 再生成×2でshasum一致、10セル |
| 既存機能の非破壊 | `uv run pytest -q` 303 passed |
| 日本語表示の実確認 | 次回Kaggle実行時にユーザーが目視（plotlyはKaggle標準搭載） |
