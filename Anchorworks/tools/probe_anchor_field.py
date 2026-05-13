from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from AnchorWorks.anchor_field import build_anchor_field_from_observed_map, skim_three_level_cloud


def choose_seed(field) -> str:
    blocked = {"__NULL__", ".", ",", ":", ";", "(", ")", "-", "/", "the", "a", "an", "of", "to", "in", "as", "and"}
    counts = Counter(anchor for anchor in field.stream if anchor not in blocked and len(anchor) > 2)
    if not counts:
        return field.stream[0] if field.stream else ""
    return counts.most_common(1)[0][0]


def main() -> int:
    if len(sys.argv) > 1:
        map_path = Path(sys.argv[1])
    else:
        maps = sorted(Path("D:/AnchorMaps/observed_maps").glob("*.observed.json"), key=lambda item: item.stat().st_size)
        if not maps:
            print("no observed maps found", file=sys.stderr)
            return 1
        map_path = maps[min(10, len(maps) - 1)]
    observed_map = json.loads(map_path.read_text(encoding="utf-8"))
    field = build_anchor_field_from_observed_map(observed_map)
    seed = choose_seed(field)
    cloud = skim_three_level_cloud(field, [seed], max_level_width=6, null_stop_ratio=0.6)
    report = {
        "schema_version": "anchorworks_anchor_field_probe@1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "map_path": str(map_path),
        "source_name": field.source_name,
        "anchor_count": field.anchor_count,
        "seed": seed,
        "cloud": cloud,
    }
    output_dir = Path("reports") / "anchor_field"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"anchor_field_probe_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report_path": str(output_path), "seed": seed, "anchor_count": field.anchor_count, "shape": cloud["shape"], "stop_reason": cloud["stop_reason"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
