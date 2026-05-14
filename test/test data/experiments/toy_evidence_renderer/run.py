from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from AnchorWorks.symbol_count_cells import CANONICAL_LANE, SymbolRelation, read_symbol_cell, write_symbol_cell
from AnchorWorks.symbol_count_native import write_awss_from_symbol_count_artifacts
from AnchorWorks.symbolic_map_binary import SymbolicMapRelation, write_symbolic_map_binary


EXPERIMENT_ROOT = Path(__file__).resolve().parent
RUNTIME = EXPERIMENT_ROOT / "runtime"
REQUIRED_DIRS = ("corpus", "maps", "awss", "awsm", "awsc", "frames", "datasets", "reports")
REFUSAL_TEXT = "I do not have evidence for that in this toy dataset."
WINDOW_RADIUS = 3


TOY_ROWS = [
    {
        "id": "qa_001",
        "question": "What color is the anchor apple?",
        "doc": "The anchor apple is red.",
        "answer": "The anchor apple is red.",
        "evidence": "The anchor apple is red.",
        "supported": True,
    },
    {
        "id": "qa_002",
        "question": "Where does the brass compass rest?",
        "doc": "The brass compass rests on the oak desk.",
        "answer": "The brass compass rests on the oak desk.",
        "evidence": "The brass compass rests on the oak desk.",
        "supported": True,
    },
    {
        "id": "qa_003",
        "question": "Which tool measures the river sample?",
        "doc": "The blue probe measures the river sample.",
        "answer": "The blue probe measures the river sample.",
        "evidence": "The blue probe measures the river sample.",
        "supported": True,
    },
    {
        "id": "qa_004",
        "question": "What protects the seed tray?",
        "doc": "The glass cover protects the seed tray.",
        "answer": "The glass cover protects the seed tray.",
        "evidence": "The glass cover protects the seed tray.",
        "supported": True,
    },
    {
        "id": "qa_005",
        "question": "Which marker labels the north gate?",
        "doc": "The silver marker labels the north gate.",
        "answer": "The silver marker labels the north gate.",
        "evidence": "The silver marker labels the north gate.",
        "supported": True,
    },
    {
        "id": "qa_006",
        "question": "What color is the hidden apple?",
        "doc": "The anchor apple is red.",
        "answer": "",
        "evidence": "",
        "supported": False,
    },
    {
        "id": "qa_007",
        "question": "Where does the copper compass rest?",
        "doc": "The brass compass rests on the oak desk.",
        "answer": "",
        "evidence": "",
        "supported": False,
    },
    {
        "id": "qa_008",
        "question": "Which animal guards the seed tray?",
        "doc": "The glass cover protects the seed tray.",
        "answer": "",
        "evidence": "",
        "supported": False,
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Toy AnchorWorks evidence-frame renderer experiment.")
    parser.add_argument("command", choices=("build", "eval", "train", "all"))
    args = parser.parse_args()
    if args.command == "build":
        report = build()
        print(RUNTIME / "reports" / "build_report.json")
        print(json.dumps(report, ensure_ascii=True))
    elif args.command == "eval":
        report = evaluate()
        print(RUNTIME / "reports" / "eval_report.json")
        print(json.dumps(report, ensure_ascii=True))
    elif args.command == "train":
        report = train()
        print(RUNTIME / "reports" / "train_report.json")
        print(json.dumps(report, ensure_ascii=True))
    else:
        build()
        evaluate()
        report = train()
        print(RUNTIME / "reports" / "train_report.json")
        print(json.dumps(report, ensure_ascii=True))


def build() -> dict[str, Any]:
    if RUNTIME.exists():
        shutil.rmtree(RUNTIME)
    for name in REQUIRED_DIRS:
        (RUNTIME / name).mkdir(parents=True, exist_ok=True)
    (RUNTIME / "awsc" / "cells").mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    symbol_table = _build_symbol_table(TOY_ROWS)
    frames: list[dict[str, Any]] = []
    text_rows: list[dict[str, Any]] = []
    structured_rows: list[dict[str, Any]] = []
    artifact_paths: list[Path] = []
    all_relations: list[dict[str, Any]] = []
    schema_errors = 0

    for index, row in enumerate(TOY_ROWS, start=1):
        doc_id = f"doc_{index:03d}"
        source_path = RUNTIME / "corpus" / f"{doc_id}.txt"
        source_path.write_text(str(row["doc"]), encoding="utf-8")
        anchors = _anchorize(str(row["doc"]))
        source_symbols = [_symbol_for(anchor, symbol_table) for anchor in anchors]
        relation_rows = _relations_for_symbols(source_symbols)
        all_relations.extend(relation_rows)
        map_path = RUNTIME / "awsm" / f"{doc_id}.awsm"
        write_symbolic_map_binary(
            map_path,
            metadata={
                "schema_version": "toy_awsm_metadata@1",
                "doc_id": doc_id,
                "source_path": str(source_path),
                "row_id": row["id"],
                "source": "toy_evidence_renderer",
            },
            relations=[
                SymbolicMapRelation(
                    root_symbol_id=int(rel["root_symbol"], 16),
                    neighbor_symbol_id=int(rel["neighbor_symbol"], 16),
                    offset=int(rel["offset"]),
                    lane=int(rel["lane"]),
                    flags=int(rel["flags"]),
                    count=int(rel["observations"]),
                )
                for rel in relation_rows
            ],
        )
        artifact_path = RUNTIME / "maps" / f"{doc_id}.symbol_counts.json"
        artifact = _symbol_count_artifact(doc_id, row, anchors, source_symbols, relation_rows)
        _write_json(artifact_path, artifact)
        artifact_paths.append(artifact_path)

        frame = _frame_for_row(row, doc_id, source_path, anchors, symbol_table)
        frames.append(frame)
        _write_json(RUNTIME / "frames" / f"{row['id']}.frame.json", frame)
        text_rows.append(_text_dataset_row(frame))
        structured_rows.append(_structured_dataset_row(frame))
        if _schema_error(frame):
            schema_errors += 1

    awss_report = write_awss_from_symbol_count_artifacts(artifact_paths, RUNTIME / "awss" / "toy_relations.awss")
    awsc_report = _write_awsc_cells(all_relations)
    awsc_verify_errors = _verify_awsc_cells()
    _write_jsonl(RUNTIME / "datasets" / "symbol_frame_to_text.jsonl", text_rows)
    _write_jsonl(RUNTIME / "datasets" / "symbol_frame_to_structured.jsonl", structured_rows)

    outputs = [str(path) for path in sorted(RUNTIME.rglob("*")) if path.is_file()]
    manifest = {
        "schema_version": "toy_evidence_renderer_manifest@1",
        "runtime": str(RUNTIME),
        "isolation": {
            "blocked_roots": [
                r"D:\AnchorWorks_Clean_Runtime\State",
                r"D:\AnchorMaps",
                str(REPO_ROOT / "Canonical"),
                str(REPO_ROOT / "Spare_Slots"),
                str(REPO_ROOT / "Structural"),
            ],
            "production_writes_allowed": False,
        },
        "outputs": outputs,
        "law": "The model learns rendering over permitted evidence frames, not world facts.",
    }
    _write_json(RUNTIME / "reports" / "experiment_manifest.json", manifest)
    report = {
        "schema_version": "toy_evidence_renderer_build_report@1",
        "rows_built": len(frames),
        "symbols_generated": len(symbol_table),
        "supported_rows": sum(1 for row in TOY_ROWS if row["supported"]),
        "unsupported_rows": sum(1 for row in TOY_ROWS if not row["supported"]),
        "schema_errors": schema_errors,
        "awss_records": awss_report["record_count"],
        "awss_observations": awss_report["observation_count"],
        "awsc_cells": awsc_report["cell_count"],
        "awsc_verify_errors": awsc_verify_errors,
        "unsupported_answer_leaks": _unsupported_answer_leaks(text_rows),
        "seconds": round(time.perf_counter() - started, 6),
        "paired_jsonl_written": True,
    }
    _write_json(RUNTIME / "reports" / "build_report.json", report)
    return report


def evaluate() -> dict[str, Any]:
    text_path = RUNTIME / "datasets" / "symbol_frame_to_text.jsonl"
    structured_path = RUNTIME / "datasets" / "symbol_frame_to_structured.jsonl"
    if not text_path.exists() or not structured_path.exists():
        raise FileNotFoundError("run build before eval")
    text_rows = _read_jsonl(text_path)
    structured_rows = _read_jsonl(structured_path)
    schema_errors = 0
    evidence_errors = 0
    exact_matches = 0
    refusal_total = 0
    refusal_hits = 0
    for text_row, structured_row in zip(text_rows, structured_rows):
        frame = text_row["input_frame"]
        if _schema_error(frame):
            schema_errors += 1
        rendered = _rule_render(frame)
        if rendered == text_row["target_text"]:
            exact_matches += 1
        if not frame["frame_health"]["render_allowed"]:
            refusal_total += 1
            if rendered == REFUSAL_TEXT:
                refusal_hits += 1
        if frame["frame_health"]["render_allowed"] and not structured_row["target"]["evidence_used"]:
            evidence_errors += 1
    report = {
        "schema_version": "toy_evidence_renderer_eval_report@1",
        "rows_evaluated": len(text_rows),
        "schema_errors": schema_errors,
        "awsc_verify_errors": _verify_awsc_cells(),
        "unsupported_answer_leaks": _unsupported_answer_leaks(text_rows),
        "evidence_preservation_errors": evidence_errors,
        "exact_match_score": round(exact_matches / len(text_rows), 6) if text_rows else 0.0,
        "refusal_accuracy": round(refusal_hits / refusal_total, 6) if refusal_total else 1.0,
        "trained": False,
        "renderer": "deterministic_frame_renderer",
    }
    _write_json(RUNTIME / "reports" / "eval_report.json", report)
    return report


def train() -> dict[str, Any]:
    report = {
        "schema_version": "toy_evidence_renderer_train_report@1",
        "status": "skipped",
        "reason": "No tiny local renderer model asset is configured. Build/eval remain dependency-free.",
        "requires": ["explicit local model path", "explicit training dependency opt-in"],
        "writes_allowed": {"production": False},
    }
    (RUNTIME / "reports").mkdir(parents=True, exist_ok=True)
    _write_json(RUNTIME / "reports" / "train_report.json", report)
    return report


def _build_symbol_table(rows: list[dict[str, Any]]) -> dict[str, str]:
    anchors = set()
    for row in rows:
        anchors.update(_anchorize(str(row["question"])))
        anchors.update(_anchorize(str(row["doc"])))
        anchors.update(_anchorize(str(row.get("answer") or "")))
    return {anchor: _symbol_for_surface(anchor) for anchor in sorted(anchors)}


def _anchorize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _symbol_for_surface(surface: str) -> str:
    digest = hashlib.blake2s(surface.encode("utf-8"), digest_size=5, person=b"AWTOY").hexdigest().upper()
    return f"0x{digest}"


def _symbol_for(anchor: str, table: dict[str, str]) -> str:
    return table[anchor]


def _relations_for_symbols(symbols: list[str]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, int]] = Counter()
    for index, root in enumerate(symbols):
        for other_index in range(max(0, index - WINDOW_RADIUS), min(len(symbols), index + WINDOW_RADIUS + 1)):
            if other_index == index:
                continue
            offset = other_index - index
            counts[(root, symbols[other_index], offset)] += 1
    return [
        {
            "symbol_anchor": root,
            "root_symbol": root,
            "neighbor_symbol_anchor": neighbor,
            "neighbor_symbol": neighbor,
            "offset": f"{offset:+d}",
            "lane": CANONICAL_LANE,
            "flags": 0,
            "observations": count,
        }
        for (root, neighbor, offset), count in sorted(counts.items(), key=lambda item: (item[0][0], item[0][2], item[0][1]))
    ]


def _symbol_count_artifact(
    doc_id: str,
    row: dict[str, Any],
    anchors: list[str],
    symbols: list[str],
    relation_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    symbol_authority = [
        {"anchor": anchor, "symbol": symbol, "authority": "canonical"}
        for anchor, symbol in sorted(set(zip(anchors, symbols)), key=lambda item: item[0])
    ]
    return {
        "schema_version": "toy_source_local_symbol_counts@1",
        "doc_id": doc_id,
        "row_id": row["id"],
        "source_format": "toy_text",
        "symbol_authority": symbol_authority,
        "symbol_relation_counts": relation_rows,
        "relation_fates": [{"relation": "canonical", "count": len(relation_rows)}],
        "writes_allowed": {"production": False},
    }


def _frame_for_row(
    row: dict[str, Any],
    doc_id: str,
    source_path: Path,
    source_anchors: list[str],
    symbol_table: dict[str, str],
) -> dict[str, Any]:
    supported = bool(row["supported"])
    query_symbols = [_symbol_for(anchor, symbol_table) for anchor in _anchorize(str(row["question"]))]
    evidence_symbols = [_symbol_for(anchor, symbol_table) for anchor in _anchorize(str(row["evidence"]))] if supported else []
    answer_symbols = [_symbol_for(anchor, symbol_table) for anchor in _anchorize(str(row["answer"]))] if supported else []
    source_symbols = [_symbol_for(anchor, symbol_table) for anchor in source_anchors]
    return {
        "schema_version": "toy_evidence_frame@1",
        "row_id": row["id"],
        "doc_id": doc_id,
        "query": row["question"],
        "query_symbols": query_symbols,
        "source_symbols": source_symbols,
        "evidence_symbols": evidence_symbols,
        "answer_symbols": answer_symbols,
        "evidence_used": [
            {
                "doc_id": doc_id,
                "source_path": str(source_path),
                "text": row["evidence"],
                "symbols": evidence_symbols,
                "locator": {"block_id": "block_1", "line_start": 1, "line_end": 1},
            }
        ]
        if supported
        else [],
        "count_context": _count_context_for(query_symbols, source_symbols),
        "frame_health": {
            "has_query_symbols": bool(query_symbols),
            "has_evidence_symbols": bool(evidence_symbols),
            "has_count_context": True,
            "citation_required": False,
            "render_allowed": supported,
        },
        "target_text": row["answer"] if supported else REFUSAL_TEXT,
    }


def _count_context_for(query_symbols: list[str], source_symbols: list[str]) -> list[dict[str, Any]]:
    source_set = set(source_symbols)
    return [
        {"symbol": symbol, "source_overlap": symbol in source_set, "weight": 1.0 if symbol in source_set else 0.0}
        for symbol in query_symbols
    ]


def _text_dataset_row(frame: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "toy_symbol_frame_to_text@1",
        "input_frame": frame,
        "target_text": frame["target_text"],
    }


def _structured_dataset_row(frame: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "toy_symbol_frame_to_structured@1",
        "input_frame": frame,
        "target": {
            "answer_symbols": frame["answer_symbols"],
            "evidence_used": frame["evidence_used"],
            "render_allowed": frame["frame_health"]["render_allowed"],
            "text": frame["target_text"],
        },
    }


def _write_awsc_cells(relations: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[SymbolRelation]] = defaultdict(list)
    for row in relations:
        grouped[str(row["root_symbol"])].append(
            SymbolRelation(
                offset=int(str(row["offset"]).replace("+", "")),
                neighbor_symbol=str(row["neighbor_symbol"]),
                count=int(row["observations"]),
                lane=CANONICAL_LANE,
                flags=0,
            )
        )
    for root_symbol, rows in grouped.items():
        cell_name = root_symbol[2:].upper()
        cell_path = RUNTIME / "awsc" / "cells" / cell_name[:2] / f"{cell_name}.cell"
        write_symbol_cell(cell_path, symbol=root_symbol, root_lane=CANONICAL_LANE, generation=1, relations=rows)
    return {"cell_count": len(grouped)}


def _verify_awsc_cells() -> int:
    errors = 0
    for path in (RUNTIME / "awsc" / "cells").glob("*/*.cell"):
        try:
            read_symbol_cell(path)
        except Exception:
            errors += 1
    return errors


def _rule_render(frame: dict[str, Any]) -> str:
    if not frame["frame_health"]["render_allowed"]:
        return REFUSAL_TEXT
    evidence = frame.get("evidence_used") or []
    if not evidence:
        return REFUSAL_TEXT
    return str(evidence[0].get("text") or REFUSAL_TEXT)


def _schema_error(frame: dict[str, Any]) -> bool:
    health = frame.get("frame_health") or {}
    required_health = {"has_query_symbols", "has_evidence_symbols", "has_count_context", "citation_required", "render_allowed"}
    if set(health) != required_health:
        return True
    if not health["has_query_symbols"]:
        return True
    if health["render_allowed"]:
        return not (health["has_evidence_symbols"] and frame.get("answer_symbols") and frame.get("evidence_used"))
    return bool(frame.get("answer_symbols") or frame.get("evidence_used"))


def _unsupported_answer_leaks(rows: list[dict[str, Any]]) -> int:
    leaks = 0
    for row in rows:
        frame = row["input_frame"]
        if not frame["frame_health"]["render_allowed"] and row.get("target_text") != REFUSAL_TEXT:
            leaks += 1
        if not frame["frame_health"]["render_allowed"] and (frame.get("answer_symbols") or frame.get("evidence_used")):
            leaks += 1
    return leaks


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
