from argparse import ArgumentParser, Namespace
import csv
from dataclasses import dataclass
import json
import time
from typing import Any, Callable, Dict

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
        '--sort',
        choices=['total', 'average'],
        default='average',
        help='順位の付け方を指定します。デフォルトは平均投稿数(合計投稿数÷所属メンバ数)です。')
    parser.add_argument(
        '--team',
        default='team_master.csv',
        help='メンバとチームを定義づけたCSVファイル')
    parser.add_argument(
        '--json', help='JSON形式で結果を出力します')
    parser.set_defaults(func=run)


def run(args: Namespace) -> None:
    init_db(args.db)
    since, until = get_date_range(args)

    # CSVを読み込みユーザ(e-mail)とチーム名のマッピングを取得する
    teams: Dict[str, TeamSummary] = {}
    team_master = {}
    with open(args.team, newline='', encoding='utf8') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        next(reader)  # skip header
        for email, team_name, _, _ in reader:
            team_master[email] = team_name
            if team_name not in teams:
                teams[team_name] = TeamSummary(name=team_name)
            teams[team_name].total_members += 1

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
            t = teams.get(team_master.get(email))  # type: ignore
            if t is None:
                continue
            t.total_posts += count
            t.active_members += 1

    if args.sort == 'total':
        def _sort_key(x: 'TeamSummary') -> Any:
            return x.total_posts
    elif args.sort == 'average':
        def _sort_key(x: 'TeamSummary') -> Any:
            return x.total_posts / x.total_members
    else:
        assert(False)
    leaderboard = sorted(teams.values(), key=_sort_key, reverse=True)

    output = ['{} のチーム発言数ランキング'.format(
        get_date_range_str(since, until, args))]
    output_json = []
    for i, t in enumerate(leaderboard):
        inactive = ''
        if t.active_members < t.total_members:
            inactive = ' ({} inactive)'.format(
                t.total_members - t.active_members)
        output.append(
            '{}. {}: {} posts, {:.2f} posts/member, '
            '{} members{}'.format(
                i + 1, t.name, t.total_posts, t.total_posts / t.total_members,
                t.total_members, inactive))
        output_json.append({
            'leaderboard_rank': i + 1,
            'name': t.name,
            'rating': t.total_posts / t.total_members,
            'members': t.total_members,
            'inactive_members': t.total_members - t.active_members,
        })
    print('\n'.join(output))
    print()

    if args.json:
        if args.month or args.this_month:
            current_season: Any = '{:%Y-%m}'.format(since)
        else:
            current_season = {'since': '{:%Y-%m-%d}'.format(since),
                              'until': '{:%Y-%m-%d}'.format(until)}
        with open(args.json, 'w', encoding='utf8') as f:
            json.dump({
                'current_season': current_season,
                'last_updated': int(time.time() * 1000),
                'teams': output_json}, f, ensure_ascii=False, indent=2)

    if not args.dry_run and len(output) > 1:
        post(args, '\n'.join(output))


@dataclass
class TeamSummary:
    name: str
    total_posts: int = 0
    total_members: int = 0
    active_members: int = 0
