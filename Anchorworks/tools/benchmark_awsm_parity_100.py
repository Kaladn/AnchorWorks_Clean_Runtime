from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from AnchorWorks.store import LexiconStore


EXTENSION_MIX = [
    (".cnxml", 16),
    (".html", 12),
    (".css", 10),
    (".js", 10),
    (".svg", 10),
    (".xml", 10),
    (".json", 10),
    (".yml", 10),
    (".md", 12),
]

ANCHORS = [
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "zeta",
    "eta",
    "theta",
    "iota",
    "kappa",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the 100-doc AWSM/JSON source-local symbol parity benchmark.")
    parser.add_argument("--output", type=Path, default=Path("reports/benchmarks/awsm_parity_100.json"))
    parser.add_argument("--keep-workdir", action="store_true")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="anchorworks-awsm-parity-") as temp_dir:
        root = Path(temp_dir)
        report = run_benchmark(root)
        if args.keep_workdir:
            kept = args.output.resolve().with_suffix(".workdir")
            if kept.exists():
                shutil.rmtree(kept)
            shutil.copytree(root, kept)
            report["workdir"] = str(kept)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))


def run_benchmark(root: Path) -> dict[str, Any]:
    data_root = root / "LexicalData"
    source_root = root / "source_docs"
    awsm_artifact_root = root / "awsm_artifacts"
    source_root.mkdir(parents=True)
    awsm_artifact_root.mkdir(parents=True)
    _seed_runtime(data_root)
    sources = _write_sources(source_root)

    store = LexiconStore(data_root)

    map_started = time.perf_counter()
    map_results = [store.build_observed_map(path) for path in sources]
    dual_write_seconds = time.perf_counter() - map_started

    awsm_payloads: dict[str, dict[str, Any]] = {}
    json_payloads: dict[str, dict[str, Any]] = {}
    awsm_artifacts: list[Path] = []
    awsm_seconds = 0.0
    json_seconds = 0.0
    mismatches: list[dict[str, Any]] = []

    for row in map_results:
        name = str(row["saved_map_name"])
        awsm_started = time.perf_counter()
        awsm_result = store.build_source_local_symbol_counts(name)
        awsm_seconds += time.perf_counter() - awsm_started
        awsm_payload = _read_json(Path(awsm_result["symbol_counts_path"]))
        awsm_payloads[name] = awsm_payload
        awsm_copy = awsm_artifact_root / Path(awsm_result["symbol_counts_path"]).name
        shutil.copy2(awsm_result["symbol_counts_path"], awsm_copy)
        awsm_artifacts.append(awsm_copy)

        symbolic_path = Path(str(row["symbolic_map_path"]))
        symbolic_backup = symbolic_path.with_suffix(".awsm.benchbak")
        symbolic_path.rename(symbolic_backup)
        try:
            json_started = time.perf_counter()
            json_result = store.build_source_local_symbol_counts(name)
            json_seconds += time.perf_counter() - json_started
            json_payload = _read_json(Path(json_result["symbol_counts_path"]))
            json_payloads[name] = json_payload
        finally:
            symbolic_backup.rename(symbolic_path)

        mismatch = _compare_artifacts(name, awsm_payloads[name], json_payloads[name])
        if mismatch:
            mismatches.append(mismatch)

    binary_started = time.perf_counter()
    binary = store.build_binary_symbol_counts_from_source_local(
        generation=100,
        artifact_names=[str(path) for path in awsm_artifacts],
    )
    binary_seconds = time.perf_counter() - binary_started
    verify = binary.get("verify") or {}

    return {
        "schema_version": "anchorworks_awsm_parity_benchmark@1",
        "doc_count": len(sources),
        "extension_mix": _extension_counts(sources),
        "dual_write_seconds": round(dual_write_seconds, 6),
        "awsm_artifact_build_seconds": round(awsm_seconds, 6),
        "json_fallback_build_seconds": round(json_seconds, 6),
        "awsm_vs_json_speedup": round(json_seconds / awsm_seconds, 4) if awsm_seconds else None,
        "awss_awsc_build_seconds": round(binary_seconds, 6),
        "parity_mismatch_count": len(mismatches),
        "parity_mismatches": mismatches[:10],
        "awss_records": int(binary.get("stream_record_count", 0) or 0),
        "awss_observations": int(binary.get("stream_observation_count", 0) or 0),
        "awsc_cells_verified": int(verify.get("checked", 0) or 0),
        "awsc_verify_errors": len(verify.get("errors") or []),
        "json_role": "fallback/parity/debug only",
        "ok": len(mismatches) == 0 and bool(binary.get("ok")) and len(verify.get("errors") or []) == 0,
    }


def _seed_runtime(data_root: Path) -> None:
    canonical = [
        {"word": word, "hex": f"0x{index:010X}"}
        for index, word in enumerate(ANCHORS[:8], start=1)
    ]
    _write_json(data_root / "Canonical" / "canonical_A.json", canonical)
    _write_json(data_root / "Structural" / "structural.json", [{"word": ".", "status": "STRUCTURAL"}])
    _write_json(data_root / "Spare_Slots" / "spare_slots.json", [])


def _write_sources(source_root: Path) -> list[Path]:
    paths: list[Path] = []
    doc_index = 0
    for extension, count in EXTENSION_MIX:
        for _ in range(count):
            doc_index += 1
            path = source_root / f"source_{doc_index:03d}{extension}"
            path.write_text(_content_for(doc_index, extension), encoding="utf-8")
            paths.append(path)
    return paths


def _content_for(index: int, extension: str) -> str:
    a = ANCHORS[index % len(ANCHORS)]
    b = ANCHORS[(index + 1) % len(ANCHORS)]
    c = ANCHORS[(index + 3) % len(ANCHORS)]
    phrase = f"{a} {b} {a} {c} {b} {a}"
    if extension == ".html":
        return f"<html><body><h1>{a}</h1><p>{phrase}</p></body></html>"
    if extension == ".css":
        return f".{a} {{ content: '{phrase}'; }}\n.{b} {{ color: blue; }}"
    if extension == ".js":
        return f"const {a} = '{phrase}';\nfunction {b}() {{ return {a}; }}"
    if extension == ".svg":
        return f"<svg><title>{a}</title><text>{phrase}</text></svg>"
    if extension == ".xml":
        return f"<root><title>{a}</title><body>{phrase}</body></root>"
    if extension == ".cnxml":
        return f"<document><metadata>{a}</metadata><para>{phrase}</para></document>"
    if extension == ".json":
        return json.dumps({"title": a, "body": phrase, "tags": [a, b, c]})
    if extension == ".yml":
        return f"title: {a}\nbody: {phrase}\ntags:\n  - {a}\n  - {b}\n"
    return f"# {a}\n\n{phrase}\n\n{b} {c} {a}\n"


def _compare_artifacts(name: str, awsm: dict[str, Any], observed_json: dict[str, Any]) -> dict[str, Any] | None:
    checks = {
        "symbol_authority": awsm.get("symbol_authority") == observed_json.get("symbol_authority"),
        "symbol_relation_counts": awsm.get("symbol_relation_counts") == observed_json.get("symbol_relation_counts"),
        "relation_fates": awsm.get("relation_fates") == observed_json.get("relation_fates"),
    }
    if all(checks.values()):
        return None
    return {"observed_map_name": name, "checks": checks}


def _extension_counts(paths: list[Path]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        counts[path.suffix] = counts.get(path.suffix, 0) + 1
    return dict(sorted(counts.items()))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
