# ルカリオexデッキ 戦闘意思決定ロジック（energy_score/calc_attack_plan/RETREAT）徹底監査

- 日付: 2026-07-20
- 経緯: `docs/analyses/20260720-lucario-ex-nullifier-fix-verification-20-games.md`のフォローアップとして、「居座りボーナス」修正の設計（`docs/superpowers/specs/2026-07-20-lucario-combat-split-stay-bonus-fix-design.md`）を進める中で、controller自身の再計算により当初の仮説（`calc_attack_plan`の位置ボーナス+220/+300がバグの主因）が実は誤りだった可能性が浮上した。ユーザーの指示で一旦立ち止まり、4本のバックグラウンドAgentによる徹底監査を実施した
- 対象コード: `src/lucario_agent/main.py`の`energy_score`（154-181行）・`calc_attack_plan`（274-401行）・`pokemon_score`（135-151行）・`_score_card_option`（405-490行）・`_score_attach_option`（684-707行）・`_score_option`のRETREAT/ATTACKケース（752-760行）
- 手法: 4本の独立したバックグラウンドAgentが、それぞれ異なる角度から監査：
  1. `energy_score`の全分岐を全パターン試算し、呼び出し元も含めて非対称性を洗い出す
  2. `calc_attack_plan`のスコア式（居座りボーナス含む）を実カードデータ・実バトルログで再検証する
  3. RETREATスコア式自体の妥当性と、`plan`（グローバル変数）の鮮度問題を実ログで裏取りする
  4. 「エネルギーがソルロック/オーガポンexに届かない」パターンが他のCrustle敗戦ログでも再現するかクロスチェックする

## 結論（先に要点）

- **当初の「居座りボーナス」修正（`calc_attack_plan`のi==0/j==0ボーナスをdamage>0でゲートする案）はYAGNIで撤回する。** `pokemon_score`のプライズ枚数×1000という下駄が大きすぎるため、位置ボーナス（最大520点）が実際の決定を左右する場面は、数式的な境界条件の導出でも実バトルログ3戦の再現検証でも確認できなかった
- **真因は`energy_score`側の2つの実バグだった**。実ログ86898758のturn3・turn11を実コードで再現し、「メガルカリオex8051点 vs ソルロック8020点」「リオル8100点 vs ソルロック8020点」でルカリオ側が勝ち続けていたことを直接確認した。他3件のCrustle敗戦ログのうち2件でも同じパターンを確認済み
- 加えて、当初の調査対象ではなかった**RETREATスコア式のHP温存欠如**という新規の実害も見つかった
- 全体として、「main.pyが分割されておらずコンテキストが溢れて見逃されていた」というユーザーの仮説を裏付ける形で、当初の1点の仮説から芋づる式に複数の独立したバグが見つかった

## 確定・実害あり（優先度：高）

### 1. `_score_card_option`のATTACH_FROMケースが`op_active_nullifies_ex`を渡し忘れている

**箇所**: main.py:486-487

```python
case SelectContext.ATTACH_FROM:
    return energy_score(card, o.area == AreaType.ACTIVE, attacker1)  # op_active_nullifies_exが欠落
```

`_score_card_option`関数自体は`op_active_nullifies_ex`を引数として正しく受け取っているにもかかわらず、この分岐だけ`energy_score`への転送を忘れている。もう一つの呼び出し元`_score_attach_option`（696行）は正しく転送している。

**実際の用途と影響範囲**: `SelectContext.ATTACH_FROM`は、メガルカリオexの通常技「アクセルジャブ（Aura Jab）」自身のテキスト「捨て札から基本闘エネルギーを最大3枚、好きなように自分のベンチポケモンにつける」に対応する選択コンテキストで、**メガルカリオexが攻撃するほぼ毎ターン使われる主要チャネル**（`calc_attack_plan`でa==0の主力技として明示的に優先されており、`base_score += 60 * min(3, discard_counts[Basic_Fighting_Energy])`という大きなボーナスも付いている）。手札からの1ターン1回の通常装着より頻度・影響量ともに大きい。

**テストカバレッジ**: `tests/test_lucario_agent.py`に`SelectContext.ATTACH_FROM`を明示的にカバーするテストは0件。

**実測での影響**: Agent3が実ログ86898758のturn3(step33)・turn11(step64)で、このコンテキストの実際のスコアリングを実コードで再現した結果、メガルカリオex/リオルがソルロックより高スコアで実際に選ばれ続けていたことを確認（下記2と複合）。

**修正案**:
```python
case SelectContext.ATTACH_FROM:
    return energy_score(card, o.area == AreaType.ACTIVE, attacker1, op_active_nullifies_ex)
```

### 2. `energy_score`のMega_Lucario_ex/Riolu分岐に、相手がex無効化持ちのときの減点が一切ない

**箇所**: main.py:167-173

```python
elif pokemon.id in (Riolu, Mega_Lucario_ex):
    if pokemon.id == Mega_Lucario_ex:
        score += 1
    if energy_count < 2:
        score += 100
    if attacker1:
        score -= 50
    # op_active_nullifies_ex を一切見ていない
```

Ogerpon_exの分岐には「相手がex無効化持ちなら優先」の`+150`ボーナスがあるが、対になる減点がMega_Lucario_ex/Riolu側に存在しない。試算：ベンチのMega_Lucario_ex（`energy_count<2`）は`8000+1+100=8101`、ソルロック（`energy_count<1`）は`8000+20=8020`。`op_active_nullifies_ex=True`でも`8101>8020`のままのため、Crustle対面でも（2体目以降を含む）Mega Lucario exへのエネルギー投資が止まらない。

Riolu自身は`calc_attack_plan`のアタッカー候補に含まれておらず（Mega Lucario exへの進化前段階としてのみ存在）、Rioluへのエネルギー投資もいずれ同じ無効化を受けるMega Lucario exを育てることに繋がるため、同じ減点をRiolu/Mega_Lucario_ex共通の分岐に適用するのが妥当。

**実測での確認**: Agent4が別の2試合（86899338, 86905948）で、「ルナトーンは常在しソルロックの発動条件は満たされているのに、ソルロックが終始0エネルギーのまま放置され、2体目以降のMega_Lucario_exに計3エネルギーが流れ続けた」ことを確認。3戦中2戦で明確に再現。

**修正案**:
```python
elif pokemon.id in (Riolu, Mega_Lucario_ex):
    if pokemon.id == Mega_Lucario_ex:
        score += 1
    if energy_count < 2:
        score += 100
    if attacker1:
        score -= 50
    if op_active_nullifies_ex:
        score -= 150  # 相手がex無効化持ちならOgerpon_ex/Solrockへ道を譲る
```

## 確定だが発生条件が狭い（優先度：中）

### 3. `_score_attach_option`のRock_Fighting_Energyへの「アクティブ優先+500」が無条件加算される

**箇所**: main.py:697-700

```python
if card.id == Rock_Fighting_Energy and o.inPlayArea == AreaType.ACTIVE:
    # Alakazam「ハンドパワー」はアクティブのポケモンのみを狙うため、
    # そのときアクティブの子を優先的に守る
    score += 500
```

Alakazam「ハンドパワー」対策として書かれたこのボーナスは、対戦相手やアクティブポケモンの種族を一切見ずに無条件加算される。試算：アクティブのMega Lucario ex（ec=0, nullify=True想定でも本来のnullifyボーナスはOgerpon_ex側にしか無いためLucario自身のスコアには影響しない）は`8000+10+1+100+500=8611`、ベンチのOgerpon_ex（ec=0, nullify=True）は`8000+80+150=8230`。Lucarioが381点差で勝ち、Crustle/Sylveon戦で「攻撃してもダメージが通らないex」に、まさにその無効化を貫通できるOgerpon_exを差し置いてエネルギーが装着され続ける。

発生には複数条件の重なりが必要（アクティブがex・相手がCrustle/Sylveon・ベンチにOgerpon_exがいる・手札にRock_Fighting_Energyがある）ため優先度は中程度。

**修正案（要判断）**:
```python
if card.id == Rock_Fighting_Energy and o.inPlayArea == AreaType.ACTIVE:
    attacker_is_ex = card_table[pokemon.id].ex or card_table[pokemon.id].megaEx
    if not (op_active_nullifies_ex and attacker_is_ex):
        score += 500
```

## 新規発見・実害確認済みだが設計課題（優先度：要相談）

### 4. RETREATのスコア式にHP温存の観点が一切ない

**箇所**: main.py:752-753

```python
case OptionType.RETREAT:
    return 2000 if current_plan.attacker >= 1 else -1
```

「攻撃可能な控えがいるかどうか」だけを退却の判断材料にしており、「今のアクティブが瀕死級で、控えが攻撃できなくても退避させる価値がある」というHP温存の観点が式に組み込まれていない。

**実測での確認**: Agent3が実ログ86898758のturn7(step45-52)で、HP100/340（3割未満）まで削られたMega Lucario exが、控え（ソルロック等）が全て攻撃候補になれない状況（上記1・2のバグにより0エネルギーのまま）でRETREATが一貫して-1点になり続け、退却されないままopponentのturn8で撃破され、相手に3プライズを献上（相手残りプライズ6→3）したことを直接確認した。

この問題は1・2のバグが解消されれば発生頻度は下がると見込まれるが（控えに攻撃可能な駒がいればそもそも`current_plan.attacker>=1`になりRETREATが機能する）、「攻撃できる控えが本当に一体もいない」局面では1・2を直しても解消しない、独立した設計上の穴である。修正には「HPが閾値を下回っている」「攻撃候補が一体もいない」等の新しい条件をRETREATスコアに組み込む設計判断が必要で、単純な1行修正では済まない。

## ついでに見つかった別軸の潜在バグ（優先度：低・Crustleとは無関係）

### 5. ソルロックの「弱点・抵抗力の影響を受けない」効果が`_calc_attack_damage`に未実装

**箇所**: main.py:255

```python
attack_ignores_defender_effects = attacker_id == Ogerpon_ex  # ぶちやぶる：相手にかかっている効果を計算しない
```

カードテキスト上、ソルロックの技「コズミックビーム」も「このワザのダメージは、弱点や抵抗力の影響を受けない」効果を持つが、この判定はOgerpon_ex専用になっている。今回のCrustle戦ではCrustleの弱点が炎（闘ではない）のため実害はなかったが、将来ソルロックが闘弱点の相手と対峙すると、本来通らないはずの2倍ダメージが誤って計算される可能性がある。

## 誤りだったと判明・対応不要

### 「居座りボーナス」修正（当初の設計、撤回）

`docs/superpowers/specs/2026-07-20-lucario-combat-split-stay-bonus-fix-design.md`で設計した、`calc_attack_plan`の`i==0`(+220)/`j==0`(+300)ボーナスを`damage>0`でゲートする修正案。以下の理由でYAGNI判定とし撤回する。

- `pokemon_score`は`プライズ枚数×1000+HP+エネルギー数×150+ステージボーナス`という式のため、実測のCrustle/Sylveonのpokemon_score（ツールによるHP上昇込みで最大2870程度）に対し、位置ボーナス（最大520点、メガルカリオexの捨て札ボーナス込みでも最大700点）は常に小さく、決定を左右する境界条件（`pokemon_score×damage比率 < 220〜420`程度）は実測データ上ほぼ再現しない
- 実バトルログ3戦（86898758, 86899338, 86905948）を実コードで再現検証したが、いずれも「居座りボーナスが実ダメージの出る選択肢を打ち負かした」瞬間は確認できず、「実ダメージの出る選択肢自体が長期間存在しなかった」（＝上記1・2のバグでエネルギーが届いていなかった）ことが直接の原因だった

### `plan`（グローバル変数）の鮮度問題

既存のコード内コメント（main.py:417-423付近）は「MAIN以外のコンテキストで古いattacker/targetを参照し続ける」と説明していたが、実ログでの再現検証の結果、`_reset_turn_state()`は正しく`AttackPlan()`のデフォルト値（attacker=-1）にリセットしており、「古いデータの参照」ではなく「情報が一切ない状態へのフォールバック」であることが判明した。今回確認できた実例（1件）では、フォールバック後も種族優先度やOgerpon_exボーナスにより偶然正しい選択がなされており、実害は確認できなかった。潜在リスクとしては残るが、緊急の対応は不要と判断する。

## 次のステップ

上記1・2（`energy_score`関連の2つのバグ）を本命の修正として進める方針で合意済み（ユーザー確認待ちは3・4・5の扱いのみ）。3・4・5をどう扱うかはユーザー判断待ち。判断後、`docs/superpowers/specs/2026-07-20-lucario-combat-split-stay-bonus-fix-design.md`を本レビュー結果に合わせて書き直し、`superpowers:writing-plans`で実装計画を作成する。
