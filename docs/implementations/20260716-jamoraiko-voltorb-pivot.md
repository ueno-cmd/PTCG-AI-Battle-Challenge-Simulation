# ジャモライコ ビリリダマ軸ピボット 実装サマリー

## 背景

2026-07-14までの校正ノートブック実測で、ジャモライコの勝率は複数回の改修を経ても2〜4.5%で頭打ちだった。根本原因は「きょくらいごう」（タケルライコex）が要求する雷1闘1のうち、基本闘エネルギーが60枚中3枚しかなく構造的に揃わないことと判明。ユーザー判断により、タケルライコex・闘エネルギー依存を解消し、ナンジャモのビリリダマの「チェインボルト」（闘エネルギー不要・場全体の雷エネルギー数でダメージが決まる技）を主軸に据える方向へピボットした。

## 変更内容

### デッキ変更（`decks/jamoraiko_20260713.py`）

| カード | 変更前 | 変更後 |
|---|---|---|
| タケルライコex (63) | 2枚 | 0枚 |
| ナンジャモのビリリダマ (265) | 1枚 | 3枚 |
| 基本闘エネルギー (6) | 3枚 | 0枚 |
| 基本雷エネルギー (4) | 12枚 | 15枚 |

### コード変更（`src/jamoraiko_agent/main.py`）

- タケルライコex専用の死んだコードを削除：`FieldState.own_board_basic_energy_total`/`active_fighting_energy_count`、`Attacker.requires_fighting`/`is_utility`、`ATTACKERS`テーブルの2技（Bellowing Thunder/Burst Roar）、`POKEMON_LINES`のタケルライコexエントリ、`calc_attack_plan`内の関連分岐、`_score_attach_option`/`_score_search_candidate`/`_score_discard_candidate`の闘エネルギー分岐、`_score_energy_card_option`のDISCARD_ENERGY_CARDケース
- `POKEMON_LINES`のビリリダマ`max_field_copies`を2→3に変更（3枚採用に合わせる）
- `EnergyPolicy`クラスを「タケルライコexへのエネルギー集中」から「アクティブのハラバリーex(4エネ必要)/タイカイデン(3エネ必要)が攻撃可能本数に届いていない時、ベンチの余剰供給元から回す」ロジックに作り直し

## テスト

- `tests/test_jamoraiko_deck.py`：デッキ内容変更に合わせて全面更新
- `tests/test_jamoraiko_agent.py`：タケルライコex関連テストを削除・置き換え、EnergyPolicy再設計に伴うテストを新規作成
- `uv run pytest -q`でリポジトリ全体が全PASSであることを確認済み

## 未検証事項（次回以降）

- ビリリダマ軸への変更が実際に勝率を改善するかは、校正ノートブックの再ビルド・Kaggle実行でのみ確認できる（本タスクのスコープ外、ユーザー側で別途実施）
- カイデン（id=270）がATTACKERSテーブルに未登録の件は既知の軽微なロジック穴として引き続き別件で持ち越し
