# レビュー結果: 影武者カウント計測（校正実験v2）

- 日付: 2026-07-12
- ブランチ: feature/grimmsnarl-hybrid-step0（59f5771..0a70001、1コミット）
- 実装計画: `docs/superpowers/plans/2026-07-12-grimmsnarl-shadow-count.md`
- 背景: 校正実験v1でA vs Bが200試合で勝率50.0%（差なし）。原因切り分け用の計測を追加
  （結果データ: `data/experiments/20260712_grimmsnarl_calibration.json`）
- レビュー体制: タスク単位レビュー×2（サブエージェント）＋最終ブランチ全体レビュー（Opusモデル）

## 最終判定

**Ready to merge = Yes**（Critical/Important無し。持ち越しMinor 4件＋新規Minor 2件は全て記録のみと判定）

## 検証サマリー（レビュアーが実測・実コード照合で確認）

| 観点 | 結果 |
|---|---|
| 全体テスト `uv run pytest -q` | 303 passed（既存295＋新規8） |
| 傍受メカニズム | `agent()`(main.py:473)はグローバル名 `_score_attach` を参照するため、名前の再束縛で確実に傍受できることを実コードで確認 |
| 乱数の非干渉 | `_rng` 消費は `Boss_Orders` 分岐のみで重みに非依存 → A/Bの消費数は常に一致。本線の乱数消費はA側1回分のみ（v1のweighted_agentと等価挙動） |
| log整列前提 | `_score_attach` の呼び出し回数・順序はobs由来で重みに非依存 → A/Bのログは常に同長・同順。カウンタ比較は正当 |
| ノートブック生成 | 10セル構成、`shadow-agent` の位置・セル間の名前依存を実ファイル検証。冪等（shasum一致） |
| テスト方式 | セルソースをスタブ名前空間にexecし、グローバル再束縛経路を忠実に再現して検証（モック依存なし） |

## Minor指摘（全て対応不要・記録のみ）

1. `make_shadow_agent` にtry/finallyなし（B側例外時に `_rng`/`TUNABLE_WEIGHTS` 未復元のまま伝播。例外時はセルごと停止するため無害）
2. Notebook上で `shadow-agent` セルを2回実行すると多重ラップ（正規手順は上から1回実行。冪等ガード1行で防げるが必須でない）
3. `main()` のセル挿入配線はユニットテスト対象外（Task 2の実物構造検証で担保済み）
4. `_score_attach` の恒久ラップにより `series_aa` 中も `_ATTACH_LOG` が伸び続ける（`shadow_stats_ab` はスナップショット済みで実害なし）
5. （最終レビュー新規）`attach_score_diff=0 → バグ` の判定は厳密には「swapの効く候補（グリムスナール<2エネ／モルペコ）が一度も出なかった」ケースと区別できない。序盤頻出経路のため実質発火するが、結果解釈時に内訳を一応確認すると盤石
6. （最終レビュー新規）`select_diff` は順序込みリスト比較のため、`maxCount>1` の場面では「同じ集合で優先順位だけ違う」もカウントされる（付与判断は通常maxCount=1で実害ほぼなし）

## 次のアクション

1. `src/rl_experiments/grimmsnarl_calibration_experiment.ipynb` を再度Kaggleにアップロードし、
   前回と同じ入力（`deck_20260705_185905.csv` を含むデータセット＋公式コンペデータ）で実行（ユーザー）
2. 持ち帰るのは `calibration_shadow_results.json`。`shadow_stats` の6カウンタで
   ①重み反映の有無（`attach_score_diff`）②競合場面の頻度（`grimmsnarl_morpeko_both`）
   ③意思決定への影響（`select_diff`/`attach_top_diff`）を判定する
3. 判定結果に基づき、ステップ1のチューニング対象を維持または再選定する
