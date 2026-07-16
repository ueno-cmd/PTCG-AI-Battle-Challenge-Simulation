# ジャモライコデッキ ビリリダマ軸ピボット 設計書

## 背景・目的

2026-07-14までの校正ノートブック実測（ジャモライコ vs イオナサンプル、200試合）で、ジャモライコの勝率は3回の改修を経ても2〜4.5%で頭打ちだった。`superpowers:systematic-debugging`によるログ解析で、根本原因は個々のロジックバグではなく**デッキ構築（エネルギー配分）の構造的ボトルネック**と特定済み：

- 主砲「きょくらいごう」（タケルライコex, id=63）は雷1闘1の同時保持が必須
- デッキ60枚中、基本闘エネルギーはわずか3枚（対して基本雷エネルギーは12枚）
- 実測ログでは10試合中、闘エネルギーの装填が18回発生したにもかかわらず、きょくらいごう発動はわずか4回。希少な闘エネルギーを的確に集中させ続けることが構造的に困難

ユーザー判断：タケルライコex・闘エネルギー依存を解消し、**ナンジャモのビリリダマ（id=265）の「チェインボルト」**（コスト無色2、20+自分の場の全ナンジャモポケモンの雷エネルギー数×20ダメージ）を主軸に寄せる方向にピボットする。ビリリダマは技コストに闘エネルギーを一切要求せず、ダメージも場全体の雷エネルギー合計で決まるため、今回のボトルネックを構造的に解消できる。

## デッキ変更

対象ファイル：`decks/jamoraiko_20260713.py`（既存ファイルをそのまま改修。過去のグリムスナールデッキ改修と同じ方式でファイル名は変えない）

| カード | 変更前 | 変更後 |
|---|---|---|
| タケルライコex (id=63) | 2枚 | 0枚（削除） |
| ナンジャモのビリリダマ (id=265) | 1枚 | 3枚 |
| 基本闘エネルギー (id=6) | 3枚 | 0枚（削除） |
| 基本雷エネルギー (id=4) | 12枚 | 15枚 |

他のカードは変更なし。増減合計は±0（-2-3+2+3=0）で60枚を維持する。

「エネルギーつけかえ」（Energy_Switch, id=1116, 2枚）は**デッキに残し**、後述の通り運用目的をタケルライコex向けからハラバリーex/タイカイデン向けに作り直す。

## コード変更方針（`src/jamoraiko_agent/main.py`）

### 削除する死んだコード（タケルライコex専用ロジック）

タケルライコex・基本闘エネルギーがデッキから消えることで、以下は実戦で二度と到達しないロジックになるため削除する（[[feedback_fix_and_refactor_together]]の方針：動作変更とリファクタは同時に行う）。

- 定数：`Raging_Bolt_ex`、`Basic_Fighting_Energy`
- `FieldState.active_fighting_energy_count`／`own_board_basic_energy_total`とその集計処理（`_collect_field_state`内）。`own_board_basic_energy_total`はきょくらいごうのダメージ計算専用で他に利用箇所なし
- `ATTACKERS`テーブルのタケルライコexの2技（Bellowing Thunder＝きょくらいごう、Burst Roar＝はじけるほうこう）
- `Attacker.requires_fighting`／`Attacker.is_utility`フィールド（削除後に残る3技はいずれも使わない）
- `POKEMON_LINES`のタケルライコexエントリ
- `calc_attack_plan`内のrequires_fighting判定、is_utility関連の温存ロジック（山札温存チェック・きょくらいごうへの伸びしろ判定によるはじけるほうこう抑制）、is_lethal算出のis_utility除外（残り3技はいずれもダメージ技のため不要になる）
- `_is_attack_ready`の`fighting_count`パラメータとrequires_fighting判定
- `_score_attach_option`／`_score_search_candidate`／`_score_discard_candidate`内の基本闘エネルギー分岐
- `EnergyPolicy.has_growth_path`（`calc_attack_plan`の利用箇所ごと削除するため）
- `EnergyPolicy.discard_for_damage_score`と`_score_energy_card_option`の`SelectContext.DISCARD_ENERGY_CARD`ケース（きょくらいごうの追加ダメージ用エネルギー破棄専用のため、他に破棄でダメージを増やす技がデッキ内に存在しない）

### 付随する修正

- `POKEMON_LINES`のビリリダマ`max_field_copies`を2→3に変更する。デッキの採用枚数を3枚に増やしたため、この値を合わせないと3枚目の温存・サーチ優先度スコアリングが正しく機能しない

### EnergyPolicyの作り直し（Energy_Switchの目的変更）

`EnergyPolicy`は「タケルライコexへのエネルギー集中」から「アクティブのハラバリーex（4エネ必要）/タイカイデン（3エネ必要）が攻撃可能本数に届いていない時、既に届いているベンチの同ラインから余剰の雷エネルギーを回す」という汎用ロジックに書き換える。

- `needs_lightning`：「場のどこかにタケルライコexがいて雷0枚か」の全体スキャン→「**アクティブ**が`SURPLUS_THRESHOLD`に含まれるポケモン（ハラバリーex/タイカイデン）で、自身の雷エネルギー数が閾値未満か」に変更
- `find_surplus_source`：ロジック自体は維持（`SURPLUS_THRESHOLD`辞書ベースで、非アクティブのベンチから閾値以上の雷エネルギーを持つ1体を探す）。タケルライコex除外前提のコメントを削除
- `switch_destination_score`：「タケルライコexなら+500/-500、それ以外0」→「`SURPLUS_THRESHOLD`に含まれるポケモンが閾値未満なら+500、閾値以上なら-500、含まれなければ0」に一般化
- `switch_source_score`：「タケルライコex自身は-1000」の特殊分岐を削除し、`SURPLUS_THRESHOLD`ベースの閾値判定のみにする
- `attach_priority`：タケルライコex用のelif分岐を削除

## テスト方針

- `tests/test_jamoraiko_deck.py`：デッキ内容変更（タケルライコex0枚・闘エネ0枚・ビリリダマ3枚・雷エネ15枚）に合わせて更新
- `tests/test_jamoraiko_agent.py`：タケルライコex関連テスト（約20箇所）のうち、削除したロジックの回帰確認にしかならないものは削除。EnergyPolicy再設計に伴い、「アクティブのハラバリーex/タイカイデンが閾値未満の時、届いているベンチの同ラインから正しくエネルギーを回せるか」を検証するテストに書き直す
- 既存の`test_score_attach_option`等、闘エネルギー分岐を削除した箇所は該当テストケースも削除
- リポジトリ全体`uv run pytest -q`で全PASSを確認する

## スコープ外（今回は着手しない）

- カイデン（id=270）がATTACKERSテーブルに未登録の件（軽微なロジック穴、既知の問題として別途持ち越し中）
- 校正ノートブック（`jamoraiko_vs_iono_experiment.ipynb`）・Kaggle提出用ノートブックへの転記・再ビルド・実測はユーザー側で別途実施する
