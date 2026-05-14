from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from AnchorWorks.document_film import extract_pdf_document_film
from AnchorWorks.document_prep import prepare_file
from AnchorWorks.visual_manifest import manifest_from_image_bytes

FOLDERS = [
    Path(r"C:\Users\mydyi\OneDrive\Documents\Desktop\How to Read and Follow Uploaded File Content_"),
    Path(r"C:\Users\mydyi\OneDrive\Documents\Desktop\Download"),
]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".ico"}
SUPPORTED_TEXTLIKE = {
    ".txt", ".md", ".markdown", ".py", ".ps1", ".sh", ".js", ".dart", ".mmd",
    ".json", ".jsonl", ".csv", ".html", ".htm", ".ipynb", ".docx", ".xlsx", ".xlsm",
}
PDF_EXTENSIONS = {".pdf"}
SKIP_PARTS = {"How_to_Read_and_Follow_Uploaded_File_Content__TrueVision_Document_Films"}
RUN_LIMITS = [1, 5, 25, 100, None]
REPORT_PATH = Path(r"D:\AnchorWorks_Clean_Runtime\Anchorworks\reports\truevision\truevision_two_folder_dry_run_2026-05-11.json")
NO_WRITE_POLICY = {"maps": False, "counts": False, "lifetime": False, "lexicon": False}


def should_skip(path: Path) -> bool:
    lowered = {part.lower() for part in path.parts}
    return any(part.lower() in lowered for part in SKIP_PARTS)


def collect_files() -> list[Path]:
    files: list[Path] = []
    allowed = PDF_EXTENSIONS | IMAGE_EXTENSIONS | SUPPORTED_TEXTLIKE
    for folder in FOLDERS:
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if path.is_file() and not should_skip(path) and path.suffix.lower() in allowed:
                # Skip converter helper output from this session; it is tooling, not user evidence.
                if path.name in {"Convert-AllDocs-ToPdf.ps1", "Convert-AllDocs-ToPdf-Fallback.py"}:
                    continue
                files.append(path)
    return sorted(files, key=lambda p: (str(p.parent).lower(), p.name.lower()))


def dry_probe(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    started = time.perf_counter()
    row: dict[str, Any] = {
        "source_path": str(path),
        "source_name": path.name,
        "extension": suffix,
        "bytes": path.stat().st_size,
        "writes": "metadata_only",
    }
    try:
        if suffix in PDF_EXTENSIONS:
            try:
                packet = extract_pdf_document_film(path)
                row.update({
                    "ok": True,
                    "mode": "pdf_embedded_page_image_film_in_memory",
                    "frame_count": int(packet.get("frame_count") or 0),
                    "page_count": int(packet.get("source_page_count") or packet.get("frame_count") or 0),
                    "region_status": "empty",
                    "recognition_status": "not_run",
                    "writes_allowed": packet.get("writes_allowed") or NO_WRITE_POLICY,
                })
            except Exception as exc:
                row.update({
                    "ok": False,
                    "mode": "pdf_needs_render_adapter",
                    "frame_count": 0,
                    "page_count": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                    "writes_allowed": NO_WRITE_POLICY,
                })
        elif suffix in IMAGE_EXTENSIONS:
            raw = path.read_bytes()
            manifest = manifest_from_image_bytes(
                raw,
                path.name,
                frame_index=0,
                frame_timestamp_ms=0,
                page_index=0,
                page_number=1,
                source_document_id="dry_run_image",
            )
            source = manifest.source
            row.update({
                "ok": True,
                "mode": "native_image_frame_manifest_in_memory",
                "frame_count": 1,
                "page_count": 1,
                "width": source.width,
                "height": source.height,
                "file_format": source.file_format,
                "region_status": "empty",
                "recognition_status": "not_run",
                "writes_allowed": manifest.writes_allowed.to_dict(),
            })
        else:
            prepared = prepare_file(path)
            text_len = len(prepared.prepared_text or "")
            # 1 document per frame for text-like dry-run: this is a single frame-worthy rendered document object.
            row.update({
                "ok": True,
                "mode": "prepared_text_doc_per_frame_dry_run",
                "converter": prepared.converter,
                "frame_count": 1,
                "page_count": 1,
                "prepared_text_chars": text_len,
                "region_status": "not_run",
                "recognition_status": "not_run",
                "writes_allowed": NO_WRITE_POLICY,
            })
    except Exception as exc:
        row.update({
            "ok": False,
            "mode": "probe_error",
            "frame_count": 0,
            "page_count": 0,
            "error": f"{type(exc).__name__}: {exc}",
            "writes_allowed": NO_WRITE_POLICY,
        })
    row["elapsed_sec"] = round(time.perf_counter() - started, 6)
    return row


def summarize_run(run_index: int, limit: int | None, files: list[Path]) -> dict[str, Any]:
    selected = files if limit is None else files[:limit]
    started = time.perf_counter()
    rows = [dry_probe(path) for path in selected]
    elapsed = time.perf_counter() - started
    ok_rows = [row for row in rows if row.get("ok")]
    frame_count = sum(int(row.get("frame_count") or 0) for row in rows)
    page_count = sum(int(row.get("page_count") or 0) for row in rows)
    return {
        "run_index": run_index,
        "limit": limit if limit is not None else "all",
        "files_considered": len(selected),
        "ok_count": len(ok_rows),
        "error_count": len(rows) - len(ok_rows),
        "frame_count": frame_count,
        "page_count": page_count,
        "elapsed_sec": round(elapsed, 6),
        "files_per_sec": round(len(selected) / elapsed, 6) if elapsed else 0,
        "frames_per_sec": round(frame_count / elapsed, 6) if elapsed else 0,
        "pages_per_sec": round(page_count / elapsed, 6) if elapsed else 0,
        "modes": _counter(row.get("mode") for row in rows),
        "errors": [row for row in rows if not row.get("ok")][:25],
        "rows_preview": rows[:20],
    }


def _counter(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        key = str(value or "")
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def main() -> None:
    started = time.perf_counter()
    files = collect_files()
    report = {
        "schema_version": "anchorworks_truevision_dry_run_metadata@1",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "folders": [str(folder) for folder in FOLDERS],
        "write_policy": "metadata_only_no_films_no_frames_no_maps_no_counts",
        "normalization_rule": "NEVER normalize before vision; all manipulation is post visual proofing.",
        "input_file_count": len(files),
        "extension_counts": _counter(path.suffix.lower() for path in files),
        "runs": [],
    }
    for index, limit in enumerate(RUN_LIMITS, start=1):
        report["runs"].append(summarize_run(index, limit, files))
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        report["elapsed_sec_so_far"] = round(time.perf_counter() - started, 6)
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    report["elapsed_sec"] = round(time.perf_counter() - started, 6)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
