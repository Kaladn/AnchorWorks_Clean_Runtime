from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import uvicorn

from .app import create_app, _default_data_root
from .store import LexiconStore


def main() -> None:
    parser = argparse.ArgumentParser(prog="anchorworks")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the standalone lexicon server")
    serve.add_argument("--data-root", type=Path, default=_default_data_root())
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)

    symbolic_batch = sub.add_parser("symbolic-batch-intake", help="Build maps, symbol streams, and AWSC cells for a source group")
    symbolic_batch.add_argument("--data-root", type=Path, required=True)
    symbolic_batch.add_argument("--source-dir", type=Path, required=True)
    symbolic_batch.add_argument("--pattern", default="*")
    symbolic_batch.add_argument("--map-root", type=Path, default=None)
    symbolic_batch.add_argument("--max-workers", type=int, default=None)
    symbolic_batch.add_argument("--generation", type=int, default=0)

    args = parser.parse_args()

    if args.command == "serve":
        app = create_app(args.data_root)
        uvicorn.run(app, host=args.host, port=args.port)
    elif args.command == "symbolic-batch-intake":
        source_dir = args.source_dir.expanduser().resolve()
        if not source_dir.exists():
            raise FileNotFoundError(source_dir)
        if not source_dir.is_dir():
            raise NotADirectoryError(source_dir)
        if args.map_root is not None:
            os.environ["ANCHORWORKS_MAP_ROOT"] = str(args.map_root.expanduser().resolve())
        source_paths = sorted(
            (path for path in source_dir.rglob(args.pattern) if path.is_file()),
            key=lambda path: str(path).lower(),
        )
        store = LexiconStore(args.data_root)
        result = store.build_symbolic_intake_batch(
            source_paths,
            max_workers=args.max_workers,
            generation=args.generation,
        )
        print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
