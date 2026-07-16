# ジャモライコ ビリリダマ軸ピボット 最終ブランチ全体レビュー

- 対象ブランチ: `feature/jamoraiko-voltorb-pivot`
- 対象範囲: `4f59445..c6a4cec`（5コミット、Task1〜5全て）
- レビューア: Opusモデル（最終ブランチ全体レビュー）
- 各タスクの個別レビューは全てCritical/Important無しで承認済み。本レビューはその上での全体横断チェック

## 総評

**Ready to merge: Yes**

設計書・実装計画の5タスク全てに忠実で逸脱なし。タケルライコex・基本闘エネルギー専用の死んだコードは実コードから完全に削除済み。作り直したEnergyPolicyは責務分離が明確でエッジケースのテストも実在（モックのモックではない）。デッキ内容は`main.py`のロジックが前提とする値と整合。兄弟デッキ（grimmsnarl_agent, lucario_agent等）には一切影響なし。テストスイート495件全PASS。

## 良い点

- 5タスク全ての実装がプランのコードブロックと完全一致
- `Raging_Bolt_ex`/`Basic_Fighting_Energy`/`own_board_basic_energy_total`/`active_fighting_energy_count`/`is_utility`/`requires_fighting`/`has_growth_path`/`discard_for_damage_score`のいずれも実コードから参照ゼロ（履歴的な意図的コメント3箇所を除く）
- `lucario_agent`の独自`Basic_Fighting_Energy`定数など、他デッキへの影響なし
- デッキ60枚・`265:3`・`4:15`・`63`/`6`不在をランタイムで確認済み。`POKEMON_LINES`/`ATTACKERS`の値とも整合
- `EnergyPolicy.needs_lightning`はactiveなしの2パターンを正しくガード。`switch_source_score`/`switch_destination_score`は`SURPLUS_THRESHOLD`を軸に対称的で自己参照バグなし
- Kaggle提出ノートブック関連ファイルは未変更（ユーザー側作業として明示的にスコープ外を維持）

## 指摘事項

### Critical
なし

### Important
なし

### Minor（対応不要・記録のみ）

1. **`calc_attack_plan`の`my_state`引数が未使用に**（`src/jamoraiko_agent/main.py:152`付近）：Task2で唯一の利用箇所（`_safe_draws`呼び出し・`has_growth_path`呼び出し）が削除されたが、シグネチャ自体は4引数のまま計画通り残された。プラン側の見落としであり実装の逸脱ではない。次回のついで作業候補
2. **`lethal`選択・`locks_next_turn`減点ロジックが実質死重に**：現在の`ATTACKERS`テーブルは1ポケモンにつき1エントリのみのため、`candidates`は常に1件以下。コード内コメントで意図的な将来対応と明記されており許容範囲
3. **（設計通り・要対応なし）`switch_destination_score`は非アクティブのハラバリーex/タイカイデンにも+500を付与しうる**：`play_score`側の発動条件（`needs_lightning`）はアクティブのみを見るため、同点時にベンチへエネルギーが回る可能性がある。設計書の一般化方針（[[docs/superpowers/specs/2026-07-16-jamoraiko-voltorb-pivot-design.md]]）通りの意図的挙動

## 未検証事項（本ブランチのスコープ外）

- ビリリダマ軸への変更が実際に勝率を改善するかは、校正ノートブックの再ビルド・Kaggle実行でのみ確認可能（ユーザー側で別途実施）
