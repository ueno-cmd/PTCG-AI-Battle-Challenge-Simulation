# ジャモライコエージェント トレーナーズカード ポリシー登録制 設計書

## 背景

`EnergyPolicy`クラス導入（`docs/superpowers/specs/2026-07-14-jamoraiko-energy-policy-class-design.md`、実装済み）後、ユーザーがKaggle上でノートブックを再実行し、新しい手番選択ログ（`data/jamoraiko_vs_iono_turn_log.json`）を取得した。systematic-debuggingで解析した結果：

- 勝率は200試合中5勝（2.5%）。前回9勝（4.5%）・前々回3勝（1.5%）と比べ、試合数が少なくブレが大きいため一概に悪化とは言えない
- **`EnergyPolicy`の新規実装（`switch_source_score`・`discard_for_damage_score`）は実ログで正しく動作していると確認**：エネルギーつけかえの供給元選択4回全てでタケルライコex自身のエネルギーを選ばず、余剰のあるベンチポケモンを正しく選択していた
- 一方、タイカイデンの特性「フラッシュドロー」が7回発動（前回0回）。全て「手札に雷エネルギーが無い時のみ許可」というTask1のルール通りの発動であり、以前の自滅バグとは異なるが、**タイカイデン自身のエネルギーが1〜2枚と少ない状態でも発動し、結果的にエネルギーが伸びない状態が続く場面**を確認した

ユーザーはこれを「フラッシュドロー依存になっている」と分析し、デッキ内の他のトレーナーズカード（エネルギー回収・エネルギーつけかえ等）がエネルギー供給にどう関わるかを踏まえた構成にすべきか、という問題提起を行った。

その上でユーザーは、個別カードの条件をこれ以上`if`文で積み増すより、**「数千数万行のif文」に向かう手前で構造そのものを見直すこと**を優先する判断を下した。あわせて、将来ドラパルドex等の新デッキに着手する際にも同じ設計パターンを踏襲できるようにしたいという要望が示された。

### 今回のスコープ判断（ユーザー合意済み）

- 個々のカード（フラッシュドロー依存等）の挙動調整は**今回は行わない**。構造そのものの整備を優先する
- **ドラパルドex等への「流用」は設計パターンの流用**であり、コード自体の共有ではない。Kaggle提出は各エージェントごとに`main.py`を1ファイルにまとめる必要がある（`%%writefile`制約）ため、複数エージェント間での物理的なコード共有はビルド時埋め込みの仕組みが別途必要になる。今回はそこまでは踏み込まず、「同じクラス構造を別のエージェントでも同じ形で書ける」という再現可能なパターンの提供にとどめる
- 適用範囲は`_score_play_option`（現在11個の`if card.id == X`分岐）に限定する。`OptionType.ABILITY`分岐（2個）や`_score_switch_target`・`_score_search_candidate`・`_score_discard_candidate`内の個別カードチェックは対象外とし、次回以降パターンが確立してから展開するか判断する
- **今回は設計書・実装計画の作成までとし、実装（コード変更）は次回セッションで行う**

## 設計：`TrainerCardPolicy`レジストリパターン

### 現状の問題

`_score_play_option`は`if card.id == X: return ...`という分岐を11個持つ。新しいトレーナーズカードを追加するたびにこの関数が線形に膨らみ、「数千数万行のif文」に向かう最も分岐が集中している箇所である。また、各カードの判断が完全に独立しており（例：フラッシュドローの判断はエネルギー回収・エネルギーつけかえの状況を一切見ない）、カード間の相互作用を考慮した判断を後から追加しにくい構造になっている。

### 採用する設計

`_score_play_option`のif/elif連鎖を、「カードID→ポリシーオブジェクト」のレジストリ（辞書）に置き換える。新しいカードを追加する際は、分岐を増やすのではなく、小さなポリシークラスを1つ書いてレジストリに登録するだけで済むようにする。

```python
# ==================== PLAYスコアリングのポリシー登録制 ====================
@dataclass
class PlayScoringContext:
    """OptionType.PLAY のスコアリングに必要な情報をまとめる。
    将来カードが増えても、ポリシークラス側のシグネチャを変えずに済む"""
    obs: Observation
    o: "Option"
    my_index: int
    fs: FieldState
    my_state: "PlayerState"
    plan: AttackPlan


class TrainerCardPolicy(ABC):
    """1枚のトレーナーズカード（サポート/グッズ/スタジアム）のPLAY判断を表す"""
    @abstractmethod
    def play_score(self, ctx: PlayScoringContext) -> int: ...


class FixedScorePolicy(TrainerCardPolicy):
    """固定スコアを返すだけのカード用（ハイパーボール等、条件分岐が無いもの）"""
    def __init__(self, score: int):
        self._score = score

    def play_score(self, ctx: PlayScoringContext) -> int:
        return self._score


class LillieDeterminationPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        consumption = _deck_consumption(Lillie_Determination, ctx.my_state, ctx.fs.hand_counts)
        if consumption is not None and consumption > _safe_draws(ctx.my_state):
            return -1
        return 3100


class BossOrdersPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        return 8800 if ctx.plan.is_lethal else 500


class EnergySwitchPolicy(TrainerCardPolicy):
    """既存のENERGY_POLICYに委譲する（EnergyPolicy自体は変更しない）"""
    def play_score(self, ctx: PlayScoringContext) -> int:
        return ENERGY_POLICY.play_score(ctx.my_state)


TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {
    Lillie_Determination: LillieDeterminationPolicy(),
    Boss_Orders: BossOrdersPolicy(),
    Energy_Switch: EnergySwitchPolicy(),
    Buddy_Buddy_Poffin: FixedScorePolicy(8000),
    Ultra_Ball: FixedScorePolicy(6000),
    Night_Stretcher: FixedScorePolicy(4800),
    Energy_Retrieval: FixedScorePolicy(6100),
    Max_Rod: FixedScorePolicy(5500),
    Switch: FixedScorePolicy(2500),
    Canari: FixedScorePolicy(5900),
    Levincia: FixedScorePolicy(8500),
}
```

`_score_play_option`本体は以下のように簡素化される：

```python
def _score_play_option(obs, o, my_index: int, fs: FieldState, my_state, plan: AttackPlan) -> int:
    """OptionType.PLAY のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    data = card_table[card.id]

    if data.cardType == CardType.POKEMON:
        return 20000

    policy = TRAINER_CARD_POLICIES.get(card.id)
    if policy is None:
        return 1000

    ctx = PlayScoringContext(obs=obs, o=o, my_index=my_index, fs=fs, my_state=my_state, plan=plan)
    return policy.play_score(ctx)
```

### なぜこの設計が「フラッシュドロー依存」問題の解決に繋がるか（今回は着手しないが、方向性として）

`PlayScoringContext`は`fs`（`FieldState`）を持つため、将来的にトレーナーズカードのポリシークラスが「今後手札にどれだけエネルギー供給源が残っているか」を判断材料にできる。今回はここまで実装しないが、フラッシュドロー依存の調整に着手する際は、このコンテキストを`OptionType.ABILITY`側にも同様の形で渡せるようにすることが次の一歩になる（今回のスコープ外）。

### 各カードのPOKEMON判定について

`data.cardType == CardType.POKEMON`のケース（進化ポケモン等がPLAYされる場合）は、レジストリの対象外のまま最上部で処理する。これはカードID固有の判断ではなく「型」による判断であり、レジストリパターンになじまないため現状維持とする。

## テスト方針

- `TrainerCardPolicy`の各具象クラス（`LillieDeterminationPolicy`・`BossOrdersPolicy`・`EnergySwitchPolicy`・`FixedScorePolicy`）を個別に単体テストする（`PlayScoringContext`を直接構築して`play_score()`を呼ぶ）
- `_score_play_option`経由の既存テスト（`TestScorePlayOption`）は、レジストリ経由でも同じ結果になることを確認する回帰テストとして残す（振る舞い変更なしのリファクタリングであるため）
- `TRAINER_CARD_POLICIES`に未登録のカードIDが来た場合に1000を返すことのテストを追加する
- 既存の499件のテストスイート全体の回帰確認（`uv run pytest -q`）

## スコープ外（今回はやらないこと）

- フラッシュドロー依存の実際の調整（エネルギー供給源の有無を考慮したABILITY判断の変更）
- `OptionType.ABILITY`分岐・`_score_switch_target`・`_score_search_candidate`・`_score_discard_candidate`のレジストリ化
- 他エージェント（grimmsnarl/lucario/cinderace_starmie/decidueye）への同パターンの展開
- ドラパルドex等の新規デッキ・エージェント構築そのもの
- 前回セッションで保留したresilience調査（ドラパルドex・イワパレス・フーディンとの実対戦速度・タケルライコex撃破後の立て直し力）
- **今回は設計書・実装計画の作成までとし、実装（コード変更）は次回セッションで行う**

## 未検証事項・次のステップ

- 実装完了後、次回以降のセッションで①フラッシュドロー依存の調整に着手するか、②`OptionType.ABILITY`・CARD系サブ選択への展開を検討するか、③resilience調査に戻るかを判断する
- ドラパルドex等の新規エージェントに着手する際、今回確立した`TrainerCardPolicy`パターンが実際に踏襲しやすい形になっているかは、実際にもう1つエージェントを作ってみるまで確証は持てない
