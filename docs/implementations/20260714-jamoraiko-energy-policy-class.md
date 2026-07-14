# 実装サマリー：ジャモライコ EnergyPolicyクラス導入 + OptionType.ENERGY_CARD修正

- ブランチ: `feature/jamoraiko-energy-policy-class`
- 対象コミット: `c55f3c8..1784bd6`（2タスク、2コミット）
- 設計書: `docs/superpowers/specs/2026-07-14-jamoraiko-energy-policy-class-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-14-jamoraiko-energy-policy-class.md`
- 実行方式: Subagent-Driven Development（実装Haiku・タスクレビューSonnet・最終レビューOpus）

## 背景

前回の修正（`docs/implementations/20260714-jamoraiko-energy-logic-fix.md`）で勝率0.015→0.045に改善したが、まだ低水準だった。ユーザーが新たに取得した`data/jamoraiko_vs_iono_turn_log.json`を解析した結果、以下が判明した：

- タイカイデンの自滅ループは完全解消（0回）、ATTACK提示率は10.3%→29.6%に改善、きょくらいごうも実際に5回発動
- しかし「エネルギーつけかえ」のSelectContextに関する前回の設計上の推測（`DETACH_FROM`）が誤りで、実際は`SWITCH_ENERGY_CARD`（`OptionType.ENERGY_CARD`）を通ることが判明
- きょくらいごうの追加ダメージ用エネルギー破棄も、想定していた`OptionType.ENERGY`ではなく同じ`OptionType.ENERGY_CARD`（`DISCARD_ENERGY_CARD`）経由だった
- `_score_option`に`OptionType.ENERGY_CARD`のケースが一つも実装されておらず常にスコア0。実戦ログでは、序盤にタケルライコex自身の唯一のエネルギーが誤って動かされる事故を確認

さらにユーザーから「関数手続き型のままだとエネルギー関連ロジックが分散し続けるのではないか」という懸念が示され、ブレストの結果、今回のバグ修正範囲に限定してエネルギー関連ロジックをクラスに集約する方針で合意した。

## 実装内容

### Task 1：`EnergyPolicy`クラスへの移植（振る舞い変更なし、commit `ee867d6`）

散らばっていた6つの自由関数（`energy_score`・`_find_energy_switch_source`・`_raging_bolt_ex_needs_lightning`・`_raging_bolt_ex_has_growth_path`・`_score_play_option`内のEnergy_Switch分岐・`_score_energy_switch_destination_candidate`）を`EnergyPolicy`クラスの6メソッドへ1:1で移植（`attach_priority`/`find_surplus_source`/`needs_lightning`/`has_growth_path`/`play_score`/`switch_destination_score`）。モジュールレベルで`ENERGY_POLICY = EnergyPolicy()`を1個だけ生成。ロジックは一切変更していない純粋なリファクタリング。

**計画との差分（発見・解決済み）**：Task1が削除する`_ENERGY_SWITCH_SURPLUS_THRESHOLD`辞書に、Task2で削除予定だった`_score_energy_switch_source_candidate`関数が依存していたため、その1行だけを`ENERGY_POLICY.SURPLUS_THRESHOLD`参照に更新する必要があった（動作は完全に維持、タスクレビューで承認済み）。

### Task 2：`OptionType.ENERGY_CARD`の実装とデッドコード削除（commit `1784bd6`）

- `EnergyPolicy`に新規メソッド追加：
  - `switch_source_score(obs, o, my_index)`：`SWITCH_ENERGY_CARD`（エネルギーつけかえの供給元エネルギー選択）。タケルライコex自身のエネルギーは-1000（絶対に選ばせない）、余剰ありのナンジャモポケモンは+500、余剰なしは-500
  - `discard_for_damage_score()`：`DISCARD_ENERGY_CARD`（きょくらいごうの追加ダメージ用破棄）。貪欲方針で常に9000
- 新規ディスパッチ関数`_score_energy_card_option`を追加し、`_score_option`に`case OptionType.ENERGY_CARD:`を新設
- デッドコード削除：`_score_card_option`の`DETACH_FROM`分岐・`_score_energy_switch_source_candidate`関数・`_score_option`の`OptionType.ENERGY`分岐（いずれも実戦ログで一度も通らないと確認済み）

## テスト結果

- 各タスクでTDD（RED→GREEN）を実施し、2回の個別タスクレビュー（Sonnet）と1回の最終ブランチ全体レビュー（Opus）で全てCritical/Important無し・承認
- 全体テストスイート：`uv run pytest -q` → **499件 全PASS**（開始時491件から8件増加）

## 既知の未検証事項・v2課題（最終レビューで記録、対応不要と判断）

- `switch_source_score`の`my_index`引数が本体で未使用（`o.playerIndex`を正としているため実害なし、シグネチャの対称性のために残している）
- `discard_for_damage_score`は無差別に貪欲（希少な闘エネルギーも区別なく破棄しうる）。ただし旧`OptionType.ENERGY`の挙動をそのまま踏襲したものであり、今回のスコープ外
- `switch_source_score`/`discard_for_damage_score`が実戦で意図通り動くかは、ローカルでは`libcg.so`が動かないためKaggle実測でしか最終検証できない

## 次のステップ

ユーザーがKaggle上でノートブックを再実行し、`jamoraiko_vs_iono_results.json`（勝率）と`jamoraiko_vs_iono_turn_log.json`（手番ログ）を再取得して効果を検証する。特に「エネルギーつけかえ」がタケルライコex自身のエネルギーを動かしてしまう事故が解消されたか、`DISCARD_ENERGY_CARD`が想定通り1枚ずつの選択か「何枚破棄するか」のカウント選択かを確認する。
