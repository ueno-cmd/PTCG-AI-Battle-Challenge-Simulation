# ジャモライコ（新・ビリリダマ軸）実戦バトルログ10本 解析サマリー

- 日付: 2026-07-17
- 分析対象: `data/battle_logs/86396404.json` ほか10本（Kaggle実際のランクマッチ、`Kagura_UT`名義）
- 確認事項: 10本すべてデッキ内にIono's Voltorb(id=265)×3枚・Raging Bolt ex(id=63)×0枚を確認し、
  **ビリリダマ軸（`jamoraiko_voltorb_agent`、現行main）**と判定
- 結果: **3勝7敗**（[[project_ptcg_competition]]記載の旧ジャモライコ（タケルライコex軸）実戦10戦の
  2勝8敗より改善）
- 解析手法: `docs/analyses/20260717-jamoraiko-raging-bolt-real-battle-logs-analysis.md`と同一
  （[[project_battle_log_parser]]のLogType再構築技法）

## 結論（重要度順）

### ① Mega Lucario ex（Solrock/Hariyama系）に0勝3敗、実質詰み

- 対戦相手3戦（Javier Arturo Gutierrez Sanchez・RNA4219・Mai Kevin）が全てMega Lucario ex
  （Riolu/Makuhita/Hariyama/Solrock/Lunatone構成）で、3戦とも敗北。しかも全て6〜11ターンの
  短期決着、自分の攻撃回数はほぼ0（0回・0回・1回）
- `Javier Arturo`戦（`86397493`）の全ログを精査：Solrockが70〜130ダメの技を毎ターン撃ち、
  こちらが新しく場に出したポケモン（Wattrel→Wattrel→Bellibolt ex→Voltorb）を**エネルギーが
  攻撃圏内に届く前に順番に一撃で狩られ続ける**展開。極めつけはMega Lucario exの技が
  エネルギー2個だけ乗ったBellibolt exに**-540ダメ**を叩き込んでおり、こちらの攻撃準備が
  間に合う余地が構造的に無かった
- `RNA4219`戦（`86399098`）は開幕手札にたねポケモンが**Iono's Tadbulb 1匹のみ**（ズピカは
  デッキ内1枚制限）という事故が重なり、ベンチ0体のままMega Lucario ex側の高速コンボで
  実質1ターンで敗北。ロジックバグではなく確率的な初手事故とMega Lucario exの速度の複合
- **結論**：Mega Lucario ex系は「相手が攻撃圏内に届く前にこちらの攻撃圏内に届く」速度型
  デッキで、ジャモライコ（ビリリダマ軸）の2〜4エネルギー要求アタッカーは根本的に間に合わない
  相性。旧デッキでも指摘されていた「超高速デッキとの相性問題」（[[project_ptcg_competition]]
  2026-07-02メモ参照）がビリリダマ軸でも解消されずそのまま残っている

### ② Dragapult ex系にも滑り出しで負けるケースあり

- `Hiroki Maruo`戦（`86396944`）：6ターンで敗北、自分の攻撃0回、ATTACH（エネルギー装填）も
  1回のみ。Dragapult exの立ち上がりの速さに対して初動が遅れている

### ③ Alakazam・中速デッキには通用（2勝1敗）

- `Optimal Prime`戦・`Danilo Antonietto`戦は共にAlakazam系（Abra/Kadabra/Alakazam）に勝利。
  `Optimal Prime`戦は相手の山札が0枚になっての決着（相手が大量ドロー戦術で自滅）
- 一方`sk1012`戦（同じくAlakazam系）は敗北。ATTACH回数がわずか2回に留まり、①②と同種の
  「滑り出しの遅さ」がこの試合単体では出た形

### ④ エネルギー供給さえ回れば強い（onionring26戦の完封勝利で裏付け）

- `onionring26`戦（Ogerpon ex/Arboliva ex系）はATTACH13回と非常に円滑にエネルギーが
  循環し、11ターンで**相手の攻撃を1回も許さず完封勝利**。①〜②の敗因が「デッキの地力不足」
  ではなく「立ち上がり速度」由来であることの裏返しの証拠になる

### ⑤ Crustle系との対戦は今回0戦・未検証

- 旧デッキ解析で判明した「exアタッカー（Bellibolt ex等）がCrustleの特性で0ダメージ化される」
  問題は、今回の10戦にCrustle採用デッキが含まれていなかったため再現確認できていない

## 10戦の内訳一覧

| 相手 | 相手デッキ（Pokémon軸） | 結果 | 自分攻撃回数(ターン数) | ATTACH回数 | 備考 |
|---|---|---|---|---|---|
| monnosuke | Steven's Metagross ex/Empoleon ex/Genesect ex/Latias ex | 負 | 5(19T) | 17 | プライズ4-5僅差負け、地力負け |
| Hiroki Maruo | Dragapult ex | 負 | 0(6T) | 1 | 滑り出し負け（②） |
| Javier Arturo Gutierrez Sanchez | Mega Lucario ex | 負 | 0(11T) | 4 | 速度負け（①、詳細解析済み） |
| Optimal Prime | Alakazam | **勝** | 6(19T) | 5 | 相手デッキアウトで勝利 |
| onionring26 | Ogerpon ex/Arboliva ex | **勝** | 5(11T) | 13 | 完封勝利（④） |
| RNA4219 | Mega Lucario ex | 負 | 0(1T相当) | 1 | 初手事故＋速度負け（①、詳細解析済み） |
| Danilo Antonietto | Alakazam | **勝** | 8(18T) | 12 | プライズ5-2で快勝 |
| Mai Kevin | Mega Lucario ex | 負 | 1(6T) | 3 | 速度負け（①） |
| sk1012 | Alakazam | 負 | 0(11T) | 2 | 滑り出し負け |
| Konno Ryoya | Mega Starmie ex/Mega Froslass ex | 負 | 0(6T) | 2 | 滑り出し負け |

## 旧デッキ（タケルライコex軸）との比較

|  | 旧（タケルライコex軸） | 新（ビリリダマ軸） |
|---|---|---|
| 実戦勝率 | 2勝8敗(20%) | 3勝7敗(30%) |
| Crustle系ウォールへの弱点 | 実測確認済み（0ダメ×7回） | 対戦なし・未検証 |
| 低攻撃回数の敗北 | 8敗中3敗 | 7敗中6敗（さらに顕著） |
| デッキアウト負け | 8敗中2敗 | 0敗（今回は出現せず） |
| 新たに見えた弱点 | - | Mega Lucario ex系に0勝3敗（構造的な速度負け） |

## 追加検証：Mega Lucario ex連敗は「ロジックバグ」か「構造的な速度不足」か

ユーザーからの要望で、`superpowers:systematic-debugging`のPhase1〜2に沿い
`src/jamoraiko_agent/main.py`のスコアリング/ディスパッチ全体を精査した。

- **発見①（未実装のまま放置）**：`_score_option`の`OptionType.RETREAT`分岐が常に`-1`固定
  （578-579行目）。ENDのデフォルトスコア0を下回るため、**自主的な撤退が数式上絶対に選ばれない**。
  グリムスナールex/ルカリオexデッキには意味のある撤退ロジックがあるが、ジャモライコだけ未実装
  のまま。ただし`Javier Arturo`戦（Mega Lucario ex負け）を1ステップずつ追跡した結果、
  ハラバリーexは撃墜されるまで一度もダメージを受けておらず（280/280のまま推移）、
  **この試合の敗因には直接寄与していない**ことを確認。修正候補ではあるが今回の連敗の主犯ではない
- **発見②（正常動作を確認）**：ハラバリーexの特性「エレキストリーマー」（自分の番に手札の
  基本雷エネルギーを何枚でも付けられる）が正しく複数回発動することを実測で確認。
  `onionring26`戦（完封勝利）では**1ターンに7回のエネルギー装填**を記録（通常の手張り1枚/ターン
  制限を超える＝特性が複数回発動している証拠）。一方`Javier Arturo`戦では各ターン1回のみで、
  特性がほぼ発動していない。**これは実装の不具合ではなく、手札に雷エネルギーが十分無かった
  （引き運）ことが原因**と判断
- **結論**：Mega Lucario ex/ドラパルドex系との連敗は、スコアリングロジックの欠陥ではなく、
  「ハラバリーex(4エネ技)が手張り1枚/ターン＋特性頼みで立ち上がりに数ターンかかり、
  それを補う低コストアタッカーがビリリダマ(2エネ技)以外に存在しない」という**デッキ構成・
  速度面の構造的な限界**が実測で裏付けられた。ロジックをどれだけ磨いても、この種の超高速
  デッキには一定数間に合わない試合が残ると考えられる
- イワパレス（Crustle）・超フーディンとの実対戦例は前回・今回とも0件のため、実測での
  確認はまだできていない

## 未対応・次回持ち越し

1. Mega Lucario ex対策の要否判断（旧ルカリオexデッキが導入した「Ogerpon ex的な壁貫通」とは
   逆に、こちらは**速度不足**が問題のため対策の方向性が異なる。エネルギー要求を抑えた
   低コスト先制アタッカーの追加や、たねポケモン事故率を下げるための1枚制限カード
   （Iono's Tadbulb, Iono's Wattrel）の増量が候補になりうるが、今回はスコープ外）
2. Crustle系との対戦がまだ無いため、Bellibolt exの無効化問題がビリリダマ軸でも起きるかは
   次に対戦ログが取れてから確認する
3. 「低攻撃回数での敗北」が新デッキでさらに悪化（7敗中6敗）している点の根本原因を、
   旧デッキ解析で見えた「ATTACHがほぼ発生しない」パターンと合わせて追加調査するか判断
