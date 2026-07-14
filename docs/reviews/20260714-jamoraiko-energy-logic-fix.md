# レビュー結果：ジャモライコ エネルギー運用ロジック修正

- ブランチ: `feature/jamoraiko-energy-logic-fix`
- レビュー範囲: `5e9367a..2742775`（Task 1〜6、6コミット）
- レビューア: Opusモデルによる最終ブランチ全体レビュー（各タスクはSonnetによるタスク単位レビューで個別承認済み）

## 検証したこと（レビューアが実行）

- `uv run pytest -q` → 491 passed（回帰なし）
- `data/cg/api.py`の`SelectContext`定義と突合し、`DETACH_FROM`＝供給元選択・`ATTACH_FROM`＝宛先選択のマッピングが実装計画の解釈通り正しいことを確認
- 「はじけるほうこう」抑制ロジックが`_score_option`ではなく`calc_attack_plan`の候補フィルタに実装されている点（設計書の技術判断メモ通りの妥当な補正）を確認
- Task 6の`_raging_bolt_ex_has_growth_path`がTask 4の`_find_energy_switch_source`・`Energy_Switch`定数を重複実装なく再利用していることを確認
- `Energy_Search`（ID1119）がPythonコード・テスト全体から完全に削除されていることを確認（残存する`1119`の参照は無関係な`src/rl_references/*.ipynb`のみ）
- `_ENERGY_SWITCH_SURPLUS_THRESHOLD`テーブルがPLAY時ゲート（`_find_energy_switch_source`）とCARD時スコアリング（`_score_energy_switch_source_candidate`）の唯一の情報源として共有され、矛盾が生じない設計であることを確認
- 新規CARDディスパッチ関数2つに`isinstance(card, Pokemon)`ガードが実際に実装されていることをコードで確認（タスクレビュー時点では未テストと指摘されていた項目）

## Critical（必須修正）

なし。

## Important（修正推奨）

なし。全ての指摘は設計書で明示済みのv1簡略化として許容範囲と判断。

## Minor（あると良い、対応不要と判断）

1. `OptionType.ENERGY`が`SelectContext`を見ずに常に9000を返す（`main.py`）。現デッキで到達しうるのは「きょくらいごう」の`DISCARD_ENERGY`のみのため実害はないが、将来カードが増えた場合の明示的なガードとして`context == SelectContext.DISCARD_ENERGY`を追加する余地あり。
2. `_score_energy_switch_source_candidate`/`_score_energy_switch_destination_candidate`に、既存の`_score_switch_target`にある`test_non_pokemon_card_returns_zero_without_crashing`相当の回帰テストが無い（ガード自体は実装済み・動作は正しい）。
3. `_find_energy_switch_source`/`_raging_bolt_ex_needs_lightning`はRaging_Bolt_exの複数コピー（デッキ内2枚）を考慮しない（計画で明示済みの簡略化）。
4. タイカイデン特性抑制（修正1）とはじけるほうこう抑制（修正5）を組み合わせると、雷エネが豊富な手札の時に「特性も使わない・攻撃もしない」ターンが発生しうる。デッドロックはしない（毎ターンエネルギーは場に付いていく）が、実測で過剰温存になっていないか確認が必要。

## Assessment

**Ready to merge: Yes**

**Reasoning:** 設計書の5つの修正方針を6タスクで全て実装し、タスク間の結合（Task 6がTask 4のヘルパーを再利用、Task 2で削除したカードの参照が完全にゼロ、FieldState新規フィールドが後続タスクと矛盾なく連携）に問題がないことを確認した。491件のテストが全てPASS。残る指摘は全て設計書で明示済みのv1簡略化であり、マージをブロックしない。

**注記**：ローカルでは`libcg.so`が動かないため実対戦での検証は不可能。特に「エネルギーつけかえ」のCARDサブ選択コンテキスト（`DETACH_FROM`/`ATTACH_FROM`）のマッピングと、`OptionType.ENERGY`の貪欲方針の妥当性は、Kaggle実測でしか最終確認できない。ユーザーがKaggle上でノートブックを再実行し、`jamoraiko_vs_iono_results.json`と`jamoraiko_vs_iono_turn_log.json`を再取得して勝率変化とログ内容を確認する必要がある。
