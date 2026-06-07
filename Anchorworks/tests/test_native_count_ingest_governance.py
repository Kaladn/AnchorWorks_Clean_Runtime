from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src" / "AnchorWorks"

FORBIDDEN_SOURCE_SNIPPETS = [
    "build_source_local_symbol_counts",
    "build_binary_symbol_counts_from_source_local",
    "build_symbolic_intake_batch",
    "build_symbolic_intake_batch_chunked",
    "write_awss_from_symbol_count_artifacts",
    "_pack_awss_record",
    "symbol_relation_counts",
    "ProcessPoolExecutor",
    "symbolic-batch-intake",
    "chunked_symbolic_intake",
    "source_local_symbol_counts.awss",
    "awss_stream",
    "_build_observed_map_worker",
    "lifetime_co_occurrence_counts.json",
    "_load_combined_relation_counts",
    "_load_relation_counts_file",
    "load_lifetime_by_symbol_dir",
    "ANCHORWORKS_LIFETIME_BY_SYMBOL_DIR",
]


def test_python_count_producing_ingest_paths_are_removed() -> None:
    offenders: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for snippet in FORBIDDEN_SOURCE_SNIPPETS:
            if snippet in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {snippet}")
    assert offenders == []
