# ルカリオexデッキ Dragapult ex系トゥールボックス対策（Maximum Belt導入）設計書

- 日付: 2026-07-26
- 背景ドキュメント: `docs/analyses/20260726-lucario-dragapult-toolbox-loss-mechanism-deep-dive.md`

## 1. 背景・目的

Dragapult ex（HP320）の技「ファントムダイブ」は、1回の攻撃でこちらのアクティブに200ダメージ・
同時にベンチ全体へダメカン6個(60ダメ相当)を撒く非対称技である。これに対し、こちらの攻撃手段
（Mega Lucario exのAura Jab/Mega Brave等）は相手アクティブ1体にしかダメージを与えられないため、
Dragapult exが完成すると一方的に押し切られる（実測3戦中2戦で構造的敗因と確認済み）。

対策として、ACE SPEC「Maximum Belt」（相手のアクティブ`ex`ポケモンへの技ダメージ+50、弱点・抵抗力
適用前に加算）をMega Lucario exに装着し、メガブレイブ(270)と組み合わせることで
**270+50=320でDragapult ex(HP320)をちょうど1発でワンパンできる**ようにする。Dragapult exは
弱点・抵抗力ともに`n/a`（`data/competition/EN_Card_Data.csv`確認済み）のため、この320ダメージは
確実に通る。

## 2. スコープ

- 今回はMaximum Belt導入によるDragapult ex対策の1点のみ
- 「カースドボム（ヨノワール）／超タイプアタッカー（ラティアスex等）の奇襲に備えた盤面管理」は
  今回のスコープ外（ユーザー判断・実ログ`88005023`/`88012470`/`88016835`に登場実績なしのため）
- Premium Power Pro（既採用、パワープロテイン、+30）との連携ロジックは組み込まない。
  Maximum Belt単体で270+50=320のちょうどKOが成立するため不要と判断

## 3. 変更内容

### 3.1 デッキ構築変更（`decks/lucario_20260621.py`）

ACE SPEC枠（1枚制限）を`Hero's Cape`(ID1159)から`Maximum Belt`(ID1158)に差し替える。
Hero's Capeとの両立は不可（ACE SPECは1枚制限）。

### 3.2 `src/lucario_agent/constants.py`

`Maximum_Belt = 1158` を新規追加する。既存の`Hero_Cape`定数は削除しない
（`decks/cinderace_starmie_20260630.py`が引き続き使用するため、他デッキへの影響はなし）。

### 3.3 `src/lucario_agent/main.py`

`_score_attach_option()`内の`Hero_Cape`分岐を`Maximum_Belt`分岐に置き換える。

- ベーススコア7000（Hero_Capeと同水準）
- 装着先がMega Lucario exなら+200（メガブレイブでの一撃KOを狙う主目的のため最優先）
- 装着先がRiolu（進化前）なら+100（進化後もツールが維持されるため次点で温存的に許容）

このモジュールから`Hero_Cape`のimportと参照を削除する（他デッキ用エージェントとは独立モジュールの
ため影響なし）。

### 3.4 `src/lucario_agent/combat.py`

`_calc_attack_damage()`に新しい引数`attacker_tools: tuple = ()`を追加する。

- 攻撃側が`Maximum_Belt`を装着しており、かつ相手が`ex`/`megaEx`の場合、弱点・抵抗力の判定より
  **前に**base_damageへ+50する（カード効果文「before applying Weakness and Resistance」の順序を
  忠実に再現）
- `calc_attack_plan()`内のループは、その時点で評価している`op_pokemon`が実質的に「相手のアクティブ
  （現在、または相手の交代後）」を表しているため、Maximum Beltの「相手のアクティブ限定」制約は
  ループ内の全候補に対してそのまま成立する。よって`defender_is_active`のような追加フラグは不要
  と判断（ベンチポケモンを直接攻撃対象にする経路自体がこのコードベースに存在しないため）
- `calc_attack_plan()`内の2箇所の`_calc_attack_damage()`呼び出し（通常ダメージ計算・メガブレイブが
  過剰火力でないかの再計算）双方に`attacker_tools=my_pokemon.tools`を渡す
- 既存呼び出し（テスト等）は`attacker_tools`省略時デフォルト`()`となり、Maximum Belt関連の分岐は
  発火しないため後方互換

## 4. テスト方針

- `tests/test_lucario_deck.py`：`ACE_SPEC_IDS`を`{1158}`に更新。Maximum Belt採用(1枚)・
  Hero's Cape不在を確認する回帰テストを追加
- `tests/test_lucario_agent.py`：
  - `mock_card_table`フィクスチャの`lm.Hero_Cape`エントリを`lm.Maximum_Belt`
    （`cardType=CardType.TOOL`）に置換
  - 既存のHero_Cape優先度テスト（`test_hero_cape_beats_air_balloon_for_mega_lucario_ex`/
    `test_hero_cape_beats_air_balloon_for_riolu`）をMaximum_Belt版に書き換え
  - `TestCalcAttackDamage`に以下を追加：
    - Maximum Belt装着時、相手`ex`に対して+50されること
    - 相手が非`ex`なら+50されないこと
    - 弱点適用より先に+50が加算される順序であること（弱点×2との組み合わせで検証）
  - `TestCalcAttackPlan`に統合テストを追加：Mega Lucario ex（2エネ・Maximum Belt装着）が
    HP320・`ex`の相手に対し、メガブレイブ(270)のみでは足りないがMaximum Belt込みで
    ちょうどKOと判定されること

## 5. 影響範囲外・意図的に対応しないこと

- `hand_score()`や`PremiumPowerProPolicy`等、Maximum Belt以外のPLAY/ATTACHロジックへの変更なし
- 他デッキ（`cinderace_starmie_agent`等）でのHero's Cape運用には一切影響しない
