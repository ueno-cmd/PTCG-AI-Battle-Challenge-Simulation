# ルカリオexデッキ 実戦バトルログ7本 解析サマリー

- 日付: 2026-07-17
- 分析対象: `data/battle_logs/86320270.json`ほか7本（Kaggle実際のランクマッチ、`Kagura_UT`名義）
- 確認したデッキ構成（7戦全て一致）: Riolu×4, Mega Lucario ex×3, Solrock×2, Lunatone×2,
  Cornerstone Mask Ogerpon ex×2, Hero's Cape×1 ＋トレーナーズ・エネルギー
  （2026-07-07「Crustle対策強化・オーガポンex優先ロジック導入」時点の構成と一致）
- 結果: **2勝5敗（29%）**
- 目的：前回の会話で浮上した「ルカリオに集中すべきか」の判断材料として、直近の実戦成績を
  ジャモライコ（ビリリダマ軸: 3勝7敗=30%）と同条件（実戦バトルログの生解析）で比較する

## 結論

**ルカリオexデッキの直近実戦勝率（29%）は、ビリリダマ軸ジャモライコ（30%）とほぼ同水準**でした。
7/13時点の記憶（LBスコア600〜877で安定、自滅パターンゼロ）から約1週間経ち、環境が変化した
可能性がある（[[project_ptcg_competition]]参照）。ただし内訳を見ると、負けパターンは
ジャモライコと共通する部分と異なる部分がある。

### 共通する弱点：Dragapult ex系・Alakazam系への苦戦

- Dragapult ex系との対戦は1勝1敗（`RMatsugen`戦は際どい引き分け級の勝利、`Moricha27`戦は
  9ターンで自分の攻撃わずか2回の完敗）
- Alakazam系（`Tian hao Qing Nano7ko`戦）は4攻撃までこぎつけプライズ4-5の接戦まで持ち込んだが、
  相手の大量ドロー戦術（最終手札25枚）に押し切られて敗北

### Crustle（イワパレス）対策は機能している

- `YAKIIMO3`戦（Crustle軸）は**勝利**。オーガポンexが機能し、相手の場を残り0体（Pokémon枯渇）
  まで追い込んでの勝利だった（プライズ枚数は1-2で相手の方が多いが、相手が場に出せる
  ポケモンが尽きて敗北したパターン）。2026-07-07に導入したCrustle対策が実戦で機能している
  ことを確認できた

### 新たに見えた敗因：Team Rocket系・Archaludon ex+Cinderace・ミラー戦

- `Kurokawa`戦（Team Rocket's Mewtwo ex/Articuno等）：22ターンの長期戦、プライズ2-3の接戦負け
- `Krizsó Gergely`戦（Archaludon ex + Cinderace）：9ターンでプライズ1-3、明確な力負け
- `Aevion-Labs`戦（Mega Lucario exミラー）：13ターンでプライズ1-4、ミラー戦負け

## 7戦の内訳一覧

| 相手 | 相手デッキ（Pokémon軸） | 結果 | 自分攻撃回数(ターン数) | ATTACH回数 | 備考 |
|---|---|---|---|---|---|
| RMatsugen | Dragapult ex/Mega Starmie ex | **勝** | 6(15T) | 11 | プライズ4-4の接戦を制す |
| Moricha27 | Dragapult ex | 負 | 2(9T) | 8 | 速攻に押し負け |
| YAKIIMO3 | Crustle | **勝** | 6(14T) | 14 | 相手ポケモン枯渇で勝利、Crustle対策機能 |
| Kurokawa | Team Rocket's Mewtwo ex等 | 負 | 5(22T) | 15 | 長期戦の接戦負け |
| Krizsó Gergely | Archaludon ex + Cinderace | 負 | 3(9T) | 8 | 明確な力負け |
| Tian hao Qing Nano7ko | Alakazam | 負 | 5(11T) | 7 | 大量ドローに押し切られる接戦負け |
| Aevion-Labs | Mega Lucario ex（ミラー） | 負 | 4(13T) | 9 | ミラー戦負け |

## ジャモライコ（ビリリダマ軸）との比較

|  | ルカリオex | ジャモライコ（ビリリダマ軸） |
|---|---|---|
| 実戦勝率（本サンプル） | 2勝5敗(29%) | 3勝7敗(30%) |
| Dragapult ex系 | 1勝1敗 | 0勝1敗 |
| Alakazam系 | 0勝1敗（接戦） | 2勝1敗 |
| Mega Lucario ex（自分がルカリオの場合はミラー） | 0勝1敗 | 0勝3敗 |
| Crustle系 | 1勝0敗（対策機能） | 対戦なし・未検証 |
| 自滅パターン（デッキアウト・進化事故等） | 確認されず | 確認されず |

## 未対応・次回持ち越し

1. 7戦はサンプルサイズが小さく、統計的にはジャモライコとの差（29% vs 30%）はほぼ誤差範囲。
   「ルカリオに集中すべきか」の判断には、もう少しサンプルを増やすか、実際のLBスコア推移
   （7/13時点600〜877から動いたか）を確認する方が確実
2. Team Rocket系・Archaludon ex+Cinderace・Mega Lucario exミラーへの対応要否は今回未判断
3. 「ルカリオは勝てるがLBポイント効率が低い」という2026-07-08の未解決の指摘は、
   依然として検証できていない
