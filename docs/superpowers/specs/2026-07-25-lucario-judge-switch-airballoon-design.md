# ルカリオexデッキ 低リスク改修（Judge増量＋ポケモンいれかえ・ふうせん新規採用）設計書

- 日付: 2026-07-25
- 対象: `decks/lucario_20260621.py`, `src/lucario_agent/main.py`, `src/lucario_agent/constants.py`

## 背景

2つの実測検証で既知だった構造的ギャップに対応する。

1. `docs/analyses/20260719-lucario-post-fix-20-games-analysis.md`：Judgeの相手手札枚数トリガー導入後もAlakazam系対面が1勝3敗(25%)のまま改善せず、「Judgeがデッキに2枚しかなく序盤の自己都合トリガーで枯渇し、終盤の防御用途に使えない」という資源制約が原因と推定されている
2. `docs/analyses/20260720-lucario-ex-nullifier-fix-verification-20-games.md`：「デッキに自分から交代するトレーナーズが1枚もない」（ボスの指令は相手専用）という構造的ギャップが判明。`docs/analyses/20260725-lucario-stay-bonus-retreat-fix-20-games.md`でも、RETREATの選択肢自体がエネルギー不足で提示されない状況（Crustle戦）が確認されている

ユーザーが発見した実在のジムバトル優勝デッキ（Riolu4/Mega Lucario ex3/Makuhita2/Hariyama2/Solrock3/Lunatone2/Meowth ex1/Genesect1/Fighting Gong4/Ultra Ball3/Poké Pad4/Premium Power Pro4/Night Stretcher1/Switch1/Air Balloon2/Maximum Belt1/Lillie's Determination4/Boss's Orders2/Judge3/Team Rocket's Watchtower1/Gravity Mountain1/Basic Fighting Energy9/Rock Fighting Energy2）を参考に、このうち**既存の判断パターンを流用でき新規ロジックの実装リスクが低い部分（Judge増量・ポケモンいれかえ・ふうせん）のみ**を今回のスコープとする。ゲノセクトのエースカンセラー・マクノシタ/ハリテヤマ系統・ロケット団の監視塔は、新しい意思決定ロジックが必要でリスクが高いため対象外（別セッションで慎重に扱う）。

これはドラパルトexのver7（イワパレス対策デッキ）で、新カード追加時に意思決定ロジックの作り込みが漏れて3件の実バグ（エネルギー種別チェック漏れ・スイッチ優先度逆転・カースドボム発動条件の狭さ）が発生した反省を踏まえた、意図的なリスク分離である。

## 変更内容

### ①デッキ構成（`decks/lucario_20260621.py`）

60枚のまま、以下を入れ替える。

**削除（計4枚）**
- Hilda（トウコ、ID1225）2枚
- Wally's Compassion（ミツルの思いやり、ID1229）1枚
- Ciphermaniac's Codebreaking（暗号マニアの解読、ID1188）1枚

**追加（計4枚）**
- Judge（ID1213）2→3枚（+1）
- Switch（ポケモンいれかえ、ID1123）1枚（新規）
- Air Balloon（ふうせん、ID1174）2枚（新規）

Hero's Cape（ヒーローマント、ID1159、ACE SPEC、装着ポケモンの最大HP+100）は温存する（既に生存率へ寄与しており、ACE SPEC枠は1種類しか採用できないため他の候補と競合しない）。

`constants.py`に`Switch = 1123`・`Air_Balloon = 1174`を追加する。

### ②ポケモンいれかえ（Switch）— 新規`SwitchPolicy`

`TrainerCardPolicy`を継承し、`_score_retreat_option(ctx.current_plan, ctx.my_state.active[0] if ctx.my_state.active else None, card_table)`の戻り値をそのまま使わず、**成立時は+100して返す**（2000→2100、-1はそのまま）。

理由：実際のカードルール上、RETREAT（OptionType.RETREAT）は「にげるコスト分のエネルギーをアクティブから捨てる」という代償を伴うが、Switch（トレーナーズカード）はコストゼロでエネルギーを一切失わない。同じ条件が同時に成立する局面では、資源を消費しないSwitchを優先させる。

`SelectContext.SWITCH`（交代後どのベンチポケモンを場に出すか）は、RETREATと共有している既存ロジック（`main.py` 177行目〜のSelectContext.SWITCH | SelectContext.TO_ACTIVE分岐）がカードの種類を問わず適用されるため、変更不要。

`TRAINER_CARD_POLICIES`辞書に`Switch: SwitchPolicy()`を登録する。

### ③ふうせん（Air Balloon）— `_score_attach_option`への分岐追加

`_score_attach_option`（`main.py` 445行目〜）のHero_Cape分岐（448-455行目）と同じ位置に、`card.id == Air_Balloon`の専用分岐を追加する。

優先度：メガルカリオex最優先、次いでリオル。両者ともにげるコストが2（デッキ内最大）で、ふうせんの-2を最大限活かせるため（ソルロック/ルナトーン/オーガポンexはにげるコスト1で、効果の一部が切り捨てられる）。スコア水準はHero_Cape分岐と同じ7000ベースに揃え、対象ポケモンによって加点する：

```python
if card.id == Air_Balloon:
    pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
    score = 7000
    if pokemon.id == Mega_Lucario_ex:
        score += 200
    elif pokemon.id == Riolu:
        score += 100
    return score
```

（Hero_Cape分岐の直後、同じ`if card.id == X: ... return score`の並びに追加する）

## テスト方針

`tests/test_lucario_agent.py`にTDDで追加：
- `SwitchPolicy`が`_score_retreat_option`と同条件（①より良いアタッカーに交代 ②実質ノーダメージ×アクティブがex/megaExなら温存）で発火すること
- 同条件が成立するとき、`SwitchPolicy`のスコアが`_score_retreat_option`（RETREATのスコア）を上回ること
- `_score_attach_option`のAir Balloon分岐：メガルカリオex > リオル > その他（Hero_Capeと同型のテストケースを追加）

`tests/test_lucario_deck.py`の既存デッキ内容検証（60枚・カード種別）が新しい構成でも通ることを確認する。

## スコープ外（意図的に対象としないもの）

- ゲノセクトのエースカンセラー（ACE SPEC封殺ロジック）
- マクノシタ・ハリテヤマ系統（新規アタッカー候補・強制交代アビリティ）
- ロケット団の監視塔（スタジアム設置判断）
- マキシマムベルト（ex対面のみに有効、Alakazam対策としては効果なし）
- Judgeの`OPPONENT_HAND_THRESHOLD`閾値自体の見直し（今回は枚数のみ変更）

## 提出

実装後、`uv run python scripts/build_lucario_submission_notebook.py`で提出用notebookを再生成する（Kaggleアップロードはユーザー実施）。
