# レビュー結果：ジャモライコ EnergyPolicyクラス導入 + OptionType.ENERGY_CARD修正

- ブランチ: `feature/jamoraiko-energy-policy-class`
- レビュー範囲: `c55f3c8..1784bd6`（Task 1〜2、2コミット）
- レビューア: Opusモデルによる最終ブランチ全体レビュー（各タスクはSonnetによるタスク単位レビューで個別承認済み）

## 検証したこと（レビューアが実行）

- `uv run pytest -q` → 499 passed（回帰なし）
- 削除対象の全シンボル（`energy_score`・`_find_energy_switch_source`・`_raging_bolt_ex_*`・`_score_energy_switch_*_candidate`・`_ENERGY_SWITCH_SURPLUS_THRESHOLD`）が`src/jamoraiko_agent/main.py`に一切残っていないことをgrepで確認（他モジュール`lucario_agent`等の同名`energy_score`は無関係な独立関数と確認）
- Task1の既知の計画矛盾（`_score_energy_switch_source_candidate`が削除予定の辞書に依存）が最終状態に禍根を残していないことを確認
- `_score_option`・`_score_card_option`の`match`文が新しいディスパッチと自然に統合されていることを確認（`_score_card_option`に`case _: return 0`が追加され、未マッチ時に`None`ではなく整数を返すようになった副次的な改善も確認）
- 新テストが実際に意味のある値（500/-500/-1000/0）をアサートしており、トートロジーでないことを確認

## Critical（必須修正）

なし。

## Important（修正推奨）

なし。

## Minor（あると良い、対応不要と判断）

1. `switch_source_score(self, obs, o, my_index)`の`my_index`引数が本体で未使用（`o.playerIndex`を正としているため実害なし）
2. `discard_for_damage_score()`が無差別に貪欲（希少な闘エネルギーも区別なく破棄しうる）。旧`OptionType.ENERGY`の挙動を忠実に踏襲したものであり、今回のスコープ外

## Assessment

**Ready to merge: Yes**

**Reasoning:** 2タスクの計画を過不足なく実装し、削除対象シンボルが全て消えていることをgrepで確認、クラスの最終メソッド構成（8個）に重複・矛盾がないことを確認した。499件のテストが全てPASS。今回の`SelectContext`マッピング（`SWITCH_ENERGY_CARD`/`DISCARD_ENERGY_CARD`）は前回の推測（`DETACH_FROM`）とは異なり実際のKaggleバトルログから直接導出したものであり、根拠の強度が格段に高い。残る指摘は全てMinorで対応不要。

**注記**：ローカルでは`libcg.so`が動かないため実対戦での検証は不可能。ユーザーがKaggleでノートブックを再実行し、`jamoraiko_vs_iono_turn_log.json`を再取得して、`DISCARD_ENERGY_CARD`が想定通り1枚ずつの選択か「何枚破棄するか」のカウント選択かを確認することが望ましい。
