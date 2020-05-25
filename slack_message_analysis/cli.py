from argparse import ArgumentParser
import os
from importlib import import_module


def main() -> None:
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()
    excludes = set(['common.py', 'cli.py', 'models.py'])
    topdir = os.path.dirname(__file__)
    ns_root = os.path.dirname(topdir)

    for dirpath, _, filenames in os.walk(topdir):
        ns = os.path.relpath(
            dirpath, start=ns_root).replace('/', '.').replace('\\', '.') + '.'
        for fn in filenames:
            if not fn.endswith('.py') or fn.startswith('_') or fn in excludes:
                continue
            n, _ = os.path.splitext(fn)
            m = import_module(ns + n)
            getattr(m, 'init_argparser')(subparsers.add_parser)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()
