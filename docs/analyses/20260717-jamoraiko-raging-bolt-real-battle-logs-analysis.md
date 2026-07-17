# ジャモライコ（旧・タケルライコex軸）実戦バトルログ10本 解析サマリー

- 日付: 2026-07-17
- 分析対象: `data/battle_logs/86395893.json`〜`86400935.json`（10本、Kaggle実際のランクマッチ、`Kagura_UT`名義）
- 確認事項: 10本すべて `jamoraiko_raging_bolt_agent`（旧・タケルライコex軸、コミット`33d493e`時点の
  main.py）による対戦だった（デッキ内にRaging Bolt ex(id=63)×2枚＋Iono's Voltorb(id=265)×1枚を確認して判定）。
  ビリリダマ軸（現行main、`jamoraiko_voltorb_agent`）のログはユーザーが別途取得予定で未着手
- 結果: **2勝8敗**
- 解析手法: `superpowers:systematic-debugging`スキルに沿い、生JSONの`LogType`（ATTACK/HP_CHANGE/ATTACH等）を
  [[project_battle_log_parser]]記載の技法（片方のplayerIndexのACTIVEステップの`logs`をそのまま連結）で
  再構築し、10戦全ての攻撃回数・エネルギー装填回数・最終盤面（山札枚数・プライズ取得数）を実測

## 結論（重要度順）

### ① Crustle（イワパレス）系の壁デッキへの構造的な相性負け（8敗中3敗）

- 対戦相手3戦（Psy Duck: Mega Kangaskhan ex+Crustle、svackle: 同型、loveispoison: Great Tusk+Crustle）が
  いずれもCrustleを採用したウォールデッキで、3戦とも敗北
- **実測で確認**：`loveispoison`戦（`86398583`）では、Raging Bolt exの攻撃が試合中7回発動したが、
  直後のHP_CHANGEログは**7回とも空（＝ダメージ0）**。同戦は最終的に山札0枚・プライズ0-0のまま敗北
- 一方、`svackle`戦（`86396954`）では非exのIono's Kilowattrelの攻撃で相手のCrustle自身に-70の
  HP_CHANGEが実測されており、**exポケモンの攻撃だけがCrustle対面で無効化される**ことを確認。
  これは[[project_ptcg_competition]]のルカリオexデッキ開発時に判明した「Crustleの特性は相手の
  『ポケモン【ex】』の技ダメージを無効化する」という既知の裁定と完全に一致する
- **現行（ビリリダマ軸）main.pyもBellibolt exをexアタッカーとして採用したまま**なので、
  同じ弱点をそのまま引き継いでいる可能性が高い。ルカリオexデッキが導入した
  「Ogerpon exの『相手のバトルポケモンにかかっている効果を計算しない』でCrustleを貫通する」
  パターンの適用要否は、ビリリダマ軸ログが揃ってから検討する

### ② 極端な攻撃停滞（8敗中3敗：らすはる戦・Psy Duck戦・natz戦）

- 13〜21ターンの試合で自分の攻撃がわずか1回のみ、というゲームが3戦
- `らすはる`戦（`86395893`、21ターン）で顕著：**自分のATTACH（エネルギー装填）が試合を通じて
  たった3回**（Iono's Voltorbに2回、Iono's Tadbulbに1回）。一方でハイパーボール2回・
  エネルギー転送2回・なかよしポフィン2回など、サーチ系トレーナーズは13回もプレイしており、
  「探しているのに場にエネルギーがほとんど乗らない」という不整合な挙動を確認
- 校正ノートブック（`jamoraiko_vs_iono_turn_log.json`、イオナミラー戦限定）で以前から疑われていた
  「MAIN判断でのATTACK提示率が低い」問題（[[project_ptcg_competition]]参照）が、
  実際の多様な対戦相手でも再現し、一部の試合ではさらに深刻（ほぼ攻撃機会自体が来ない）だと確認できた。
  根本原因（なぜATTACHがほぼ発生しないのか）は未特定・次回調査候補

### ③ デッキアウト負け（8敗中2敗：loveispoison戦・yasu.78戦）

- `loveispoison`戦：最終盤面で自分の山札0枚、プライズ0-0（①のCrustle無効化と複合）
- `yasu. 78`戦：最終盤面で自分の山札0枚、アクティブポケモン不在
- デッキアウト脆弱性は他デッキ（グリムスナールex・ルカリオex）でも過去に繰り返し発生している
  既知パターンで、ジャモライコでも実戦で確認された形

### ④ 素直な火力・展開速度負け（8敗中1敗：torusuke戦、Dragapult ex）

- 攻撃回数3対8で完全に押し負け。ベンチ展開の速いDragapult ex系の速攻に対して、
  自分側の展開・攻撃準備が追いついていない

### 参考：2勝の内容

| 相手 | 相手デッキ | 自分攻撃回数(ターン数) | 勝因 |
|---|---|---|---|
| KDelapeace | Mega Abomasnow ex + Kyogre | 2回(8T) | Bellibolt exの230ダメで速攻KO、壁もスピードも無い対面 |
| Unreal Drip | Blaziken ex + Dragapult ex + Fezandipiti ex | 11回(29T) | 長期戦をVoltorbのチェインボルト連打で粘り勝ち |

## 10戦の内訳一覧

| 相手 | 相手デッキ（Pokémon軸） | 結果 | 自分攻撃回数(ターン数) | 備考 |
|---|---|---|---|---|
| らすはる | Alakazam + Fezandipiti ex | 負 | 1(21T) | エネルギー装填3回のみ（②） |
| Psy Duck | Mega Kangaskhan ex + Crustle | 負 | 1(19T) | 壁（①） |
| svackle | Mega Kangaskhan ex + Crustle | 負 | 8(24T) | プライズ3-1で優勢も敗北（①） |
| KDelapeace | Mega Abomasnow ex + Kyogre | **勝** | 2(8T) | 速攻KO成功 |
| Xan Morice-Atkinson | Hop系ゴースト（Trevenant/Phantump） | 負 | 5(24T) | プライズ3-5で押し負け |
| loveispoison | Great Tusk + Crustle | 負 | 7(20T) | 壁＋デッキアウト（①③複合） |
| torusuke | Dragapult ex | 負 | 3(20T) | 素の火力・展開負け（④） |
| yasu. 78 | Dragapult ex + ゴースト | 負 | 7(16T) | デッキアウト（③） |
| natz | Mega Abomasnow ex + Kyogre | 負 | 1(13T) | 同型相手に前回は勝利（②、変動大） |
| Unreal Drip | Blaziken ex + Dragapult ex + Fezandipiti ex | **勝** | 11(29T) | 長期戦を粘り勝ち |

## 未対応・次回持ち越し

1. **最優先（ユーザー側作業待ち）**：ビリリダマ軸（`jamoraiko_voltorb_agent`）の同条件バトルログ10本を
   取得し、本レポートと同じ手法で比較解析する
2. Crustle対策の要否判断（ビリリダマ軸でもBellibolt exが無効化されるかログで確認してから着手するか判断）
3. 「②極端な攻撃停滞」の根本原因（なぜATTACHがほぼ発生しない試合があるのか）は未特定。
   手札のエネルギー保有状況・`energy_score`のスコアリング詳細まで踏み込んだ追加調査が必要
4. デッキアウト対策の強化要否（`_safe_draws`のロジックが実戦でどこまで機能しているか）
