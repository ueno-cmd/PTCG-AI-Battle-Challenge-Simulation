# 実装サマリー：ジャモライコ エネルギー運用ロジック修正

- ブランチ: `feature/jamoraiko-energy-logic-fix`
- 対象コミット: `5e9367a..2742775`（6タスク、6コミット）
- 設計書: `docs/superpowers/specs/2026-07-14-jamoraiko-energy-logic-fix-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-14-jamoraiko-energy-logic-fix.md`
- 実行方式: Subagent-Driven Development（実装Haiku・レビューSonnet・最終レビューOpus）

## 背景

Kaggle上の校正実験（vs イオナサンプル200試合）で勝率0.015という結果が続いていたため、手番選択ログ出力機能（別ブランチで実装済み）を使って実際の10試合分のログを解析した。その結果、3つの根本原因が判明した：

1. タイカイデン（Iono's Kilowattrel）の特性「フラッシュドロー」が、付けたばかりの雷エネルギーを同じターン内に自分で捨てる自滅ループを起こしていた
2. タケルライコex（Raging Bolt ex）が92回の判断中一度もエネルギー1枚を超えず、ほぼダメージを与えられていなかった
3. `_score_option`の`match`文で`OptionType.ENERGY`が一つもケース分けされておらず、常にスコア0になっていた（`OptionType.CARD`丸ごと未実装だった過去の事故と同種の抜け漏れ）

さらにカード効果の裏取り（`data/JP_Card_Data.csv`）により、タケルライコexは「ナンジャモのポケモン」ではない（ハラバリーex等の特性の対象外）こと、「きょくらいごう」の追加ダメージ計算対象は自分の場のポケモン全体であり、タケルライコex自身に限定されないことが判明し、当初の設計方針を修正した。

## 実装した5つの修正

### 修正1：タイカイデンの自滅ループ防止（Task 1、commit `32512e4`）
`FieldState`に`hand_has_basic_lightning_energy: bool`フィールドを追加し、手札に基本雷エネルギーが残っている間は`_score_option`のABILITY分岐（タイカイデン）を-1にして特性発動を抑制する。

### 修正2：デッキ変更（Task 2、commit `1cd8f5a`）
`decks/jamoraiko_20260713.py`から「エネルギー転送」（ID1119、山札サーチ）を削除し、「エネルギーつけかえ」（ID1116、場のポケモン間でのエネルギー付け替え）を追加。`main.py`の`Energy_Search`定数と関連スコアリングは完全に削除し、`Energy_Switch`定数を新設した。

### 修正3：タケルライコexへのエネルギー供給（Task 3・4、commit `15c4261`・`1c97493`）
- `energy_score()`にタケルライコex分岐を追加（雷エネルギー1枚未満の時のみ+90）
- 新規ヘルパー`_find_energy_switch_source`（ベンチの余剰供給元探索）・`_raging_bolt_ex_needs_lightning`を実装
- 「エネルギーつけかえ」のPLAYスコアリング（供給元があり、かつタケルライコexが雷0枚の時のみ高優先）
- CARDサブ選択（`SelectContext.DETACH_FROM`＝供給元選択／`ATTACH_FROM`＝宛先選択）のスコアリングを新規実装

### 修正4：`OptionType.ENERGY`の実装（Task 5、commit `424f869`）
`_score_option`に`case OptionType.ENERGY: return 9000`を追加。きょくらいごうの追加ダメージ用に、提示された基本エネルギーは常に貪欲に捨てる方針とした（ターン内状態追跡はv2以降の課題）。

### 修正5：はじけるほうこうの抑制（Task 6、commit `2742775`）
新規ヘルパー`_raging_bolt_ex_has_growth_path`（手札に闘/雷エネがある、またはエネルギーつけかえの供給元がある）を実装し、`calc_attack_plan`の候補フィルタでタケルライコexの「はじけるほうこう」（ダメージ0）を、まだきょくらいごうへ伸びる見込みがある間は候補から除外するようにした。

## テスト結果

- 各タスクでTDD（RED→GREEN）を実施し、6回の個別タスクレビュー（Sonnet）と1回の最終ブランチ全体レビュー（Opus）で全てCritical/Important無し・承認
- 全体テストスイート：`uv run pytest -q` → **491件 全PASS**（開始時451件から40件増加）

## 既知の未検証事項・v2課題（最終レビューで記録、対応不要と判断）

- `OptionType.ENERGY`が`SelectContext`を見ずに常に9000を返す（現デッキでは`DISCARD_ENERGY`のみ到達するため実害無し）
- 新規CARDディスパッチ関数2つに、非Pokemonカードに対する回帰テストが未追加（isinstance ガード自体は実装済み・動作確認済み）
- `_find_energy_switch_source`等はRaging_Bolt_exの複数コピー（デッキ内2枚）を考慮しない設計（計画で明示済みの簡略化）
- タイカイデン特性抑制とはじけるほうこう抑制を組み合わせた時の過剰温存リスク（デッドロックはしないが、実測で確認が必要）
- エネルギーつけかえのCARDサブ選択コンテキスト（`DETACH_FROM`/`ATTACH_FROM`）の対応関係、`OptionType.ENERGY`の貪欲方針の妥当性は、ローカルでは`libcg.so`が動かないためKaggle実測でしか最終検証できない

## 次のステップ

ユーザーがKaggle上でノートブックを再実行し、`jamoraiko_vs_iono_results.json`（勝率）と`jamoraiko_vs_iono_turn_log.json`（手番ログ）を再取得して効果を検証する。
