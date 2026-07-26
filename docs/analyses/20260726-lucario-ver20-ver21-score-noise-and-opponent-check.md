# ルカリオexデッキ ver20/ver21（同一ロジック連続提出）のスコア乱高下 実測検証

- 日付: 2026-07-26
- 対象:
  - ver20（初回提出、9戦）: `88001243, 88001858, 88002474, 88003128, 88003756, 88004377, 88005023, 88005659, 88006302`
  - ver21（同一ロジックのまま再提出、20戦）: `88006834, 88007496, 88008113, 88008755, 88009378, 88009993, 88010598, 88011222, 88011839, 88012470, 88013095, 88013712, 88014351, 88014964, 88015580, 88016086, 88016202, 88016835, 88017467, 88018089`
  - いずれも`Kagura_UT`視点
- 目的: ユーザー報告「コード変更なしで再提出したところ、収束スコアが481.0→596に大きく変わった」という現象について、原因が対戦相手の質の違い（マッチメイキングの偏り）にあるのかを実測で検証する
- 手法: `src/etl/gold.py`の`find_player_index`/`extract_deck_list`/`classify_archetype`を直接呼び、各バトルログの勝敗と相手デッキのアーキタイプ（exポケモン構成）を抽出する軽量スクリプトで両バッチを集計

## 結論（先に要点）

- **勝率はほぼ同一**：ver20 4勝5敗(44.4%)、ver21 9勝11敗(45.0%)。一方で収束スコアはver20:481.0、ver21:596と100点以上の差
- **対戦相手の難易度に明確な偏りは確認できなかった**。両バッチとも同様の環境メタ（Mega Lucario exミラー、Fezandipiti ex系トゥールボックス、Dragapult ex、Mega Abomasnow ex等）に当たっており、既知のハードカウンター（Crustle壁）は両バッチとも0件で条件は互角だった
- → **「勝率がほぼ変わらないのにスコアが大きく動く」ことから、スコアの乱高下は対戦相手の質の差ではなく、レーティングシステム自体の計算特性（対戦相手のレート・勝敗の順序に依存する等）に起因するノイズである可能性が高い**。ロジックの良し悪しを判断する材料として、単発の提出のLBスコア推移を使うのは引き続きリスクがある
- **副次的な収穫**：29戦を通算した相手アーキタイプ別成績を見ると、**Dragapult ex系トゥールボックスに3戦3敗(0%)**という結果が出た。これは2026-07-20の別バッチ分析で判明していた既存バックログ課題「Dragapult ex系トゥールボックス対策」（当時1勝4敗=20%）と整合しており、今回のサンプルでも同じ弱点が再現している

## 1. バッチ別の内訳

### ver20（初回提出、9戦、4勝5敗）

| ログID | 相手プレイヤー | 結果 | 相手デッキ軸 |
|---|---|---|---|
| 88001243 | NSTS04 | 負 | Team Rocket's Mewtwo exx2 |
| 88001858 | Jihyekor02 | 勝 | Mega Lucario exx4（ミラー） |
| 88002474 | harlen | 負 | Archaludon exx4 |
| 88003128 | AlanXM | 負 | Mega Abomasnow exx4（34ステップの短期決着） |
| 88003756 | uenohara-s | 勝 | Teal Mask Ogerpon exx4 + Mega Venusaur exx2 + Meowth exx2 + Fezandipiti exx1 + Mega Meganium exx1 |
| 88004377 | Mikiya Takada | 勝 | Fezandipiti exx1 |
| 88005023 | Astandri K | 負 | **Dragapult exx2 + Fezandipiti exx1 + Meowth exx1** |
| 88005659 | Aditya Palit | 負 | Mega Lucario exx4（ミラー） |
| 88006302 | Josh Mcateer | 勝 | Mega Lucario exx4 + Cornerstone Mask Ogerpon exx2 + Okidogi exx2 |

### ver21（再提出・同一ロジック、20戦、9勝11敗）

| ログID | 相手プレイヤー | 結果 | 相手デッキ軸 |
|---|---|---|---|
| 88006834 | CarsonHu | 負 | Fezandipiti exx1 |
| 88007496 | luck is all you need | 勝 | Mega Lucario exx4（ミラー） |
| 88008113 | ぶれめか | 負 | Cornerstone Mask Ogerpon exx1 |
| 88008755 | kishingo | 勝 | Mismagius exx3 + Fezandipiti exx1 + Latias exx1 + Lillie's Clefairy exx1 |
| 88009378 | Camaro | 負 | Fezandipiti exx1 |
| 88009993 | DaifukuMochi | 勝 | (exなし) |
| 88010598 | Nidy | 勝 | Mega Abomasnow exx4（35ステップの短期決着） |
| 88011222 | Otsuka Naotsugu | 負 | Archaludon exx4 |
| 88011839 | nimous | 負 | (exなし) |
| 88012470 | ituhime | 負 | **Dragapult exx4 + Fezandipiti exx1 + Meowth exx1** |
| 88013095 | Rensei K | 勝 | Fezandipiti exx1 |
| 88013712 | ペンギン | 勝 | Marnie's Grimmsnarl exx3 |
| 88014351 | blibli.com | 負 | Mega Lucario exx4（ミラー） |
| 88014964 | yuuri | 勝 | Marnie's Grimmsnarl exx3 |
| 88015580 | Zammaar Shafqat Malhi | 勝 | (exなし) |
| 88016086 | theredbluepill | 負 | Mega Kangaskhan exx4（61ステップの短期決着） |
| 88016202 | sereinless | 勝 | (exなし) |
| 88016835 | Diogo Sena | 負 | **Dragapult exx4** |
| 88017467 | ichitaro3 | 負 | Cynthia's Garchomp exx3 |
| 88018089 | Keisuke_kaggle | 負 | Mega Lucario exx4（ミラー） |

## 2. 相手アーキタイプ別 通算成績（29戦）

| アーキタイプ | 出現数 | 勝 | 負 | 勝率 |
|---|---|---|---|---|
| Dragapult ex系（トゥールボックス含む） | 3 | 0 | 3 | **0%** |
| Mega Lucario exミラー | 6 | 3 | 3 | 50% |
| Archaludon exx4 | 2 | 0 | 2 | 0%（サンプル僅少） |
| Fezandipiti exx1（単独テック） | 4 | 2 | 2 | 50% |
| Mega Abomasnow exx4 | 2 | 1 | 1 | 50% |
| (exなし) | 4 | 3 | 1 | 75% |
| その他単発 | 8 | 4 | 4 | 50% |

Crustle壁（イワパレス、既知のハードカウンター）は両バッチとも0件で、条件は互角だった。

## 3. スコア乱高下についての判断

勝率がver20:44.4%、ver21:45.0%とほぼ同一であるにもかかわらず、収束スコアはver20:481.0、ver21:596と100点以上異なる。相手アーキタイプの分布にも明確な有利・不利の偏りは見られなかったため、**「対戦相手の質が違ったから」という説明は今回のデータでは支持されない**。

より可能性が高いのは、レーティングシステム自体の特性（対戦相手の現在のレートに応じて増減幅が変わる、勝敗が発生する順序によって収束軌道が変わる等）による、サンプル数（9〜20戦）レベルでは避けられない統計的なノイズという解釈である。今後、ロジック修正の効果を判定する際は、単発の提出のLBスコア推移だけでなく、これまで通り実バトルログの勝率・敗因パターンを主たる判断材料にする方針を継続する。

## 4. 次のアクション

Dragapult ex系トゥールボックスへの3戦3敗(0%)は、2026-07-20の別バッチ分析（1勝4敗=20%）で判明していた既存バックログ課題の再現であるため、今回の3敗（88005023, 88012470, 88016835）を`GameStateTracker`で深掘りし、具体的な敗因（盤面全体ダメカン分散への対応不足等）を特定する調査に進む（セッションは継続、次のタスクとして着手）。

Archaludon exx4への2戦2敗はサンプル数が少なすぎるため、現時点ではウォッチリスト行きとし断定しない。
