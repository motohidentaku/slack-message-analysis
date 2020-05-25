from argparse import ArgumentParser, Namespace
from datetime import datetime, timedelta
from typing import Callable, Counter
import sys

from sqlalchemy import func

from .common import (
    setup_common_args, setup_token_args, setup_dryrun_args, datetime_parser,
    create_slack_client)
from .models import init_db, transaction, Channel, User, Message


def init_argparser(create_parser: Callable[..., ArgumentParser]) -> None:
    parser = setup_common_args(setup_token_args(setup_dryrun_args(
        create_parser(
            'leaderboard', help='ユーザごとの発言/リアクション数、チャンネルごとの発言数、'
            'リアクションの利用数、チーム単位の発言数を集計し順位表を作成します。\n'
            '--sinceと--until または --day または --week または --month を指定する必要があります。'
        ))))
    parser.add_argument(
        '--post',
        help='ポスト先チャンネルIDを指定します。--dry-run未指定時は必須オプションです')
    parser.add_argument(
        '--since',
        help='集計開始日時(ISO8601)を指定します',
        type=datetime_parser)
    parser.add_argument(
        '--until',
        help='集計終了日時(ISO8601)を指定します',
        type=datetime_parser)
    parser.add_argument(
        '-n',
        default=10,
        help='上位何位まで表示するかを指定します。(デフォルト: 10位)',
        type=int)
    parser.add_argument(
        '--day', action='store_true',
        help='昨日の投稿を集計対象とします')
    parser.add_argument(
        '--week', action='store_true',
        help='先週の投稿を集計対象とします')
    parser.add_argument(
        '--month', action='store_true',
        help='先週の投稿を集計対象とします')
    parser.set_defaults(func=run)


def run(args: Namespace) -> None:
    # DB初期化
    init_db(args.db)

    # 集計日時の範囲を取得
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
            return
        since, until = args.since, args.until

    assert since
    assert until

    _user_posts(since, until, args)
    _channel_posts(since, until, args)
    _reactions(since, until, args)


def _post(msg: str, args: Namespace) -> None:
    client = create_slack_client(args)
    if args.post is None:
        print('集計結果ポスト先のチャンネルIDを指定してください',
              file=sys.stderr)
        sys.exit(1)
    client.chat_postMessage(channel=args.post, blocks=[{
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': msg
        }
    }, {
        'type': 'divider'
    }])


def _get_range_msg(since: datetime, until: datetime, args: Namespace) -> str:
    if args.day:
        return '昨日'
    if args.week:
        return '先週'
    if (until - since).days == 1:
        return since.date().isoformat()
    return '{}〜{}'.format(
        since.date().isoformat(),
        (until - timedelta(days=1)).date().isoformat())


def _user_posts(since: datetime, until: datetime, args: Namespace) -> None:
    with transaction() as s:
        sq = s.query(
            Message.user_id.label('user_id'),
            func.count(Message.user_id).label('count'),
        ).filter(
            Message.timestamp >= since.timestamp(),
            Message.timestamp < until.timestamp(),
            Message.subtype == '',
        ).group_by(
            Message.user_id,
        ).order_by(
            func.count(Message.user_id).desc(),
        ).limit(args.n).subquery()
        q = s.query(sq.c.count, User.name).join(User, sq.c.user_id == User.id)

        output = [
            '{} の発言数ランキング'.format(_get_range_msg(since, until, args))]
        for i, (count, name) in enumerate(q):
            output.append('{}. {} ({} posts)'.format(i + 1, name, count))

    print('\n'.join(output))
    print()
    if not args.dry_run and len(output) > 1:
        _post('\n'.join(output), args)


def _channel_posts(since: datetime, until: datetime, args: Namespace) -> None:
    with transaction() as s:
        sq = s.query(
            Message.channel_id.label('channel_id'),
            func.count(Message.channel_id).label('count'),
        ).filter(
            Message.timestamp >= since.timestamp(),
            Message.timestamp < until.timestamp(),
            Message.subtype == '',
        ).group_by(
            Message.channel_id,
        ).order_by(
            func.count(Message.channel_id).desc(),
        ).limit(args.n).subquery()
        q = s.query(
            sq.c.count, Channel.name,
        ).join(Channel, sq.c.channel_id == Channel.id)

        output = [
            '{} の人気チャンネルランキング'.format(_get_range_msg(since, until, args))]
        for i, (count, name) in enumerate(q):
            output.append('{}. #{} ({} posts)'.format(i + 1, name, count))

    print('\n'.join(output))
    print()
    if not args.dry_run and len(output) > 1:
        _post('\n'.join(output), args)


def _reactions(since: datetime, until: datetime, args: Namespace) -> None:
    user_counts = Counter[str]()
    reaction_counts = Counter[str]()

    with transaction() as s:
        q = s.query(Message).filter(
            Message.timestamp >= since.timestamp(),
            Message.timestamp < until.timestamp(),
            Message.subtype == '')

        for m in q:
            reactions = m.raw.get('reactions', [])
            for r in reactions:
                user_counts.update({
                    user_id: 1 for user_id in r.get('users', [])})
                reaction_counts[r['name']] += r['count']

        user_leaderboard = []
        for user_id, count in user_counts.most_common(args.n):
            name = s.query(User.name).filter(User.id == user_id).scalar()
            if name is None:
                continue
            user_leaderboard.append((name, count))

    output_user = [
        '{} のリアクション数ランキング'.format(
            _get_range_msg(since, until, args))]
    for i, (name, count) in enumerate(user_leaderboard):
        output_user.append('{}. {} ({} reactions)'.format(i + 1, name, count))
    print('\n'.join(output_user))
    print()

    output_reaction = [
        '{} の人気リアクションランキング'.format(
            _get_range_msg(since, until, args))]
    for i, (name, count) in enumerate(reaction_counts.most_common(args.n)):
        output_reaction.append('{}. :{}: ({} 回)'.format(i + 1, name, count))
    print('\n'.join(output_reaction))
    print()

    if not args.dry_run:
        if len(output_user) > 1:
            _post('\n'.join(output_user), args)
        if len(output_reaction) > 1:
            _post('\n'.join(output_reaction), args)
