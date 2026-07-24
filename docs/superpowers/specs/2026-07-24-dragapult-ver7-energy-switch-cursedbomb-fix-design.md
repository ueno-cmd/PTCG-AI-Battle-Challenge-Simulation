# ドラパルトex ver7実測ログで判明した3件の修正 設計書

## 背景・問題

イワパレス対策デッキ提出（ver7）後の新規30戦（`87665219`〜`87680882`）をユーザーの所感と
突き合わせて解析した結果、独立した3件の問題が判明した。詳細な調査経緯は本セッションの
会話ログを参照。

### ①④ `_attach_score()` にエネルギー種別チェックが無い（確定バグ）

`src/dragapult_agent/main.py:50-132`の`_attach_score()`は、イベルタルにだけ
「悪エネルギー以外なら-1」という専用ガード（84行目）があるが、ドラパルト系統
（ドラメシヤ/ドロンチ/ドラパルトex、炎/超エネルギーのみ要求）とマシマシラ
（悪エネルギーのみ要求）には同様のチェックが無い。設計書
（`docs/superpowers/specs/2026-07-23-dragapult-crustle-counter-deck-design.md:166-167`）は
マシマシラを「専用分岐なし・汎用ルールのまま」とする方針だったが、汎用ルールは
エネルギー種別を一切見ないため、実質的に「どんなエネルギーでも付けてしまう」バグに
なっていた。

実ログ30戦を`GameStateTracker`のATTACHイベントで検証した結果：
- ドラパルト系統への悪エネルギー誤装着：**30件**（ドラメシヤ14件/ドラパルトex12件/ドロンチ4件）
- マシマシラへの炎・超エネルギー誤装着：**10件**

### ② `_own_switch_target_score()` のスボミー優先度が非exアタッカーより高い

`src/dragapult_agent/main.py:152-184`の`_own_switch_target_score()`で、スボミーは
`bench_attacker`が偽（ベンチに攻撃準備完了のドラパルトexがいない）なら常に30000点。
一方イベルタルは15000点、ファイヤーは相手アクティブが非exなら5000点で、スボミー
（HP30・攻撃10ダメージのみ）が実戦的な非exアタッカーより優先されてしまう。

30戦中、以下3試合（いずれも敗戦）で、実際にこの逆転により非exアタッカーが
見送られていたことを確認した：
- `87674403`(敗) step41：イベルタルが選択肢にあったのにスボミーへ交代
- `87675484`(敗) step88：ファイヤーが選択肢にあったのにスボミーへ交代
- `87677096`(敗) step20：イベルタルが選択肢にあったのにスボミーへ交代

いずれも「ベンチにドラパルトex無し・相手アクティブが非ex」の条件で発生していた。

### ③ `_cursed_bomb_score()` の発動条件が狭すぎる

`src/dragapult_agent/main.py:224-233`の`_cursed_bomb_score()`は、相手アクティブが
`no_damage_dex()`該当（イワパレス系）の時だけ90000点、それ以外は常に-1を返す。
一方でヨノワール/サマヨールは`_attach_score()`側で意図的にエネルギー投資を
避けられている（90-92行目、score=500固定）ため、攻撃技を使う手段がそもそも無い。

実測30戦のうち、ヨノワール/サマヨール系統まで進化した21戦を検証した結果、
**21戦全てで進化後に一度も攻撃していなかった**。うち`no_damage_dex()`条件を
満たしたのは2戦（`87666838`, `87676557`）だけで、両方ともカースドボムは正しく
発動していた（この2件については当初の解析にオフバイワンの誤りがあり「未発動」と
誤って報告したが、再検証で発動を確認済み）。残る**19戦では、進化に2回分の
投資をしたカードが試合終了まで一切何もしない「文鎮」になっていた**
（進化から試合終了までの残りステップ数は平均80〜90、多いものは200超）。

## 修正範囲

`src/dragapult_agent/main.py`内の3関数のみ。デッキ構成（`decks/dragapult_20260721.py`）
・`TrainerCardPolicy`登録辞書・その他の関数は変更しない。

## 変更後の設計

### ①④ `_attach_score()`

既存のif/elif連鎖（71-92行目）に、イベルタルと同じ書き方で2つの分岐を追加する。
型が一致する場合はどちらの新規分岐にも該当しないため、既存の汎用スコアリング
（93行目以降）にそのまま流れ、既存の優先度計算には影響しない。

```python
# Attach energy
if pokemon.id == Budew:
    return -1
elif pokemon.id == Meowth_ex or pokemon.id == Fezandipiti_ex:
    ...
elif pokemon.id == Yveltal:
    # イベルタルの技コストは悪エネルギーのみ。それ以外は装着しても無意味
    if attach_id != Basic_Dark_Energy:
        return -1
    ...
elif pokemon.id in (Dreepy, Drakloak, Dragapult_ex) and attach_id not in (Basic_Fire_Energy, Basic_Psychic_Energy):
    # ドラパルト系統の技コストは炎/超エネルギーのみ。悪エネルギー等を誤装着させない
    return -1
elif pokemon.id == Munkidori and attach_id != Basic_Dark_Energy:
    # マシマシラの特性発動には悪エネルギーの装着が必須。それ以外は無意味
    return -1
elif pokemon.id == Dusknoir or pokemon.id == Dusclops:
    return 500
if active and can_main_attack:
    return -1
...
```

挿入位置はYveltal分岐の直後・Dusknoir/Dusclops分岐の直前とする（既存の分岐順序への
影響を避けるため）。

### ② `_own_switch_target_score()`

スボミーの返り値のみ変更する。

```python
elif card_id == Budew:
    return 3000 if not bench_attacker else 0
```

イベルタル(15000)・ファイヤー(5000/49000)を下回るため、他に攻撃可能な駒が
候補にあれば必ずそちらが優先される。`bench_attacker`がTrueの場合は既存通り0のまま。

### ③ `_cursed_bomb_score()`

シグネチャに`energy_count`（ヨノワール/サマヨール自身の装着エネルギー数）と
`has_other_attacker`（既存の`bench_attacker or can_main_attack`）を追加する。

```python
def _cursed_bomb_score(opponent_active_id: int | None, energy_count: int, has_other_attacker: bool) -> int:
    """ヨノワール／サマヨールの特性「カースドボム」
    （自分を気絶させ、相手ポケモン1匹にダメカンを直接配置）のスコアを返す。
    「ダメカンの直接配置」は「攻撃ダメージ」ではないため、イワパレスのような
    no_damage_dex()該当の特性ブロックを迂回できる。自爆前提のため、
    相手アクティブが直接攻撃を完全ブロックする相手の時は最優先で発動する。
    それ以外でも、_attach_score()側でエネルギー投資を避けられているため
    このポケモンは攻撃手段を持たず(energy_count==0)、かつ自分の場に
    他の攻撃可能な駒がある(has_other_attacker)場合は、
    試合終了まで何もしない「文鎮」になるより自爆してダメカンを置く方が
    価値があると判断し、中程度の優先度で発動を許可する
    （2026-07-24、実測30戦中21戦でヨノワール/サマヨール到達後に
    一度も攻撃しない事例を確認して追加。本命アタッカーを犠牲にする
    リスクを避けるため、他に攻撃札が無い場合は発動しない）"""
    if opponent_active_id is not None and no_damage_dex(opponent_active_id):
        return 90000
    if energy_count == 0 and has_other_attacker:
        return 20000
    return -1
```

呼び出し元（1121-1123行目付近）を次のように変更する。

```python
elif card.id == Dusknoir or card.id == Dusclops:
    opponent_active_id = op_state.active[0].id if op_state.active else None
    score = _cursed_bomb_score(
        opponent_active_id, len(pokemon.energies), bench_attacker or can_main_attack,
    )
```

`pokemon`（このABILITY選択肢の持ち主＝ヨノワール/サマヨール自身）は同スコープ内の
`get_card(obs, o.area, o.index, my_index)`で取得済みの`card`と同一オブジェクトを想定。
`bench_attacker`・`can_main_attack`は`agent()`内で既に計算済みの変数をそのまま渡す。

## テスト方針（TDD）

`tests/test_dragapult_agent.py`に既存テストと同じスタイル（Given-When-Then・
日本語docstringでWHYを明記）で追加する。

1. **`_attach_score()`**
   - ドラパルト系統(Dreepy/Drakloak/Dragapult_ex)に悪エネルギーを装着しようとすると-1になること
   - マシマシラに炎/超エネルギーを装着しようとすると-1になること
   - ドラパルト系統に炎/超エネルギーを装着する場合は既存のスコアが変わらないこと（回帰確認）
   - マシマシラに悪エネルギーを装着する場合は既存の汎用スコアリングがそのまま適用されること（回帰確認）

2. **`_own_switch_target_score()`**
   - `bench_attacker=False`の時、スボミー(3000)がイベルタル(15000)を下回ること
   - `bench_attacker=False`の時、スボミー(3000)がファイヤーの非ex優先スコア(5000)を下回ること
   - `bench_attacker=True`の時は既存通りスボミーが0のままであること（回帰確認）

3. **`_cursed_bomb_score()`**
   - `energy_count=0, has_other_attacker=True`で相手が通常ポケモンの場合、20000を返すこと（新規）
   - `energy_count=0, has_other_attacker=False`の場合、-1のままであること（本命アタッカーを
     犠牲にしないことの回帰テスト）
   - `energy_count>0`の場合、-1のままであること（エネルギーが付いているなら文鎮ではないため対象外）
   - 既存の`no_damage_dex()`該当時90000のケースは変更しないこと（回帰確認）
   - 既存テスト`test_cursed_bomb_score_low_for_normal_opponent`・
     `test_cursed_bomb_score_low_when_no_opponent_active`はシグネチャ変更に合わせて
     引数を追加し、期待値はそのまま維持する

## 検証手順

1. `uv run pytest -q`でリポジトリ全体を実行し、既存テストに回帰がないことを確認
2. 実装完了後、`docs/implementations/`に実装サマリーを保存
3. 提出用notebook（`scripts/build_dragapult_submission_notebook.py`）を再生成
4. Kaggle再提出はユーザー側で実施。次回バトルログ取得時に、①④のエネルギー誤装着が
   解消されたか、②のスボミー交代頻度が減ったか、③のヨノワール/サマヨールが
   自爆するようになったか（かつ勝率への影響）を実測で確認する

## スコープ外（今回は対応しない）

- ヨノワール/サマヨール自身への攻撃技スコアリングの新規実装（現状通りエネルギー非投資のまま）
- ③の20000という数値自体のチューニング（次回実測ログで妥当性を再検証する）
- むかえにいく（ヨマワル）・アドレナブレイン（マシマシラ）のスコアリング条件見直し
  （今回指摘があったのはカースドボムのみ）
- ABILITY分岐全体のTrainerCardPolicy的なクラス化（バックログ記載の別課題、[[project_ptcg_backlog]]参照）
