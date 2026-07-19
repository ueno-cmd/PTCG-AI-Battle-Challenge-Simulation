# ルカリオexデッキ ex無効化検知の汎用化・スタジアム未考慮・オーガポンex優先度連動 設計書

## 背景・目的

`docs/analyses/20260719-lucario-rock-energy-20-games-analysis.md`（ロック闘エネルギー導入後20戦の分析）で、ユーザーがKaggleビジュアライザーの観戦で気づいた4点を検証した結果、2件の実バグが確定した。

1. **ex無効化のCrustle専用ハードコード**：`src/lucario_agent/main.py:244`の`defender_nullifies_ex_damage = defender_id == Crustle and attacker_id == Mega_Lucario_ex`は、カードID345（Crustle）のみを判定する固定ロジックで、相手フィールドを汎用的に読んで「ex技無効化」を検知する仕組みがない。Sylveon戦（`86803900`）でこの判定が働かず、メガルカリオexが0ダメージ攻撃を繰り返す一方、無効化を貫通できるオーガポンexにエネルギーが回らないまま敗北した。
2. **`calc_attack_plan`のスタジアム未考慮**：`86804728`のturn9、スタジアム「Nighttime Mine」（ID1266、テラスタルポケモンの技コスト+1）が場にあるにもかかわらず、`calc_attack_plan`がオーガポンexの技コストをスタジアム補正なしで計算し、3エネルギーで確定KOと誤算定した。この誤ったプランのせいでフルHPのメガルカリオexを不要に退却させ、オーガポンexをベンチの無敵状態から出してしまい、2ターン後に無駄死にした。

さらに、上記の分析レポートで「壁デッキ対面（Crustle系・Sylveon系）でオーガポンexが展開したのに攻撃に踏み切れない不発パターン」が複数試合で共通して見られると報告されている。この不発は、バグ1（ex無効化への気づきの欠如）と直接関連していると考えられる。相手が無効化持ちだと分かっていれば、本来はエネルギー配分・アクティブ交代の両方でオーガポンexを優先すべき場面である。

本設計では、ユーザーとの合意により以下3点を一体で扱う。

1. ex無効化検知の汎用化（静的レジストリ方式）
2. `calc_attack_plan`のNighttime Mineコスト考慮
3. 「相手アクティブがex無効化持ち」を軸にしたオーガポンexのエネルギー配分・SWITCH優先度の連動強化

**スコープ外（今回は対象としない）**：Full Metal Lab等、Nighttime Mine以外のスタジアム対応（ユーザー判断、次回持ち越し）。ex無効化検知を`skills`テキストの動的パターン検知にする案は、ローカルmacOS環境で`cg.api`の`lib.AllCard()`が動作せず実際のランタイムテキスト形式を検証できないためリスクが高いと判断し不採用（静的レジストリ方式を採用）。

## 設計1：ex無効化検知の汎用化

### 新規定数

```python
Sylveon = 330
EX_DAMAGE_NULLIFIER_IDS = frozenset({Crustle, Sylveon})
```

カードデータ調査の結果、「Prevent all damage done to this Pokémon by attacks from your opponent's Pokémon {ex}.」という完全一致の効果文を持つカードはCrustle（345）とSylveon（330）の2枚のみと確認済み（`data/EN_Card_Data.csv`）。類似カードのFarigiraf ex（「Basic Pokémon {ex}」限定）・Milotic ex（「Tera Pokémon」限定）・Cornerstone Mask Ogerpon ex（「Pokémon that have an Ability」限定）は、無効化対象の条件が異なるためレジストリに含めない。

### `_calc_attack_damage`の一般化

現状：
```python
defender_nullifies_ex_damage = defender_id == Crustle and attacker_id == Mega_Lucario_ex
```

変更後：
```python
attacker_is_ex = card_table[attacker_id].ex or card_table[attacker_id].megaEx
defender_nullifies_ex_damage = (
    not attack_ignores_defender_effects  # オーガポンexの「ぶちやぶる」は無効化を貫通するため対象外
    and defender_id in EX_DAMAGE_NULLIFIER_IDS
    and attacker_is_ex
)
```

「攻撃側がexかどうか」を`CardData`の構造化フィールド（`.ex`/`.megaEx`）から判定するため、将来デッキに別のexアタッカーが追加された場合も自動対応する。「防御側が無効化持ちか」はレジストリで判定し、新規カードが判明した場合はIDを1件追加するだけで済む。

オーガポンexの「効果無視」判定（`attack_ignores_defender_effects = attacker_id == Ogerpon_ex`）はこの一般化と独立で、従来通りID固定のまま変更しない。無効化を貫通できる技はオーガポンexの「ぶちやぶる」（技テキスト：相手のバトルポケモンにかかっている効果を計算しない）のみであり、この情報を汎用的に構造化フィールドから取得する手段が`CardData`にはないため（`skills`/`attacks`のテキストパースが必要になりランタイム未検証のリスクを負うため、上記スコープ外の判断と同じ理由でID固定を維持する）。

**重要（自己レビューで発見）**：`attacker_is_ex`はOgerpon_ex自身にも真になる（Ogerpon_exも「Pokémon ex」のため）。`attack_ignores_defender_effects`の除外条件を入れないと、Ogerpon_exの攻撃までCrustle/Sylveonに無効化されてしまい、「オーガポンexは無効化を貫通できる」という設計意図と矛盾する。この条件を先頭に置くことで回避する。

## 設計2：`calc_attack_plan`のスタジアム（Nighttime Mine）考慮

### 新規定数・ヘルパー関数

```python
Nighttime_Mine = 1266  # テラスタルポケモンの技コスト+1（両プレイヤー対象）

def _tera_stadium_cost_bonus(pokemon_id: int, stadium_id: int) -> int:
    """Nighttime Mine下でテラスタルポケモンが支払う追加コストを返す"""
    if stadium_id == Nighttime_Mine and card_table[pokemon_id].tera:
        return 1
    return 0
```

`tera`フラグ（`CardData.tera`）を使って判定するため、オーガポンex専用ではなくテラスタルポケモン全般に汎用対応する。

### `calc_attack_plan`への配線

- シグネチャに`stadium_id: int`を追加する。呼び出し元の`agent()`は既に`_get_stadium_id(state)`でスタジアムIDを保持しているため、`calc_attack_plan`呼び出し箇所に渡すだけでよい
- 各アタッカー候補の`energy_required`計算に`energy_required += _tera_stadium_cost_bonus(my_pokemon.id, stadium_id)`を追加する（非テラスタルポケモンは常に+0となるため、Mega_Lucario_ex/Solrockの分岐には影響しない）

Nighttime Mine下ではオーガポンexの技コストが3→4エネルギーとなり、3エネルギー時点での確定KO誤算定が解消される。

## 設計3：オーガポンexのエネルギー配分・SWITCH優先度の連動強化

### 相手アクティブの無効化判定

`agent()`内で1回だけ計算し、`_score_option`経由で`energy_score`・`_score_card_option`（SWITCH/TO_ACTIVE分岐）まで引き回す。

```python
op_active_nullifies_ex = (
    bool(op_state.active) and op_state.active[0] is not None
    and op_state.active[0].id in EX_DAMAGE_NULLIFIER_IDS
)
```

相手のベンチにいる無効化持ちは対象外とする（今アクティブに出ているポケモンだけが今ターンの攻撃対象になるため。Grimmsnarlエージェントの`op_active_id`と同じ考え方を踏襲）。

### `energy_score`への反映

```python
elif pokemon.id == Ogerpon_ex:
    if energy_count < 3:
        score += 80
    if attacker1:
        score += 40
    if op_active_nullifies_ex:
        score += 150
```

`+150`は、Riolu/Mega_Lucario_exの最大加点（`energy_count < 2`の`+100` + アクティブの`+10`＝合計110）を確実に上回る値として設定する。相手が無効化持ちのときは、通常なら優先されるはずのメガルカリオex側候補よりオーガポンexへのエネルギー装着が優先される。

### SWITCH/TO_ACTIVEへの反映

```python
elif card.id == Ogerpon_ex:
    score += 20 if energy_count >= 3 else 6
    if op_active_nullifies_ex:
        score += 30
```

Mega_Lucario_exの最大加点（`+20`）を上回る値として`+30`を設定し、相手が無効化持ちのときはオーガポンexが優先的にアクティブへ出るようにする。

### 数値についての注意

上記の加点値（+150、+30）はヒューリスティックな叩き台であり、絶対的な正解があるわけではない。実装時のテストでは「相手が無効化持ちのとき、Ogerpon_exが他候補より優先される」という相対的な順序を検証し、具体的な数値は将来のチューニングで調整可能とする。

## テスト方針（TDD）

1. **`_calc_attack_damage`の一般化**：
   - Crustle/Sylveon以外の相手に対してはMega_Lucario_exの攻撃が通常通りダメージを与えること（回帰確認）
   - Crustle・Sylveonそれぞれに対してMega_Lucario_exの攻撃が0ダメージになること
   - Crustle・Sylveonに対してもOgerpon_exの攻撃（ぶちやぶる）は貫通してダメージを与えること
2. **`calc_attack_plan`のスタジアム考慮**：
   - Nighttime Mine下でOgerpon_exの技が4エネルギー要求に変わり、3エネルギーでは攻撃候補として選ばれないこと
   - Nighttime Mine以外のスタジアム・スタジアム無しでは従来通り3エネルギーで攻撃候補になること（回帰確認）
   - Mega_Lucario_ex/Solrock（非テラスタル）はNighttime Mine下でもコストが変化しないこと
3. **オーガポンex優先度連動**：
   - `energy_score`：`op_active_nullifies_ex=True`のとき、Ogerpon_exのスコアがRiolu/Mega_Lucario_exの候補スコアを上回ること
   - `op_active_nullifies_ex=False`のときは従来通りの優先順位のままであること（回帰確認）
   - SWITCH/TO_ACTIVE：同条件でOgerpon_exのスコアがMega_Lucario_exを上回ること
4. **既存テストの回帰確認**：`uv run pytest -q`で全件PASSを維持する

## 構造面の確認（YAGNI判断）

`feedback_fix_and_refactor_together`の方針に従い、今回touchする`energy_score`・`calc_attack_plan`・`_score_card_option`の構造的負債（if/elif連鎖）を確認した。今回の変更はいずれも既存の分岐に条件付き加点を追加する形（新しい枝を増やすのではなくパラメータを増やす形）であり、新規の構造的負債を生まない。`calc_attack_plan`のアタッカー候補テーブル化（2026-07-06/07に検討・YAGNIで複数回見送り済み）は今回のスコープに含めない。
