# ルカリオexデッキ combat.py切り出し・energy_score無効化考慮修正 設計書

## 背景・目的

`docs/analyses/20260720-lucario-ex-nullifier-fix-verification-20-games.md`（ex無効化汎用化・スタジアム考慮修正後20戦の検証）で、ユーザーがKaggleビジュアライザーの観戦で気づいた4点（①ソルロックへのエネルギー過剰投資、②オーガポンでなくベンチのルカリオにエネルギーが回る、③イワパレス対面で交代せず殴り続ける「出遅れバグ」、④ベンチに手張りすると逃げられない構造）を検証する過程で、当初は`calc_attack_plan`の「居座りボーナス」（現在アクティブなポケモンを優先する`i==0`+220・`j==0`+300、main.py:387-390）が本命バグだと考えていた。

しかし設計・実装計画の作成中に、実カードデータ・実バトルログを使った再検証（`docs/reviews/20260720-lucario-combat-decision-logic-audit.md`）で、**この「居座りボーナス」仮説はYAGNIで撤回した**。`pokemon_score`のプライズ枚数×1000という下駄が大きすぎるため、位置ボーナス（最大520点）が実際の決定を左右する場面は、数式的な境界条件の導出でも実バトルログ3戦の再現検証でも確認できなかった。

代わりに、同じレビューで**`energy_score`関連の実バグ2件**が実ログの直接再現で確定した。

1. `_score_card_option`のATTACH_FROMケース（main.py:486-487）が`op_active_nullifies_ex`引数を`energy_score`へ渡し忘れている。このケースはメガルカリオexの通常技「アクセルジャブ」自身の効果（捨て札のエネルギーを最大3枚ベンチへ再配置）で毎ターン使われる主要チャネルで、テストは0件だった
2. `energy_score`のMega_Lucario_ex/Riolu分岐（main.py:167-173）に、相手がex無効化持ちのときの減点が一切ない（Ogerpon_exには対になる`+150`ボーナスがあるのに非対称）

さらに、`_score_attach_option`のRock_Fighting_Energyへの「アクティブ優先+500」ボーナス（main.py:697-700）が、対戦相手を見ずに無条件加算されるため、上記の修正後もCrustle対面でOgerpon exへの優先ボーナスを上書きしてしまう問題も見つかった（発生条件は狭いが実装は単純なため今回まとめて対応する）。

ユーザーの指摘（③④）は、当初想定した「居座りボーナス」ではなく、この一連の**エネルギー配分の意思決定チェーン**（`energy_score`とその呼び出し元）のバグで説明できる。

併せて、ユーザーから「`main.py`（現状826行）を修正しやすくするため、この意思決定チェーンを別ファイルに切り出せないか」との提案があり、さらに「各カードのエネルギー条件を手打ちではなくテキスト情報から検証できる仕組みを将来のために仕込めないか」との追加要望があった。本設計ではこれらを一体で扱う。

## スコープ

### 今回やること

1. `src/lucario_agent/combat.py`への機能切り出し（意思決定チェーンの集約）
2. `energy_score`関連3件の修正（本命バグ）：
   - ATTACH_FROMケースの`op_active_nullifies_ex`転送漏れ修正
   - `energy_score`のMega_Lucario_ex/Riolu分岐への減点追加
   - Rock_Fighting_Energyの「アクティブ優先+500」を無効化持ち対面では抑制
3. `EN_Card_Data.csv`とのエネルギー条件突き合わせテストの新設
4. 提出用ビルドスクリプトの新設

### 今回やらないこと

- `calc_attack_plan`の「居座りボーナス」修正（実害を再現できずYAGNIで撤回。経緯は`docs/reviews/20260720-lucario-combat-decision-logic-audit.md`参照）
- RETREATスコア式へのHP温存観点の追加（同レビューで新規発見。設計判断が必要なため別途ブレストする）
- ソルロックの「弱点・抵抗力を無視する」効果の`_calc_attack_damage`未実装（同レビューで発見。Crustleとは無関係の軽微な潜在バグのため見送り）
- `all_attack()`/CSVベースの本格的なアタッカーテーブル化（2026-07-07に中断した案。3.の一致テストが将来の足がかりになるが、実装自体は次回以降に持ち越す）
- Crustle壁への根本対策（今回の4連敗は小サンプルでの偶然の可能性が高いため、本修正の効果を見てから再評価する）
- Nighttime Mineスタジアム考慮の実戦検証（引き続き未出現で持ち越し）

## 設計1：`combat.py`への切り出し

### 対象

`src/lucario_agent/combat.py`（新規）に以下を移動する。

- `AttackPlan`データクラス（main.py:77-82）
- `prize_count`（main.py:122-132）・`pokemon_score`（main.py:135-151）：`calc_attack_plan`が内部で直接呼び出しており、かつ両関数とも`card_table`を参照するため、`_tera_stadium_cost_bonus`と同じ理由（main.pyへの逆import回避）で同時に移動する。他の呼び出し元は存在しない（grep確認済み）
- `energy_score`（main.py:154-181）
- `_calc_attack_damage`（main.py:252-271）
- `_tera_stadium_cost_bonus`（main.py:222-226）：`calc_attack_plan`が内部で直接呼び出しており（main.py:335）、切り離すと`main.py`への逆import（循環import）が必要になるため同時に移動する
- `calc_attack_plan`（main.py:274-401）
- `_score_option`の`match`文に埋め込まれている`OptionType.RETREAT`・`OptionType.ATTACK`ケース（main.py:752-760）を、それぞれ`_score_retreat_option(current_plan) -> int`・`_score_attack_option_choice(o, current_plan) -> int`として関数化した上で移動
- `EPSILON`（main.py:39、`calc_attack_plan`のメガブレイブ探索判断でのみ使用）

これらは「エネルギーがどこに行くか→どのポケモンで何を狙うか→交代するかどうか」という1本の意思決定チェーンを構成しており、ユーザー指摘の4点全てがこのチェーンの中で起きている。トレーナーズカードのPLAY判断（`TrainerCardPolicy`群）やデッキ読み込み・エージェント入口はこのチェーンと無関係なため`main.py`に残す。

`_rng`（`random.Random()`の実乱数インスタンス、main.py:40）は`calc_attack_plan`（移動）と`_score_play_option`配下のポリシークラス（main.py:568、main.py残留）の両方で使われているが、どちらも「デフォルトの実乱数」としての役割のみで、2つのインスタンスが同一オブジェクトである必要はない（テスト時は`rng`引数でスタブを注入する設計のため）。`combat.py`・`main.py`それぞれが独立に`_rng = random.Random()`を持つ（意図的な重複、共有state化はしない）。

### 新規`constants.py`

`main.py`の「カードID定数」ブロック（main.py:12-36、`Lunatone`から`EX_DAMAGE_NULLIFIER_IDS`まで）を`src/lucario_agent/constants.py`（新規）へ移動する。`combat.py`・`main.py`の両方がこのカードID定数群を必要とする（例：`Solrock`・`Ogerpon_ex`・`Mega_Lucario_ex`は`combat.py`の攻撃プラン計算と、`main.py`に残る`_score_card_option`のSWITCH/TO_ACTIVE分岐の両方で参照される）ため、どちらか一方に定義して他方からimportすると循環importになる。`EPSILON`は上記の通り`combat.py`側に置くため`constants.py`には含めない。

### `main.py`側の変更

```python
from lucario_agent.constants import (
    Lunatone, Solrock, Riolu, Mega_Lucario_ex, Ogerpon_ex,
    Crustle, Sylveon, EX_DAMAGE_NULLIFIER_IDS, Nighttime_Mine,
    # ...main.py に残る他の定数も含め、constants.py 全体をそのままimportする
)
from lucario_agent.combat import (
    AttackPlan,
    energy_score,
    _calc_attack_damage,
    calc_attack_plan,
    _score_retreat_option,
    _score_attack_option_choice,
)
```

`_score_option`内の該当`case`は関数呼び出しに置き換える：

```python
case OptionType.RETREAT:
    return _score_retreat_option(current_plan)
case OptionType.ATTACK:
    return _score_attack_option_choice(o, current_plan)
```

### `card_table`の暗黙グローバル参照を解消する

現状、`prize_count`・`pokemon_score`（`card_table[pokemon.id]`）・`_calc_attack_damage`（`card_table[attacker_id].ex`等）・`_tera_stadium_cost_bonus`（`card_table[pokemon_id].tera`）は、`main.py`モジュール直下のグローバル変数`card_table`（`_build_card_table()`が`global card_table`で更新する辞書）を暗黙に参照している。この4関数を`combat.py`へ移動すると、`combat.py`が`main.py`の同じ辞書インスタンスを暗黙に参照する手段がなくなる（`from lucario_agent.main import card_table`は値のコピーを束縛してしまい、後から`main.py`側で辞書が更新されても`combat.py`側の参照は更新前の空辞書のままになる、かつ循環importでもある）。

そのため、この4関数と`calc_attack_plan`のシグネチャに`card_table: dict`を明示的な引数として追加し、暗黙のグローバル参照をやめる。呼び出し元の`agent()`（main.py側に残る）は、既に`_build_card_table()`で取得した`card_table`を持っているため、`calc_attack_plan(...)`呼び出し時に`card_table=card_table`を渡すだけでよい。

```python
def prize_count(pokemon: Pokemon, card_table: dict) -> int:
    ...
    data = card_table[pokemon.id]
    ...

def pokemon_score(pokemon: Pokemon, card_table: dict) -> int:
    ...
    data  = card_table[pokemon.id]
    score = prize_count(pokemon, card_table) * 1000
    ...

def _calc_attack_damage(attacker_id: int, base_damage: int, defender_id: int, defender_data, card_table: dict) -> int:
    ...
    attacker_is_ex = card_table[attacker_id].ex or card_table[attacker_id].megaEx
    ...

def _tera_stadium_cost_bonus(pokemon_id: int, stadium_id: int, card_table: dict) -> int:
    if stadium_id == Nighttime_Mine and card_table[pokemon_id].tera:
        return 1
    return 0

def calc_attack_plan(obs, my_state, op_state, state, field_counts, hand_counts, discard_counts,
                     can_switch, can_op_switch, can_use_mega_brave, can_attack, my_prize,
                     card_table: dict, stadium_id: int = 0, rng: "random.Random | None" = None) -> AttackPlan:
    ...
```

これは暗黙のモジュール間共有状態を除去する副次的な構造改善であり、`feedback_fix_and_refactor_together`の方針（動作修正と同時に構造整理も行う）にも合致する。

## 設計2：`energy_score`関連3件の修正

`docs/reviews/20260720-lucario-combat-decision-logic-audit.md`で確定した3件の実バグを、いずれもエネルギー配分の意思決定チェーンに属するため一体で修正する。

### 2-1. ATTACH_FROMケースの転送漏れ（main.py:486-487）

現状：

```python
case SelectContext.ATTACH_FROM:
    return energy_score(card, o.area == AreaType.ACTIVE, attacker1)
```

修正後：

```python
case SelectContext.ATTACH_FROM:
    return energy_score(card, o.area == AreaType.ACTIVE, attacker1, op_active_nullifies_ex)
```

`SelectContext.ATTACH_FROM`はメガルカリオexの通常技「アクセルジャブ」自身の効果（捨て札から基本闘エネルギーを最大3枚、好きなベンチポケモンへ再配置する）に対応する選択コンテキストで、メガルカリオexが攻撃するほぼ毎ターン使われる。もう一つの呼び出し元`_score_attach_option`（main.py:696、`combat.py`移動後も`main.py`に残る）は既に`op_active_nullifies_ex`を正しく転送しており、この箇所だけの片手落ちだった。

### 2-2. `energy_score`のMega_Lucario_ex/Riolu分岐への減点追加（main.py:167-173、移動後はcombat.py）

現状：

```python
elif pokemon.id in (Riolu, Mega_Lucario_ex):
    if pokemon.id == Mega_Lucario_ex:
        score += 1
    if energy_count < 2:
        score += 100
    if attacker1:
        score -= 50
```

修正後：

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

Ogerpon_exの分岐には「相手がex無効化持ちなら優先」の`+150`ボーナスがあるが、対になる減点がMega_Lucario_ex/Riolu側に存在しなかった。`Riolu`は`calc_attack_plan`のアタッカー候補に含まれておらず（Mega Lucario exへの進化前段階としてのみ存在）、Riolu自身へのエネルギー投資もいずれ同じ無効化を受けるMega Lucario exを育てることに繋がるため、Riolu/Mega_Lucario_ex共通の分岐に同じ減点を適用する。

`-150`はOgerpon exの`+80`（`energy_count<3`）ボーナスを確実に下回らせる値として設定する：修正後のMega_Lucario_ex最大スコアは`8101-150=7951`、Ogerpon exの最小スコア（`energy_count<3`のみ、`attacker1`なし）は`8000+80+150=8230`となり、常にOgerpon exが優先される。ソルロック（8020、変更なし）も相対的に優先されるようになる。

**実測での裏付け**（`docs/reviews/20260720-lucario-combat-decision-logic-audit.md`参照）：実ログ86898758のturn3・turn11を実コードで再現した結果、2-1・2-2の修正前は「メガルカリオex8051点 vs ソルロック8020点」「リオル8100点 vs ソルロック8020点」でルカリオ側が実際に選ばれ続けていたことを確認済み。

### 2-3. Rock_Fighting_Energyの無条件+500ボーナスの抑制（main.py:697-700、移動後はcombat.py配下の`_score_attach_option`は main.py 残留）

現状：

```python
if card.id == Rock_Fighting_Energy and o.inPlayArea == AreaType.ACTIVE:
    # Alakazam「ハンドパワー」はアクティブのポケモンのみを狙うため、
    # そのときアクティブの子を優先的に守る
    score += 500
```

修正後：

```python
if card.id == Rock_Fighting_Energy and o.inPlayArea == AreaType.ACTIVE:
    attacker_is_ex = card_table[pokemon.id].ex or card_table[pokemon.id].megaEx
    if not (op_active_nullifies_ex and attacker_is_ex):
        score += 500
```

Alakazam「ハンドパワー」対策として書かれたこのボーナスは対戦相手を見ずに無条件加算されるため、2-1・2-2の修正後も、Crustle/Sylveon対面でアクティブのexポケモンへロック闘エネルギーを装着する場面では、Ogerpon exへの優先ボーナスを`+500`で上書きしてしまう。攻撃対象がex（Crustle/Sylveonに無効化される）かつ相手が無効化持ちのときだけ抑制する。`_score_attach_option`は`combat.py`への移動対象に含まれていない（main.py残留）ため、`energy_score`同様に`combat.py`からimportして使う形になる。

## 設計3：エネルギー条件の食い違い検知テスト

`data/competition/EN_Card_Data.csv`には各技の`Cost`（例：`{F}●●`）・`Damage`列があり、`libcg.so`（macOSで実行不可）を経由せずに手元のCSVだけでエネルギー要求数・威力を機械的に検証できる。

新規テスト`tests/test_lucario_attacker_energy_consistency.py`を追加し、`combat.py`の`calc_attack_plan`が使う以下の手打ち値を、CSVから独立に計算した期待値と突き合わせる。

| ポケモン | 技 | 手打ち値（現状） | CSV(`Cost`/`Damage`) |
|---|---|---|---|
| Mega Lucario ex | Aura Jab | 1エネ・130ダメ | `{F}`・130 |
| Mega Lucario ex | Mega Brave | 2エネ・270ダメ | `{F}{F}`・270 |
| Solrock | Cosmic Beam | 1エネ・70ダメ | `{F}`・70 |
| Cornerstone Mask Ogerpon ex | Demolish | 3エネ・140ダメ | `{F}●●`・140 |

`Cost`文字列内の記号数（`{F}`や`●`等、1記号=1エネルギー）をカウントする軽量パーサーをテスト内に実装し、エネルギー総数を比較する（エネルギータイプ別の内訳までは検証対象としない。現行コードも`energy_count = len(pokemon.energies)`で総数のみを見ているため、検証粒度をコードの実際の使用範囲に合わせる）。

このテストは今回の修正の正しさを保証するものではなく、**将来`all_attack()`/CSVベースのテーブル化に着手する際、新実装が現行の手打ち値と同じ結果を再現できているかの回帰テストとして転用できる**ことを狙いとする。

## 設計4：提出用ビルドスクリプト

`scripts/build_lucario_submission_main.py`（新規）を追加する。`src/lucario_agent/constants.py` + `combat.py` + `main.py`の内容を結合し、`main.py`側の`from lucario_agent...`のimport文を取り除いた上で1ファイルに連結したテキストを標準出力（または`--out`オプション指定時はファイル）に出力する。既存の`scripts/build_lucario_selfcheck_notebook.py`が「複数ソースを読み込んでビルド時に結合する」パターンを既に持っているため、同じ考え方を踏襲する。

ユーザーの実際の提出フロー（Kaggleノートブックの`%%writefile main.py`セルへの手動コピペ）は今回変更しない。このスクリプトが生成した結合済みファイルをコピペ元にすることで、複数ファイルを手で辻褄合わせする手間と、それに伴うタイポ混入リスク（過去の「iimport os」インシデント）を減らす。

## テスト方針（TDD）

1. **`combat.py`切り出し**：既存の`tests/test_lucario_agent.py`は`import lucario_agent.main as lm`で全ての定数・関数に`lm.X`としてアクセスしている（416箇所）。`main.py`が移動対象を`from lucario_agent.combat import ...`・`from lucario_agent.constants import ...`で再exportする形にするため、**テストファイル自体は一切変更せずに全件継続PASSする**想定（Pythonの仕様上、importした名前は元のモジュールの属性としても参照できるため）。これを実際に`uv run pytest -q`で確認し、想定通りゼロ変更でPASSすることを検証する
2. **`energy_score`関連3件の修正**：
   - ATTACH_FROMケース：`op_active_nullifies_ex=True`のとき、Ogerpon_exが渡された場合のスコアがMega_Lucario_exより高くなること（修正前は転送漏れにより同じ結果にならないことを回帰確認）
   - `energy_score`のMega_Lucario_ex/Riolu分岐：`op_active_nullifies_ex=True`のとき、Ogerpon_ex（`energy_count<3`のみ）のスコアがMega_Lucario_ex（`energy_count<2`のみ）を上回ること。`op_active_nullifies_ex=False`のときは従来通りの優先順位のままであること（回帰確認）
   - Rock_Fighting_Energyのアクティブ優先ボーナス：`op_active_nullifies_ex=True`かつ対象がexのときは`+500`が付与されないこと。それ以外（`op_active_nullifies_ex=False`、または対象が非ex）では従来通り`+500`が付与されること（回帰確認）
3. **エネルギー条件突き合わせテスト**：設計3の4パターン全てで手打ち値とCSV由来の期待値が一致すること
4. **ビルドスクリプト**：生成された結合ファイルが構文エラーなくimportできること（`ast.parse()`または実際に`exec`せず`compile()`での構文チェック）、`def agent(`が結合後ファイルに含まれること
5. **既存テストの回帰確認**：`uv run pytest -q`でリポジトリ全体が全件PASSを維持する

## 構造面の確認（YAGNI判断）

`feedback_fix_and_refactor_together`の方針に従い、今回touchする`energy_score`・`_score_card_option`・`_score_attach_option`の構造的負債を確認した。今回の修正はいずれも既存の条件分岐に1行の条件・引数を追加するだけで、新しい分岐や責務を増やすものではない。`calc_attack_plan`のアタッカー候補テーブル化（2026-07-06/07に検討・YAGNIで複数回見送り済み）は今回のスコープに含めないが、設計3のテストがその際の検証手段として再利用できる形にしてある。
