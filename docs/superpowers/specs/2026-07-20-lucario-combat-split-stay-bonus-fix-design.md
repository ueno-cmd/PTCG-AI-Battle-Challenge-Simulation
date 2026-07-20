# ルカリオexデッキ combat.py切り出し・居座りボーナス修正 設計書

## 背景・目的

`docs/analyses/20260720-lucario-ex-nullifier-fix-verification-20-games.md`（ex無効化汎用化・スタジアム考慮修正後20戦の検証）で、ユーザーがKaggleビジュアライザーの観戦で気づいた4点を検証した結果、`calc_attack_plan`（`src/lucario_agent/main.py:274-401`）に実バグが確定した。

現在アクティブなポケモンを優先する「居座りボーナス」（`i==0`で+220・`j==0`で+300、main.py:387-390）が、実ダメージの多寡と無関係に加算されるため、**Crustle/Sylveonに対し0ダメージと分かっている攻撃のプランスコアが、実ダメージの出る控えのSolrock/Ogerpon exへの切替プランより高くなるケースがある**。試合`86898758`で実測：交代（RETREAT）の選択肢自体は一貫して提示されていたにも関わらず、9ターン連続でMega Lucario exの0ダメージ攻撃が選ばれ続けた。RETREATのスコア式（`case OptionType.RETREAT: return 2000 if current_plan.attacker >= 1 else -1`・main.py:753）が`calc_attack_plan`の出力に完全依存する二段構えのため、誤ったプラン選択がそのまま「交代しない」という行動選択に直結する。

ユーザーがビジュアライザー観戦で気づいた4点（①ソルロックへのエネルギー過剰投資、②オーガポンでなくベンチのルカリオにエネルギーが回る、③イワパレス対面で交代せず殴り続ける「出遅れバグ」、④ベンチに手張りすると逃げられない構造）は、いずれもこの一連の意思決定チェーン（エネルギー配分→`calc_attack_plan`のプラン選択→交代するかどうか）の中で説明できる。

併せて、ユーザーから「`main.py`（現状826行）を修正しやすくするため、この意思決定チェーンを別ファイルに切り出せないか」との提案があり、さらに「各カードのエネルギー条件を手打ちではなくテキスト情報から検証できる仕組みを将来のために仕込めないか」との追加要望があった。本設計ではこれらを一体で扱う。

## スコープ

### 今回やること

1. `src/lucario_agent/combat.py`への機能切り出し（意思決定チェーンの集約）
2. `calc_attack_plan`の居座りボーナス修正（本命バグ）
3. `EN_Card_Data.csv`とのエネルギー条件突き合わせテストの新設
4. 提出用ビルドスクリプトの新設

### 今回やらないこと

- `energy_score`のOgerpon ex優先度自体の変更（後述の試算で現状の`+150`ボーナスは既に正しく機能していると判断できるため、様子見とする）
- `all_attack()`/CSVベースの本格的なアタッカーテーブル化（2026-07-07に中断した案。3.の一致テストが将来の足がかりになるが、実装自体は次回以降に持ち越す）
- Crustle壁への根本対策（今回の4連敗は小サンプルでの偶然の可能性が高いため、本修正の効果を見てから再評価する）
- Nighttime Mineスタジアム考慮の実戦検証（引き続き未出現で持ち越し）

## 設計1：`combat.py`への切り出し

### 対象

`src/lucario_agent/combat.py`（新規）に以下を移動する。

- `AttackPlan`データクラス（main.py:77-82）
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

現状、`_calc_attack_damage`（`card_table[attacker_id].ex`等）と`_tera_stadium_cost_bonus`（`card_table[pokemon_id].tera`）は、`main.py`モジュール直下のグローバル変数`card_table`（`_build_card_table()`が`global card_table`で更新する辞書）を暗黙に参照している。この2関数を`combat.py`へ移動すると、`combat.py`が`main.py`の同じ辞書インスタンスを暗黙に参照する手段がなくなる（`from lucario_agent.main import card_table`は値のコピーを束縛してしまい、後から`main.py`側で辞書が更新されても`combat.py`側の参照は更新前の空辞書のままになる、かつ循環importでもある）。

そのため、この2関数と`calc_attack_plan`のシグネチャに`card_table: dict`を明示的な引数として追加し、暗黙のグローバル参照をやめる。呼び出し元の`agent()`（main.py側に残る）は、既に`_build_card_table()`で取得した`card_table`を持っているため、`calc_attack_plan(...)`呼び出し時に`card_table=card_table`を渡すだけでよい。

```python
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

## 設計2：居座りボーナスの修正

### 現状のコード（main.py:366-391、移動後はcombat.py）

```python
prize = 0
score = pokemon_score(op_pokemon)
if op_pokemon.hp <= damage:
    prize = prize_count(op_pokemon)
else:
    score *= damage / op_pokemon.hp
score += base_score
...
if len(op_state.prize) <= prize:
    score = 50000

if i == 0:
    score += 220
if j == 0:
    score += 300
score += energy_count
```

`damage`が0（ex無効化貫通不可）のとき、`score *= damage / op_pokemon.hp`で`score`は0になるが、その後に加算される`i==0`(+220)・`j==0`(+300)の位置ボーナスは無条件に乗ってしまう。この結果、0ダメージプランのスコアが「実ダメージは出るが今アクティブではない（`i!=0`のため+220が付かない）」候補を上回るケースが生まれる。

### 修正後

```python
if damage > 0:
    if i == 0:
        score += 220
    if j == 0:
        score += 300
score += energy_count
```

位置ボーナスを`damage > 0`の場合のみ加算するよう変更する。`base_score`（Mega Lucario exの通常技「Aura Jab」が持つ、捨て山の基本闘エネルギーをベンチに再配置する効果に由来する加点、最大180）はダメージの有無と無関係に発生する副次効果のため、意図的にゲートしない。

### 試算による効果確認（Crustle対面、Mega Lucario ex vs Solrock切替の比較）

| 候補 | 現状スコア | 修正後スコア |
|---|---|---|
| Mega Lucario ex継続（0ダメージ、`i=0,j=0`） | 220+300+base_score(最大180)+energy_count ≈ 522〜702 | base_score(最大180)+energy_count ≈ 182 |
| Solrockへ切替（実ダメージ70、`i=1,j=0`） | pokemon_score×(70/hp)+300+energy_count ≈ 441 | 変化なし（`i≠0`のため元々+220は付かない）≈ 441 |

修正前はMega Lucario exの0ダメージ継続（522〜702）がSolrock切替（441）を上回っていたが、修正後は逆転し（182 < 441）、Solrockへの切替が正しく選ばれる。これに伴い`_score_retreat_option`（`current_plan.attacker >= 1`で+2000）が有効化され、RETREATの選択スコアが攻撃継続を上回るため、実際の交代行動につながる。

### `energy_score`は変更しない（設計判断）

「相手がex無効化持ちのとき、Ogerpon exへエネルギーを優先する」ボーナス（`op_active_nullifies_ex`時+150、main.py:179-180）を含む現行の`energy_score`を試算したところ、`op_active_nullifies_ex=True`の場面ではOgerpon ex（最大8230点）が既にMega Lucario ex/Riolu（最大8111点）・Solrock（8020点）を上回っており、優先順位自体は正しく機能している。ユーザーが観測した「ベンチのルカリオにエネルギーが回る」現象は、**Crustle対面と判明する前のターンに既にMega Lucario exへ投資済みだったエネルギーが後から動かせない**という試合展開上の制約であり、`energy_score`のロジック自体の誤りではないと判断する。したがって今回`energy_score`のスコア値は変更しない。

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
2. **居座りボーナス修正**：
   - Crustle/Sylveon対面で、0ダメージ確定のMega Lucario ex継続プランより、実ダメージが出るSolrock/Ogerpon exへの切替プランが選ばれること（新規テスト）
   - Crustle/Sylveon以外の通常対面では、位置ボーナスの有無による選択の変化がないこと（回帰確認）
   - 全ての候補が0ダメージの場合（詰み盤面）でも、従来通りいずれかのプランが選ばれること（フォールバック確認）
   - `_score_retreat_option`：`calc_attack_plan`が切替を選んだ場合にRETREATが攻撃継続より高スコアになること
3. **エネルギー条件突き合わせテスト**：設計3の4パターン全てで手打ち値とCSV由来の期待値が一致すること
4. **ビルドスクリプト**：生成された結合ファイルが構文エラーなくimportできること（`ast.parse()`または実際に`exec`せず`compile()`での構文チェック）、`def agent(`が結合後ファイルに含まれること
5. **既存テストの回帰確認**：`uv run pytest -q`でリポジトリ全体が全件PASSを維持する

## 構造面の確認（YAGNI判断）

`feedback_fix_and_refactor_together`の方針に従い、今回touchする`calc_attack_plan`の構造的負債（if/elif連鎖によるアタッカー候補判定）を確認した。今回の修正はスコア式に条件（`damage > 0`）を1つ追加するだけで、新しい分岐や責務を増やすものではない。`calc_attack_plan`のアタッカー候補テーブル化（2026-07-06/07に検討・YAGNIで複数回見送り済み）は今回のスコープに含めないが、設計3のテストがその際の検証手段として再利用できる形にしてある。
