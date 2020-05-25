from argparse import ArgumentParser
from datetime import datetime


def setup_common_args(p: ArgumentParser) -> ArgumentParser:
    # 共通の引数を設定します.
    # 親parser.add_argumentではサブパーサのhelpに表示されないため
    # サブパーサ毎に設定します
    p.add_argument(
        '--db', default='slack.sqlite',
        help='SQLiteのパスを指定します。デフォルトはカレントディレクトリの"slack.sqlite"です')
    return p


def datetime_parser(s: str) -> datetime:
    return datetime.fromisoformat(s)
