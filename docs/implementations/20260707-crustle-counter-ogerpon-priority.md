# 実装サマリー：Crustle対策強化とオーガポンex優先ロジック導入

**実装日：** 2026-07-07
**関連計画書：** `docs/superpowers/plans/2026-07-07-crustle-counter-ogerpon-priority.md`
**関連バトルログ：** `data/battle_logs/84580427.json`（player1 Kagura_UT敗北）

## 背景

バトルログ84580427の解析で、相手デッキ（Crustle×4、Card ID 345、特性「ふしぎな
岩の宿」＝相手の「ポケモン【ex】」の技ダメージを無効化）に対し、メガルカリオex
の攻撃が試合を通じて一度も実際のダメージを与えられていなかったことが判明した
（HP_CHANGEログが常にvalue=0）。`calc_attack_plan`はこの特性を考慮しておらず、
メガブレイブ（270ダメージ）でKOできると誤って評価し続けていた。

一方、ベンチのオーガポンex（Card ID 117）は「ぶちやぶる」（相手のバトルポケモン
にかかっている効果を計算しない仕様）により、この特性を貫通して実ダメージを与え
られる可能性がある（ユーザーからの裁定指摘）。しかし試合を通じて一度もアクティブ
に切り替えられなかった。

なお過去の実装（`docs/implementations/20260706-lucario-ogerpon-subattacker.md`）
では「特性の効果無視部分はシミュレータが処理するためエージェント側の実装対象外」
としていた。その最終レビューでも「イワパレス系特性ダメージ無効化を実際に突破でき
るかが実機シミュレータで未検証」というImportant指摘（設計上のリスク）が既に記録
されていたが、今回の実バトルログでこのリスクが実際に敗因として顕在化したことが
確認できたため、前提を撤回し、`calc_attack_plan`にCrustle固有の耐性チェックを
追加する方針に切り替えた。

## 変更内容

### デッキ（`decks/lucario_20260621.py`）— commit `72f5740`
- Solrock (676) を3枚→2枚に削減
- Cornerstone Mask Ogerpon ex (117) を1枚→2枚に増量
- デッキ合計60枚・ACE SPEC（Hero's Cape, 1枚）は変更なし

### エージェントロジック（`src/lucario_agent/main.py`）

- **`calc_attack_plan`（commit `3631700`）**：
  新規定数 `Crustle = 345` を追加。ダメージ計算ループに
  `if op_pokemon.id == Crustle and my_pokemon.id == Mega_Lucario_ex: damage = 0`
  を追加し、Crustle相手のメガルカリオexの技ダメージ（はどうづき／メガブレイブ
  どちらも）を0として評価するようにした。オーガポンexの「ぶちやぶる」は対象外
  （既存のweakness/resistance無視ロジックと同じ`my_pokemon.id`分岐で区別）のため、
  この耐性チェックの影響を受けず140ダメージのまま評価される。

- **`_score_card_option`（SWITCH/TO_ACTIVE, commit `110d3fc`）**：
  既存のMega_Lucario_ex（+8〜20）・Solrock（+5）・Riolu（+4）の優先度分岐に
  `elif card.id == Ogerpon_ex: score += 20 if energy_count >= 3 else 6` を追加。
  攻撃プランが未確定の強制交代場面（撃破直後のTO_ACTIVEなど）でも、3エネルギー
  以上充填済みのオーガポンexが優先的に選ばれるようにするフォールバック。

## テスト結果

- 追加テスト計7件：
  - `tests/test_lucario_deck.py`（Task1・2件、既存2件を置換）：
    `test_ogerpon_ex_present_with_2_copies`、`test_solrock_reduced_to_2`
  - `tests/test_lucario_agent.py` `TestCrustleAbilityInteraction`（Task2・3件）：
    `test_mega_lucario_ex_damage_nullified_by_crustle_ability`、
    `test_ogerpon_ex_bypasses_crustle_ability`、
    `test_switches_to_ogerpon_ex_over_mega_lucario_ex_against_crustle`
  - `tests/test_lucario_agent.py` `TestSwitchContext`（Task3・2件）：
    `test_ogerpon_ex_prioritized_when_charged`、
    `test_ogerpon_ex_low_priority_when_not_charged`
- リポジトリ全体：`uv run pytest -q` を実行し、**253 passed**（全件PASS、回帰なし）を確認。

```
$ uv run pytest -q
........................................................................ [ 28%]
........................................................................ [ 56%]
........................................................................ [ 85%]
.....................................                                    [100%]
253 passed in 0.10s
```

## 各タスクのレビュー結果

- Task 1（デッキ構成変更）：Approved。Issues無し。
- Task 2（Crustle耐性チェック）：Approved。Minor2件（`Crustle`定数の桁揃えの見た目、
  非exアタッカー[Solrock]の回帰テスト未追加）→いずれも対応不要と判断（後者は
  完全一致条件`my_pokemon.id == Mega_Lucario_ex`により解析的に安全と確認済み）。
- Task 3（SWITCH/TO_ACTIVE優先度）：Approved。Issues無し。

## 未対応事項

- Crustle以外の「特性による技ダメージ無効化」を持つ壁ポケモンが今後の対戦相手
  デッキに出てきた場合、同様の個別対応が必要になる（現状は345のみハードコード）。
  複数種類が確認された時点でテーブル化を検討する。
- オーガポンexの「ぶちやぶる」がCrustleの特性を実際に貫通するかどうかは、
  ユーザーの裁定情報に基づく実装であり、次戦の実バトルログで実際に貫通した
  ことを確認できていない。次回オーガポンexがCrustle相手に攻撃した試合が
  あれば、ログで実ダメージが入ったかを検証すること。
- Solrock（非exアタッカー、Crustleに対して本来ダメージが通るはず）がCrustle
  を相手にした場合の回帰テストは今回追加していない（Task2レビューのMinor指摘）。

## 次のステップ

- `output/`用デッキCSVの生成、およびKaggleへの再アップロードは本改修のスコープ外。
  実施可否はユーザー判断待ち。
- Kaggle再提出後のLBスコア変化、および次回Crustle系デッキとの対戦ログでの
  実ダメージ貫通確認はユーザーが手動で実施する。
