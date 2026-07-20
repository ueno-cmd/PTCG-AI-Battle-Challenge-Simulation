# ルカリオexデッキ 居座りボーナス修正＋RETREAT HP温存観点追加 レビュー結果

**関連実装サマリー：** `docs/implementations/20260720-lucario-stay-bonus-retreat-hp-preservation.md`
**対象コミット範囲：** `1056801..9c0c712`（feature/lucario-stay-bonus-retreat-hp-preservation、4コミット）

## タスク別レビュー

### Task 1: `AttackPlan.damage`フィールド追加（コミット`64a2b9b`）

- Spec Compliance: ✅ Spec compliant
- Issues: Critical/Important無し
- Minor: `damage`フィールドにインラインコメント無し（既存フィールド`attacker`等も無コメントで一貫性あり、対応不要）
- Task quality: **Approved**

### Task 2: 居座りボーナスバグ本体の修正（コミット`839befe`）

- Spec Compliance: ✅ Spec compliant（`i==0`/`j==0`の両方が`damage > 0`配下に正しく入っており、KO確定プランへの影響も実質なしと確認済み）
- Issues: Critical/Important無し
- Minor:
  1. `if damage > 0:`ブロックに説明コメント無し
  2. 実装者報告書の変更行数記載が実際のdiffと軽微に不一致（コードへの影響なし）
- Task quality: **Approved**

### Task 3: `_score_retreat_option`へのHP温存退却分岐追加（コミット`d514e95`）

- Spec Compliance: ✅ Spec compliant（既存`attacker>=1`分岐は無変更、新分岐のex/megaEx判定・Noneフォールバックともに正確）
- Issues: Critical/Important無し
- ⚠️ Cannot verify from diff: `attacker==-1`（プラン未計算）ケースでの新分岐発火は、設計書「`attacker < 1`」の記述で意図された挙動と確認済み（controllerが解決）
- Minor:
  1. `make_pokemon`のimportが重複（既存ファイルの慣習通り）
  2. `my_active`パラメータの型注釈省略（ブリーフのコード例自体が型注釈なしだった）
- Task quality: **Approved**

### Task 4: `main.py`の呼び出し配線（コミット`9c0c712`）

- Spec Compliance: ✅ Spec compliant（設計書の「main.py側の呼び出し変更」節と一字一句一致）
- Issues: Critical/Important無し
- Minor:
  1. `MagicMock`/`Option`/`OptionType`のローカルimportが重複
  2. `my_state.active`が空の場合を直接検証する統合テストが無い（三項演算子のNone分岐は静的に安全と確認済み）
- Task quality: **Approved**

## 最終ブランチ全体レビュー（Opusモデル）

**Ready to merge: Yes**

**Reasoning:** 実装は設計書・計画と1行単位で一致し、574件全テストがPASS、後方互換性・変更局所性・2バグ修正の協調がいずれも健全に確認できた。残る指摘はすべてMinor（冗長import・型注釈省略・テスト網の薄さ）で、機能の正しさや本番挙動に影響しない。

### Strengths（抜粋）

- 計画・設計書との完全一致（4タスクすべてがコードブロックと1行単位で一致）
- 位置ボーナス撤去（Task2）とHP温存退却（Task3）が役割重複なく補完的に機能する設計
- KO確定プラン（`score=50000`）は必ず`damage>0`のため、位置ボーナスによるタイブレークは維持され、影響範囲が「ダメージ0プランが位置ボーナスだけでベンチ交代を上回るケース」に限定されている
- `_score_retreat_option`の新引数はデフォルト`None`で既存の単一引数呼び出しに対し非破壊
- wiring統合テストは`autouse`の`mock_card_table`経由で`lm.card_table`を実際に差し替えており、モックだけの空虚なテストではない

### Issues

Critical: 無し
Important: 無し

Minor（3件、いずれも対応不要と判断）:
1. `tests/test_lucario_agent.py`内で`make_pokemon`のimportが重複（既存ファイルの慣習と一貫）
2. `src/lucario_agent/combat.py:253`の`my_active`パラメータに型注釈が無い（計画書のInterfaces節とコードブロックが内部で不一致だったため、実装はコードブロックに忠実に従った）
3. `damage == -1`（プラン未計算）で温存退却が発火するケースの直接テストが無い（`damage == 0`のケースは検証済み）

### Recommendations

- 温存退却分岐が`damage == -1`（プラン未計算）でも発火する点は設計思想と整合しているが、トリガーがやや広い。将来アプローチB（脅威判定）を導入する際、Kaggle実戦ログで「攻撃できないだけで無害に居座れる場面」まで退却を誘発していないか観測することを推奨
- 上記Minorはいずれもマージをブロックしない。次回のテストファイル整理時にまとめて対応で十分

## 結論

**マージ判定：Ready to merge = Yes**。Critical/Important指摘は無く、Minor指摘はいずれも対応不要と判断した。`main`へfast-forwardマージ済み（コミット範囲`1056801..9c0c712`）。
