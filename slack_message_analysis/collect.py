from argparse import ArgumentParser, Namespace
from functools import partial
import time
from typing import Any, Callable, Dict, Tuple, Union, List, TYPE_CHECKING
import sys

from slack.errors import SlackApiError
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
    #
    # https://api.slack.com/methods/conversations.list
    # "We recommend no more than 200 results at a time."
    # よりlimitに200を指定する (デフォルトは100)
    print('チャンネル一覧を取得中 ', end='')
    success, channels = _fetch_all_pages(
        partial(client.conversations_list, exclude_archived=1, limit=200),
        'channels')
    with transaction() as s:
        for c in channels:
            s.add(Channel(id=c['id'], name=c['name'], is_member=c['is_member'],
                          raw=c))
    if success:
        print(' Found {} channels'.format(len(channels)))
    else:
        print('[ERROR]')
        return

    # 全ユーザをスキャンしDBにUPSERTする
    #
    # https://api.slack.com/methods/users.list
    # "We recommend no more than 200 results at a time."
    # よりlimitに200を指定する (デフォルトは0と記載があり謎)
    print('ユーザ一覧を取得中 ', end='')
    success, users = _fetch_all_pages(
        partial(client.users_list, limit=200), 'members')
    with transaction() as s:
        for u in users:
            name = (
                u['profile'].get('display_name') or
                u.get('real_name') or
                u['profile'].get('real_name') or
                u['name'])
            email = u['profile'].get('email')
            s.add(User(id=u['id'], name=name, email=email, raw=u))
    if success:
        print(' Found {} users'.format(len(users)))
    else:
        print('[ERROR]')
        return

    def _ts_tostring(ts: float) -> str:
        return '{:.6f}'.format(ts)

    # 各チャンネルの会話を取得しDBにUPSERTする
    for c in channels:
        if not c['is_member']:  # joinしているチャンネル以外は読み取れないのでskip
            continue
        print('会話ログを取得中 id:{} #{} '.format(
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
        #
        # https://api.slack.com/methods/conversations.history
        # "We recommend no more than 200 results at a time."
        # よりlimitに200を指定する (デフォルトは100)
        success, messages = _fetch_all_pages(partial(
            client.conversations_history, channel=c['id'], limit=200,
            **kwargs), 'messages')
        if not success:
            print('[ERROR]')
            return

        # スレッドがあればリプライを全部収集する
        all_replies = []
        fetched_threads = set()
        for m in messages:
            thread_ts = m.get('thread_ts')
            if not thread_ts or thread_ts in fetched_threads:
                continue
            fetched_threads.add(thread_ts)
            #
            # https://api.slack.com/methods/conversations.replies
            # "We recommend no more than 200 results at a time."
            # よりlimitに200を指定する (デフォルトは10)
            success, replies = _fetch_all_pages(partial(
                client.conversations_replies, channel=c['id'],
                ts=thread_ts, limit=200), 'messages')
            if not success:
                print('[ERROR]')
                return
            all_replies += replies

        # スレッドの関係により重複するメッセージが含まれるので、
        # 重複を除去する
        insert_messages: Dict[Tuple[float, str, str, str], Message] = {}
        for m in messages + all_replies:
            user_id = m.get('user')
            if not user_id:
                # ユーザIDが含まれないメッセージは収集対象外
                continue
            key = (float(m['ts']), c['id'], user_id, m.get('subtype', ''))
            tmp = Message(
                timestamp=key[0], channel_id=key[1], user_id=user_id,
                subtype=key[3], raw=m)
            insert_messages[key] = tmp

        # DBにUPSERT
        with transaction() as s:
            print(' {} messages '.format(len(insert_messages)), end='')
            for im in insert_messages.values():
                s.add(im)
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
            print('.', end='')
        except Exception as e:
            if isinstance(e, SlackApiError):
                if e.response["error"] == "ratelimited":
                    delay = int(e.response.headers['Retry-After'])
                    print('\nrate limited. retry-after {}s\n'.format(delay),
                          end='')
                    time.sleep(delay)
                    continue

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
