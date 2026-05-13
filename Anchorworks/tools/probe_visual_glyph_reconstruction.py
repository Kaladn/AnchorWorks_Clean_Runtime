from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from AnchorWorks.visual_black_pixel_reconstruction import reconstruct_from_known_components
from AnchorWorks.visual_glyph_lexicon import VisualGlyphLexicon


def glyph_record(display: str, pattern: list[str]) -> dict[str, object]:
    safe = {
        ".": "period",
        ":": "colon",
        "-": "dash",
        "/": "slash",
        "(": "lparen",
        ")": "rparen",
    }.get(display, display)
    return {
        "schema_version": "anchorworks_visual_glyph_lexicon@1",
        "glyph_id": f"vglyph_{safe}_0001",
        "display": display,
        "class": "controlled",
        "width": max(len(row) for row in pattern),
        "height": len(pattern),
        "trim_pattern": pattern,
        "match_policy": {"max_hamming_distance": 0},
        "promotion_status": "approved",
    }


def main() -> int:
    run_id = datetime.now(timezone.utc).strftime("visual_glyph_probe_%Y%m%dT%H%M%SZ")
    lexicon = VisualGlyphLexicon.from_records(
        [
            glyph_record("A", ["010", "101", "111", "101", "101"]),
            glyph_record("B", ["110", "101", "110", "101", "110"]),
            glyph_record(":", ["1", "0", "1"]),
            glyph_record(".", ["1"]),
        ]
    )
    components = [
        {"component_id": "c1", "bounds": (0, 0, 3, 5), "pattern": ["010", "101", "111", "101", "101"]},
        {"component_id": "c2", "bounds": (4, 0, 5, 5), "pattern": ["1", "0", "1"]},
        {"component_id": "c3", "bounds": (6, 0, 9, 5), "pattern": ["110", "101", "110", "101", "110"]},
        {"component_id": "c4", "bounds": (10, 0, 11, 5), "pattern": ["1"]},
    ]
    expected_text = "A:B."
    reconstruction = reconstruct_from_known_components(lexicon, components, word_gap_pixels=6)
    report = {
        "schema_version": "anchorworks_visual_glyph_reconstruction_probe@1",
        "run_id": run_id,
        "expected_text": expected_text,
        "text_candidate": reconstruction["text_candidate"],
        "exact_match": reconstruction["text_candidate"] == expected_text,
        "unknown_glyphs": reconstruction["unknown_glyphs"],
        "blocking_anomalies": reconstruction["blocking_anomalies"],
        "anomalies": reconstruction["anomalies"],
        "resolved_anchor": reconstruction["resolved_anchor"],
        "count_eligible": reconstruction["count_eligible"],
        "memory_truth": reconstruction["memory_truth"],
    }
    output_dir = Path("reports") / "truevision" / "visual_glyph_reconstruction"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{run_id}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report_path": str(output_path), **report}, indent=2))
    return 0 if report["exact_match"] and report["unknown_glyphs"] == 0 and report["blocking_anomalies"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
