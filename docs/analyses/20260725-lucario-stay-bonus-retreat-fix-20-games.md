# ルカリオexデッキ 居座りボーナス修正＋RETREAT HP温存分岐 実測検証（修正後最初の20戦）

- 日付: 2026-07-25
- 対象: commit範囲`1056801..9c0c712`（`docs/implementations/20260720-lucario-stay-bonus-retreat-hp-preservation.md`参照）を含むKaggle再提出後、最初に貯まった20戦
  - `87089365, 87089926, 87090468, 87091030, 87091575, 87092118, 87092666, 87093243, 87093816, 87094354, 87094904, 87095432, 87095978, 87096538, 87097076, 87097649, 87098195, 87098735, 87099293, 87099843`（`Kagura_UT`視点、2026-07-21 10:37〜11:13取得）
- 目的: 2026-07-20の分析（`docs/analyses/20260720-lucario-ex-nullifier-fix-verification-20-games.md`）で確定した「居座りボーナスバグ」（`calc_attack_plan`の位置ボーナスが実ダメージ無関係に加算され、0ダメージ確定プランがRETREATより優先されてしまう）の修正、および新設した「RETREAT HP温存分岐」（`_score_retreat_option`、実質ノーダメージ×アクティブがex/megaExなら温存退却）が、修正後初の実戦ログで意図通り機能しているかを検証する
- 手法: 2本のバックグラウンドAgentに「①マクロ集計（勝敗・対戦相手デッキ内訳）」「②`GameStateTracker`によるイベント再生＋生ログ直接精査での修正1/2の効果検証」を分担させ、controller（本セッション）がAgent①の分類結果をユーザー指摘を受けて裏取り・訂正した

## 結論（先に要点）

- **20戦合計：10勝10敗（50%）**。前回検証（2026-07-20時点、修正前）と同率で、勝率の絶対水準に大きな変化はない
- **居座りボーナス修正（修正1）の再発は確認されなかった**。ただし本来の検証対象であるCrustle/Sylveon（`EX_DAMAGE_NULLIFIER_IDS`）との対戦は20戦中2戦のみで、その2戦も「RETREATの選択肢自体が提示されていなかった（エネルギー不足で物理的に逃げられない）」状況であり、修正1が効いたことの直接証拠にはならない。**「悪化していない」ことは分かったが、「狙った状況で正しく機能する」ことの強い裏付けは今回のサンプルからは得られなかった**
- **RETREAT HP温存分岐（修正2）の発火が確証できる事例は見つからなかった**。唯一の候補事例は、Crustle/Sylveonとは別の未対応の無効化要因（ACE SPECスタジアム「Neutralization Zone」、ID1247）によるものと判明し、修正2の対象外だった
- **【副産物・新規発見】`_calc_attack_damage()`が`EX_DAMAGE_NULLIFIER_IDS`（Crustle/Sylveonの特性）しかモデル化しておらず、スタジアムカード「Neutralization Zone」由来の同種の無効化を検知できない**。実戦で1戦・5ターン連続の無意味な0ダメージ攻撃が発生した
- **【マクロ集計の訂正】** Agent①は対戦相手デッキを「exポケモンの内訳」だけで簡易分類したため、非exが主軸のAlakazamデッキ4戦が「Fezandipiti ex軸」に誤分類されていた（ユーザー指摘で発覚・裏取り済み）。訂正後、**Alakazam系の実際の対戦成績は6戦中1勝5敗（17%）**で、2026-07-18深掘り分析で既知だった弱点が今回高頻度（30%）で再出現していたことが判明

## 1. 20戦の内訳（訂正済み）

| ログID | 自分index | 相手プレイヤー名 | 相手デッキ軸(実際のアーキタイプ) | 結果 |
|---|---|---|---|---|
| 87089365 | 1 | atuage70 | Ethan's Typhlosion（炎非ex軸、Fezandipiti exはテック1枚） | 勝 |
| 87089926 | 0 | rurumi | **Alakazam**（非ex軸、Fezandipiti exテック1枚） | 負 |
| 87090468 | 1 | Eric Wu | **Alakazam**（非ex軸） | 負 |
| 87091030 | 0 | naoki | Team Rocket's Mewtwo exx2 + Lillie's Clefairy exx1 | 勝 |
| 87091575 | 0 | Taishoh | **Alakazam**（非ex軸、Fezandipiti exテック1枚） | 負 |
| 87092118 | 1 | Masaya_SAN | **Alakazam**（非ex軸、Fezandipiti exテック1枚） | 負 |
| 87092666 | 0 | terassyi | Alakazam系（exなし） | 負 |
| 87093243 | 0 | abidencewww | Dragapult exx3 + Fezandipiti exx1 + Latias exx1 + Meowth exx1 | 負 |
| 87093816 | 1 | Tomoya Otani | Okidogi exx4 + Pecharunt exx2 + Bloodmoon Ursaluna exx1 + Fezandipiti exx1 + Munkidori exx1 | 勝 |
| 87094354 | 0 | Sébastien henry | Crustle壁（ex無効化持ち） | 負 |
| 87094904 | 1 | YYma1201 | Alakazam系（exなし） | 勝 |
| 87095432 | 0 | Felipe Sens Bonetto | Comfey/Shaymin/Yveltal系（Neutralization Zone採用） | 負 |
| 87095978 | 0 | pickles0923 | Dragapult exx3 | 勝 |
| 87096538 | 0 | ノノノノノノノノ | Marnie's Grimmsnarl exx2 + Mega Gengar exx2 + Cornerstone Mask Ogerpon exx1 + Fezandipiti exx1 | 勝 |
| 87097076 | 0 | YoshiBrightside | Applin/Dipplin系（exなし） | 勝 |
| 87097649 | 1 | naoto714 | Mega Kangaskhan exx4 | 負 |
| 87098195 | 0 | takemurahironori | Mega Kangaskhan exx4（相手はCrustleも展開） | 勝 |
| 87098735 | 0 | Akhil Kumar060 | Mega Abomasnow exx4 | 負 |
| 87099293 | 1 | 600505-ศิวกร | Mega Lucario exx4 + Koraidon exx3 | 勝 |
| 87099843 | 0 | ShoKSE | Xerneas exx4 | 勝 |

合計10勝10敗（50%）。

## 2. 相手デッキ軸別 出現回数・勝敗（訂正版）

| デッキ軸 | 出現数 | 勝 | 負 | 勝率 |
|---|---|---|---|---|
| **Alakazam系（非ex軸）** | **6** | **1** | **5** | **17%** |
| Dragapult ex系 | 2 | 1 | 1 | 50% |
| Mega Kangaskhan ex | 2 | 1 | 1 | 50% |
| Crustle壁（ex無効化持ち、単独） | 1 | 0 | 1 | 0% |
| Mega Lucario exミラー（+Koraidon ex） | 1 | 1 | 0 | 100% |
| Mega Abomasnow ex | 1 | 0 | 1 | 0% |
| その他単発（Typhlosion/Mewtwo ex/Okidogi box/Grimmsnarl box/Applin/Xerneas等） | 7 | 6 | 1 | 86% |

**Alakazam系が20戦中6戦(30%)と最頻出で、かつ1勝5敗(17%)と大きく負け越している**のが今回のバッチの最大の特徴。2026-07-18の深掘り分析で既知の弱点だったが、出現率・敗率ともに悪化して再出現した形。

3つの既知の要注意アーキタイプの推移：

| | 前回20戦(0720時点) | 今回20戦 |
|---|---|---|
| Mega Lucario exミラー | 5/20(25%)・4勝1敗(80%) | 1/20(5%)・1勝0敗(100%) |
| Crustle壁 | 4/20(20%)・0勝4敗(0%) | 1/20(5%)・0勝1敗(0%) |
| Dragapult ex系 | 1/20(5%)・0勝1敗(0%) | 2/20(10%)・1勝1敗(50%) |
| Alakazam系 | （前回レポート未集計） | 6/20(30%)・1勝5敗(17%) |

## 3. 修正1（居座りボーナス）の実測検証

自動検出で「同一アクティブがdamage≤0の攻撃を2回以上連続、間にRETREATなし」のパターンが2件ヒットした（87094354, 87098195、いずれもCrustle系相手）。生データ（`observation.current.players[].active[].energies`）を精査した結果、**両試合ともMega Lucario exの装着エネルギーが1個のみ（にげるコスト2に対して不足）で、RETREATの選択肢自体がそもそも提示されていなかった**（`main.py`の`_analyze_main_options()`はゲームエンジンがRETREATを選択肢として出した場合のみ`can_switch=True`にする仕組み）。

→ **旧バグ（スコアリングが原因で交代を選ばない）の再発は確認されなかった。** ただし「RETREATが実際に選択可能だったのにCrustle戦で居座った」という、修正の主目的そのものずばりのケースは今回のサンプルには含まれておらず、修正1の効果を強く裏付ける事例は得られていない。

## 4. 修正2（RETREAT HP温存分岐）の実測検証

自動検出で87095432（vs Comfey/Shaymin/Yveltal系）に5件ヒットしたが、精査の結果、この試合の相手アクティブはCrustle/Sylveon（`EX_DAMAGE_NULLIFIER_IDS`）ではなくComfeyで、代わりに**ACE SPECスタジアム「Neutralization Zone」（ID1247、ルールボックスを持たないポケモンへの相手ex/V技ダメージを無効化）が展開されていた**ことが判明。`_calc_attack_damage()`はこの無効化パターンを一切モデル化していないため、`current_plan.damage`は誤って正の値を計算していたと考えられ、`_score_retreat_option()`の修正2分岐（`damage<=0`条件）はそもそも発火していなかった可能性が高い。観測された5回の交代往復は、別の既存分岐（`current_plan.attacker >= 1`＝より良いアタッカーへの切替）経由と推測されるが、切替先も同じくexのMega Lucario exでNeutralization Zone下では同様に無意味だった。

→ **修正2が意図通り発火したと確証できる事例はゼロ件。** ただし「発火しなかった＝壊れている」わけではなく、今回のバッチにはそもそも修正2の対象となる状況（Crustle/Sylveon×自分の攻撃が実質ノーダメージ×RETREAT可能）が含まれていなかった、というのが実態に近い。

### 4-1. 副産物：Neutralization Zoneスタジアムの無効化が未対応

`_calc_attack_damage()`（`combat.py` 85-117行目）は弱点・抵抗力・`EX_DAMAGE_NULLIFIER_IDS`（Crustle/Sylveonの特性）のみを考慮しており、**スタジアムカード由来のダメージ無効化（Neutralization Zone等）は一切考慮していない**。試合87095432では、この無効化に気づかないままMega Lucario exがComfeyに5ターン連続で0ダメージ攻撃を続けた。なお控えにはSolrock/Lunatoneが展開済みで、Solrock（非ex、Neutralization Zoneの無効化対象外）へ切り替えれば実ダメージを狙えた可能性があるが、実際には選ばれなかった（この選択ロジックの深掘りは今回のタスク範囲外、次回以降の検討候補）。

## 5. 次回セッションへの申し送り

1. **Alakazam対策の優先度引き上げを検討**：今回30%出現・17%勝率と、既知の弱点が悪化して再出現。2026-07-18深掘り分析の内容を再確認した上で対応要否をユーザーと相談する
2. **修正1・修正2の効果は「悪化なし」までしか言えていない**。狙った状況（Crustle/Sylveon戦でRETREAT可能、または実質ノーダメージ×ex/megaEx）を含むログがもう少し貯まってから再検証するのが望ましい
3. **新規発見：Neutralization Zoneスタジアムのダメージ無効化が未対応**。`EX_DAMAGE_NULLIFIER_IDS`と同様の枠組みで対応するか検討（優先度・対応要否は未判断）
4. **マクロ分類ロジックの限界**：`classify_archetype()`はexポケモンの内訳のみで分類するため、非ex主軸デッキ（Alakazam等）にex1枚がテック採用されていると誤分類される。今後同様の集計をする際は、上位カード（ポケモン全体）も見て裏取りする一手間が必要
