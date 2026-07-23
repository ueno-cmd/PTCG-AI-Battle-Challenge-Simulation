# main.py if/elif構造 全体監査（2026-07-23）

## 経緯
アカマツ(Crispin)のhand_scoreで、`if`が`elif`になっておらず低評価(10点)の分岐が
常に上書きされて死んでいるバグが発見された(main.py:604-611)。同種のバグが
他に潜んでいないか、ユーザー指摘によりmain.py全体を監査した。

## 監査対象と結論

### `_attach_score`（main.py:47-118）
- Budew/Meowth_ex/Fezandipiti_ex/Latias_exの分岐は全てreturn文で終わるため、
  後続の`if active and can_main_attack: return -1`（line 79）が誤って実行される
  ことはない（先行するreturnにより到達しない）。問題なし。
- `energy_count>=2/==1/==0`のif/elif/elseチェーン（line 82-115）は正しくelifで
  分岐しており、siblingなif問題は無い。
- 末尾の`if no_more_dex and (...): score -= 500`（line 116-117）は`-=`による
  意図的な合成であり、上書きバグではない。問題なし。

### `hand_score`内の各カード分岐（main.py:508-657）
- Crispin（line 604-611）：**バグ確認**。2つ目の`if`が`elif`になっておらず、
  1つ目の`if`で設定した`score=10`が常に上書きされる。本計画のTask 2で修正。
- Dreepy/Drakloak/Dragapult_ex/Fezandipiti_ex/Latias_ex/Budew/Meowth_ex/
  Rare_Candy/Unfair_Stamp/Buddy_Buddy_Poffin/Night_Stretcher/Crushing_Hammer/
  Ultra_Ball/Poke_Pad/Lucky_Helmet/Boss_Orders/Brock_Scouting/
  Lillie_Determination/Team_Rocket_Watchtower/Basic_Fire_Energy/
  Basic_Psychic_Energyの各分岐を個別に確認。全てif/elif/elseの正しいチェーン、
  または`+=`/`-=`による意図的な合成、もしくは単一のif/elseで構成されており、
  Crispinと同種の「siblingなifによる無条件上書き」は見つからなかった。
- 末尾の`if not ignore_count and hand_counts[id] > 0: ... score -= 100 (等)`
  （line 650-656）は`-=`による意図的な合成であり、上書きバグではない。

### `main_option_proc`（main.py:297-392）
- line 313-319のoptionループ内`if/elif`、line 333-348の逆算アルゴリズム
  （`continue`によるガード付き）、line 352-392のプラン選択スコア計算、
  いずれもsiblingなif上書き問題は見当たらなかった。

### `agent()`メイン処理（main.py:394-908）
- `OptionType`ごとの`elif`チェーン（line 692-895）を全て確認。
  `SelectContext.TO_BENCH`/`TO_HAND`のアカマツ専用の逆転スコアリング
  （line 726-728, `if effect_card_id == Crispin: score = 100000 - hand_score(...)`）
  や、`DAMAGE_COUNTER`系の`no_damage_counter`による無条件上書き
  （line 760-761, `score = -1`）は、いずれも「特定条件下でスコアを
  意図的に上書きする」設計であり、siblingなif由来の偶発的なバグではない。
  他に同種のバグは見つからなかった。

## 結論
main.py全体で確認されたsiblingなif上書きバグは、アカマツ(Crispin)の
hand_score（line 604-611）の1件のみ。他の条件分岐は、elifチェーンによる
正しい排他分岐か、`+=`/`-=`・`return`による意図的な合成/早期終了パターンで
構成されており、追加のバグは発見されなかった。
