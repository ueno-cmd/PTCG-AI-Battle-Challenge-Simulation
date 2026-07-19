# ルカリオexデッキ ex無効化検知汎用化・スタジアム考慮・オーガポンex優先度連動 実装サマリー

- 日付: 2026-07-19
- 設計書: `docs/superpowers/specs/2026-07-19-lucario-ex-nullifier-stadium-ogerpon-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-19-lucario-ex-nullifier-stadium-ogerpon.md`
- ブランチ: `feature/lucario-ex-nullifier-stadium-ogerpon`

## 背景

`docs/analyses/20260719-lucario-rock-energy-20-games-analysis.md`（ロック闘エネルギー導入後20戦の分析）で、ユーザーがKaggleビジュアライザーの観戦から気づいた点を検証した結果、実バグ2件が確定した。

1. **ex無効化のCrustle専用ハードコード**：`_calc_attack_damage`の`defender_nullifies_ex_damage`判定がカードID345（Crustle）のみを固定で見ており、同一効果文を持つSylveon（330）を無効化対象として検知できていなかった。Sylveon戦（`86803900`）でメガルカリオexが0ダメージ攻撃を繰り返す一方、無効化を貫通できるオーガポンexにエネルギーが回らないまま敗北していた。
2. **`calc_attack_plan`のスタジアム未考慮**：スタジアム「Nighttime Mine」（ID1266、テラスタルポケモンの技コスト+1）下でも`calc_attack_plan`がスタジアム補正なしでオーガポンexの技コストを計算し、3エネルギーで確定KOと誤算定していた（`86804728` turn9）。この誤算定でフルHPのメガルカリオexを不要に退却させ、オーガポンexを無防備な状態でアクティブに出してしまい、2ターン後に落とされた。

さらに、壁デッキ対面（Crustle系・Sylveon系）でオーガポンexが展開したのに攻撃に踏み切れない不発パターンが複数試合で共通して見られると分析レポートで報告されており、これがバグ1（ex無効化への気づきの欠如）と直接関連していると判断した。ユーザーとの合意により、上記2件のバグ修正に加えて「相手アクティブがex無効化持ち」を軸にしたオーガポンexのエネルギー配分・SWITCH優先度の連動強化を一体で扱った。

## 変更内容

### Task 1: ex無効化検知の汎用化（コミット `6bff4d7`）

- `src/lucario_agent/main.py`に`Sylveon = 330`と`EX_DAMAGE_NULLIFIER_IDS = frozenset({Crustle, Sylveon})`を追加。データ調査の結果、Crustleと完全一致の効果文（相手のポケモンexの技ダメージ無効化）を持つカードはSylveonのみと確認済み（`data/EN_Card_Data.csv`）。Farigiraf ex・Milotic ex・Cornerstone Mask Ogerpon exは無効化対象の条件が異なるため対象外。
- `_calc_attack_damage`の判定を、防御側は`EX_DAMAGE_NULLIFIER_IDS`のメンバーシップ判定、攻撃側は`CardData.ex`/`.megaEx`による構造化フィールド判定に一般化。`Mega_Lucario_ex`固定ではなくなったため、将来デッキに別のexアタッカーが追加された場合も自動対応する。
- オーガポンexの「ぶちやぶる」（`attack_ignores_defender_effects`）による無効化貫通は従来通りID固定のまま維持。`attacker_is_ex`はOgerpon_ex自身にも真になるため、この貫通判定を先頭ガード条件に置くことでOgerpon_ex自身の攻撃が誤って無効化されることを防いでいる（設計時の自己レビューで発見）。

### Task 2: 相手アクティブのex無効化判定とオーガポンex優先度連動（コミット `65efe0b`）

- 新規ヘルパー`_op_active_nullifies_ex(op_state) -> bool`を追加し、相手アクティブが`EX_DAMAGE_NULLIFIER_IDS`のメンバーかどうかを1箇所で判定。相手のベンチにいる無効化持ちは対象外（今アクティブのポケモンのみが今ターンの攻撃対象になるため）。
- `energy_score`・`_score_attach_option`・`_score_card_option`・`_score_option`の各シグネチャに`op_active_nullifies_ex: bool = False`を追加し、`agent()`から1回計算した値を引き回す配線とした（すべてデフォルト値付きのため既存呼び出しは無変更で動作する）。
- スコアリング：
  - `energy_score`：相手が無効化持ちのとき、オーガポンexに`+150`（Riolu/Mega_Lucario_exの最大加点110を確実に上回る値として設定）。
  - `_score_card_option`のSWITCH/TO_ACTIVE分岐：相手が無効化持ちのとき、オーガポンexに`+30`（Mega_Lucario_exの最大加点20を上回る値として設定）。
- これにより、壁デッキ対面でエネルギー配分・アクティブ交代の両方でオーガポンexが優先されるようになり、報告されていた「展開したのに攻撃に踏み切れない不発パターン」への対策とした。

### Task 3: `calc_attack_plan`のスタジアム（Nighttime Mine）考慮（コミット `6fab96d`）

- `Nighttime_Mine = 1266`を追加し、新規ヘルパー`_tera_stadium_cost_bonus(pokemon_id, stadium_id) -> int`で、Nighttime Mine下かつ`CardData.tera`が真のポケモンにコスト+1を返す汎用判定を実装。オーガポンex専用ではなくテラスタルポケモン全般に対応する。
- `calc_attack_plan`のシグネチャに`stadium_id: int = 0`を追加し、各アタッカー候補の`energy_required`計算に`_tera_stadium_cost_bonus`を加算。`agent()`側は既に保持していた`stadium_id`を呼び出し箇所に渡すだけで配線が完了した。
- Nighttime Mine下ではオーガポンexの技コストが3→4エネルギーとなり、3エネルギー時点での確定KO誤算定が解消された。Mega_Lucario_ex・Solrock（非テラスタル）はコスト変化しないことを回帰テストで確認済み。

## テスト結果

`uv run pytest -q`でリポジトリ全体が全件PASS。

- 開始前（`feature/lucario-ex-nullifier-stadium-ogerpon`ブランチ分岐元`a1a42dd`時点）：523件
- 完了後（最終ブランチ全体レビューの指摘反映後、再確認）：**541件**（既存523件＋新規18件）

（最終ブランチ全体レビューで、開始前の件数が526件と誤記されていた点を指摘され修正。`git checkout a1a42dd -- .`で分岐元コミット時点のコードを再現し`uv run pytest -q`で523件PASSと直接確認済み。また、テラスタル×スタジアム×ex無効化の複合ケースを検証する統合テストが無い点も指摘され、`test_ogerpon_ex_pierces_wall_with_4_energy_under_nighttime_mine`を追加した）

## コミット範囲

`feature/lucario-ex-nullifier-stadium-ogerpon`ブランチ（分岐元: `a1a42dd`）の最初のコミットから最後のコミットまで：

```
6bff4d7 fix(lucario): ex無効化検知をCrustle専用ハードコードから静的レジストリへ一般化
65efe0b feat(lucario): 相手のex無効化持ち対面でオーガポンexへエネルギー・SWITCH優先度を連動
6fab96d fix(lucario): calc_attack_planにNighttime Mineのテラスタルコスト+1を考慮
```

（`git log --oneline a1a42dd..HEAD`で確認。3コミットとも各タスク末尾で全件PASSを確認してからコミットしている。）

## 最終ブランチ全体レビュー（Opusモデル）の対応

Critical/Important無し。「Ready to merge: With fixes（ドキュメントのみ）」との判定で、以下3件のMinor指摘に対応した。

- テスト件数の誤記（526→523への修正、上記「テスト結果」参照）
- `_tera_stadium_cost_bonus`の呼び出し位置を`if base_damage <= 0: continue`の後ろに移動（`src/lucario_agent/main.py`）。非攻撃候補（base_damage=0で捨てられるポケモン）への無駄な`card_table`参照を避けるための整理で、挙動に変化はない
- テラスタル×スタジアム×ex無効化の複合ケース（Nighttime Mine下でオーガポンexが4エネルギーで140ダメージを通す）を検証する統合テストを追加

いずれもcontrollerが直接対応し、`uv run pytest -q`で541件PASSを確認済み。

## 未対応・次回持ち越し

- **Full Metal Lab等、Nighttime Mine以外のスタジアム対応**：今回のスコープ外（設計時にユーザー判断済み）。次回別途検討する。
- **エネルギー優先度の具体値（`+150`/`+30`）の妥当性検証**：設計時点ではヒューリスティックな叩き台であり、絶対的な正解があるわけではない。実装時のテストでは「相手が無効化持ちのとき、オーガポンexが他候補より優先される」という相対的な順序のみを検証しており、具体値の妥当性はKaggle再提出後の実戦ログで効果検証が必要。
