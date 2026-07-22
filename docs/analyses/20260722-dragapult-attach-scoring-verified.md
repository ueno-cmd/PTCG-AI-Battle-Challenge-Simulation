**このファイルの位置付け：** 2026-07-22に一度「65件中4件が矛盾」と分析したが、
分析手法自体に致命的なバグ2つ（ステップ内の複数ターン混在／SWITCHのフィールド名の
意味の取り違え）が発覚し全て汚染された（詳細は
`docs/superpowers/plans/2026-07-22-dragapult-energy-attach-debug-plan.md`参照）。
本ファイルは`GameStateTracker`によるイベント再生方式で正しく再検証した結果であり、
前回の`docs/analyses/20260722-dragapult-attach-and-unfair-stamp-review.md`の
ベンチ配分部分を置き換えるものである。

---

# ドラパルトex ベンチ向けエネルギー装着 再検証レポート（20戦・GameStateTracker方式）

## 実行コマンドと結果

```bash
uv run python scripts/analyze_dragapult_attach_scoring.py \
  --target-player Kagura_UT \
  data/battle_logs/87204277.json data/battle_logs/87204845.json data/battle_logs/87205390.json \
  data/battle_logs/87205929.json data/battle_logs/87206482.json data/battle_logs/87207033.json \
  data/battle_logs/87207578.json data/battle_logs/87208132.json data/battle_logs/87208679.json \
  data/battle_logs/87209220.json data/battle_logs/87209770.json data/battle_logs/87210329.json \
  data/battle_logs/87210886.json data/battle_logs/87211430.json data/battle_logs/87211992.json \
  data/battle_logs/87212533.json data/battle_logs/87213077.json data/battle_logs/87213619.json \
  data/battle_logs/87214153.json data/battle_logs/87214695.json
```

```
# ドラパルトex ベンチ向けエネルギー装着 再検証レポート

検証対象試合数: 20
ベンチ向けATTACHイベント総数: 77
矛盾件数: 4
要目視確認件数(can_switchの値次第で判定が割れる): 6

## 矛盾事例
- 試合87208679 step=82
- 試合87208679 step=130
- 試合87211430 step=79
- 試合87212533 step=138

## 要目視確認事例
- 試合87206482 step=115
- 試合87210329 step=66
- 試合87211430 step=41
- 試合87211992 step=21
- 試合87213077 step=24
- 試合87214153 step=137
```

2026-07-22時点で改めて実行し、上記の通り**完全に一致**することを確認済み
（20戦・77件・矛盾4件・要目視確認6件、該当のepisode ID・step番号もすべて一致）。

---

## 矛盾事例

4件すべてについて、`etl.gold.build_event_timeline`で該当試合の生ログを1イベントずつ再生し、
ATTACHイベント直前の実際の盤面（アクティブ/ベンチの種族・エネルギー数・装着済みエネルギーの
カードID列）を`GameStateTracker`から直接読み出した上で、本番の`dragapult_agent.main._attach_score()`
をそのまま呼び出してスコアを再計算した。4件とも、**`GameStateTracker`の状態は
EVOLVE/SWITCH/PLAYなどの生イベントから独立に裏取りでき、`_own_candidates()`の候補列挙にも
見落としはなかった**（候補となったポケモンは全員、当該ATTACHより十分前のイベントで既に場に
出ていたことを確認済み）。そのため4件とも **(a) `_attach_score()`自身のロジックが、実際に選ばれた
対象より高いスコアを別候補に与えてしまっている、という現行コードの実態に基づく矛盾** と結論した。
（b）の「トラッカーの未対応イベント（MOVE_ATTACHED/CHANGE等）による見せかけの矛盾」ではないことを、
各事例で候補ポケモンの登場イベントまで遡って個別に確認している。

### 試合87208679 step=82

- 盤面（イベント適用前）: アクティブ=Budew(id235, energy0) / ベンチ=Drakloak(serial77, id120, energy0), Dragapult ex(serial81, id121, **energy2**＝既にファントムダイブ可能なベンチアタッカー)
- イベント: エネルギー(id5, Psychic)をserial81(Dragapult ex, 既にenergy2)へ装着（＝実際に選ばれた対象）
- クリスピン由来ではない（直前にPLAY(Crispin)なし。同ターン内で既にstep77にクリスピン自動装着でこのDragapult exへenergy1→2まで済んでおり、本イベントはその後の通常の「1ターン1枚」の手動エネルギー装着）
- スコア: 選ばれた対象(Dragapult ex, energy2, ベンチ)=**-1**（`_attach_score()`のenergy_count>=2分岐は非アクティブなら常に-1）に対し、Drakloak(serial77, energy0, ベンチ)=**19850**（can_switch True/False両方で同じ）
- 判定: 既に攻撃可能なベンチのDragapult exへ3枚目のエネルギーを積む（無駄打ち）よりも、未着手のDrakloakへ配ることを`_attach_score()`自身が明確に高く評価しているにもかかわらず、実際は前者が選ばれた。矛盾。

### 試合87208679 step=130

- 盤面（イベント適用前）: アクティブ=Dragapult ex(serial79, id121, energy0＝直前のSWITCHで新しくアクティブになったばかり) / ベンチ=Dreepy(serial73, id119, energy0), Budew(serial84, id235, energy0)
- イベント: エネルギー(id2, Fire)をserial73(Dreepy, ベンチ)へ装着（＝実際に選ばれた対象）。**クリスピン由来**（直前のPLAY(Crispin)から、山札→手札の1回のパススルーのみを挟んで直後にATTACHが来ている）
- スコア: クリスピンの自動装着は、装着先がDragapult exなら+200ボーナスが乗る（`main.py:759-760`）。アクティブのDragapult ex(energy0)=20000+200(クリスピンボーナス)=**20200**、対して選ばれたDreepy(ベンチ,energy0)=**20100**（can_switch True/False両方で同じ）
- 判定: クリスピンで探索したエネルギーを、直前にアクティブへ入れ替わったばかりの空のDragapult exに充填する方がスコア上位（アクティブ最優先攻撃者への充填を明示的に優遇するボーナス）にもかかわらず、実際はベンチのDreepyへ装着された。矛盾。

### 試合87211430 step=79

- 盤面（イベント適用前）: アクティブ=Dragapult ex(serial81, energy2, 攻撃可) / ベンチ=Drakloak(serial75, energy1, [card 2]), Drakloak(serial77, **energy0**＝直前のstep76で進化したばかり), Fezandipiti_ex(serial82, energy1), Budew(serial85, energy0)
- イベント: エネルギー(id5, Psychic)をserial75(Drakloak, energy1)へ装着（＝実際に選ばれた対象）
- クリスピン由来ではない（直近のクリスピン自動装着はstep75で完了済み、本イベントは別カード）
- スコア: 選ばれたDrakloak(energy1)=**19800**に対し、同じくベンチの別Drakloak(serial77, energy0)=**20050**（can_switch True/False両方で同じ）。`_attach_score()`のenergy_count==1分岐はDrakloak（Dragapult_exでもDreepyでもない種族）に対し一律-200のペナルティを課す一方、energy_count==0分岐はペナルティなし＋50加点となるため、「1エネルギー付いた個体を継続充填する」より「0エネルギーの個体に新規着手する」方が常にスコアが高くなる非対称な設計になっている
- 判定: 両方のDrakloakは本イベントより十分前の別々のイベント（進化・以前の装着）で既に場に存在しており、候補列挙の見落としではない。`_attach_score()`自身のロジックが推奨する配分と実際の選択が食い違っている。矛盾。

### 試合87212533 step=138

- 盤面（イベント適用前）: アクティブ=Dragapult ex(serial21, energy2, 攻撃可) / ベンチ=Drakloak(serial16, **energy0**), Drakloak(serial17, energy1, [card 2]), Fezandipiti_ex(serial22, energy0), Budew(serial24, energy0), Meowth_ex(serial26, energy0)。相手残りサイド1枚のためno_more_dex=True
- イベント: エネルギー(id5, Psychic)をserial17(Drakloak, energy1)へ装着（＝実際に選ばれた対象）
- クリスピン由来ではない
- スコア: 選ばれたDrakloak(energy1)=**19300**に対し、同じくベンチの別Drakloak(serial16, energy0)=**19550**（can_switch True/False両方で同じ）。step79事例と全く同じ「energy1ペナルティ vs energy0の非ペナルティ」パターン（no_more_dexによるDrakloak一律-500は両候補に均等にかかるため、相対順位には影響しない）
- 判定: step79事例と同型の矛盾。矛盾。

### 全体所見

4件のうち3件（87208679/82、87211430/79、87212533/138）は、**「既にエネルギーが1枚以上ついているDragapult_ex以外のベンチ種族（Drakloak）に追加装着する」ケースで`_attach_score()`が一律に不利なスコアを与える**という同一パターンに起因しており、実際の選択とは逆の推奨をしている。残り1件（87208679/130）は、クリスピン自動装着時のDragapult_exボーナス（+200）がアクティブのDragapult_exにも及ぶ結果、ベンチへの実際の配分よりアクティブ優先の配分の方が高スコアになるケース。
いずれも`GameStateTracker`側の不整合や候補列挙漏れは確認されず、`_attach_score()`のロジックと実際の選択が噛み合っていないという現行コードの実態を反映した矛盾であると判断した。

---

## 要目視確認事例

以下6件は、`_attach_score()`のMeowth_ex/Fezandipiti_ex/Latias_ex分岐が参照する`can_switch`
（「にげるができるか」の実際の値）が生ログから正確に復元できないため、`can_switch=True`と
`can_switch=False`で矛盾の有無の判定が割れてしまう事例。深掘りは行っていないが、代表例として
1件だけ盤面を確認した。

- 試合87206482 step=115
  - 盤面: アクティブ=Latias_ex(id184, energy0) / ベンチ=Drakloak(energy1), Dragapult ex(energy1,＝選ばれた対象), Fezandipiti_ex(energy0), Dragapult ex(energy2)
  - `can_switch=False`の場合のみ、アクティブのLatias_exが「にげるができない」ことを理由に22000のボーナススコアを得て、選ばれたベンチのDragapult ex(20250)を上回り矛盾となる。`can_switch=True`なら該当ボーナスが外れて矛盾なし。
- 試合87210329 step=66
- 試合87211430 step=41
- 試合87211992 step=21
- 試合87213077 step=24
- 試合87214153 step=137

これら6件は`can_switch`値が確定できない以上、本レポートでは判定を保留する。
