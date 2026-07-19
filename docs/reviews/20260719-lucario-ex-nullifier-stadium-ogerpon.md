# ルカリオex ex無効化検知汎用化・スタジアム考慮・オーガポンex優先度連動 — ブランチ全体レビュー

- レビュー範囲: `a1a42dd..7f20735`（4コミット、featureブランチ`feature/lucario-ex-nullifier-stadium-ogerpon`）
- レビュー方式: `superpowers:subagent-driven-development`（タスクごとのレビュー3回＋最終ブランチ全体レビュー1回）
- 設計書: `docs/superpowers/specs/2026-07-19-lucario-ex-nullifier-stadium-ogerpon-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-19-lucario-ex-nullifier-stadium-ogerpon.md`
- 実装サマリー: `docs/implementations/20260719-lucario-ex-nullifier-stadium-ogerpon.md`

## タスクごとのレビュー結果

| タスク | 内容 | 結果 |
|---|---|---|
| Task 1 | ex無効化検知の汎用化（`EX_DAMAGE_NULLIFIER_IDS`・`_calc_attack_damage`） | 承認（Critical/Important/Minor無し） |
| Task 2 | 相手アクティブの無効化判定＋オーガポンex優先度連動 | 承認（Critical/Important無し。Minor1件・対応不要） |
| Task 3 | `calc_attack_plan`のスタジアム（Nighttime Mine）考慮 | 承認（Critical/Important無し。Minor2件・対応不要） |
| Task 4 | 全体回帰確認・実装サマリー作成 | controllerが直接内容確認（テスト件数・コミット範囲・事実関係とも正確） |

## 最終ブランチ全体レビュー（Opusモデル）

### Strengths

- 設計書で予定された3件（ex無効化検知の汎用化、Nighttime Mineコスト考慮、オーガポンex優先度連動）すべてが計画どおり実装済み。計画外のスコープ拡張なし
- **クロスタスクの相互作用を明示的に検証**：テラスタル×スタジアム（Task3）とex無効化（Task1）は`energy_required`（撃てるか）と`damage`（通るか）という直交する軸で、互いをマスクしないことを`calc_attack_plan`のループで確認
- Task1で発見・修正した「オーガポンex自身の`.ex`フラグで自己無効化してしまう」落とし穴（`not attack_ignores_defender_effects`を先頭ガードに配置）が、以降のタスクの編集を経ても正しく維持されていることを確認
- Task2のエネルギー優先度（`+150`）とTask3のコスト増（Nighttime Mineで+1）が衝突しないこと（コスト増は単に「もう1ターン装着が必要」になるだけで、クラッシュや誤ったKO判定にはならない）を確認
- 5つの関数シグネチャに新規パラメータが追加されたが、いずれもデフォルト値付きで既存呼び出し箇所は無変更のまま動作。パラメータの引き回しも既存の`attacker1`等のパターンを踏襲しており一貫性あり
- テストが実際の挙動（スコアの相対順序・具体的な差分値）を検証しており、モックへの依存に留まっていない

### Issues

**Critical（必須修正）**：なし
**Important（対応推奨）**：なし
**Minor（3件、いずれもcontrollerが直接対応済み）**：
1. 実装サマリーのテスト件数誤記（開始前526件と記載していたが、実際に`a1a42dd`時点のコードを再現し実測したところ523件だった）→ 修正
2. `_tera_stadium_cost_bonus`の呼び出しが`base_damage <= 0`ガードの前にあり、非攻撃候補にも無駄な`card_table`参照が発生（実害なしだが整理の余地）→ ガードの後ろへ移動
3. テラスタル×スタジアム×ex無効化の複合ケース（Nighttime Mine下でオーガポンexが4エネルギーで140ダメージを通す）を検証する統合テストが欠落 → `test_ogerpon_ex_pierces_wall_with_4_energy_under_nighttime_mine`を追加

### Assessment

**Ready to merge:** Yes（Minor指摘3件は`7f20735`で対応済み、`uv run pytest -q`で541件全PASS確認済み）

**Reasoning:** 予定された3件の変更が設計どおりに実装され、クロスタスクの相互作用（コスト計算と無効化判定の直交性、自己無効化ガードの維持）も個別に検証済み。指摘はいずれもドキュメント精度・コードの整理・テストカバレッジ拡充という軽微なもので、マージを妨げる欠陥はなし。

## 未対応・次回持ち越し

- Full Metal Lab等、Nighttime Mine以外のスタジアム対応（今回スコープ外、ユーザー判断済み）
- エネルギー優先度の具体値（`+150`/`+30`）はヒューリスティックな叩き台。Kaggle再提出後の実戦ログで効果検証が必要
- オーガポンexが実際にSylveonの特性を貫通してダメージを与えられたか、Nighttime Mine下での誤算定が解消されたかは実バトルログでの確認が必要（次に該当デッキ・スタジアムと対戦した際に検証）
