from __future__ import annotations

import argparse

import uvicorn


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="receipty")
    subcommands = result.add_subparsers(dest="command", required=True)
    serve = subcommands.add_parser("serve", help="Open one workspace and run Receipty")
    serve.add_argument("workspace")
    serve.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    serve.add_argument("--port", type=int, default=8000)
    return result


def main() -> None:
    args = parser().parse_args()
    if args.command == "serve":
        from .app import create_app

        uvicorn.run(create_app(args.workspace), host=args.host, port=args.port)


if __name__ == "__main__":
    main()

