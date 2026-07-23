# ドラパルトex 強制入場時スボミー優先ロジックの削除 設計書

## 背景・問題

`docs/analyses/20260723-dragapult-post-attach-fix-20-games.md`の検証で、KOによる強制入場
（`SelectContext.TO_ACTIVE`/`SETUP_ACTIVE_POKEMON`）時にスボミー（Budew）を優先する
現行ロジック（`src/dragapult_agent/main.py:701-705`）に次の問題を確認した。

- 実測20戦中、該当する強制入場4件のうち3件で、スボミーを出した**同じ自分のターン中に
  自分から交代させて**おり、特性「むずむずかふん」（場に出た瞬間、相手は次の番アイテムを
  使えない）の発動意図と矛盾する運用になっていた
- 唯一「相手の次ターンにアイテムが封じられたか」を実ログで検証できた1件（試合87464081）では、
  相手が実際にアイテム（ポケパド）を通してしまっており、狙った妨害効果が機能していなかった
- 一方で、強制入場の瞬間にスボミーを優先することで、**本来出したかった本命アタッカー
  （Dragapult_ex）を出し損ね、逆転のチャンスを逃すリスク**は設計上明確に存在する

効果が実戦で機能している証拠が乏しい一方、リスクは明確なため、ユーザー判断により
**強制入場時のスボミー優先処理を完全に削除**する。

## 修正範囲

`src/dragapult_agent/main.py:687-714`の「アクティブへ送るポケモンの選択」ロジック
（`SelectContext.SWITCH`/`TO_ACTIVE`/`SETUP_ACTIVE_POKEMON`共通）のうち、
**`o.playerIndex == my_index`（自分のポケモンを選ぶ場合）の分岐のみ**を対象とする。

対象外（今回は変更しない）：
- 相手ポケモンを選ぶ側の分岐（`plan_a.attack`を使う部分）
- `SelectContext.SWITCH`（自発的な交代）でのスボミー+30000自体の値
- ニャースex/フェザンディピティex/ラティアスexの優先ロジック

## 現状のコード

```python
if (context == SelectContext.SWITCH
    or context == SelectContext.TO_ACTIVE
    or context == SelectContext.SETUP_ACTIVE_POKEMON):
    # Selection of the Pokémon to send to the Active Spot
    if o.playerIndex == my_index:
        if card.id == Dreepy:
            score += 10000
        elif card.id == Drakloak:
            if energy_count >= 1:
                score += 20000
            else:
                score -= 10000
        elif card.id == Dragapult_ex:
            score += 50000
        elif card.id == Budew:
            if context != SelectContext.SWITCH:
                score += 100000
            elif not bench_attacker:
                score += 30000
        elif card.id == Fezandipiti_ex:
            score -= 1000
        elif card.id == Meowth_ex:
            score -= 2000
    else:
        if plan_a.attack == o.index + 1:
            score += 100000
    score += energy_count * 1000
    score += hp
```

## 変更後の設計

このロジックは巨大な`agent()`関数の内部にベタ書きされており、単体テストできない。
`_attach_score()`・`_boss_orders_score()`が同じ理由でテスト用に関数として切り出されている
前例に倣い、次の関数を新規に切り出す。

```python
def _own_switch_target_score(card_id: int, energy_count: int, bench_attacker: bool) -> int:
    """SelectContext.SWITCH/TO_ACTIVE/SETUP_ACTIVE_POKEMON共通で、
    自分のポケモンをアクティブへ送る候補への優先度スコアを返す
    （hp・energy_count*1000の共通加点は呼び出し側で加算する）。
    強制入場時のみスボミーを特別優先していた分岐は、実戦で効果が
    機能している確証がなく、本命アタッカーを出し損ねるリスクの方が
    明確なため削除した（2026-07-23、docs/analyses/20260723-dragapult-post-attach-fix-20-games.md参照）。"""
    if card_id == Dreepy:
        return 10000
    elif card_id == Drakloak:
        return 20000 if energy_count >= 1 else -10000
    elif card_id == Dragapult_ex:
        return 50000
    elif card_id == Budew:
        return 30000 if not bench_attacker else 0
    elif card_id == Fezandipiti_ex:
        return -1000
    elif card_id == Meowth_ex:
        return -2000
    return 0
```

呼び出し側（`agent()`内、`SelectContext.SWITCH`/`TO_ACTIVE`/`SETUP_ACTIVE_POKEMON`の
`OptionType.CARD`分岐）は次のように変更する。

```python
if (context == SelectContext.SWITCH
    or context == SelectContext.TO_ACTIVE
    or context == SelectContext.SETUP_ACTIVE_POKEMON):
    # Selection of the Pokémon to send to the Active Spot
    if o.playerIndex == my_index:
        score += _own_switch_target_score(card.id, energy_count, bench_attacker)
    else:
        if plan_a.attack == o.index + 1:
            score += 100000
    score += energy_count * 1000
    score += hp
```

`context`による分岐（SWITCHか否か）が不要になったため、関数の引数からも`context`を含めない。

## テスト方針（TDD）

`tests/test_dragapult_agent.py`に、既存の`_attach_score`テストと同じスタイル
（Mockデータクラス・Given-When-Then・日本語docstringでWHYを明記）で追加する。

1. **強制入場相当の条件でもDragapult_exがスボミーより優先されること**：
   `_own_switch_target_score(Dragapult_ex, ...)` (=50000) が
   `_own_switch_target_score(Budew, ..., bench_attacker=False)` (=30000) を上回ることを確認
   （「強制入場時のみ+100000」の抜け道が完全に消えたことの直接的な回帰テスト）
2. **bench_attackerがTrueの場合、スボミーのスコアが0になること**
3. **既存の他カードのスコアが変わらないこと**（回帰確認）：
   Dreepy=10000、Drakloak(energy>=1)=20000、Drakloak(energy=0)=-10000、
   Fezandipiti_ex=-1000、Meowth_ex=-2000、未知カード=0

既存テストに`Budew`やこの関数を直接使うものは無いため、後方互換の壊れは発生しない。

## 検証手順

1. `uv run pytest -q` でリポジトリ全体を実行し、既存テストに回帰がないことを確認
2. 実装完了後、`docs/implementations/`に実装サマリーを保存
3. デッキ本体（`decks/dragapult_20260721.py`）は変更しないため、CSV再生成は不要。
   提出用notebook（`scripts/build_dragapult_submission_*.py`）はmain.pyの変更を反映するため
   再生成が必要
4. Kaggle再提出後、次回バトルログ取得時に、強制入場時に本命アタッカーが選ばれるようになったか
   （スボミーが以前ほど強制入場で選ばれなくなったか）を実測で確認する

## スコープ外（今回は対応しない）

- スボミーの`_attach_score()`側の扱い（`pokemon.id == Budew: return -1`、常にエネルギー非対応）は変更しない
- 「87492541 step=153の新規矛盾パターン」「クリスピン+200ボーナスの妥当性」は別タスクとして
  次回以降に持ち越す（`docs/analyses/20260723-dragapult-post-attach-fix-20-games.md`参照）
