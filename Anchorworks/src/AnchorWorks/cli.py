from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .app import create_app


def _default_data_root() -> Path:
    candidate = Path.home() / "OneDrive" / "Documents" / "Desktop" / "Lexical Data"
    return candidate if candidate.exists() else Path.cwd()


def main() -> None:
    parser = argparse.ArgumentParser(prog="anchorworks")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the standalone lexicon server")
    serve.add_argument("--data-root", type=Path, default=_default_data_root())
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)

    args = parser.parse_args()

    if args.command == "serve":
        app = create_app(args.data_root)
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
