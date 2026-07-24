# ドラパルトex ver7実測ログ3件修正 実装サマリー

## 背景

イワパレス対策デッキ提出（ver7）後の新規30戦（`87665219`〜`87680882`）を実測解析した
結果、独立した3件の問題が判明した。詳細な原因分析と修正方針は設計書
（`docs/superpowers/specs/2026-07-24-dragapult-ver7-energy-switch-cursedbomb-fix-design.md`）
にまとめている。

1. `_attach_score()`にエネルギー種別チェックが存在せず、ドラメシヤ/ドロンチ/ドラパルトex
   （炎/超エネルギーのみ要求）とマシマシラ（悪エネルギーのみ要求）に対して、どんな
   エネルギーでも装着してしまうバグがあった。実測30戦でドラパルト系統への悪エネルギー
   誤装着30件、マシマシラへの炎・超エネルギー誤装着10件を確認した。
2. `_own_switch_target_score()`でスボミー（HP30・攻撃10ダメージのみ）の交代優先度が
   30000点と高すぎ、ベンチにドラパルトexがいない場面で実戦的な非exアタッカー
   （イベルタル15000点、ファイヤー5000/49000点）を上回ってしまい、3試合
   （`87674403`・`87675484`・`87677096`、いずれも敗戦）で見送りの原因になっていた。
3. `_cursed_bomb_score()`は相手アクティブがイワパレス系（`no_damage_dex()`該当）の
   時しか自爆を許可しておらず、それ以外は常に-1だった。一方でヨノワール/サマヨールは
   `_attach_score()`側で意図的にエネルギー投資を避けられているため攻撃技を使う手段が
   そもそも無い。実測30戦中21戦で進化まで到達し、うち19戦で試合終了まで一度も
   攻撃せず「文鎮」化していた（進化から終局までの残りステップ数は平均80〜90）。

## 実装内容

`src/dragapult_agent/main.py`内の3関数のみを変更した（デッキ構成・
`TrainerCardPolicy`登録辞書・その他の関数は変更なし）。

### ① `_attach_score()`（Task 1）

既存のイベルタル用ガード（悪エネルギー以外なら-1）と同じパターンで、Yveltal分岐の
直後・Dusknoir/Dusclops分岐の直前に2つの分岐を追加した。

- ドラパルト系統(Dreepy/Drakloak/Dragapult_ex)：炎/超エネルギー以外なら`-1`
- マシマシラ(Munkidori)：悪エネルギー以外なら`-1`

型が一致する場合はどちらの新規分岐にも該当せず、既存の汎用スコアリングにそのまま
流れるため既存の優先度計算への影響はない。

### ② `_own_switch_target_score()`（Task 2）

スボミー(Budew)の返り値を`30000`から`3000`に引き下げた（`bench_attacker=True`の
ケースは従来通り`0`のまま）。イベルタル(15000)・ファイヤー(5000/49000)を下回るため、
他に攻撃可能な駒が候補にあれば必ずそちらが優先される。

### ③ `_cursed_bomb_score()`（Task 3）

シグネチャに`energy_count`（ヨノワール/サマヨール自身の装着エネルギー数）と
`has_other_attacker`（`bench_attacker or can_main_attack`）を追加し、新しい分岐を
1件追加した。

- 相手アクティブがイワパレス系（`no_damage_dex()`該当）: `90000`（従来通り最優先）
- **新規**：`energy_count == 0`（攻撃手段なし）かつ`has_other_attacker`（本命の
  代わりがいる）: `20000`（中優先度で自爆を許可し、文鎮化を回避）
- それ以外: `-1`（従来通り温存）

呼び出し元も`opponent_active_id, len(card.energies), bench_attacker or can_main_attack`
の3引数を渡すよう更新した。

## テスト結果

TDD（RED→GREEN）で各タスクごとにテストを追加・更新した（新規11件・既存更新数件、
詳細はTask 1〜3の各報告を参照）。最終確認として、本タスクでリポジトリ全体を実行した。

```
uv run pytest -q
704 passed in 0.90s
```

失敗・エラーともに0件。既存テストへの回帰も無い。

## 提出用notebookの再生成

`uv run python scripts/build_dragapult_submission_notebook.py`を実行し、
`notebooks/submissions/dragapult_agent_submission.ipynb`を再生成した（更新日時が
実行時刻に更新されたことを確認）。再生成後のnotebookに3関数の修正内容
（`has_other_attacker`引数、スボミーの`return 3000 if not bench_attacker`、
ドラパルト系統/マシマシラのエネルギー種別ガード）が反映されていることをソース文字列
検索で確認した。同ファイルは`.gitignore`対象のため今回のコミットには含めない。

## 次のアクション

Kaggle再提出はユーザー側で実施する。次回の実測バトルログ取得時に、以下3点が
改善されているかを確認する。

1. ドラパルト系統・マシマシラへのエネルギー誤装着イベントが解消されているか
   （`GameStateTracker`のATTACHイベントで再検証）
2. スボミーへの交代頻度が下がり、非exアタッカー（イベルタル・ファイヤー）が
   見送られるケースが減っているか（特に敗戦試合での交代選択を優先確認）
3. ヨノワール/サマヨールが「文鎮」化せず、エネルギー0かつ他に攻撃可能な駒がある
   局面で自爆・ダメカン設置を選択するようになっているか、またそれが勝率に
   悪影響を与えていないか

いずれも本設計書の「スコープ外」節（20000という数値のチューニング、ABILITY分岐の
クラス化等）は次回以降の課題として保留する。

## 関連ドキュメント・コミット

- 設計書: `docs/superpowers/specs/2026-07-24-dragapult-ver7-energy-switch-cursedbomb-fix-design.md`
- 計画書: `docs/superpowers/plans/2026-07-24-dragapult-ver7-energy-switch-cursedbomb-fix.md`
- Task 1（`_attach_score()`修正）: コミット`ccc4f72`
- Task 2（`_own_switch_target_score()`修正）: コミット`f6429cc`
- Task 3（`_cursed_bomb_score()`修正）: コミット`a411f33`
- 本サマリー: 本コミット
