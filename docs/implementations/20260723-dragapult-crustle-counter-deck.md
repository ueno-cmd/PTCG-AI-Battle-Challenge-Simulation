# ドラパルトex イワパレス対策デッキ 実装サマリー

## 背景

`TrainerCardPolicy`移植版をKaggleに提出した直後、レーティングが300まで急落した
（`docs/analyses/20260723-dragapult-trainer-card-policy-300-drop-17-games.md`）。
17戦分のバトルログを実測解析した結果、勝率自体は過去バッチと同水準（47%）だったが、
17戦中7戦（41%）がMega Abomasnow ex・Crustle（イワパレス）という「デッキ構成上
ほぼ勝ち目のない構造的ハードカウンター」相手だったことが判明した。

イワパレスの特性「ミステリアスロックイン」は、相手の**exポケモンの攻撃ダメージ**を
すべて無効化する。従来のデッキ（`decks/dragapult_20260721.py`）の攻撃要員はドラパルト
ex・フェザンディピティex・ラティアスex・ニャースexとほぼ全てexポケモンで、実戦的な
突破手段が存在しなかった。

そこでユーザーが実際のジムバトル（対人戦）環境で確認した「イワパレス対策済み
ドラパルトexデッキ」の構成をそのまま移植し、壁ポケモン相手にも勝ち筋を作ることにした。
Mega Abomasnow ex自体は「ガチャ・非トップランカー環境デッキ」としてユーザー判断で
対策の対象外とした。

- 設計書：`docs/superpowers/specs/2026-07-23-dragapult-crustle-counter-deck-design.md`
- 実装計画：`docs/superpowers/plans/2026-07-23-dragapult-crustle-counter-deck.md`
- 300急落分析：`docs/analyses/20260723-dragapult-trainer-card-policy-300-drop-17-games.md`

## デッキ構成の変更点

### 除外した5種

ラティアスex、クラッシングハンマー（4枚）、ラッキーヘルメット、
ロケット団の見張り搭（2枚）、ブロックの探索（2枚）。これらの専用スコアリング分岐
（`hand_score()`・`OptionType.PLAY`分岐・`TeamRocketWatchtowerPolicy`）を全て削除した。
フェザンディピティex（id=140）は既存のまま変更なし（当初「キチキギスex」という
別カードと誤認していたが、EN/JPカードデータ突き合わせの結果、既存カードと同一と判明）。

### 追加した9種（新規カード）

| カード | 役割 |
|---|---|
| ヨマワル(Duskull, id=131)×2 | 特性「むかえにいく」でトラッシュから回収 |
| サマヨール(Dusclops, id=132)×1 | 1進化。カースドボム対応 |
| ヨノワール(Dusknoir, id=133)×1 | 2進化。カースドボムの主役（13個=130ダメージ） |
| マシマシラ(Munkidori, id=112)×1 | 特性「アドレナブレイン」でダメカン移し替え |
| ファイヤー(Moltres, id=791)×1 | 非exの攻撃手段。相手アクティブがexなら高火力 |
| イベルタル(Yveltal, id=689)×1 | 非exの攻撃手段。悪エネルギー専用アタッカー |
| ヒカリ(Dawn, id=1231)×1 | サポート |
| メイのはげまし(Rosas_Encouragement, id=1240)×1 | サポート |
| ジャミングタワー(Jamming_Tower, id=1246)×1 | スタジアム |

基本悪エネルギー(Basic_Dark_Energy, id=7)×2も新規追加。合計60枚、ACE SPEC
（アンフェアスタンプ）は1枚制限を遵守。ジムバトルデッキ原本にあった
「スペシャルレッドカード」（カードプール非存在のため代替不可）はアカマツ4→3枚、
「危ない廃墟」（不採用）はボスの指令3→4枚で補填した。

## 新規実装したロジック

`src/dragapult_agent/main.py`（`agent()`関数中心の1ファイル構成）へ、既存の判断
ポイントのパターンに沿って追加した。

1. **カード定数・デッキリスト**（Task 1）：`constants.py`に新規9種＋
   `Basic_Dark_Energy`を追加し、`decks/dragapult_20260721.py`を新構成へ全面差し替え
2. **除外カードの削除**（Task 2）：`hand_score()`・PLAY分岐・
   `TeamRocketWatchtowerPolicy`から旧ロジックを削除
3. **`hand_score()`拡張**（Task 3）：ヨマワル系統3種＋マシマシラ／ファイヤー／
   イベルタルの手札評価を追加。進化ライン追跡フラグ`can_evolve_yomawaru`・
   `can_evolve_samayouru`を新設
4. **PLAY dispatch**（Task 4）：たねポケモン4種（ヨマワル・マシマシラ・
   ファイヤー・イベルタル）を場に出す分岐を追加
5. **`_evolve_score()`切り出し**（Task 5）：`OptionType.EVOLVE`分岐にベタ書き
   されていた進化優先度ロジックを独立関数へ切り出し、ヨマワル→サマヨール
   （+25000）・サマヨール→ヨノワール（+60000）の優先度を追加（TDD）
6. **むかえにいく：`_fetch_from_discard_score()`**（Task 6）：トラッシュに
   回収対象があり、かつベンチに空きがある場合のみ発動（TDD）
7. **カースドボム：`_cursed_bomb_score()`**（Task 7）：「ダメカンの直接配置」は
   「攻撃ダメージ」ではないためイワパレスの特性を迂回できる。自爆前提のため、
   相手アクティブが`no_damage_dex()`該当（直接攻撃が完全ブロックされる相手）の
   時のみ発動するようゲーティング（TDD）
8. **アドレナブレイン：`_adrena_brain_score()`**（Task 8）：カースドボムと同じ
   理由でイワパレスを迂回できる。発動条件（ABILITY選択時のゲーティング）のみを
   実装し、対象選択の詳細は次回以降に持ち越し（TDD）
9. **`_attach_score()`統合**（Task 9）：イベルタルは悪エネルギー装着の最優先先
   （技コストが悪エネルギーのみのため、それ以外は装着しても無意味）、
   ヨノワール／サマヨールはカースドボムがエネルギー不要のため低優先度に設定
10. **`_own_switch_target_score()`統合**（Task 10）：シグネチャに
    `opponent_active_is_ex: bool`を追加。ファイヤーは相手アクティブがexの時のみ
    ドラパルトexと同等の高優先度（それ以外は低優先度）、イベルタルはドラパルト
    exより低い中程度の優先度、ヨノワールは貴重な1枚を無駄撃ちしないよう低優先度
11. **`TrainerCardPolicy`登録**（Task 11）：ヒカリ・メイのはげまし・
    ジャミングタワーを既存のABC＋登録辞書パターンに乗せ、`agent()`内に
    カードID分岐を新規追加せずに統合

## 未検証・次回持ち越しの項目

計画書の「実装後の残課題」節（`docs/superpowers/plans/2026-07-23-dragapult-crustle-counter-deck.md`）に基づく。

- マシマシラの特性「アドレナブレイン」の対象選択詳細（自分のどのポケモンから
  ダメカンを移すか、自分側HPが40以下にならないようにするガード等）は、実際の
  SelectContext形状が実戦ログでまだ確認できていないため、実戦ログ検証後に精緻化する
- ヒカリの実際のSelectContext形状（`TO_HAND`経由で汎用的に処理されると想定して
  いるが未検証）が、意図通り`hand_score()`の値を使って優先順位付けされているか
- Rare CandyとヨマワルNサマヨール／ヨノワールラインの相互作用（現行の
  `RareCandyPolicy`はドラパルトex専用の`no_more_dex`ゲートのみで、ヨマワル系統の
  進化短縮には対応していない）
- `bench_attacker`フラグが現状Dragapult_exの準備状況のみ判定しており
  （`field_counts[Dragapult_ex]`とエネルギー数2以上の組み合わせのみ）、ファイヤーが
  ベンチで攻撃準備完了している状況を拾えない可能性がある。この場合、
  `_own_switch_target_score()`でファイヤーが高優先度と評価されても、
  `OptionType.RETREAT`分岐の`do_switch`判定（`bench_attacker`依存）が先に交代自体を
  却下してしまい、実際には交代が起きない懸念がある。`bench_attacker`は
  `_attach_score()`・`hand_score()`・スボミーのswitch_target優先度等、既存の多数箇所で
  参照されている共有フラグのため、安易な定義拡張は副作用が大きい。次回、実戦ログで
  「相手アクティブがexの時にファイヤーへ交代できているか」を確認し、必要なら
  別フラグの新設を検討する
- Kaggle再提出後の勝率実測検証（`project_battle_log_parser`の手法）

## テスト結果

- `uv run python scripts/build_dragapult_submission_notebook.py`：正常終了。
  再生成された`notebooks/submissions/dragapult_agent_submission.ipynb`に新規カード名
  （Duskull/Dusclops/Dusknoir/Munkidori/Moltres/Yveltal/Dawn/Rosas_Encouragement/
  Jamming_Tower）が計59件出現していることを目視確認（notebookのJSONが1行に
  折り畳まれているため`grep -c`（行数カウント）は1件だが、`grep -o`（出現数カウント）
  で確認済み）
- `uv run pytest -q`（リポジトリ全体）：**697件PASS、失敗0件、エラー0件**
  （このリポジトリは現時点で完全にグリーンで、対応不要な既知の失敗は存在しない）

## 運用

- ブランチ：`feature/dragapult-crustle-counter-deck`（Task 1〜12を個別コミット）
- 提出用notebook`notebooks/submissions/dragapult_agent_submission.ipynb`は
  `.gitignore`対象のビルド成果物のため未コミット（`.gitignore:40`の`*.ipynb`ルール）
- push・Kaggle再提出はユーザー判断で別途実施（本タスクでは未実施）
