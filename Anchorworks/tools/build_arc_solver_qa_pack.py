"""Build a Q/A pack from Lee's local ARC solver documentation.

The output is external to the AnchorWorks repo. It copies the ARC solver docs as
source evidence and writes a curated, evidence-tagged Q/A corpus from verified
project results.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ARC_ROOT = Path(r"D:\arc_solver_clean")
DEFAULT_OUTPUT_ROOT = Path(r"D:\AnchorWorks_Data_Curation\arc_solver_proven_qa")


CURATED_QA = [
    {
        "question": "What is Lee's ARC solver?",
        "answer": "Lee's ARC solver is a zero-training symbolic ARC reasoning engine built around deterministic operators, mathematical specifications, and verified task outputs.",
        "sources": ["docs/ARCHITECTURE_SPEC.md", "docs/README.md"],
        "evidence_terms": ["zero-training", "symbolic", "mathematically-specified", "operator"],
    },
    {
        "question": "How many tasks did the ARC production solver solve in the verified baseline?",
        "answer": "The verified production baseline solved 56 tasks, with the composition layer finding no additional real solves at that checkpoint.",
        "sources": ["docs/working-notes/session chat_log 11_29_25.md", "docs/ARCHITECTURE_SPEC.md"],
        "evidence_terms": ["56 solves", "composition", "0 new"],
    },
    {
        "question": "What result did the implementation pass improve?",
        "answer": "The implementation pass improved the solver from 53 solved tasks to 56 solved tasks by adding three new solves.",
        "sources": ["docs/IMPLEMENTATION_RESULTS.md"],
        "evidence_terms": ["53", "56", "+3"],
    },
    {
        "question": "Which operators produced the three new ARC solves?",
        "answer": "The three new solves came from shape_reference_recolor and enclosed_region_fill.",
        "sources": ["docs/IMPLEMENTATION_RESULTS.md"],
        "evidence_terms": ["shape_reference_recolor", "enclosed_region_fill"],
    },
    {
        "question": "Which tasks did shape_reference_recolor solve?",
        "answer": "shape_reference_recolor solved tasks 009d5c81 and aabf363d.",
        "sources": ["docs/IMPLEMENTATION_RESULTS.md"],
        "evidence_terms": ["009d5c81", "aabf363d"],
    },
    {
        "question": "Which task did enclosed_region_fill solve?",
        "answer": "enclosed_region_fill solved task a5313dff.",
        "sources": ["docs/IMPLEMENTATION_RESULTS.md"],
        "evidence_terms": ["a5313dff"],
    },
    {
        "question": "What is the ARC solver's baseline algorithm?",
        "answer": "The baseline tries each operator against all training examples, analyzes input and expected output pairs, applies the operator, and accepts it only when all training outputs match.",
        "sources": ["docs/ALGORITHM_DOCUMENTATION.md", "docs/ARCHITECTURE_SPEC.md"],
        "evidence_terms": ["solve_baseline", "operator", "all training examples"],
    },
    {
        "question": "Why were the claimed ARC composition solves rejected?",
        "answer": "The composition results were rejected because the multi-step scan had a bug and the supposed composition tasks were actually single-operator solves under the stronger baseline.",
        "sources": ["docs/MULTI_STEP_COMPOSITION_RESULTS.md", "docs/working-notes/session chat_log 11_29_25.md"],
        "evidence_terms": ["false positives", "single-operator", "bug"],
    },
    {
        "question": "What did the ARC composition layer prove at the checkpoint?",
        "answer": "The composition layer proved the architecture was ready, but it did not add new verified solves beyond the 56-solve baseline at that checkpoint.",
        "sources": ["docs/working-notes/session chat_log 11_29_25.md"],
        "evidence_terms": ["Layer 1", "0 new solves", "56 solves"],
    },
    {
        "question": "What does the ARC math DSL provide?",
        "answer": "The ARC math DSL provides formal operator specifications that describe objects, equations, transforms, and validation structure for symbolic ARC operations.",
        "sources": ["docs/MATH_DSL_RESULTS.md", "docs/PATH_B_MATH_FORMALIZATION.md"],
        "evidence_terms": ["Math DSL", "operator specifications", "validation"],
    },
    {
        "question": "What was the speed of the ARC full scan reported in the implementation results?",
        "answer": "The implementation results reported a full scan time of about 1.6 seconds for 1000 tasks, averaging roughly 1.6 milliseconds per task.",
        "sources": ["docs/IMPLEMENTATION_RESULTS.md"],
        "evidence_terms": ["1.6 seconds", "1000 tasks", "1.6ms"],
    },
    {
        "question": "What is shape_reference_recolor?",
        "answer": "shape_reference_recolor is an ARC operator where a reference shape encodes a property that determines how the main shape should be recolored.",
        "sources": ["docs/IMPLEMENTATION_RESULTS.md"],
        "evidence_terms": ["reference", "property", "recolor"],
    },
    {
        "question": "What is enclosed_region_fill?",
        "answer": "enclosed_region_fill is an ARC operator that detects enclosed interior regions with flood-fill logic and fills qualifying regions.",
        "sources": ["docs/IMPLEMENTATION_RESULTS.md"],
        "evidence_terms": ["Boundary", "Interior", "flood fill"],
    },
    {
        "question": "What operator categories does the ARC architecture use?",
        "answer": "The ARC architecture groups operators into recoloring, geometric, compositional, advanced, and incomplete or broken tiers.",
        "sources": ["docs/ARCHITECTURE_SPEC.md"],
        "evidence_terms": ["TIER 1", "TIER 2", "TIER 3", "TIER 4", "TIER 5"],
    },
    {
        "question": "What is the ARC solver's no hallucination rule?",
        "answer": "The ARC solver only counts verified solves, requiring explicit operator parameters and output checks instead of speculative or hallucinated solutions.",
        "sources": ["docs/ARC_SESSION_SUMMARY.md", "docs/ARCHITECTURE_SPEC.md"],
        "evidence_terms": ["No hallucinated solves", "verified solves", "explicit rule"],
    },
    {
        "question": "What was the ARC-AGI-master dataset result?",
        "answer": "On the ARC-AGI-master format, the solver reported 13 solved tasks out of 800 total tasks, with 11 training solves and 2 evaluation solves.",
        "sources": ["docs/ARC_AGI_MASTER_RESULTS.md"],
        "evidence_terms": ["13 tasks", "800", "11", "2"],
    },
    {
        "question": "Which operators solved tasks in the ARC-AGI-master report?",
        "answer": "The ARC-AGI-master report listed center_halo_expansion, color_histogram_fill, horizontal_replicate, mirror, position_based_recolor, recolor_mapping, self_masking_tiling, swap_mapping, and symmetry_completion as solving operators.",
        "sources": ["docs/ARC_AGI_MASTER_RESULTS.md"],
        "evidence_terms": ["center_halo_expansion", "mirror", "recolor_mapping"],
    },
    {
        "question": "What was the critical ARC lesson about weaker solvers?",
        "answer": "The critical lesson was not to replace the strongest baseline with weaker helper solvers; the 56-solve baseline should remain Layer 0 and composition should overlay it.",
        "sources": ["docs/working-notes/session chat_log 11_29_25.md"],
        "evidence_terms": ["56-solve baseline", "Layer 0", "weaker solvers"],
    },
    {
        "question": "What is the production ARC solver layering rule?",
        "answer": "The production layering rule is baseline solver first, composition solver second, and production orchestration above them without losing baseline solves.",
        "sources": ["docs/working-notes/session chat_log 11_29_25.md"],
        "evidence_terms": ["baseline_solver.py", "composition_solver.py", "production_solver.py"],
    },
    {
        "question": "Why is Lee's ARC solver useful to AnchorWorks?",
        "answer": "It provides proven language about deterministic symbolic reasoning, operator selection, verified outputs, and layered solver discipline that can strengthen AnchorWorks count-based rendering and routing.",
        "sources": ["docs/ARCHITECTURE_SPEC.md", "docs/ALGORITHM_DOCUMENTATION.md"],
        "evidence_terms": ["deterministic", "symbolic", "verified", "operator"],
    },
]


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def relative_to_arc(path: Path, arc_root: Path) -> str:
    return str(path.relative_to(arc_root)).replace("\\", "/")


def copy_docs(arc_root: Path, output_root: Path) -> list[dict[str, Any]]:
    docs_root = arc_root / "docs"
    target_root = output_root / "source_docs"
    if target_root.exists():
        shutil.rmtree(target_root)
    copied: list[dict[str, Any]] = []
    for source in sorted(docs_root.rglob("*")):
        if not source.is_file():
            continue
        rel = source.relative_to(docs_root)
        target = target_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        rel_text = str(rel).replace("\\", "/")
        copied.append(
            {
                "source_path": str(source),
                "copied_path": str(target),
                "relative_arc_path": f"docs/{rel_text}",
                "bytes": source.stat().st_size,
            }
        )
    return copied


def find_evidence(arc_root: Path, sources: list[str], terms: list[str]) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    for source in sources:
        path = arc_root / source
        if not path.exists():
            evidence.append({"source": source, "status": "missing", "excerpt": ""})
            continue
        text = clean_text(path.read_text(encoding="utf-8", errors="replace"))
        lower = text.lower()
        excerpt = ""
        for term in terms:
            index = lower.find(term.lower())
            if index >= 0:
                start = max(0, index - 180)
                end = min(len(text), index + 320)
                excerpt = clean_text(text[start:end])
                break
        if not excerpt:
            excerpt = clean_text(text[:420])
        evidence.append({"source": source, "status": "found", "excerpt": excerpt})
    return evidence


def build_rows(arc_root: Path) -> list[dict[str, Any]]:
    rows = []
    for index, item in enumerate(CURATED_QA):
        rows.append(
            {
                "schema_version": "anchorworks.qa_plain.v1",
                "source_key": f"lee_arc_solver_proven::{index:04d}",
                "dataset_id": "lee/arc_solver_proven_docs",
                "dataset_config": "curated_verified_results",
                "dataset_split": "local",
                "domain": "symbolic_arc_reasoning",
                "row_index": index,
                "question_text": item["question"],
                "answer_text": item["answer"],
                "source_context_text": "\n\n".join(
                    ev["excerpt"] for ev in find_evidence(arc_root, item["sources"], item["evidence_terms"]) if ev["excerpt"]
                ),
                "source_refs": item["sources"],
                "blocked_alternatives": [],
                "approved_for_intake": True,
                "license_review_required": False,
            }
        )
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_plaintext(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(f"Question: {row['question_text']}\n")
            handle.write(f"Answer: {row['answer_text']}\n")
            if row["source_context_text"]:
                handle.write(f"Evidence: {row['source_context_text']}\n")
            handle.write("\n---\n\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Q/A from local ARC solver proof docs.")
    parser.add_argument("--arc-root", default=str(DEFAULT_ARC_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()
    arc_root = Path(args.arc_root)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    copied_docs = copy_docs(arc_root, output_root)
    rows = build_rows(arc_root)

    jsonl_path = output_root / "jsonl" / "lee_arc_solver_proven_qa.jsonl"
    text_path = output_root / "plain_text" / "lee_arc_solver_proven_qa.txt"
    write_jsonl(jsonl_path, rows)
    write_plaintext(text_path, rows)

    report = {
        "schema_version": "anchorworks.arc_solver_qa_pack.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "arc_root": str(arc_root),
        "output_root": str(output_root),
        "source_docs_copied": len(copied_docs),
        "qa_rows": len(rows),
        "jsonl_path": str(jsonl_path),
        "plain_text_path": str(text_path),
        "source_doc_manifest": str(output_root / "reports" / "source_doc_manifest.json"),
    }
    reports = output_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "source_doc_manifest.json").write_text(json.dumps(copied_docs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (reports / "arc_solver_qa_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
