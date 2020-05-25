from argparse import ArgumentParser, Namespace
from typing import Callable

from fugashi import GenericTagger  # type: ignore
from wordcloud import WordCloud  # type: ignore

from .common import (
    setup_common_args, setup_token_args, setup_date_range_args,
    setup_post_args, get_date_range, get_date_range_str, create_slack_client)
from .models import init_db, transaction, Message


def init_argparser(create_parser: Callable[..., ArgumentParser]) -> None:
    parser = create_parser(
        'wordcloud', help='MeCabで形態素解析した結果を用いてWordCloudを作成します\n'
        '--sinceと--until または --day または --week または --month を指定する必要があります。'
    )
    parser.add_argument(
        '-r', '--mecab-rcfile',
        help='MeCabのリソースファイルパス',
        required=True)
    parser.add_argument(
        '-d', '--mecab-dicdir',
        help='MeCabの辞書パス',
        required=True)
    setup_common_args(setup_token_args(setup_date_range_args(setup_post_args(
        parser))))
    parser.add_argument(
        '--font',
        default='meiryo.ttc',
        help='フォントファイル名 (デフォルト: meiryo.ttc)')
    parser.add_argument(
        '-u', '--mecab-userdic',
        help='MeCabのユーザ辞書のパス')
    parser.add_argument(
        '--exclude',
        default='助詞,助動詞',
        help='除去する品詞をカンマ区切りで指定 (デフォルト: 助詞,助動詞)')
    parser.add_argument(
        '--width', type=int, default=1280,
        help='画像の幅 (デフォルト: 1280px)')
    parser.add_argument(
        '--height', type=int, default=720,
        help='画像の高さ (デフォルト: 720px)')
    parser.add_argument(
        '--background', default='white',
        help='背景色。transparentを指定すると透明。(デフォルト: white)')
    parser.add_argument(
        '--max-words', default=200, type=int,
        help='最大表示単語数 (デフォルト: 200)')
    parser.add_argument(
        '--stop-word-file',
        help='ストップワードを記載したテキストファイルパス (改行や空白区切り)')
    parser.set_defaults(func=run)


def run(args: Namespace) -> None:
    init_db(args.db)
    since, until = get_date_range(args)

    # MeCab初期化
    mecab_args = '-r "{}" -d "{}"'.format(
        args.mecab_rcfile, args.mecab_dicdir)
    if args.mecab_userdic:
        mecab_args += ' -u "{}"'.format(args.mecab_userdic)
    tagger = GenericTagger(args=mecab_args)

    # WordCloudのパラメータを解釈し設定
    wc_kwargs = dict(
        font_path=args.font, width=args.width, height=args.height,
        max_words=args.max_words,
    )
    if args.background == 'transparent':
        wc_kwargs.update(dict(mode='RGBA', background_color=None))
    else:
        wc_kwargs['background_color'] = args.background
    if args.stop_word_file:
        with open(args.stop_word_file, 'r', encoding='utf8') as f:
            wc_kwargs['stopwords'] = set(f.read().split())

    text_list = []
    excludes = set(args.exclude.split(','))
    with transaction() as s:
        q = s.query(Message).filter(
            Message.timestamp >= since.timestamp(),
            Message.timestamp < until.timestamp(),
            Message.subtype == '',
        )
        for m in q:
            if m.raw.get('bot_id'):
                continue  # botの発言は集計対象外
            text = m.raw.get('text', '')
            if not text:
                continue
            tokens = [
                w.surface for w in tagger(text)
                if (w.feature_raw and
                    w.feature_raw.split(',')[0] not in excludes)]
            if tokens:
                text_list.append(' '.join(tokens))

    wordcloud = WordCloud(**wc_kwargs).generate(' '.join(text_list))

    print('Save to "wordcloud.png"')
    wordcloud.to_file('wordcloud.png')
    if args.dry_run:
        return

    title = '{} の頻出単語'.format(get_date_range_str(since, until, args))
    client = create_slack_client(args)
    client.files_upload(
        channels=args.post, file='wordcloud.png', title=title)
