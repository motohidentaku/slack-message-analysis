from argparse import ArgumentParser, Namespace
from datetime import datetime
from typing import Callable, Counter

from sqlalchemy import func

from .common import (
    setup_common_args, setup_token_args, setup_date_range_args, post,
    setup_post_args, get_date_range, get_date_range_str, TARGET_SUBTYPES)
from .models import init_db, transaction, Channel, User, Message


def init_argparser(create_parser: Callable[..., ArgumentParser]) -> None:
    parser = setup_common_args(setup_token_args(setup_date_range_args(
        setup_post_args(create_parser(
            'leaderboard', help='ユーザごとの発言/リアクション数、チャンネルごとの発言数、'
            'リアクションの利用数、チーム単位の発言数を集計し順位表を作成します。\n'
            '--sinceと--until または --day または --week または --month を指定する必要があります。'
        )))))
    parser.add_argument(
        '-n',
        default=10,
        help='上位何位まで表示するかを指定します。(デフォルト: 10位)',
        type=int)
    parser.set_defaults(func=run)


def run(args: Namespace) -> None:
    init_db(args.db)
    since, until = get_date_range(args)

    _user_posts(since, until, args)
    _channel_posts(since, until, args)
    _reactions(since, until, args)


def _user_posts(since: datetime, until: datetime, args: Namespace) -> None:
    with transaction() as s:
        sq = s.query(
            Message.user_id.label('user_id'),
            func.count(Message.user_id).label('count'),
        ).filter(
            Message.timestamp >= since.timestamp(),
            Message.timestamp < until.timestamp(),
            Message.subtype.in_(TARGET_SUBTYPES),
        ).group_by(
            Message.user_id,
        ).order_by(
            func.count(Message.user_id).desc(),
        ).limit(args.n).subquery()
        q = s.query(sq.c.count, User.name).join(User, sq.c.user_id == User.id)

        output = [
            '{} の発言数ランキング'.format(get_date_range_str(since, until, args))]
        for i, (count, name) in enumerate(q):
            output.append('{}. {} ({} posts)'.format(i + 1, name, count))

    print('\n'.join(output))
    print()
    if not args.dry_run and len(output) > 1:
        post(args, '\n'.join(output))


def _channel_posts(since: datetime, until: datetime, args: Namespace) -> None:
    with transaction() as s:
        sq = s.query(
            Message.channel_id.label('channel_id'),
            func.count(Message.channel_id).label('count'),
        ).filter(
            Message.timestamp >= since.timestamp(),
            Message.timestamp < until.timestamp(),
            Message.subtype.in_(TARGET_SUBTYPES),
        ).group_by(
            Message.channel_id,
        ).order_by(
            func.count(Message.channel_id).desc(),
        ).limit(args.n).subquery()
        q = s.query(
            sq.c.count, Channel.name,
        ).join(Channel, sq.c.channel_id == Channel.id)

        output = [
            '{} の人気チャンネルランキング'.format(get_date_range_str(since, until, args))]
        for i, (count, name) in enumerate(q):
            output.append('{}. #{} ({} posts)'.format(i + 1, name, count))

    print('\n'.join(output))
    print()
    if not args.dry_run and len(output) > 1:
        post(args, '\n'.join(output))


def _reactions(since: datetime, until: datetime, args: Namespace) -> None:
    user_counts = Counter[str]()
    reaction_counts = Counter[str]()

    with transaction() as s:
        q = s.query(Message).filter(
            Message.timestamp >= since.timestamp(),
            Message.timestamp < until.timestamp(),
            Message.subtype.in_(TARGET_SUBTYPES))

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
            get_date_range_str(since, until, args))]
    for i, (name, count) in enumerate(user_leaderboard):
        output_user.append('{}. {} ({} reactions)'.format(i + 1, name, count))
    print('\n'.join(output_user))
    print()

    output_reaction = [
        '{} の人気リアクションランキング'.format(
            get_date_range_str(since, until, args))]
    for i, (name, count) in enumerate(reaction_counts.most_common(args.n)):
        output_reaction.append('{}. :{}: ({} 回)'.format(i + 1, name, count))
    print('\n'.join(output_reaction))
    print()

    if not args.dry_run:
        if len(output_user) > 1:
            post(args, '\n'.join(output_user))
        if len(output_reaction) > 1:
            post(args, '\n'.join(output_reaction))
