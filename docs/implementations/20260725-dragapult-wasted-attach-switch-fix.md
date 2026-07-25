# ドラパルトex 所感a・b修正 実装サマリー（2026-07-25）

## 対象

2026-07-25の実測20戦ログ調査（`docs/analyses/20260725-dragapult-ver8-5symptoms-investigation.md`）で確定した2件のバグのうち、ユーザー選択で優先度最高の2件のみを修正した。

- **所感a「無駄なエネルギー消費→にげる」の主因**（20戦中12戦・16件）
- **所感b「ドロンチ在場中の無駄なベンチ手張り」**（20戦中8戦・9件）

設計書：`docs/superpowers/specs/2026-07-25-dragapult-wasted-attach-switch-fix-design.md`
計画書：`docs/superpowers/plans/2026-07-25-dragapult-wasted-attach-switch-fix.md`
ブランチ：`feature/dragapult-wasted-attach-switch-fix`

## 実施内容

### Task 1（コミット`f5e58b6`）：`_should_switch()`新規関数の追加

`agent()`内にベタ書きだった`do_switch`変数を、テスト可能な純粋関数`_should_switch()`として抽出。Budew節に「アクティブが未投資(energy_count==0)の時だけ発火」という条件を追加した。`bench_attacker`分岐（攻撃準備済みの控えがいれば無条件に交代）は変更していない。この時点では`agent()`からはまだ呼ばれていない（Task 2で配線）。

### Task 2（コミット`865e110`）：`agent()`への配線

`agent()`内の`do_switch = (...)`インライン式を`_should_switch()`呼び出しに置き換え。純粋な配線変更で、`bench_attacker`分岐を含む既存の全挙動は変更なし。

### Task 3（コミット`e2dc7c1`→`aec010f`）：`_attach_score()`のenergy_count==0分岐修正

ベンチ側にのみあった種族ボーナス（Dragapult_ex +150 / Dreepy +100 / それ以外 +50）をアクティブ側にも対称に追加。`bench_attacker`による加減点（+400/-200）のみactive/benchで分岐させる形にリファクタした。

**修正の実効性について（最終レビューでの再検証、2026-07-25）**：この修正で解消されるのは「同一種族・同一階層でのactive/bench非対称」である。所感bの調査で指摘された典型パターン（アクティブ=ドロンチ・0エネルギーが、ベンチのドロディーやドラパルトexに負ける）は、この修正だけでは解消しない。理由は構造的なもの：ドロンチ(Drakloak)は`_attach_score()`のenergy_count==0分岐でelse枠（+50）に該当するのに対し、ドロディー(Dreepy)は専用枠（+100）、ドラパルトex(Dragapult_ex)はさらに上位の専用枠（+150）を持つ。`bench_attacker=False`後のスコアは`20000+種族ボーナス`の純粋比較に帰着するため、アクティブのドロンチ(+50)がベンチのドロディー(+100)やドラパルトex(+150)に勝つことは数学的にあり得ない。今回のTask 3は同一種族・同一階層の比較を対称化しただけで、種族間の階層順位そのものは変更していない。

最終レビューでは、元の調査（`docs/analyses/20260725-dragapult-ver8-5symptoms-investigation.md`）に使った同じ実測20戦ログに対し、`scripts/analyze_dragapult_attach_scoring.py`の手法を流用して修正後の挙動を再検証した。結果：

- ベンチ向けATTACHイベント計85件のうち、修正前スコアリングでアクティブ候補がベンチ候補に負けていたケースは40件。
- 修正後：**5件がactive勝ちへ逆転**（いずれもactive=Dragapult_exまたはactive=Dreepy vs より低階層のベンチ種族のケースで、典型パターンであるDrakloak-activeのケースではない）、**19件が完全同点化**（順序依存・非決定的な結果になる）、**21件は変化なし（active負けのまま）**。
- 特に重要な点：調査で名指しされた典型パターン（active=Drakloak・0エネルギー）に該当する12件のうち、逆転したものは**0件**。これは実測データ上の偶然ではなく、上記の理由により数学的に保証された結果である。

**未解決事項（次回以降の調査対象）**：所感bの最も頻出する実例（アクティブ=ドロンチ・0エネルギーが、ベンチのドロディーやドラパルトexに負ける）は、本ブランチの修正では未解消のまま残っている。ただしこれは本ブランチの実装に不備があったわけではない——本ブランチは承認済み設計（active/bench対称化）を設計どおりに実装しており、残っている差分は「種族優先度階層の値そのものをどう設計すべきか」という、より深い別の設計課題である。ユーザーは2026-07-25、以下の方針を決定した：

- 今回の提出ラウンドではこの制約を既知の限界として受け入れ、Kaggleへ再提出する。
- 次回セッションでは、いきなり修正に着手するのではなく、ドロンチ（および「新規加入直後の低階層種族より、戦闘準備が近い中間進化ポケモン」という類似ポジションにある他のポケモン）に適切な優先度を持たせるための種族優先度階層テーブルの再設計要否を、じっくり調査することに時間を割く。

なお、19件の同点化については、同点時の勝敗が選択順序に依存する非決定的な挙動が残る。これは今回のスコープでは意図的な受容事項として扱い、タイブレーク用のコードは追加していない（種族優先度の値自体を変更しないという今回のスコープ判断と同じ理由による）。

**実装中の逸脱（計画からの変更）**：
1. 計画書の新規テスト`test_attach_score_active_drakloak_beats_bench_dreepy_when_no_bench_attacker_ready`が数学的に矛盾していた（Drakloakの種族ボーナス+50がDreepyの+100に勝つとアサートしていたが、修正後の実装ではあり得ない）ことを実装者が発見・BLOCKED報告。controllerが計画書を修正（`test_attach_score_active_dragapult_ex_beats_bench_lower_priority_species_when_no_bench_attacker_ready`に差し替え）し、実装者を再開させた。
2. 修正の副作用で既存テスト3件が新規に失敗することを実装者が発見・対応：
   - `test_attach_score_dragon_line_accepts_fire_or_psychic_energy`・`test_attach_score_munkidori_accepts_dark_energy`：期待値の機械的な更新
   - `test_evaluate_attach_event_crispin_bonus_changes_verdict`（`tests/test_analyze_dragapult_attach_scoring.py`）：ドラパルトexの種族ボーナスがenergy_count==0分岐の上限になったため、旧シナリオが「ボーナス無しでも既に矛盾あり」に変化し検証が成立しなくなっていた。シナリオを再設計し対応。
3. タスクレビューで、再設計後のシナリオが「装着対象＝アクティブ自身」という、本番の`build_report()`が実際には渡さないケースを検証してしまっている点をImportant指摘。レビュアー自身の検証で、ベンチ対象のまま同じ検証を再構成することは現行のスコア式では構造的に不可能と確認されたため、その事情を説明するコメントを追加する形で対応（コミット`aec010f`）。

## テスト結果

`uv run pytest tests/ -q` → **711 passed, 0 failed**（開始時点704件 → Task1で+5 → Task3で既存1件更新+新規2件 → 711件）

## 変更ファイル

- `src/dragapult_agent/main.py`：`_should_switch()`新規追加、`agent()`内配線、`_attach_score()`の`energy_count==0`分岐リファクタ
- `tests/test_dragapult_agent.py`：新規テスト7件追加、既存テスト3件の期待値更新
- `tests/test_analyze_dragapult_attach_scoring.py`：既存テスト1件のシナリオ再設計＋説明コメント追加

## 未実装のまま残した項目（意図的にスコープ外）

- 所感aの副因（`_attach_score()`の`bench_attacker`準備時+400ボーナスが瞬間的な無駄装着を誘発、全体4/16件）
- RETREATスコアリング自体（`main.py:1172-1176`）がエネルギー投資額を無視している点
- 所感c（ミラー戦の敗因）・所感d（動けないターン、既存no_drawゲート課題）・所感e（サマヨール自爆、意図的設計と判定済み）
- クリスピンボーナステストのベンチ対象版の再構築（現行スコア式では構造的に不可能と判明。将来スコア式が変わった際に再検討する候補として`tests/test_analyze_dragapult_attach_scoring.py`のコメントに記録済み）

## フォローアップ（設計書より）

修正後の実戦での効果は、Kaggle再提出後に新規バトルログが貯まり次第、以下を再確認する（[[feedback_log_driven_debugging]]踏襲）：
- 所感bの典型パターン（アクティブ=ドロンチ）が未解消であることは最終レビューでの実測ログ再検証（Task 3節参照）で既に確認済みのため、新規ログでの再確認は不要。代わりに、active勝ちへ逆転した5件のパターン（active=Dragapult_ex/Dreepy）が実戦でも同様に機能しているか、19件の同点化が実戦でどちらに転んでいるかを観察する
- 種族ボーナス対称化による意図しない副作用（例：ベンチのDragapult_ex完成を過度に遅らせる等）が発生していないか
- 所感aのパターンについても、Budew節の限定で想定通りの効果が出ているか

## 提出用notebook

`uv run python scripts/build_dragapult_submission_notebook.py`で再生成済み（`_should_switch`・更新後の`_attach_score()`を含むことを確認済み）。Kaggleアップロード・push はユーザー側で実施予定。
