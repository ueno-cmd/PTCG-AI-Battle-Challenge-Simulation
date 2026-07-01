# 設計書：グリムスナールexエージェント「ボスの指令」導入

**作成日：** 2026-07-01
**ステータス：** 承認済み
**対象：** `decks/grimmsnarl_20260701.py` / `src/grimmsnarl_agent/main.py` の改修（新規デッキではない）

---

## 背景

LB調査（2026-07-01）により、以下が判明した。

- 自分のグリムスナールexデッキのスコアは615.9で、標準スコア600からほぼ伸びていない
- バトルログ6件（自分の負けログ3件：kazuki0123 vs The Debauchery Tea Party、自分の負けログ3件：Kagura_UT vs メガルカリオex×2/ドラパルトex×1）を解析した結果、**相手は全戦でボスの指令（Boss's Orders, ID 1182）を2〜3枚採用していたが、自分のデッキには1枚も入っていなかった**
- グリムスナールミラー戦の相手デッキとの比較でも、ボスの指令の有無が最大の差分だった
- ダメカン分散（Shadow Bullet：180+ベンチ30）を主軸とするこのデッキにとって、ボスの指令は分散したダメージを実際のKOに変換する生命線であり、欠落は致命的だったと判断できる

本設計は、この欠落を埋めるための最小限の改修を行う。範囲はグリムスナールexデッキに限定し、他デッキへの横展開は対象外とする。

---

## デッキ変更（`decks/grimmsnarl_20260701.py`）

| カード | Card ID | 変更前 | 変更後 |
|---|---|---|---|
| Energy Recycler | 1139 | 4枚 | **2枚** |
| Boss's Orders | 1182 | 0枚 | **2枚**（新規） |

- Energy Recyclerを削る理由：基本エネルギー12枚に対し、機能が一部重複するNight Stretcher（ポケモン+エネルギー回収）が既に4枚採用されており、Energy Recycler（エネルギー回収専用）が最も安全に削れる枠と判断
- 他のカード・合計60枚は変更なし（ACE SPEC枠のHero's Capeは引き続き1枚のまま）

---

## Agentロジック変更（`src/grimmsnarl_agent/main.py`）

### a. PLAY判断：ボスの指令を今使うか温存するか

`_score_play` にボスの指令用の分岐を追加する。判断はcontextual banditの発想で「KOターゲットの有無」という状況に応じて2方針（即使用 / 温存）を切り替え、温存側にのみε-greedyで小確率の探索（早目使用）を混ぜる。

```
has_ko_target = fs.op_bench_hp の中に180以下のポケモンがいるか
  （180 = Shadow Bulletの与ダメージ。_score_attackで使っている閾値と同じ基準を流用）

if has_ko_target:
    score = 8800   # 即使用（KO確定）。Rare Candy(9000)は上回らない
elif fs.op_bench_hp が空でない and rng.random() < EPSILON:
    score = 6000   # 探索的先出し（KO確定ではないが、キーポケモンを引きずり出す）
else:
    score = -1     # 温存。他のプレイに順位を譲る
```

- `EPSILON = 0.28`（目安：4回に1回程度）をモジュール定数として定義
- KO判定・探索判定いずれも「相手ベンチにポケモンが存在すること」が前提（存在しない場合は温存）

### b. ターゲット選択：ボスの指令で誰を引きずり出すか

`_score_card_option` の `SelectContext.SWITCH | SelectContext.TO_ACTIVE` 分岐を修正する。

- 現状：`o.playerIndex != my_index`（相手のポケモンが対象＝ボスの指令やガスト効果のケース）は無条件でスコア0を返しており、実質ランダムに選ばれてしまっている
- 変更後：相手のポケモンが対象の場合は `100000 - card.hp` を返し、最もHPが低い（KOに近い）ポケモンを選ぶようにする（`DAMAGE_COUNTER`コンテキストで既に使っている考え方と同じ）
- 自分のポケモンが対象の場合（既存の退却・スイッチ判断）は変更なし

このターゲット選択ロジックは、a.の「即使用」「探索的先出し」どちらの場合でも共通して使われる。

### c. 乱数の注入

- モジュールに `_rng = random.Random()`（本番用・実乱数）を追加
- `_score_play` は `rng`（`.random() -> float` を持つオブジェクト）を引数として受け取り、`agent()` から `_rng` を渡す
- テストでは `.random()` が固定値を返すスタブを注入し、explore/hold分岐を決定論的に検証する

---

## テスト方針

- 新規：`_score_play` のボスの指令分岐
  - KOターゲットあり → 8800
  - KOターゲットなし・rng値がepsilon未満 → 6000
  - KOターゲットなし・rng値がepsilon以上 → -1
  - 相手ベンチが空 → -1（rng値に関わらず）
- 新規：`_score_card_option` の `TO_ACTIVE`（相手ポケモン対象）で最低HPが選ばれること
- 既存：デッキ60枚テストをカード枚数変更に合わせて更新（Energy Recycler 2枚・Boss's Orders 2枚）
- 既存157件のテストは非破壊で全てPASSすること

---

## 成功基準

- ローカルテスト全PASS、既存機能への回帰なし
- Kaggle再提出後、スコア615.9からの改善を次回セッションで確認する（本設計のスコープ外・次のステップとして記録）

---

## 参考

- LB調査・バトルログ解析：会話ログ（2026-07-01）／`memory/project_ptcg_competition.md`
- 解析対象バトルログ：`data/battle_logs/83045618.json`, `83045672.json`, `83046246.json`, `83046382.json`, `83046837.json`, `83047032.json`
- 元デッキ設計書：`docs/superpowers/specs/2026-07-01-grimmsnarl-agent-design.md`
