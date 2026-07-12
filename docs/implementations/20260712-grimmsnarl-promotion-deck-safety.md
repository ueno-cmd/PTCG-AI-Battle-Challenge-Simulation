# 実装サマリー：グリムスナールex 立ち往生解消＋山札セーフティ

**実装日：** 2026-07-12
**関連設計書：** `docs/superpowers/specs/2026-07-12-grimmsnarl-promotion-deck-safety-design.md`
**関連計画書：** `docs/superpowers/plans/2026-07-12-grimmsnarl-promotion-deck-safety.md`
**作業ブランチ：** `feature/grimmsnarl-promotion-deck-safety`（Task 1冒頭で作成、HEAD=`7e4df4d`）

## 背景

855系バトルログ12件（85532486〜85541203、2勝10敗、全てルールベース版の対戦・デッキ一致確認済み・クラッシュなし）の敗因分析（`docs/analyses/20260712-battlecore-agents-scoring-analysis.md`の4判断レイヤーのチェックリストに基づく）で、以下4つの構造欠落を特定した。

1. **交代先選出がHP偏重で攻撃準備度を見ない**：「アクティブが攻撃不能なのにベンチに攻撃可能ポケモンがいる」立ち往生が負け10試合中7試合に関与。最悪例85534500ではエネ0のキチキギスexを壁にしたままベンチのオーロンゲにエネルギーを6枚積み続け、一度も前に出せず敗北。
2. **RETREATに昇格条件がない**：立ち往生134手番中、エンジンがRETREAT選択肢を提示していたのは63%のみ。残り37%はアクティブがエネ0でにげるコストを払えず選択肢自体が不存在。
3. **ボスの指令が攻撃不能ターンに浪費される**：負け6試合でT2〜T5にボスを使用。攻撃手段ゼロの時点で引きずり出してもダメージなし、代わりにドローサポートの権利を失い展開が遅延。
4. **山札セーフティの欠落**：85541203は山札0のデッキアウト負け（手札にRare Candy3枚死蔵）。

これら4つを1設計書・1実装サイクル（案A：攻撃準備度ヘルパー＋コスト表の新設、既存分岐への条件追加）で対策した。全修正は`FEATURE_FLAGS`（3キー）でON/OFFでき、全OFF時は現行挙動と完全一致することを回帰テストで保証している。

## 変更内容

サブエージェント駆動開発（TDD、タスクごとに実装＋回帰確認）で全5タスクを実施。

| コミット | 内容 |
|---|---|
| `3bef7a0` | 攻撃準備度ヘルパー（`ATTACK_COSTS`/`_is_attack_ready`/`_expected_damage`）と`FEATURE_FLAGS`、`FieldState`拡張フィールドの新設（基盤） |
| `db120b2` | 交代先選出（`_score_own_switch_target`）の攻撃準備度優先化、RETREATへの昇格条件追加（修正①②） |
| `e06e947` | ボスの指令（`_score_play`のBoss_Orders分岐）に攻撃可否ゲートを追加（修正③） |
| `6202d1e` | 山札セーフティ（`_safe_draws`/`_deck_consumption`、battlecore B方式）を新設（修正④） |
| `7e4df4d` | セルフ対戦A/B実験ノートブックのビルダー`scripts/build_grimmsnarl_feature_ab_notebook.py`を追加 |

### 1. 攻撃準備度ヘルパーの新設（`3bef7a0`）

`src/grimmsnarl_agent/main.py`にワザの必要エネルギー数表`ATTACK_COSTS`（Grimmsnarl_ex=2／Fezandipiti_ex=3／Marnie_Morpeko=3／Yveltal=1、いずれもEN_Card_Data.csvで実測確認済み）と、それを判定する`_is_attack_ready(pokemon)`、交代先の同点比較用`_expected_damage(pokemon)`を追加。`FieldState`に`my_active_ready`/`bench_ready_attacker`/`my_deck_count`/`my_prize_left`/`my_hand_count`の5フィールドを追加し、`_collect_field_state`で計算するようにした。

対応テスト：`TestAttackReadiness`（6件）、`TestExpectedDamage`（5件）、`TestFieldStateReadiness`（4件）。

### 2. 修正①② 交代先選出の攻撃準備度優先＋RETREAT昇格（`db120b2`）

`_score_own_switch_target`に「Crustle対面のモルペコ（現行維持）」の次点として「攻撃準備完了のアタッカー（12000+期待ダメージ）」の優先枠を新設。`OptionType.RETREAT`分岐に「アクティブが攻撃不能かつベンチに攻撃準備完了アタッカーがいる」場合の昇格条件（スコア3000）を追加。いずれも`FEATURE_FLAGS["attacker_promotion"]`でゲートし、Falseなら現行挙動に戻る。

対応テスト：`_score_own_switch_target`系5件（85534500再現テスト含む）、`agent()`レベルのRETREAT昇格テスト4件。

### 3. 修正③ ボスの指令の攻撃可否ゲート（`e06e947`）

`_score_play`のBoss_Orders分岐冒頭に「アクティブが攻撃準備完了でない場合は-1（温存）」のガード節を追加。KO確定判定（8800）やε探索（6000）より手前で弾くため、攻撃不能ターンの浪費を防ぐ。既存のボステスト6件（`TestScorePlay`4件・agent()レベル2件）は「アクティブ攻撃可能」を前提条件として更新。

対応テスト：新規4件（ゲート発動・ε探索側もゲート内・攻撃可能時は現行挙動維持・フラグOFF時の現行挙動維持）。

### 4. 修正④ 山札セーフティ（battlecore B方式）（`6202d1e`）

`_safe_draws(fs) = my_deck_count - my_prize_left - 1`（残りプライズ数を残りターン数の見積もりとして必須ドロー分を温存）を新設。山札を消費するカード（リーリエの決意／チェレン／Secret Box／ポケパッド等サーチ1枚系／Buddy-Buddy Poffin）ごとの消費量を`_deck_consumption`で定義し、`_score_play`冒頭で「消費量 > safe_draws なら-1」のゲートを追加。ナイトストレッチャー（トラッシュ回収）はゲート対象外。リーリエの決意は手札を山札に戻してから引く仕様のため、手札が多いときは消費0（むしろ回復）として扱う。

対応テスト：`TestDeckSafety`（10件、`_safe_draws`境界値・各ドロー札のゲート発動・リーリエの手札戻し計算・フラグOFF時の現行挙動維持を含む）。

### 5. セルフ対戦A/B実験ノートブックのビルダー（`7e4df4d`）

`scripts/build_grimmsnarl_calibration_notebook.py`をベースに`scripts/build_grimmsnarl_feature_ab_notebook.py`を新規作成。A=全フラグON vs B=全フラグOFFを1000試合（校正実験の教訓から±3pt精度を確保）、加えてノイズ基準としてA vs Aも1000試合実行し、結果を`feature_ab_results.json`に保存する構成。生成物`src/rl_experiments/grimmsnarl_feature_ab_experiment.ipynb`は`.gitignore`対象のためコミットしない（ビルダースクリプトのみコミット）。

### Task 5での計画誤記の発見・修正（実装者による）

計画書のAB_CODE内`make_flagged_agent`が呼び出す関数名が`grimmsnarl_agent`と誤記されていたが、`main.py`のエージェント関数の実際の名前は`agent`である。実装者がノートブック生成時の静的検証（AST構文チェック＋シンボル存在確認）でこの不一致を発見し、`agent`に修正して実装した。この修正はTask 5のレビューで承認済み（Critical/Important指摘なし）。

## テスト結果

### Task 6: 全体回帰テスト

```
$ uv run pytest -q
........................................................................ [ 21%]
........................................................................ [ 42%]
........................................................................ [ 63%]
........................................................................ [ 84%]
.....................................................                    [100%]
341 passed in 0.45s
```

- 開始時（`e0e1666`時点）のベースライン`303`件 ＋ 本計画の新規テスト`38`件（`tests/test_grimmsnarl_agent.py`が91件→129件に増加。計画書の「約30件」の範囲内）＝ `341`件、全件PASSで一致を確認。
- `test_grimmsnarl_agent.py`単体でも`129 passed`を確認。

### Task 6: 校正ノートブックの再生成

```
$ uv run python scripts/build_grimmsnarl_calibration_notebook.py
wrote src/rl_experiments/grimmsnarl_calibration_experiment.ipynb with 10 cells
```

静的検証（AST構文チェック＋`FEATURE_FLAGS`埋め込み確認）もエラーなく通過。既存の校正実験ノートブック（`TUNABLE_WEIGHTS`のセルフ対戦A/B用）は本計画で`main.py`にFEATURE_FLAGSと5フィールドの`FieldState`拡張が入ったため、埋め込みmain.py全文を最新化する目的で再生成した（生成物は`.gitignore`対象のため未コミット）。

## 設計書「リスクと備考」の確認結果

設計書に記載の確認事項：「Shadow Bulletコストを2エネと確定させたことで、既存のエネルギー配分ロジック（`TUNABLE_WEIGHTS`の`grimmsnarl_base`等）の『3エネ確保』前提と齟齬がないか実装時に確認する（挙動変更はスコープ外、確認のみ）」について、`src/grimmsnarl_agent/main.py`を確認した。

- `_score_attach`（344行目〜）の`Basic_D_Energy`分岐：`if energy_count < 2:`で`grimmsnarl_base`／`grimmsnarl_surplus_base`を切り替えており、コメントも「シャドーバレット（悪悪=2エネ）は追加投資しても威力が変わらないため、確保後はキチキギスex・モルペコへの配分を優先する」と2エネ前提で記述されている。
- 同分岐内の`grimmsnarl_ready_or_absent`ゲートも`fs.grimmsnarl_energy_count >= 2`と2エネ判定になっている。
- `TUNABLE_WEIGHTS`辞書（65〜68行目）のコメントも`grimmsnarl_base`＝「オーロンゲ2エネ未満の基礎点」、`grimmsnarl_surplus_base`＝「オーロンゲ2エネ確保後の基礎点」と一貫して2エネ前提。

以上より、**既存のエネルギー配分ロジックは元々2エネ前提で実装されており、Shadow Bullet=2エネの確定値と齟齬は無い**ことを確認した。「従来想定の3エネ」という記述は設計書冒頭の「敗因分析時点の誤った想定」を指しており、実装コード側（`_score_attach`含む）はすでに正しい2エネ前提だった。コード修正は行っていない。

## 未実施事項（次回持ち越し・ユーザー作業）

1. `src/rl_experiments/grimmsnarl_feature_ab_experiment.ipynb`をKaggleにアップロードして実行（想定約4分：1000試合×2系列×約92ms/試合＋環境構築）
2. `feature_ab_results.json`をダウンロードし`data/experiments/20260712_grimmsnarl_feature_ab.json`として保存
3. 判定基準：A(ON) vs B(OFF)の勝率が55%以上（+5pt以上、ノイズ±3ptの外）なら効果ありと判定
   - 効果あり → `src/sample_notebook/grimmsnarl_agent.ipynb`のセル0を現行main.py全文で差し替え→Kaggle再提出
   - 効果なし/悪化 → A vs Aのノイズ基準と比較して原因を切り分け、フラグ単位のA/B（1修正ずつON）で犯人を特定
4. 提出後、次の855系ログで「立ち往生手番数」「攻撃不能ターンのボス使用回数」「終局時山札残数」の3指標を再計測（計測スクリプトは本分析のscratchpad版を流用）
