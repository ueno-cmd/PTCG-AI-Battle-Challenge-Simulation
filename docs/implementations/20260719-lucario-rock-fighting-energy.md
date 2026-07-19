# ルカリオexデッキ ロック闘エネルギー導入 実装サマリー

- 日付: 2026-07-19
- 設計書: `docs/superpowers/specs/2026-07-19-lucario-rock-fighting-energy-design.md`
- 実装計画: `docs/superpowers/plans/2026-07-19-lucario-rock-fighting-energy.md`

## 背景

直近20戦の実戦解析（`docs/analyses/20260719-lucario-post-fix-20-games-analysis.md`）で
Alakazam系デッキとの対戦成績が1勝3敗（25%）と判明。フーディンの技「ハンドパワー」
（効果ベースの一撃必殺技）への対策として、ユーザーが実際のジムバトル環境から
発見したロック闘エネルギーを導入した。

## 変更内容

- デッキ（`decks/lucario_20260621.py`）：基本闘エネルギー11→7枚、ロック闘エネルギー0→4枚（60枚維持）
- エージェントロジック（`src/lucario_agent/main.py`）5箇所：
  1. `_score_attach_option`：ロック闘エネルギーをアクティブのポケモンへ優先装着
  2. `calc_attack_plan`の先読み：基本+ロックの合算判定に修正（潜在バグ修正）
  3. `JudgePolicy`の自己都合トリガー：基本+ロックの合算判定に修正（潜在バグ修正）
  4. `SelectContext.DISCARD`：ロック闘エネルギーを常時温存
  5. `SelectContext.TO_HAND`：ロック闘エネルギーを基本闘エネルギーより優先サーチ
- 変更不要と確認（カード原文で裏取り済み）：はどうづきのdiscard_counts判定、
  ルナサイクルの発動条件はいずれも「基本」限定のカード効果のため対象外のままで正しい

## テスト結果

`uv run pytest -q`でリポジトリ全体が全件PASS（既存517件＋新規6件）。

## 未対応・次回持ち越し

- ロック闘エネルギーが実際にハンドパワーを無効化できるかは、実戦ログでの検証が必要
  （次にAlakazam系と対戦した際のログで確認する）
- カイオーガ＋メガユキノオー対策、メガジガルデex＋コアメモリ、ロケット団の監視塔の
  採用検討は今回のスコープ外（将来の別ブレストで扱う）
