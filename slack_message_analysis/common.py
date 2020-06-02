from argparse import ArgumentParser, Namespace
from datetime import datetime, timedelta
import os
import sys
from typing import Tuple, Union, List, Any

from slack import WebClient

TARGET_SUBTYPES = ('', 'thread_broadcast')


def setup_common_args(p: ArgumentParser) -> ArgumentParser:
    # 共通の引数を設定します.
    # 親parser.add_argumentではサブパーサのhelpに表示されないため
    # サブパーサ毎に設定します
    p.add_argument(
        '--db', default='slack.sqlite',
        help='SQLiteのパスを指定します。デフォルトはカレントディレクトリの"slack.sqlite"です')
    p.add_argument(
        '--base-url', default='https://api.slack.com/api/',
        help='Slack APIのURLを指定します (デフォルト: https://api.slack.com/api/)')
    return p


def setup_token_args(p: ArgumentParser) -> ArgumentParser:
    p.add_argument(
        '--token',
        help='APIトークンを指定します。省略した場合はTOKEN環境変数の値が利用されます。')
    return p


def setup_date_range_args(p: ArgumentParser) -> ArgumentParser:
    p.add_argument(
        '--since',
        help='集計開始日時(ISO8601)を指定します',
        type=datetime_parser)
    p.add_argument(
        '--until',
        help='集計終了日時(ISO8601)を指定します',
        type=datetime_parser)
    p.add_argument(
        '--day', action='store_true',
        help='昨日の投稿を集計対象とします')
    p.add_argument(
        '--week', action='store_true',
        help='先週の投稿を集計対象とします')
    p.add_argument(
        '--month', action='store_true',
        help='先週の投稿を集計対象とします')
    return p


def setup_post_args(p: ArgumentParser) -> ArgumentParser:
    p.add_argument(
        '--post',
        help='ポスト先チャンネルIDを指定します。--dry-run未指定時は必須オプションです')
    p.add_argument(
        '--dry-run', action='store_true',
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
    return WebClient(token=token, base_url=args.base_url)


def get_date_range(args: Namespace) -> Tuple[datetime, datetime]:
    since, until = None, None
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if args.day:
        since = today - timedelta(days=1)
        until = today
    elif args.week:
        until = today - timedelta(days=today.weekday())
        since = until - timedelta(days=7)
    elif args.month:
        until = datetime(year=today.year, month=today.month, day=1)
        tmp = until - timedelta(days=1)
        since = datetime(year=tmp.year, month=tmp.month, day=1)
    else:
        if not (args.since and args.until):
            print('集計日時の範囲指定が必要です', file=sys.stderr)
            sys.exit(1)
        since, until = args.since, args.until

    assert since
    assert until
    return since, until


def get_date_range_str(
        since: datetime, until: datetime, args: Namespace) -> str:
    if args.day:
        return '昨日'
    if args.week:
        return '先週'
    if (until - since).days == 1:
        return since.date().isoformat()
    return '{}〜{}'.format(
        since.date().isoformat(),
        (until - timedelta(days=1)).date().isoformat())


def post(args: Namespace, text_or_blocks: Union[str, List[Any]]) -> None:
    client = create_slack_client(args)
    if args.post is None:
        print('ポスト先のチャンネルIDを指定してください',
              file=sys.stderr)
        sys.exit(1)

    if isinstance(text_or_blocks, str):
        blocks = [{
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': text_or_blocks,
            }
        }, {
            'type': 'divider',
        }]
    else:
        blocks = text_or_blocks
    client.chat_postMessage(channel=args.post, blocks=blocks)
