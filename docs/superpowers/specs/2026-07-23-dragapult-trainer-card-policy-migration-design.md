# ドラパルトexエージェント PLAY分岐 TrainerCardPolicy移植 設計書

## 背景・目的

2026-07-23の統合調査レポート（`docs/superpowers/specs/2026-07-23-dragapult-scoring-architecture-investigation-design.md`）で、`src/dragapult_agent/main.py`のif/elif乱立解消の推奨着手順序（案2「A先行・B並走」）が示された。本設計はその「A（TrainerCardPolicy移植）」の第一弾として、`agent()`内`OptionType.PLAY`のカードID分岐（`main.py:800-879`付近、トレーナーズカード17分岐）を、`src/lucario_agent/main.py`・`src/jamoraiko_agent/main.py`で実運用中の`TrainerCardPolicy`パターン（ABC＋登録辞書）へ移植する。

`hand_score()`関数内のカードID分岐（21分岐、15変数以上を捕捉するクロージャ、Night_Stretcherの自己再帰呼び出し、DISCARD/TO_HAND/TO_BENCH/DAMAGE_COUNTER逆算等の複数SelectContextから参照される構造）は、PLAY分岐よりも構造的に複雑でありルカリオ側に対応物が存在しないため、**今回のスコープには含めない**。別セッションで改めて設計する。

RL/オフラインログ観察（統合調査レポートの「B」）も今回は着手せず、バックログに残す。

## アーキテクチャ・コンポーネント

ルカリオ/ジャモライコと同一の構造を移植する。

```python
@dataclass
class PlayTrainerCardContext:
    """OptionType.PLAY のトレーナーズカードのスコアリングに必要な情報をまとめる"""
    card: Card
    card_score: int          # hand_scores[o.index]
    active_id: int
    state: PlayerState
    stadium_id: int
    support_count: int
    hand_counts: defaultdict
    deck_counts: defaultdict
    negative_hand_count: int
    no_draw: bool
    use_support: int
    plan_a: AttackPlan
    no_more_dex: bool
    field_counts: defaultdict


class TrainerCardPolicy(ABC):
    @abstractmethod
    def play_score(self, ctx: PlayTrainerCardContext) -> int: ...


class FixedScorePolicy(TrainerCardPolicy):
    """固定スコアのみを返すカード用（Unfair_Stamp=15000, Crushing_Hammer=40000）"""
    ...


class SupporterSelectedPolicy(TrainerCardPolicy):
    """このターンの最強サポート(use_support)と一致すれば固定スコア、そうでなければ-1。
    Boss_Orders(35000)/Lillie_Determination(14000)/Crispin(35000)/Brock_Scouting(35000)で使い回す"""
    ...


class RareCandyPolicy(TrainerCardPolicy): ...       # no_more_dexゲート
class NightStretcherPolicy(TrainerCardPolicy): ...  # card_score >= 18000 判定（現行の閾値を維持）
class TeamRocketWatchtowerPolicy(TrainerCardPolicy): ...  # stadium_id>0 or turn==1
class BuddyBuddyPoffinPolicy(TrainerCardPolicy): ...      # deck_counts[Dreepy] > 0、no_drawゲート付き
class UltraBallPolicy(TrainerCardPolicy): ...             # negative_hand_count >= 2、no_drawゲート付き
class PokePadPolicy(TrainerCardPolicy): ...               # deck_counts[Dreepy]+deck_counts[Drakloak] > 0、no_drawゲート付き


TRAINER_CARD_POLICIES: dict[int, TrainerCardPolicy] = {
    Rare_Candy: RareCandyPolicy(),
    Unfair_Stamp: FixedScorePolicy(15000),
    Night_Stretcher: NightStretcherPolicy(),
    Crushing_Hammer: FixedScorePolicy(40000),
    Boss_Orders: SupporterSelectedPolicy(35000),
    Lillie_Determination: SupporterSelectedPolicy(14000),
    Team_Rocket_Watchtower: TeamRocketWatchtowerPolicy(),
    Buddy_Buddy_Poffin: BuddyBuddyPoffinPolicy(),
    Ultra_Ball: UltraBallPolicy(),
    Poke_Pad: PokePadPolicy(),
    Crispin: SupporterSelectedPolicy(35000),
    Brock_Scouting: SupporterSelectedPolicy(35000),
}
```

**対象外（現状のif/elifのまま残す）**：Dreepy/Fezandipiti_ex/Latias_ex/Budew/Meowth_exはポケモンカードであり、トレーナーズカードのポリシー辞書には含めない。ルカリオ側と同じく、`card_table[card.id].cardType == CardType.POKEMON`のガードで辞書参照の手前で処理する。

## データフロー・エッジケースの扱い

### `no_draw`ゲートの明示化

現行のif/elif連鎖では、カードID指定のない`elif no_draw: score = -1`（`main.py:858`付近）が、連鎖の中でそれより後ろに書かれているカード（`Buddy_Buddy_Poffin`・`Ultra_Ball`・`Poke_Pad`・`Crispin`・`Brock_Scouting`）だけを暗黙に-1へ落としている。それより前に書かれているカード（`Rare_Candy`・`Unfair_Stamp`・`Night_Stretcher`・`Crushing_Hammer`・`Boss_Orders`・`Lillie_Determination`・`Team_Rocket_Watchtower`）は影響を受けない。

辞書ディスパッチには暗黙のフォールスルーが無いため、この5枚の該当ポリシーだけに`if ctx.no_draw: return -1`を明示的に先頭で行う。挙動は完全に同一のまま、暗黙の副作用をコード上で可視化する。

この挙動（山札残り8枚以下でこれら5枚が一律使用不可になる設計）が本当に意図通りかは今回検証・修正の対象外とし、バックログに「実ログでの意図確認が必要」として残す。

### 未登録カードのフォールバック

現行コードでカードIDがどの分岐にも一致しない場合、`score`はオプションループ先頭の初期値`0`（`main.py:712`）のまま変化しない。ルカリオ側の`10000`とは異なる値のため、本移植でも`TRAINER_CARD_POLICIES.get(card.id)`が`None`の場合のフォールバックは`0`とする。デッキが60枚の閉じた集合であるため実運用では到達しない防御的分岐だが、現状の挙動と一致させる。

## テスト方針

- 現状`hand_score()`・PLAY分岐に専用テストは存在しない（2026-07-23統合調査で確認済み）。移植と同時に、ルカリオ側と同粒度のポリシー単体テストを新設する
- [[feedback_agent_dispatch_coverage]]の教訓に従い、移行前後で対象17カード全ての判定が一致することを確認する回帰テストを追加する（`TRAINER_CARD_POLICIES`のキー集合が、現行if/elif連鎖でカバーされている全カードIDと過不足なく一致することを確認するテストを含む）
- `no_draw`ゲートが掛かる5枚については、`no_draw=True/False`両方のケースを明示的にテストし、現状の挙動を仕様として固定する

## 進め方

- 通常のfeatureブランチで作業する（git worktreeは使わない、ユーザー既定方針）
- `superpowers:writing-plans`で実装計画を作成 → `superpowers:subagent-driven-development`で実装 → 最終ブランチレビュー → `docs/implementations/`に実装サマリー保存

## スコープ外（次回以降）

- `hand_score()`関数内カードID分岐21個のTrainerCardPolicy化（構造がより複雑なため別セッション）
- RL/オフラインログ観察（統合調査レポートの「B」トラック）
- `no_draw`ゲート・no_more_dexの妥当性そのものの検証（実ログでの確認が必要、修正は今回の対象外）
