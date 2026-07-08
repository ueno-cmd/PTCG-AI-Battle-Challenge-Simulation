# Python if文 設計ガイドライン

> 参考記事: [ifが増えすぎたコードの共通点と直し方](https://python.cbagames.jp/2026/01/17/python-too-many-if-statements/)

## 0. このガイドラインの目的

`if`文そのものは悪ではありません。問題なのは、**「分岐（条件によって処理を変えること）」が場当たり的に積み重なり、コードの見通しが悪くなること**です。

このガイドラインは、「if文を書くな」ではなく「if文が増え続ける構造を作らない」ことを徹底するためのルール集です。チーム開発・個人開発を問わず、コードレビューやセルフチェックの基準として使用してください。

---

## 1. 基本方針（最上位ルール）

| # | ルール | 理由 |
|---|--------|------|
| 1 | ネスト（入れ子構造）は **2階層まで** | 3階層以上は人間の脳内スタックが追えなくなる |
| 2 | 1つの関数の中で「判断（何をすべきか決める）」と「処理（実際に実行する）」を混在させない | 責務（役割）を分離すると、テストしやすく再利用しやすい |
| 3 | 分岐が3パターン以上になったら `if-elif` 連鎖ではなく **辞書（dict）や関数マッピング** を検討する | 条件が増えるたびにコードを書き足す構造を避ける |
| 4 | 複雑な条件式（`and`/`or`が混在するもの）はそのままif文に書かず、**意味のある変数名・関数名** を与える | 「何を判定しているか」が一目でわかるようにする |

---

## 2. 具体的コーディング規則

### 2-1. ガード節（早期リターン）でネストを浅くする

深いネストは「例外パターンを先に弾く」ことで解消できます。

**❌ Before（ネストが深い・悪い例）**

```python
def process_order(order):
    if order is not None:
        if order.is_valid():
            if order.stock_available():
                # 本来やりたい処理がここまで埋もれる
                return execute_order(order)
            else:
                return "在庫がありません"
        else:
            return "不正な注文です"
    else:
        return "注文が存在しません"
```

**✅ After（ガード節で早期リターン）**

```python
def process_order(order):
    # 例外的なケースを先に弾く（ガード節）
    if order is None:
        return "注文が存在しません"
    if not order.is_valid():
        return "不正な注文です"
    if not order.stock_available():
        return "在庫がありません"

    # 本来やりたい処理が最後にすっきり残る
    return execute_order(order)
```

> **ルール**: ネストは最大2階層まで。3階層目に入りそうになったら、ガード節で条件を先に処理できないか検討する。

---

### 2-2. 「判断」と「処理」を分離する

条件分岐のロジック（判断）と、実際の処理（実行）を1つの関数に詰め込まない。

**❌ Before（判断と処理が混在）**

```python
def send_notification(user, message):
    if user.role == "admin":
        if user.email_verified:
            send_email(user.email, message)
        send_slack(user.slack_id, message)
    elif user.role == "member":
        if user.email_verified:
            send_email(user.email, message)
    else:
        pass
```

**✅ After（判断＝どのチャネルを使うか決める処理と、送信処理を分離）**

```python
def get_notification_channels(user) -> list[str]:
    """ユーザーの役割に応じて通知チャネル（連絡手段）を判断する"""
    channels = []
    if user.role == "admin":
        channels.append("slack")
    if user.email_verified:
        channels.append("email")
    return channels


def send_notification(user, message):
    """判断結果に基づいて実際に送信する（実行のみに専念）"""
    channels = get_notification_channels(user)
    if "email" in channels:
        send_email(user.email, message)
    if "slack" in channels:
        send_slack(user.slack_id, message)
```

> **ルール**: 「何をすべきか決める部分」と「実際に実行する部分」を別関数に分ける。テストする際も、判断ロジックだけを単体でテストできるようになる。

---

### 2-3. if-elif連鎖は辞書（dict）マッピングに置き換える

分岐が増えるたびに `elif` を書き足す構造は、将来的な保守コストが高くなります。

**❌ Before（elif連鎖）**

```python
def get_discount_rate(membership):
    if membership == "bronze":
        return 0.05
    elif membership == "silver":
        return 0.10
    elif membership == "gold":
        return 0.15
    elif membership == "platinum":
        return 0.20
    else:
        return 0.0
```

**✅ After（辞書マッピング）**

```python
DISCOUNT_RATES = {
    "bronze": 0.05,
    "silver": 0.10,
    "gold": 0.15,
    "platinum": 0.20,
}

def get_discount_rate(membership):
    # 該当がなければ0.0（デフォルト値）を返す
    return DISCOUNT_RATES.get(membership, 0.0)
```

> **ルール**: `if-elif` の分岐が3パターン以上になったら、辞書やマッピングによる置き換えを検討する。ただし、分岐ごとに複雑な処理が必要な場合は無理に辞書化しない（3-2章参照）。

---

### 2-4. 複雑な条件式には名前をつける

`and`/`or` が混在する条件は、意味を読み取るのに時間がかかります。

**❌ Before（条件式がそのまま埋め込まれている）**

```python
if (user.age >= 18 and user.age <= 65) and (user.is_verified or user.is_admin):
    grant_access(user)
```

**✅ After（意味のある変数名を付ける）**

```python
is_working_age = 18 <= user.age <= 65
has_access_right = user.is_verified or user.is_admin

if is_working_age and has_access_right:
    grant_access(user)
```

> **ルール**: 条件式が2つ以上の演算子（`and`/`or`）を含む場合は、変数に切り出して名前をつける。

---

### 2-5. ループ内の単純なifは内包表記を検討する（ただし乱用しない）

**❌ Before**

```python
result = []
for item in items:
    if item.is_active:
        result.append(item.name)
```

**✅ After（単純な絞り込みのみの場合）**

```python
result = [item.name for item in items if item.is_active]
```

> **ルール**: 「絞り込み（filter）」と「変換（map）」のみのシンプルな処理に限り内包表記を使う。条件分岐の中でさらに処理が枝分かれする場合は、無理に1行に圧縮せず通常の`for`文を使う（可読性を優先）。

---

## 3. セルフチェック・レビュー用チェックリスト

コードを書き終えたら、以下を確認してください。

- [ ] ネストは2階層以内に収まっているか
- [ ] 「例外的なケース」をガード節で先に弾けないか
- [ ] 1つの関数が「判断」と「処理」の両方をやっていないか
- [ ] `if-elif` が3分岐以上続いていないか（辞書化の余地がないか）
- [ ] `and`/`or` が混在する条件式に、意味のある名前をつけたか
- [ ] 内包表記が「絞り込み・変換」の範囲を超えて複雑になっていないか

---

## 4. やりすぎ注意（アンチパターン化の防止）

ルールを機械的に適用しすぎると、かえって可読性を損なう場合があります。以下は避けてください。

- **なんでも辞書化しない**: 分岐ごとの処理が複雑・非対称な場合、無理に辞書にまとめるとかえって読みにくくなる。単純な値の対応表のときだけ使う。
- **デザインパターンの過剰適用**: Strategyパターンなどのオブジェクト指向設計は強力だが、小規模なスクリプトに導入すると過剰設計になりやすい。関数分割で十分な場合はそちらを優先する。
- **内包表記の詰め込みすぎ**: 1行に条件・変換・ネストを詰め込むと、`for`文より読みにくくなることがある。迷ったら通常の`for`文を選ぶ。

**原則**: ルールはあくまで「読みやすさ・保守しやすさ」のための手段であり、目的ではありません。チームやプロジェクトの状況に応じて柔軟に適用してください。

---

## 5. まとめ

| 症状 | 対処法 |
|------|--------|
| ネストが深い | ガード節（早期リターン） |
| 1関数が長い・複雑 | 判断と処理の分離 |
| elif連鎖が続く | 辞書マッピング |
| 条件式が読みにくい | 変数・関数への切り出し |
| ループ内if | 内包表記（単純な場合のみ） |

---

*このガイドラインは以下の記事の内容を参考に構成しています。*
*出典: [ifが増えすぎたコードの共通点と直し方](https://python.cbagames.jp/2026/01/17/python-too-many-if-statements/)*