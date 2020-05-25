from argparse import ArgumentParser
from datetime import datetime


def main() -> None:
    from .collect import main as collect_main

    parser = ArgumentParser()
    subparsers = parser.add_subparsers()

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

    collect_parser = setup_common_args(subparsers.add_parser(
        'collect', help='メッセージを収集しデータベースに格納します'))
    collect_parser.add_argument(
        '--token',
        help='APIトークンを指定します。省略した場合はTOKEN環境変数の値が利用されます。')
    collect_parser.add_argument(
        '--since', help='メッセージ取得開始日時(ISO8601)を指定します。'
        '省略した場合はDBに保存されている最新のメッセージ以降を取得対象とします。',
        type=datetime_parser)
    collect_parser.add_argument(
        '--until', help='メッセージ取得終了日時(ISO8601)を指定します。'
        '省略した場合はコマンド実行日の週の月曜日午前0時になります。',
        type=datetime_parser)
    collect_parser.set_defaults(func=collect_main)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()
