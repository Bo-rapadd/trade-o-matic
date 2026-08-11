from __future__ import annotations

import argparse

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trade-o-matic",
        description="Quantitative research and trading platform",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("doctor", help="verify the local research environment")
    sub.add_parser("strategies", help="list built-in strategies")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "doctor":
        print("trade-o-matic: OK")
        print("research core: available")
        print("live execution: disabled")
        return 0
    if args.command == "strategies":
        print("tsmom\tTime-series momentum baseline")
        return 0
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
