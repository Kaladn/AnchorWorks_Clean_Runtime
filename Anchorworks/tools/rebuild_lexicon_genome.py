from __future__ import annotations

import argparse
import json
from pathlib import Path

from AnchorWorks.lexicon_genome_rebuild import build_lexicon_genome_rebuild


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild Canonical/Structural lexicons with native C++ Symbol Genome identities.")
    parser.add_argument(
        "--data-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Root containing Canonical/ and Structural/.",
    )
    parser.add_argument(
        "--output-root",
        default="",
        help="Output root. Defaults to DATA_ROOT/Lexicon_Genome_Rebuild.",
    )
    parser.add_argument("--native-allocator", default="", help="Optional path to anchorworks-symbol-genome.exe.")
    parser.add_argument("--limit", type=int, default=0, help="Optional test limit.")
    args = parser.parse_args()

    report = build_lexicon_genome_rebuild(
        args.data_root,
        output_root=args.output_root or None,
        native_allocator=args.native_allocator or None,
        limit=args.limit or None,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
