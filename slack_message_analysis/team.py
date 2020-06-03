from argparse import ArgumentParser, Namespace
import csv
from typing import Callable, Counter

from sqlalchemy import func

from .common import (
    setup_common_args, setup_token_args, setup_date_range_args, post,
    setup_post_args, get_date_range, get_date_range_str, TARGET_SUBTYPES)
from .models import init_db, transaction, User, Message


def init_argparser(create_parser: Callable[..., ArgumentParser]) -> None:
    parser = setup_common_args(setup_token_args(setup_date_range_args(
        setup_post_args(create_parser(
            'team', help='チームごとの発言数を集計します。\n'
            '--sinceと--until または --day または --week または --month を指定する必要があります。'
        )))))
    parser.add_argument(
        '-n',
        default=10,
        help='上位何位まで表示するかを指定します。(デフォルト: 10位)',
        type=int)
    parser.add_argument(
        '--team',
        default='team_master.csv',
        help='メンバとチームを定義づけたCSVファイル')
    parser.set_defaults(func=run)


def run(args: Namespace) -> None:
    init_db(args.db)
    since, until = get_date_range(args)

    # CSVを読み込みユーザ(e-mail)とチーム名のマッピングを取得する
    team_master = {}
    with open(args.team, newline='', encoding='utf8') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        next(reader)  # skip header
        for email, team_name, _, _ in reader:
            team_master[email] = team_name

    team_posts = Counter[str]()
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
        ).subquery()
        q = s.query(sq.c.count, User.email).join(User, sq.c.user_id == User.id)

        for count, email in q:
            tmp = team_master.get(email)
            if tmp is None:
                continue
            team_posts[tmp] += count

    output = ['{} のチーム発言数ランキング'.format(
        get_date_range_str(since, until, args))]
    for i, (name, count) in enumerate(team_posts.most_common(args.n)):
        output.append('{}. {} ({} posts)'.format(i + 1, name, count))
    print('\n'.join(output))
    print()

    if not args.dry_run and len(output) > 1:
        post(args, '\n'.join(output))
