from argparse import ArgumentParser, Namespace
from functools import partial
from typing import Any, Callable, Dict, Tuple, Union, List, TYPE_CHECKING
import sys

from slack.web.slack_response import SlackResponse

from .common import (
    setup_common_args, setup_token_args, datetime_parser, create_slack_client)
from .models import init_db, transaction, Channel, User, Message

if TYPE_CHECKING:
    from asyncio import Future


def init_argparser(create_parser: Callable[..., ArgumentParser]) -> None:
    parser = setup_token_args(setup_common_args(create_parser(
        'collect', help='メッセージを収集しデータベースに格納します')))
    parser.add_argument(
        '--since', help='メッセージ取得開始日時(ISO8601)を指定します。'
        '省略した場合はDBに保存されている最新のメッセージ以降を取得対象とします。',
        type=datetime_parser)
    parser.add_argument(
        '--until', help='メッセージ取得終了日時(ISO8601)を指定します。'
        '省略した場合はコマンド実行日の週の月曜日午前0時になります。',
        type=datetime_parser)
    parser.set_defaults(func=run)


def run(args: Namespace) -> None:
    client = create_slack_client(args)
    init_db(args.db)

    # 全チャンネルをスキャンするしDBにUPSERTする
    print('チャンネル一覧を取得中...', end='')
    success, channels = _fetch_all_pages(
        partial(client.conversations_list, exclude_archived=1), 'channels')
    with transaction() as s:
        for c in channels:
            s.add(Channel(id=c['id'], name=c['name'], is_member=c['is_member'],
                          raw=c))
    print('[{}]'.format('OK' if success else 'Error'))
    if not success:
        return

    # 全ユーザをスキャンしDBにUPSERTする
    print('ユーザ一覧を取得中...', end='')
    success, users = _fetch_all_pages(
        partial(client.users_list, exclude_archived=1), 'members')
    with transaction() as s:
        for u in users:
            name = u['profile'].get('display_name') or u['real_name']
            email = u['profile'].get('email')
            s.add(User(id=u['id'], name=name, email=email, raw=u))
    print('[{}]'.format('OK' if success else 'Error'))
    if not success:
        return

    def _ts_tostring(ts: float) -> str:
        return '{:.6f}'.format(ts)

    # 各チャンネルの会話を取得しDBにUPSERTする
    for c in channels:
        if not c['is_member']:  # joinしているチャンネル以外は読み取れないのでskip
            continue
        print('会話ログを取得中 id:{} #{} ...'.format(
            c['id'], c['name']), end='')

        # since/until引数が指定されていたときや無指定の場合にAPIに渡す引数を設定
        kwargs = {}
        if not args.since:
            with transaction() as s:
                ret = s.query(
                    Message.timestamp
                ).filter(
                    Message.channel_id == c['id']
                ).order_by(Message.timestamp.desc()).limit(1).scalar()
                if ret is not None:
                    kwargs['oldest'] = _ts_tostring(ret)
        for n0, n1 in zip(('oldest', 'latest'), ('since', 'until')):
            if kwargs.get(n0) or getattr(args, n1, None) is None:
                continue
            kwargs[n0] = _ts_tostring(getattr(args, n1).timestamp())

        # 会話ログを取得しDBをにUPSERT。
        # 会話ログは降順で得られるので失敗時はDB登録せずに終える。
        success, messages = _fetch_all_pages(partial(
            client.conversations_history, channel=c['id'],
            **kwargs), 'messages')
        if not success:
            print('[ERROR]')
            break
        with transaction() as s:
            print(' {} messages '.format(len(messages)), end='')
            for m in messages:
                s.add(Message(timestamp=float(m['ts']), channel_id=c['id'],
                              user_id=m['user'], subtype=m.get('subtype', ''),
                              raw=m))
        print('[OK]')


def _fetch_all_pages(
        func: Callable[..., Union['Future', SlackResponse]],
        key: str
) -> Tuple[bool, List[Dict[str, Any]]]:
    """ページネーション対応の全アイテム取得機能.

    Args:
        func: Slack APIのページネーションに対応した関数を指定
        key: 戻り値のリストに追加するAPIレスポンスの辞書のキー
    Returns:
        成功フラグと結果配列のタプル。Falseの場合は配列には途中結果が含まれ、
        標準エラー出力に例外等が出力される。
    """
    ret: List[Dict[str, Any]] = []
    kwargs: Dict[str, str] = {}
    while True:
        try:
            resp = func(**kwargs)
        except Exception as e:
            print(type(e), e, file=sys.stderr)
            return False, ret

        assert isinstance(resp, SlackResponse)
        if not resp['ok']:
            print(resp, file=sys.stderr)
            return False, ret

        ret += resp[key]
        next_cursor = resp.get(
            'response_metadata', {}).get('next_cursor', None)
        if not next_cursor:
            break
        kwargs['cursor'] = next_cursor
    return True, ret
