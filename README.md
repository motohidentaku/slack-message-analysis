# slack-message-analysis

アプリが登録されている全チャンネルから発言を収集し、各種集計を行う。

## 事前準備

* Python 3.7以降 (3.8で動作確認してます)
* [Poetry](https://python-poetry.org/) (パッケージ管理ツール)

## インストール方法

```
$ poetry install
```

## 使い方

poetryのshellに入ってCLIを実行する

```
$ poetry shell
$ slack-message-analysis --help
```

poetryのrunでCLIを実行する

```
$ poetry run slack-message-analysis --help
```

poetryでパッケージングしてpipでインストールする

```
$ poetry build
$ pip install dist/slack_message_analysis-*.whl
$ slack-message-analysis
```

### 発言を収集する

以下の引数が利用可能です

* `--token <TOKEN>`: APIトークンを指定します。省略時は`TOKEN`環境変数の値を利用します。
  両方共設定されていない場合はエラーで終了します。
* `--since 2020-05-25`: 2020-05-25 00:00:00らの発言を収集対象とする。
  省略時はデータベースに保存されている最も新しい発言以降の発言を収集対象とします。
  データベースに発言が保存されていない場合は取得可能な最も古い発言から取得します。
* `--until 2020-05-26`: 2020-05-26 00:00:00までの発言を収集対象とする。
  省略時は現在の週の月曜日の00:00:00までの発言を収集対象とします。

既にデータベースに保存されている発言を再度取得した場合は、
新しいデータで上書きします。

```
$ slack-message-analysis collect
$ slack-message-analysis collect --since 2020-05-25
$ slack-message-analysis collect --since 2020-05-25T12:23:34
$ slack-message-analysis collect --since 2020-05-25T12:23:34 --until 2020-06-01
$ slack-message-analysis collect --until 2020-06-01T01:23:45
```

### 発言数・リアクション数の多いユーザランキング、投稿数の多いチャンネルランキング、利用数の多いリアクション数ランキングを集計する

```
$ slack-message-analysis leaderboard --post <集計結果投稿先チャンネルID> --day   # 昨日
$ slack-message-analysis leaderboard --post <集計結果投稿先チャンネルID> --week  # 先週
$ slack-message-analysis leaderboard --post <集計結果投稿先チャンネルID> --since 2020-05-25 --until 2020-06-01
```

※発言を収集を同様に`--token`や`TOKEN`環境変数の指定が必要です。
投稿せずに結果だけみたい場合は`--dry-run`を指定してください。

## 開発方法

### 静的チェック等

```
$ flake8 slack_message_analysis
$ mypy -p slack_message_analysis
```

### サブコマンドの追加(分析モジュールの追加)

`slack_message_analysis` ディレクトリ配下に以下の関数を持つファイルを配置する。

```python
from argparse import ArgumentParser, Namespace
from typing import Callable

from .common import setup_common_args


def init_argparser(create_parser: Callable[..., ArgumentParser]) -> None:
    parser = setup_common_args(create_parser(
        'hoge', help='hogeコマンド'))
    parser.add_argument(
        '--fuga', help='テスト引数')
    parser.set_defaults(func=run)

def run(args: Namespace) -> None:
    print('slack-message-analysis hogeしたときに呼び出される')
```

`parser.set_defaults(func=run)` の`func`キーワード引数に指定する関数名を変更することにより
`run`関数は任意の名前とすることができる。

# (deprecated)

アプリが登録されている全チャンネルからチャネル別、ユーザ別の発言数を集計する

## 設定
9行目のtokenをslack APIのトークンに変更

## 使い方
引数に集計対象開始日と日数を渡すと、開始日+日数を対象として集計を行う
```sh
python3 slack_analysis.py <8桁表記の集計開始日> <日数>
```

例
```sh
python3 slack_analysis.py 20200410 10
```

## 追加分析
lib配下のモジュールを利用して追加で分析が可能。追加でモジュールを開発していきたい。
開発に関する情報は下記

### インプット
下記の2種類のインプットを利用可能。dummydataフォルダにダミーデータが格納してある
mes.csv
日付,チャンネル,名前,メールアドレス,メッセージ数
```sh
date,ch,name,email,mes
```

team_master.csv
メールアドレス,チーム名,組織名,役職
※メールアドレスでmes.csvと結合可能
```sh
email,team_name,organization,position
```

### 分析
TOPフォルダから下記の形式で実行すると、outputフォルダに結果を格納する
```sh
python3 lib/calc_monthly_team.py
```

### モジュールの作り方（暫定）
上記の方法で直接実行すると、outputフォルダに結果を格納する。
他モジュールから読めるように、クラスを実装し、calcメソッドを実行するとoutputフォルダに結果を格納するようにしたい。
引数は必要に応じて設定する。サンプルはlib/calc_monthly_team.py
