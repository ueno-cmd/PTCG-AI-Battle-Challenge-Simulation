# ルカリオexエージェント トレーナーズカード ポリシー登録制＋2件のロジック修正 設計書

## 背景

`docs/analyses/20260717-lucario-real-battle-logs-analysis.md`（ルカリオexデッキの実戦バトルログ22件解析）で、`src/lucario_agent/main.py`の`_score_play_option`に以下2つのロジックミスを実測で確認した。

1. **リーリエの決意（`Lillie_Determination`）が手札の質を見ずに固定スコア3100を返す**。実ログで、手札にメガルカリオex・オーガポンex・リオル・ソルロックなど有用な札が揃っている状態でも発動し、山札に戻してしまう事例を複数確認済み（`86363073`, `86197001`, `86241854`, `86295193`, `86295949`等）
2. **ハイパーボール（`Ultra_Ball`）が主要ポケモンを確保済みでもほぼスコアが下がらない**（`already_found==0`なら6000、1以上でも5500）。`86197001`戦では手札がボスの指令とメガルカリオexの2枚しかない状況でもハイパーボールを撃ち、両方とも巻き込んで捨てていた

さらに`86197001`戦の生ログを1ステップずつ追跡した結果、この試合は開幕直後から自分の攻撃が一度も無いまま20ターンで敗北しており、直接の起点は**`SelectContext.SETUP_ACTIVE_POKEMON`のスコアリングがオーガポンexを優先しないこと**だった。開幕手札にリオル・ソルロックが無く、ルナトーン（攻撃不可）とオーガポンex（3エネで攻撃可能）が両方あった場面で、両者とも同点0のためルナトーンが選ばれてしまい、以後ルナトーンはエネルギー無しで自力で逃げられずアクティブに居座り続けた（オーガポンexとメガルカリオexは十分なエネルギーを装填されながらベンチに温存され続けた）。

ユーザーから、ジャモライコで2026-07-14に実装済みの`TrainerCardPolicy`レジストリパターンをルカリオにも適用し、上記2件のPLAYロジック修正・SETUP_ACTIVE_POKEMONの修正を**同一セッションでまとめて**行う方針が示された（[[feedback_fix_and_refactor_together]]：修正とリファクタは並行必須、という既存方針に沿う）。

### 今回のスコープ判断（ユーザー合意済み）

- クラス化の対象は`_score_play_option`（トレーナーズカードの`if card.id == X`分岐、11個）**のみ**。`_score_card_option`内のSWITCH/TO_ACTIVE/TO_HAND/DISCARD等の他の分岐や`calc_attack_plan`のアタッカー候補if/elif連鎖は対象外。ただし目を通した上で気づいた点はコード内コメントとして残す（機能変更はしない）
- **リーリエの決意**：手札に主要ポケモン（Riolu/Mega_Lucario_ex/Ogerpon_ex/Solrock/Lunatoneのいずれか）が1枚でもあればスコアを抑制し温存する
- **ハイパーボール**：主要ポケモンを十分確保済み（`already_found`が閾値以上）ならスコアを大幅に下げる
- **SETUP_ACTIVE_POKEMON**：オーガポンexにルナトーン（0点）より高いスコアを与え、両方が候補にある場合はオーガポンexが選ばれるようにする。ルナトーン単体しか無い場合はこれまで通りルナトーンが選ばれる（他に選択肢が無いため変更不要）
- ジャモライコ側の`LillieDeterminationPolicy`にも同じ固定3100バグが残っていることを確認済みだが、**今回はルカリオのみを対象とし、ジャモライコへの横展開は次回セッションに持ち越す**
- ジャモライコとの間で物理的なコード共有は行わない（2026-07-14に既に合意済み：Kaggle提出は各デッキ`main.py`単一ファイル構成のため、流用は「設計パターンの流用」に留める）

## 設計①：`TrainerCardPolicy`レジストリパターン（ジャモライコと同じ骨格）

### 現状の問題

`_score_play_option`は`if card.id == X: return ...`という分岐を11個（Premium_Power_Pro / Boss_Orders / Lillie_Determination / Ultra_Ball / Pokegear / Night_Stretcher / Judge / Hilda / Ciphermaniac_Codebreaking / Wally_Compassion / Gravity_Mountain）持つ、約65行の関数になっている。

### 採用する設計

```python
@dataclass
class PlayScoringContext:
    """OptionType.PLAY のスコアリングに必要な情報をまとめる（既存の_score_play_option引数をそのまま集約）"""
    obs: Observation
    o: "Option"
    my_index: int
    current_plan: AttackPlan
    can_attack: bool
    state: "PlayerState"
    my_state: "PlayerState"
    hand_counts: defaultdict
    field_counts: defaultdict
    stadium_id: int
    attacker1: bool = False
    rng: "random.Random | None" = None


class TrainerCardPolicy(ABC):
    """1枚のトレーナーズカード（サポート/グッズ/スタジアム）のPLAY判断を表す"""
    @abstractmethod
    def play_score(self, ctx: PlayScoringContext) -> int: ...


class FixedScorePolicy(TrainerCardPolicy):
    """固定スコアのみのカード用（Pokegear/Night_Stretcher/Hilda/Ciphermaniac_Codebreaking）"""
    def __init__(self, score: int):
        self._score = score

    def play_score(self, ctx: PlayScoringContext) -> int:
        return self._score


class PremiumPowerProPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        # 既存if分岐（478-487行目）をそのまま移植
        ...


class BossOrdersPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        # 既存if分岐（488-496行目）をそのまま移植
        ...


class LillieDeterminationPolicy(TrainerCardPolicy):
    """★修正対象：手札に主要ポケモンがあれば温存する"""
    KEY_POKEMON_IDS = (Riolu, Mega_Lucario_ex, Ogerpon_ex, Solrock, Lunatone)

    def play_score(self, ctx: PlayScoringContext) -> int:
        if any(ctx.hand_counts[pid] >= 1 for pid in self.KEY_POKEMON_IDS):
            return -1
        return 3100


class UltraBallPolicy(TrainerCardPolicy):
    """★修正対象：主要ポケモンを十分確保済みなら大幅に抑制する"""
    ALREADY_FOUND_SUPPRESS_THRESHOLD = 3  # 閾値は実装時にテストで調整

    def play_score(self, ctx: PlayScoringContext) -> int:
        already_found = (
            ctx.field_counts[Riolu] + ctx.field_counts[Mega_Lucario_ex] + ctx.field_counts[Ogerpon_ex]
            + ctx.hand_counts[Riolu] + ctx.hand_counts[Mega_Lucario_ex] + ctx.hand_counts[Ogerpon_ex]
        )
        if already_found >= self.ALREADY_FOUND_SUPPRESS_THRESHOLD:
            return 100  # 他の有用なプレイに道を譲る
        return 6000 if already_found == 0 else 5500


class JudgePolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        # 既存if分岐（509-510行目）をそのまま移植
        ...


class WallyCompassionPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        # 既存if分岐（515-523行目）をそのまま移植
        ...


class GravityMountainPolicy(TrainerCardPolicy):
    def play_score(self, ctx: PlayScoringContext) -> int:
        # 既存if分岐（524-525行目）をそのまま移植
        ...


TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {
    Premium_Power_Pro: PremiumPowerProPolicy(),
    Boss_Orders: BossOrdersPolicy(),
    Lillie_Determination: LillieDeterminationPolicy(),
    Ultra_Ball: UltraBallPolicy(),
    Pokegear: FixedScorePolicy(5200),
    Night_Stretcher: FixedScorePolicy(4800),
    Judge: JudgePolicy(),
    Hilda: FixedScorePolicy(5300),
    Ciphermaniac_Codebreaking: FixedScorePolicy(5100),
    Wally_Compassion: WallyCompassionPolicy(),
    Gravity_Mountain: GravityMountainPolicy(),
}
```

`_score_play_option`本体は以下のように簡素化される（山札温存ガードは全カード共通の前置処理として残す）：

```python
def _score_play_option(obs, o, my_index, current_plan, can_attack,
                       state, my_state, hand_counts, field_counts, stadium_id,
                       attacker1: bool = False,
                       rng: "random.Random | None" = None) -> int:
    """OptionType.PLAY のスコアを返す"""
    card = get_card(obs, AreaType.HAND, o.index, my_index)
    data = card_table[card.id]
    consumption = _deck_consumption(card.id, my_state, hand_counts)
    if consumption is not None and consumption > _safe_draws(my_state):
        return -1  # 山札温存
    if data.cardType == CardType.POKEMON:
        if card.id in (Lunatone, Solrock):
            return -1 if field_counts[card.id] >= 1 else 20000
        if card.id == Riolu:
            return -1 if field_counts[Riolu] + field_counts[Mega_Lucario_ex] >= 2 else 20000
        return 20000

    policy = TRAINER_CARD_POLICIES.get(card.id)
    if policy is None:
        return 10000

    ctx = PlayScoringContext(
        obs=obs, o=o, my_index=my_index, current_plan=current_plan, can_attack=can_attack,
        state=state, my_state=my_state, hand_counts=hand_counts, field_counts=field_counts,
        stadium_id=stadium_id, attacker1=attacker1, rng=rng,
    )
    return policy.play_score(ctx)
```

### ジャモライコとの意図的な差分

ジャモライコ側は山札温存チェックを`LillieDeterminationPolicy`内で個別に行っているが、ルカリオの現行コードはこのチェックを全トレーナーズカード共通の前置ガードとして`_score_play_option`の先頭で一括処理している（`Lillie_Determination`/`Judge`/`Hilda`/`Pokegear`/`Ultra_Ball`/`Poke_Pad`が対象）。挙動を変えずに安全にクラス化するため、**この共通ガードは今回もラッパー関数側に残す**（Jamoraikoと完全に同じ構造にはしないが、機能的には既存と同等）。

未登録カードのフォールバック値は、ジャモライコの`1000`ではなくルカリオの既存デフォルト`10000`をそのまま踏襲する（Fighting_Gong・Poke_Padが対象、挙動を変えないため）。

## 設計②：SETUP_ACTIVE_POKEMONの優先度修正

```python
case SelectContext.SETUP_ACTIVE_POKEMON:
    if card.id == Solrock:
        return 4 if state.firstPlayer != my_index else 2
    if card.id == Riolu:
        return 3
    if card.id == Ogerpon_ex:
        return 1  # ルナトーン(0点)より優先。Riolu/Solrockには劣後させたまま
    return 0
```

オーガポンexとルナトーンが同時に開幕手札にある場合はオーガポンexが選ばれるようになる。ルナトーン単体しか無い場合は他に選びようが無いため、これまで通りルナトーンが選ばれる（変更なし）。

## 対象外だが目を通す箇所（コメントのみ、機能変更なし）

- `_score_card_option`のSWITCH/TO_ACTIVE分岐（379-394行目）：`current_plan.attacker`はSelectContext.MAIN・turn>=2でのみ再計算されるグローバル状態のため、それ以外のタイミングで発生するSWITCH/TO_ACTIVE判断では古い値のままになりうる。今回の`86197001`戦の直接原因では無かったが、潜在的なリスクとして次回検討の余地がある旨をコメントで残す
- `calc_attack_plan`のアタッカー候補if/elif連鎖（Mega_Lucario_ex/Solrock/Ogerpon_ex）：2026-07-07時点で「案A（アタッカー定義のみのテーブル化）」の検討が中断したままの経緯があり、今回は着手しない旨をコメントで残す

## テスト方針

1. **既存回帰テスト**：`tests/test_lucario_agent.py`の既存テスト（`_score_play_option`を直接呼ぶもの含む）は関数シグネチャを変えないため無改修で全てPASSさせる
2. **`TrainerCardPolicy`各クラスの単体テスト**：`PlayScoringContext`を直接構築して`play_score()`を呼ぶテストを追加（`FixedScorePolicy`・`PremiumPowerProPolicy`・`BossOrdersPolicy`・`JudgePolicy`・`WallyCompassionPolicy`・`GravityMountainPolicy`は既存の`TestScorePlayOption`のケースをそのまま移植）
3. **リーリエの決意ガード（新規）**：`KEY_POKEMON_IDS`の各カードが手札にある場合に温存されること／どれも無ければ従来通り3100のままであることをパラメタライズドテストで確認
4. **ハイパーボール抑制（新規）**：`already_found`が閾値未満なら従来スコア（6000/5500）を維持、閾値以上なら大幅に下がることを確認。既存の`TestUltraBallAlreadyFoundIncludesOgerponEx`等の既存テストが変わらず通ることも確認
5. **SETUP_ACTIVE_POKEMON（新規）**：オーガポンexとルナトーンが両方候補にある場合はオーガポンexが上回ること／ルナトーン単体では従来通り0点のままであることを確認
6. **実ログ再現テスト（新規）**：既存の`TestReplays85626724DeckOutLoss`と同じパターンで、`86197001`戦の開幕手札条件（オーガポンexとルナトーンが手札にあり、リオル/ソルロックが無い状況）を再現し、修正後はオーガポンexが選ばれることを確認するテストを追加
7. 最後に`uv run pytest -q`でリポジトリ全体を実行し回帰が無いことを確認

## スコープ外（今回はやらないこと）

- `_score_card_option`のSWITCH/TO_ACTIVE/TO_HAND/DISCARD分岐、`calc_attack_plan`のアタッカー候補if/elif連鎖のリファクタリング（コメントのみ残す）
- ジャモライコ側`LillieDeterminationPolicy`の同種バグ修正（次回セッションに持ち越し）
- ジャモライコとルカリオ間の物理的なコード共有化
- Alakazam系対策（1勝5敗の弱点、今回とは別テーマとして今後検討）
- RETREAT未実装への対応

## 未検証事項・次のステップ

- 実装完了後、デッキCSV再生成・Kaggle再提出でスコア変化を確認する必要がある（ユーザー側で別途実施、[[feedback_scope_out_needs_explicit_confirmation]]の教訓に沿い、この点は実装完了後に改めて明示的に確認する）
- `ALREADY_FOUND_SUPPRESS_THRESHOLD`（ハイパーボール抑制の閾値、暫定3）は実装時のテストケースを書きながら適切な値かどうかを再検討する
- ジャモライコ側の同種バグ（`LillieDeterminationPolicy`固定3100）・Alakazam対策・RETREAT未実装は次回セッションで改めて優先度を判断する
