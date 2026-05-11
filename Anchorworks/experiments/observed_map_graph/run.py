from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from AnchorWorks.symbolic_map_binary import (
    SymbolicMapRelation,
    read_symbolic_map_bundle,
    write_symbolic_map_binary,
    write_symbolic_map_locator_sidecar,
    write_symbolic_map_null_sidecar,
    write_symbolic_map_visual_sidecar,
)


EXPERIMENT_ROOT = Path(__file__).resolve().parent
RUNTIME = EXPERIMENT_ROOT / "runtime"
REQUIRED_DIRS = ("input", "graph", "exports", "reports")
SOURCE_ID = "toy_awsg_source"
SOURCE_NAME = "toy_awsg_source.txt"
WINDOW_RADIUS = 2
REQUIRED_NODE_TYPES = {"document", "block", "line", "occurrence", "symbol", "null_coordinate", "visual_ref"}
REQUIRED_EDGE_TYPES = {
    "contains_block",
    "contains_line",
    "contains_occurrence",
    "resolves_to_symbol",
    "relation_window",
    "has_null",
    "has_visual_ref",
}
BLOCKED_ROOTS = [
    r"D:\AnchorWorks_Clean_Runtime\State",
    r"D:\AnchorMaps",
    str(REPO_ROOT / "Canonical"),
    str(REPO_ROOT / "Spare_Slots"),
    str(REPO_ROOT / "Structural"),
]
WRITES_ALLOWED = {"canonical": False, "counts": False, "lifetime": False, "lexicon": False}


TOY_BLOCKS = [
    {
        "block_id": 1,
        "lines": [
            "The blue anchor marks the river sample.",
            "The brass compass rests beside the river sample.",
        ],
    },
    {
        "block_id": 2,
        "lines": [
            "The glass cover protects the seed tray.",
            "Figure one shows the river sample graph.",
        ],
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Observed map graph first proof experiment.")
    parser.add_argument("command", choices=("build", "eval", "all"))
    args = parser.parse_args()

    if args.command == "build":
        report = build()
        print(RUNTIME / "reports" / "build_report.json")
        print(json.dumps(report, ensure_ascii=True))
    elif args.command == "eval":
        report = evaluate()
        print(RUNTIME / "reports" / "eval_report.json")
        print(json.dumps(report, ensure_ascii=True))
    else:
        build()
        report = evaluate()
        print(RUNTIME / "reports" / "eval_report.json")
        print(json.dumps(report, ensure_ascii=True))


def build() -> dict[str, Any]:
    if RUNTIME.exists():
        shutil.rmtree(RUNTIME)
    for name in REQUIRED_DIRS:
        (RUNTIME / name).mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    source_path = RUNTIME / "input" / SOURCE_NAME
    source_text = _source_text()
    source_path.write_text(source_text, encoding="utf-8")
    source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    occurrences = _toy_occurrences()
    symbol_table = _symbol_table(occurrences)
    relations = _relation_counts(occurrences, symbol_table)
    bundle_paths = _write_bundle(source_path, source_hash, occurrences, relations)
    bundle = read_symbolic_map_bundle(bundle_paths["awsm"])
    nodes, edges = _build_graph(source_path, source_hash, occurrences, symbol_table, bundle)

    _write_jsonl(RUNTIME / "graph" / "nodes.jsonl", nodes)
    _write_jsonl(RUNTIME / "graph" / "edges.jsonl", edges)
    debug_export = _debug_export_from_graph(nodes, edges)
    _write_json(RUNTIME / "exports" / "observed-map-debug-export.json", debug_export)

    outputs = [str(path) for path in sorted(RUNTIME.rglob("*")) if path.is_file()]
    manifest = _graph_manifest(source_path, source_hash, bundle_paths, nodes, edges, outputs)
    _write_json(RUNTIME / "graph" / "graph_manifest.json", manifest)

    schema_errors, missing_node_types, missing_edge_types = _schema_check(nodes, edges)
    production_write_errors = _production_write_errors(outputs)
    report = {
        "schema_version": "anchorworks_awsg_build_report@1",
        "schema_errors": schema_errors,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_type_counts": dict(sorted(Counter(node["node_type"] for node in nodes).items())),
        "edge_type_counts": dict(sorted(Counter(edge["edge_type"] for edge in edges).items())),
        "missing_node_types": missing_node_types,
        "missing_edge_types": missing_edge_types,
        "debug_export_written": (RUNTIME / "exports" / "observed-map-debug-export.json").is_file(),
        "production_write_errors": production_write_errors,
        "seconds": round(time.perf_counter() - started, 6),
        "law": "JSON explains. Graph connects. AWSM serves relations. AWSC remembers weight. Sidecars prove coordinates. Renderer cites graph addresses.",
    }
    _write_json(RUNTIME / "reports" / "build_report.json", report)
    return report


def evaluate() -> dict[str, Any]:
    nodes_path = RUNTIME / "graph" / "nodes.jsonl"
    edges_path = RUNTIME / "graph" / "edges.jsonl"
    export_path = RUNTIME / "exports" / "observed-map-debug-export.json"
    manifest_path = RUNTIME / "graph" / "graph_manifest.json"
    if not nodes_path.exists() or not edges_path.exists() or not export_path.exists() or not manifest_path.exists():
        raise FileNotFoundError("run build before eval")

    nodes = _read_jsonl(nodes_path)
    edges = _read_jsonl(edges_path)
    export = _read_json(export_path)
    manifest = _read_json(manifest_path)
    schema_errors, missing_node_types, missing_edge_types = _schema_check(nodes, edges)
    production_write_errors = _production_write_errors([str(path) for path in sorted(RUNTIME.rglob("*")) if path.is_file()])
    export_errors = _debug_export_errors(export)
    if manifest.get("writes_allowed") != WRITES_ALLOWED:
        schema_errors += 1

    report = {
        "schema_version": "anchorworks_awsg_eval_report@1",
        "schema_errors": schema_errors + export_errors,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_type_counts": dict(sorted(Counter(node["node_type"] for node in nodes).items())),
        "edge_type_counts": dict(sorted(Counter(edge["edge_type"] for edge in edges).items())),
        "missing_node_types": missing_node_types,
        "missing_edge_types": missing_edge_types,
        "debug_export_written": export_path.is_file(),
        "production_write_errors": production_write_errors,
    }
    _write_json(RUNTIME / "reports" / "eval_report.json", report)
    return report


def _source_text() -> str:
    lines: list[str] = []
    for block in TOY_BLOCKS:
        lines.append(f"Block {block['block_id']}")
        lines.extend(str(line) for line in block["lines"])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _toy_occurrences() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in TOY_BLOCKS:
        block_id = int(block["block_id"])
        for line_index, line in enumerate(block["lines"], start=1):
            anchors = _anchorize(str(line))
            for position, surface in enumerate(anchors, start=1):
                rows.append(
                    {
                        "source_id": SOURCE_ID,
                        "block_id": block_id,
                        "line_start": line_index,
                        "line_end": line_index,
                        "anchor_position": position,
                        "surface": surface,
                        "resolved_anchor": surface,
                        "lane": 0,
                    }
                )
    return rows


def _symbol_table(occurrences: list[dict[str, Any]]) -> dict[str, str]:
    anchors = sorted({str(row["resolved_anchor"]) for row in occurrences})
    return {anchor: _symbol_for_surface(anchor) for anchor in anchors}


def _relation_counts(occurrences: list[dict[str, Any]], symbol_table: dict[str, str]) -> list[SymbolicMapRelation]:
    counts: Counter[tuple[str, str, int]] = Counter()
    by_line: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in occurrences:
        by_line.setdefault((int(row["block_id"]), int(row["line_start"])), []).append(row)
    for line_rows in by_line.values():
        ordered = sorted(line_rows, key=lambda row: int(row["anchor_position"]))
        symbols = [symbol_table[str(row["resolved_anchor"])] for row in ordered]
        for index, root in enumerate(symbols):
            for neighbor_index in range(max(0, index - WINDOW_RADIUS), min(len(symbols), index + WINDOW_RADIUS + 1)):
                if neighbor_index == index:
                    continue
                offset = neighbor_index - index
                counts[(root, symbols[neighbor_index], offset)] += 1
    return [
        SymbolicMapRelation(
            root_symbol_id=int(root, 16),
            neighbor_symbol_id=int(neighbor, 16),
            offset=offset,
            lane=0,
            flags=0,
            count=count,
        )
        for (root, neighbor, offset), count in sorted(counts.items())
    ]


def _write_bundle(
    source_path: Path,
    source_hash: str,
    occurrences: list[dict[str, Any]],
    relations: list[SymbolicMapRelation],
) -> dict[str, Path]:
    awsm_path = RUNTIME / "input" / "toy_awsg_source.awsm"
    write_symbolic_map_binary(
        awsm_path,
        metadata={
            "schema_version": "toy_awsg_awsm_metadata@1",
            "source_id": SOURCE_ID,
            "source_path": str(source_path),
            "source_hash": source_hash,
            "block_count": len(TOY_BLOCKS),
            "occurrence_count": len(occurrences),
        },
        relations=relations,
    )
    locator_rows = [
        {
            "paragraph_id": int(block["block_id"]),
            "block_id": int(block["block_id"]),
            "line_start": 1,
            "line_end": len(block["lines"]),
            "anchor_count": sum(1 for row in occurrences if int(row["block_id"]) == int(block["block_id"])),
            "countable_anchor_count": sum(1 for row in occurrences if int(row["block_id"]) == int(block["block_id"])),
        }
        for block in TOY_BLOCKS
    ]
    null_rows = [
        {
            "block_id": 1,
            "line_start": 2,
            "line_end": 2,
            "anchor_position": 99,
            "anchor_label": "Block 1 Ln 2 Anchor 99",
            "observed_anchor": "%%%noise%%%",
            "surface": "%%%noise%%%",
            "resolved_anchor": "__NULL__",
            "count_eligible": False,
            "memory_truth": False,
        }
    ]
    visual_rows = [
        {
            "block_id": "2",
            "block_ordinal": 2,
            "line_start": 2,
            "line_end": 2,
            "visual_record_id": "vis_river_sample_graph",
            "kind": "figure",
            "source_path_ref": "figures/river_sample_graph.png",
            "alt_text": "",
            "title": "River sample graph",
            "caption_block_id": "2",
            "manifest_id": "toy_visual_manifest",
            "geometry_status": "held",
            "recognition_status": "not_run",
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }
    ]
    locator_path = RUNTIME / "input" / "toy_awsg_source.locators.awsl"
    null_path = RUNTIME / "input" / "toy_awsg_source.nulls.awsn"
    visual_path = RUNTIME / "input" / "toy_awsg_source.visuals.awsv"
    write_symbolic_map_locator_sidecar(locator_path, locator_rows)
    write_symbolic_map_null_sidecar(null_path, null_rows)
    write_symbolic_map_visual_sidecar(visual_path, visual_rows)
    return {"awsm": awsm_path, "awsl": locator_path, "awsn": null_path, "awsv": visual_path}


def _build_graph(
    source_path: Path,
    source_hash: str,
    occurrences: list[dict[str, Any]],
    symbol_table: dict[str, str],
    bundle: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = [
        {
            "node_type": "document",
            "node_id": f"doc:{SOURCE_ID}",
            "source_id": SOURCE_ID,
            "source_path": str(source_path),
            "source_hash": source_hash,
        }
    ]
    edges: list[dict[str, Any]] = []

    for locator in bundle.locators:
        block_id = int(locator["block_id"])
        block_node = f"block:{SOURCE_ID}:{block_id}"
        nodes.append(
            {
                "node_type": "block",
                "node_id": block_node,
                "source_id": SOURCE_ID,
                "block_id": block_id,
                "block_ordinal": block_id,
            }
        )
        edges.append({"edge_type": "contains_block", "from": f"doc:{SOURCE_ID}", "to": block_node})
        for line_start in range(int(locator["line_start"]), int(locator["line_end"]) + 1):
            line_node = f"line:{SOURCE_ID}:{block_id}:{line_start}"
            nodes.append(
                {
                    "node_type": "line",
                    "node_id": line_node,
                    "source_id": SOURCE_ID,
                    "block_id": block_id,
                    "line_start": line_start,
                    "line_end": line_start,
                }
            )
            edges.append({"edge_type": "contains_line", "from": block_node, "to": line_node})

    symbol_nodes = {
        symbol: {
            "node_type": "symbol",
            "node_id": f"symbol:{symbol}",
            "symbol": symbol,
            "lane": 0,
            "display_anchor": anchor,
        }
        for anchor, symbol in sorted(symbol_table.items())
    }
    nodes.extend(symbol_nodes.values())

    occurrence_symbols: dict[str, str] = {}
    for row in occurrences:
        block_id = int(row["block_id"])
        line_start = int(row["line_start"])
        anchor_position = int(row["anchor_position"])
        symbol = symbol_table[str(row["resolved_anchor"])]
        occurrence_node = f"occ:{SOURCE_ID}:{block_id}:{line_start}:{anchor_position}"
        occurrence_symbols[occurrence_node] = symbol
        nodes.append(
            {
                "node_type": "occurrence",
                "node_id": occurrence_node,
                "source_id": SOURCE_ID,
                "block_id": block_id,
                "line_start": line_start,
                "anchor_position": anchor_position,
                "surface": row["surface"],
                "resolved_anchor": row["resolved_anchor"],
                "symbol": symbol,
                "lane": int(row["lane"]),
            }
        )
        line_node = f"line:{SOURCE_ID}:{block_id}:{line_start}"
        edges.append({"edge_type": "contains_occurrence", "from": line_node, "to": occurrence_node})
        edges.append({"edge_type": "resolves_to_symbol", "from": occurrence_node, "to": f"symbol:{symbol}"})

    by_line = _occurrences_by_line(occurrences, symbol_table)
    for line_rows in by_line.values():
        ordered = sorted(line_rows, key=lambda row: int(row["anchor_position"]))
        for index, row in enumerate(ordered):
            occurrence_node = f"occ:{SOURCE_ID}:{row['block_id']}:{row['line_start']}:{row['anchor_position']}"
            for neighbor_index in range(max(0, index - WINDOW_RADIUS), min(len(ordered), index + WINDOW_RADIUS + 1)):
                if neighbor_index == index:
                    continue
                neighbor = ordered[neighbor_index]
                neighbor_symbol = symbol_table[str(neighbor["resolved_anchor"])]
                edges.append(
                    {
                        "edge_type": "relation_window",
                        "from": occurrence_node,
                        "to": f"symbol:{neighbor_symbol}",
                        "offset": neighbor_index - index,
                        "count": 1,
                        "source": "AWSM",
                    }
                )

    for row in bundle.nulls:
        block_id = int(row["block_id"])
        line_start = int(row["line_start"])
        anchor_position = int(row["anchor_position"])
        null_node = f"null:{SOURCE_ID}:{block_id}:{line_start}:{anchor_position}"
        nodes.append(
            {
                "node_type": "null_coordinate",
                "node_id": null_node,
                "source_id": SOURCE_ID,
                "block_id": block_id,
                "line_start": line_start,
                "anchor_position": anchor_position,
                "surface": row["surface"],
                "resolved_anchor": row["resolved_anchor"],
                "reason": "junk_or_artifact",
            }
        )
        edges.append({"edge_type": "has_null", "from": f"line:{SOURCE_ID}:{block_id}:{line_start}", "to": null_node})

    for row in bundle.visuals:
        block_id = int(str(row["block_id"]))
        line_start = int(row["line_start"])
        visual_node = f"visual:{SOURCE_ID}:{row['visual_record_id']}"
        nodes.append(
            {
                "node_type": "visual_ref",
                "node_id": visual_node,
                "source_id": SOURCE_ID,
                "visual_record_id": row["visual_record_id"],
                "kind": row["kind"],
                "source_path_ref": row["source_path_ref"],
                "recognition_status": row["recognition_status"],
            }
        )
        edges.append({"edge_type": "has_visual_ref", "from": f"line:{SOURCE_ID}:{block_id}:{line_start}", "to": visual_node})

    return nodes, edges


def _occurrences_by_line(
    occurrences: list[dict[str, Any]], symbol_table: dict[str, str]
) -> dict[tuple[int, int], list[dict[str, Any]]]:
    _ = symbol_table
    by_line: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in occurrences:
        by_line.setdefault((int(row["block_id"]), int(row["line_start"])), []).append(row)
    return by_line


def _debug_export_from_graph(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "anchorworks_observed_map_debug_export@1",
        "source": next(node for node in nodes if node["node_type"] == "document"),
        "blocks": [node for node in nodes if node["node_type"] == "block"],
        "lines": [node for node in nodes if node["node_type"] == "line"],
        "occurrences": [node for node in nodes if node["node_type"] == "occurrence"],
        "symbols": [node for node in nodes if node["node_type"] == "symbol"],
        "relation_windows": [edge for edge in edges if edge["edge_type"] == "relation_window"],
        "null_coordinates": [node for node in nodes if node["node_type"] == "null_coordinate"],
        "visual_refs": [node for node in nodes if node["node_type"] == "visual_ref"],
    }


def _graph_manifest(
    source_path: Path,
    source_hash: str,
    bundle_paths: dict[str, Path],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    outputs: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": "anchorworks_awsg_manifest@1",
        "graph_name": "toy_awsg_source.awsg",
        "source_id": SOURCE_ID,
        "source_path": str(source_path),
        "source_hash": source_hash,
        "awsm_path": str(bundle_paths["awsm"]),
        "awsl_path": str(bundle_paths["awsl"]),
        "awsn_path": str(bundle_paths["awsn"]),
        "awsv_path": str(bundle_paths["awsv"]),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "writes_allowed": WRITES_ALLOWED,
        "blocked_roots": BLOCKED_ROOTS,
        "outputs": outputs,
    }


def _schema_check(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> tuple[int, list[str], list[str]]:
    node_types = {str(node.get("node_type")) for node in nodes}
    edge_types = {str(edge.get("edge_type")) for edge in edges}
    missing_node_types = sorted(REQUIRED_NODE_TYPES - node_types)
    missing_edge_types = sorted(REQUIRED_EDGE_TYPES - edge_types)
    errors = len(missing_node_types) + len(missing_edge_types)
    for node in nodes:
        if not node.get("node_id") or not node.get("node_type"):
            errors += 1
    for edge in edges:
        if not edge.get("edge_type") or not edge.get("from") or not edge.get("to"):
            errors += 1
    return errors, missing_node_types, missing_edge_types


def _debug_export_errors(export: dict[str, Any]) -> int:
    required = ("source", "blocks", "lines", "occurrences", "symbols", "relation_windows", "null_coordinates", "visual_refs")
    return sum(1 for key in required if not export.get(key))


def _production_write_errors(outputs: list[str]) -> int:
    runtime_root = RUNTIME.resolve()
    blocked = [Path(path).resolve() for path in BLOCKED_ROOTS]
    errors = 0
    for output in outputs:
        resolved = Path(output).resolve()
        if not str(resolved).startswith(str(runtime_root)):
            errors += 1
        if any(resolved == root or root in resolved.parents for root in blocked):
            errors += 1
    return errors


def _anchorize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _symbol_for_surface(surface: str) -> str:
    digest = hashlib.blake2s(surface.encode("utf-8"), digest_size=5, person=b"AWSG").hexdigest().upper()
    return f"0x{digest}"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
