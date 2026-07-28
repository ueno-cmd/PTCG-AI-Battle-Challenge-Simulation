# 実装サマリー: Maximum Belt温存・Riolu供給ガード緩和・EVOLVE優先度修正

**実装日**: 2026-07-28
**実装者**: Claude Code
**計画書**: `docs/superpowers/plans/2026-07-28-lucario-belt-discard-riolu-supply-evolve-priority.md`
**作業ブランチ**: `feature/lucario-belt-discard-riolu-supply-evolve-priority`（ベース: `2c6475e`）

---

## 概要

ver22/ver23の実測40戦のバトルログ解析（`2c6475e`）で判明した、ルカリオexエージェントの
スコアリング上の3つの問題を修正した。いずれも既存のスコアリング関数への局所パッチであり、
新規クラス・新規ファイルは追加していない。

1. **Maximum Belt（ACE SPEC）がハイパーボールのコスト等で自己破棄される**（Task 1）
2. **EVOLVEとJudgeのスコアが同点（9000）になり、進化がJudgeに競り負けることがある**（Task 2）
3. **Mega Lucario exが2体並ぶとRioluの追加展開が永久に止まる**（Task 3）

---

## Task 1: Maximum BeltをDISCARDコンテキストで温存する

### 問題
`case SelectContext.DISCARD:` ブロックにおいて、Maximum Beltが既定スコア10点のまま
「捨ててよいカード」として扱われており、ハイパーボールのコスト等のトラッシュ要求時に
誤って自己破棄されていた。Maximum BeltはACE SPEC（デッキ1枚制限）であり、
トラッシュからの回収手段も無いため、一度捨てると復帰不可能。

**実測根拠**: ver22/ver23の40戦で3件の誤破棄を確認（88184798 t1 / 88186950 t1 / 88168475 step10）。

### 修正内容
`src/lucario_agent/main.py`（`case SelectContext.DISCARD:` ブロック内、Rock_Fighting_Energy分岐と
Riolu分岐の間）

修正前: 分岐なし（既定の10点にフォールスルー）

修正後:
```python
if card.id == Maximum_Belt:
    # ACE SPECのためデッキに1枚のみ・トラッシュからの回収手段も無く、
    # 一度捨てると復帰不可。複数枚あるキーポケモン(-100)より強く温存する。
    # 実測：ver22/ver23の40戦で3件、ハイパーボールのコスト等として
    # 自己破棄していた（88184798 t1 / 88186950 t1 / 88168475 step10）
    return -150
```

`-150`はキーポケモン（Riolu等、-100）より強く温存するための値。

### テスト
`tests/test_lucario_agent.py::TestDiscardContext` に2件追加
（`test_protects_maximum_belt`、`test_maximum_belt_protected_more_strongly_than_key_pokemon`）

### コミット
`19653f7` — `fix(lucario): Maximum BeltをDISCARDコンテキストで温存する`

### テスト件数
738 → 740

---

## Task 2: EVOLVEをJudgeより優先させ同点を解消する

### 問題
`_score_option` の `case OptionType.EVOLVE:` が `9000 + len(pokemon.energies)` を返す一方、
`JudgePolicy`（相手の手札が10枚以上の時に最優先）も9000点を返すことがあり、
両者が**同点**になるケースが存在した。選択肢の提示順はエンジン（`libcg.so`、ソース非公開）が
決めるためコードから制御できず、同点だとJudgeが先に選ばれて手札のMega Lucario exが山札に
戻り、進化機会を失うリスクがあった。

### 修正内容
`src/lucario_agent/main.py`（`_score_option` 内 `case OptionType.EVOLVE:`）

修正前:
```python
case OptionType.EVOLVE:
    pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
    return 9000 + len(pokemon.energies)
```

修正後:
```python
case OptionType.EVOLVE:
    pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
    # 9100始まり：Judge(9000、相手の手札が10枚以上で最優先)と同点にしないため。
    # MAINは1ターンに複数回行動できるので、先に進化してからJudgeを撃てば両方成立する。
    # 同点だと選択肢の提示順（エンジン依存で制御不能）次第でJudgeが先に選ばれ、
    # 手札のMega Lucario exが山札に戻って進化機会を失う。
    # 9000〜10000の間に他のスコアは存在しないため上位分岐への影響はない。
    # （2026-07-28の静的監査で発見。実測40戦での実害は0件だが構造として実在）
    return 9100 + len(pokemon.energies)
```

**設計上の制約（計画書「前提の確認」より）**: メガ進化がターンを終了させる仕様かどうかは
資料から確認できていない。今回の変更はEVOLVEの相対順位をJudge(9000)に対してのみ変えるもので、
エネルギー装着(8000〜8811)や攻撃(1000)との順位は元からEVOLVEが上のため新たなリスクは生じない。
ただし**EVOLVEを10000以上に上げる変更はこの確認が取れるまで行わないこと**。

### テスト
`tests/test_lucario_agent.py::TestEvolvePriorityOverJudge` を新規追加（3件）

### コミット
`7905792` — `fix(lucario): EVOLVEをJudgeより優先させ同点を解消する`

### テスト件数
740 → 743

### レビューでのMinor指摘（残課題）
テストヘルパー `_judge_top_priority_score` が `_score_option` 経由ではなく
`JudgePolicy().play_score(ctx)` を直接呼ぶため、上流のガード（`_deck_consumption`/`_safe_draws`）を
通らない。ブリーフ指定通りの実装であり今回の検証目的には影響しないが、将来同種のテストを書く際は
経路の違いに注意すること。

---

## Task 3: 場にRioluが0体なら展開ガードを免除する

### 問題
`_score_play_option` のPOKEMON分岐にある `if card.id == Riolu:` の条件が、
「場のRiolu＋Mega Lucario exの合計が2体以上なら一律-1（温存）」という一律ルールだった。
このため、Mega Lucario exが2体並んだ時点で3体目以降のRioluを**永久に**出せなくなり、
手札のMega Lucario exが腐る事態が発生していた。

**実測根拠**: ver22/ver23の40戦で、手札にMega Lucario exがあるのに場にRioluが0体のターンが
25回。うちPLAY Rioluの選択肢が出ていたのに出さなかったのが2回
（88166297 turn12 step102 / turn14 step117、いずれもベンチ4/5で空きあり）。

### 修正内容
`src/lucario_agent/main.py`（`_score_play_option` 内、POKEMON分岐）

修正前:
```python
if card.id == Riolu:
    return -1 if field_counts[Riolu] + field_counts[Mega_Lucario_ex] >= 2 else 20000
```

修正後:
```python
if card.id == Riolu:
    # 場に進化元(Riolu)が1体もいない時は、Mega Lucario exが何体いても展開を許可する。
    # 旧条件(Riolu+Mega>=2で一律-1)では、Mega Lucario exが2体並んだ時点で3体目以降の
    # Rioluを永久に出せず、手札のMega Lucario exが腐っていた。
    # 実測：ver22/ver23の40戦で、手札にMegaがあるのに場にRioluが0体のターンが25回。
    # うちPLAY Rioluの選択肢が出ていたのに出さなかったのが2回
    # （88166297 turn12 step102 / turn14 step117、いずれもベンチ4/5で空きあり）
    if field_counts[Riolu] == 0:
        return 20000
    return -1 if field_counts[Riolu] + field_counts[Mega_Lucario_ex] >= 2 else 20000
```

「Riolu 0体のケースのみ新たに20000を返す」という完全な追加条件であり、Riolu 1体以上の
既存パスは一切変更していない。

### テスト
`tests/test_lucario_agent.py::TestRiolusSupplyGate` を新規追加（5件）

### コミット
`4d4c20f` — `fix(lucario): 場にRioluが0体なら展開ガードを免除する`

### テスト件数
743 → 748

### レビューでのMinor指摘（残課題）
`field_riolu=0` かつ `field_mega=0`（初回のRiolu展開）の境界ケースのテストが未追加。
ロジック上は新旧どちらの分岐でも20000を返す等価なケースであり実害なし。

---

## テスト結果サマリー

| 時点 | 全体テスト件数 |
|---|---|
| 着手時ベースライン | 738 |
| Task 1後 | 740 |
| Task 2後 | 743 |
| Task 3後（完了時） | 748 |

3タスクとも既存テストの失敗0件・期待値の後方修正なし。

---

## 変更ファイル（コード）

- `src/lucario_agent/main.py` — Task 1〜3の3箇所を修正
- `tests/test_lucario_agent.py` — `TestDiscardContext`（+2）、`TestEvolvePriorityOverJudge`（新規3）、
  `TestRiolusSupplyGate`（新規5）

各タスクのコミット:

| Task | 内容 | コミット |
|---|---|---|
| 1 | Maximum BeltをDISCARDコンテキストで温存（-150点） | `19653f7` |
| 2 | EVOLVEを9000→9100始まりにしてJudge(9000)との同点を解消 | `7905792` |
| 3 | 場にRioluが0体なら展開ガードを免除 | `4d4c20f` |

---

## 提出用notebookの再生成

```bash
uv run python scripts/build_lucario_submission_notebook.py
```

生成物: `notebooks/submissions/lucario_agent_submission.ipynb`（ビルド成果物・`.gitignore`対象のためコミット対象外）

### 生成物に3件の修正が含まれることの確認

```bash
grep -c "9100 + len(pokemon.energies)" notebooks/submissions/lucario_agent_submission.ipynb   # 1
grep -c "field_counts\[Riolu\] == 0" notebooks/submissions/lucario_agent_submission.ipynb       # 1
grep -c "return -150" notebooks/submissions/lucario_agent_submission.ipynb                      # 1
```

3件とも1（1以上）を確認済み。

### notebookビルドテスト

```bash
uv run pytest tests/test_build_lucario_submission_main.py tests/test_build_lucario_submission_notebook.py -v
```

12件全てPASS。

---

## 検証方法（重要）

`cg.sim` はmacOSで動作しないため、実機シミュレーションでの検証はできない。修正が実際の
ゲームエンジン上で意図通り動くかは、**Kaggle再提出後の新規バトルログでのみ確認可能**。

勝率は分散が大きく直接の検証指標にならないため、次バッチのログでは以下の**プロセス指標**を
数えて確認すること。

| 指標 | ver22/ver23（40戦） | 期待値（今回の修正後） |
|---|---|---|
| Maximum Beltが自己破棄された回数 | 3件 | **0件** |
| 手札にMega Lucario exがあるのに場にRioluが0体のターン数 | 25回/40戦 | **減少すること** |
| Maximum Beltの装着率 | ver22: 30% / ver23: 45% | **上昇すること** |

---

## スコープ外（意図的に今回は着手しない）

以下は2026-07-28の静的監査・実ログ検証で判明しているが、本計画には含めない。バックログとして残す。

1. **Mega Lucario exの体数上限ガードが無い** — ドラパルトexには「場に2体なら-1」があるが、
   ルカリオexには無く無制限に並ぶ。Mega Lucario exはKO時にサイドを**3枚**献上するため、
   非exデッキ（Alakazam軸等、1体倒しても1枚）相手のサイド枚数の非対称性に直結する。
   ユーザー判断で今回は見送り（影響が大きく慎重な設計が必要）
2. **`UltraBallPolicy.already_found`の数え方** — 場と手札のRiolu＋Mega＋Ogerponの合計が3以上で
   スコアを100点に落とす（`main.py:358-367`）。**Mega Lucario exを1枚も持っていなくても**、
   Riolu 2体＋Ogerpon 1体がベンチにいるだけでハイパーボールが実質封印される。
   進化ライン別に分離集計する案があるが、ハイパーボールの使用が増えて手札2枚コストで
   事故る可能性があるため要検討
3. **スコア階層の定数化** — 9000/10000/20000等のマジックナンバーが散在しており、
   今回のJudge同点はその帰結。`PRIORITY_ABILITY`/`PRIORITY_EVOLVE`等の定数化と、
   同点が生じないことを保証するテストの追加が恒久対策
4. **`_score_card_option`のスコアリング漏れ** — `SETUP_BENCH_POKEMON(2)` / `EVOLVES_FROM(18)` /
   `EVOLVES_TO(19)` / `TO_BENCH(5)` / `TO_FIELD(6)`のケースが無く`case _: return 0`に落ちる
   （既知の`ATTACH_TO(22)`漏れと同種）。現デッキで毎試合通るのは`SETUP_BENCH_POKEMON`のみで、
   ゲーム開始時のベンチ選択が手札順依存になっている
5. **`_score_play_option`の山札温存ゲートの位置** — `main.py:446`の`return -1`が
   ポケモン分岐より**上**にある既知の危険形。現状は`_deck_consumption`がポケモンに`None`を返すため
   無害だが、**将来ここに進化系トレーナー（ふしぎなアメ等）を足すと即座に踏む**
6. **`Hero_Cape`定数のデッドコード化** — `src/lucario_agent/constants.py:9`。
   デッキから外れており参照はゼロ。削除可否は未判断
7. **`get_card`が`PRE_EVOLUTION(10)`等で`None`を返す** — `main.py:102-103`。
   EVOLVEブランチが`None.energies`で例外化する理論的リスク（実測では未発生）
8. **Air Balloonのトラッシュコスト温存** — 今回Maximum Beltのみ保護した。
   Air Balloon（2枚採用）も既定10点のままで、同様に捨てられうる。実測での損失は未確認

---

## 関連ファイル

- `src/lucario_agent/main.py` — スコアリングロジック本体
- `tests/test_lucario_agent.py` — テストスイート
- `notebooks/submissions/lucario_agent_submission.ipynb` — Kaggle提出用ノートブック（ビルド成果物）
- `.superpowers/sdd/2026-07-28-lucario-belt-discard-riolu-supply-evolve-priority/` — 各タスクの
  ブリーフ・実行レポート
- `docs/superpowers/plans/2026-07-28-lucario-belt-discard-riolu-supply-evolve-priority.md` — 計画書
