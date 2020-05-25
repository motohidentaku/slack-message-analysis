from argparse import ArgumentParser, Namespace
from datetime import datetime
import os
import sys

from slack import WebClient


def setup_common_args(p: ArgumentParser) -> ArgumentParser:
    # 共通の引数を設定します.
    # 親parser.add_argumentではサブパーサのhelpに表示されないため
    # サブパーサ毎に設定します
    p.add_argument(
        '--db', default='slack.sqlite',
        help='SQLiteのパスを指定します。デフォルトはカレントディレクトリの"slack.sqlite"です')
    return p


def setup_token_args(p: ArgumentParser) -> ArgumentParser:
    p.add_argument(
        '--token',
        help='APIトークンを指定します。省略した場合はTOKEN環境変数の値が利用されます。')
    return p


def setup_dryrun_args(p: ArgumentParser) -> ArgumentParser:
    p.add_argument('--dry-run', action='store_true',
                   help='API投稿を行わず集計のみを行います')
    return p


def datetime_parser(s: str) -> datetime:
    return datetime.fromisoformat(s)


def create_slack_client(args: Namespace) -> WebClient:
    # 引数または環境変数よりTokenを取得してSlack WebClientを初期化
    token = args.token or os.environ.get('TOKEN', None)
    if not token:
        print('--token or TOKEN environment variable required',
              file=sys.stderr)
        sys.exit(1)
    return WebClient(token=token)
