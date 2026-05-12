from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import textwrap
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from AnchorWorks.document_film import build_document_film_from_images
from AnchorWorks.document_prep import prepare_bytes


AUDIO_VIDEO_EXTENSIONS = {
    ".aac",
    ".aiff",
    ".avi",
    ".flac",
    ".m4a",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
    ".wmv",
}
IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
TEXT_EXTENSIONS = {".csv", ".htm", ".html", ".json", ".md", ".rtf", ".txt", ".xml"}
OFFICE_EXTENSIONS = {".doc", ".docx", ".odp", ".ods", ".odt", ".ppt", ".pptx", ".xls", ".xlsx"}
ARCHIVE_EXTENSIONS = {".7z", ".bz2", ".gz", ".rar", ".tar", ".tgz", ".xz", ".zip"}
NO_WRITE_POLICY = {"maps": False, "counts": False, "lifetime": False, "lexicon": False}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert document folders to PDFs, dedupe, organize, and build TrueVision one-doc/five-frame packets."
    )
    parser.add_argument("folders", nargs="+", help="Source folders to process.")
    parser.add_argument("--output-name", default="AnchorWorks_TrueVision_PDF_Batch", help="Output directory name beside each source folder.")
    parser.add_argument("--output-root", default="", help="Single output root for a combined multi-folder dataset.")
    parser.add_argument("--doc-frames", type=int, default=5, help="Frames per document film packet.")
    parser.add_argument("--frame-rate", type=float, default=5.0, help="Frame rate used for repeated one-doc film frames.")
    parser.add_argument("--workers", type=int, default=1, help="Parallel conversion workers for the PDF conversion stage.")
    args = parser.parse_args()

    if args.output_root:
        report = process_folders_combined(
            [Path(folder) for folder in args.folders],
            output_root=Path(args.output_root),
            doc_frames=args.doc_frames,
            frame_rate=args.frame_rate,
            workers=args.workers,
        )
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        reports = [
            process_folder(Path(folder), output_name=args.output_name, doc_frames=args.doc_frames, frame_rate=args.frame_rate, workers=args.workers)
            for folder in args.folders
        ]
        print(json.dumps({"schema_version": "anchorworks_truevision_pdf_batch@1", "folders": reports}, ensure_ascii=True, indent=2))


def process_folders_combined(
    source_folders: list[Path],
    *,
    output_root: Path,
    doc_frames: int,
    frame_rate: float,
    workers: int = 1,
) -> dict[str, Any]:
    started = time.perf_counter()
    output_root = output_root.expanduser().resolve()
    layout = _layout(output_root)
    _reset_output_dirs(layout, preserve_conversions=True)
    report: dict[str, Any] = {
        "schema_version": "anchorworks_truevision_pdf_combined_dataset_report@1",
        "output_root": str(output_root),
        "source_folders": [str(folder.expanduser().resolve()) for folder in source_folders],
        "files_seen": 0,
        "skipped_audio_video": 0,
        "skipped_archives": 0,
        "converted_pdf_count": 0,
        "deduplicated_pdf_count": 0,
        "duplicate_pdf_count": 0,
        "organized_pdf_count": 0,
        "film_packet_count": 0,
        "film_error_count": 0,
        "missing_folders": [],
        "conversion_errors": [],
        "film_errors": [],
        "workers": max(1, int(workers)),
        "writes_allowed": dict(NO_WRITE_POLICY),
    }
    completed_sources = _completed_source_paths(layout["conversion_manifests"])
    conversion_tasks: list[str] = []
    for source_folder in source_folders:
        source_folder = source_folder.expanduser().resolve()
        if not source_folder.is_dir():
            report["missing_folders"].append(str(source_folder))
            continue
        for source_path in sorted(source_folder.iterdir(), key=lambda item: item.name.lower()):
            if not source_path.is_file() or output_root in source_path.parents:
                continue
            report["files_seen"] += 1
            if source_path.suffix.lower() in AUDIO_VIDEO_EXTENSIONS:
                report["skipped_audio_video"] += 1
                continue
            if _is_archive_path(source_path):
                report["skipped_archives"] += 1
                continue
            if str(source_path.resolve()).lower() in completed_sources:
                continue
            conversion_tasks.append(str(source_path))

    report["conversion_tasks"] = len(conversion_tasks)
    conversion_results = _run_conversion_tasks(conversion_tasks, layout["converted"], max(1, int(workers)))
    report["converted_pdf_count"] = sum(1 for row in conversion_results if row.get("status") == "converted")
    report["conversion_errors"].extend(row for row in conversion_results if row.get("status") == "error")

    dedup_rows = deduplicate_pdfs(layout["converted"], layout["deduplicated"])
    report["deduplicated_pdf_count"] = sum(1 for row in dedup_rows if row["status"] == "kept")
    report["duplicate_pdf_count"] = sum(1 for row in dedup_rows if row["status"] == "duplicate")
    _write_json(layout["reports"] / "dedupe_report.json", {"schema_version": "anchorworks_pdf_dedupe_report@1", "rows": dedup_rows})

    organized_rows = organize_pdfs(layout["deduplicated"], layout["organized"])
    report["organized_pdf_count"] = len(organized_rows)
    _write_json(layout["reports"] / "organization_report.json", {"schema_version": "anchorworks_pdf_organization_report@1", "rows": organized_rows})

    for row in organized_rows:
        pdf_path = Path(row["organized_pdf_path"])
        try:
            packet = build_one_doc_five_frame_packet(pdf_path, layout["films"], doc_frames=doc_frames, frame_rate=frame_rate)
            report["film_packet_count"] += 1
            _write_json(layout["films"] / f"{pdf_path.stem}.document_film.json", packet)
        except Exception as exc:
            report["film_error_count"] += 1
            report["film_errors"].append({"pdf_path": str(pdf_path), "error": str(exc)})

    report["seconds"] = round(time.perf_counter() - started, 6)
    _write_json(layout["reports"] / "combined_dataset_report.json", report)
    return report


def process_folder(source_folder: Path, *, output_name: str, doc_frames: int, frame_rate: float, workers: int = 1) -> dict[str, Any]:
    started = time.perf_counter()
    source_folder = source_folder.expanduser().resolve()
    output_root = source_folder / output_name
    layout = _layout(output_root)
    _reset_output_dirs(layout, preserve_conversions=True)

    report: dict[str, Any] = {
        "schema_version": "anchorworks_truevision_pdf_folder_report@1",
        "source_folder": str(source_folder),
        "output_root": str(output_root),
        "exists": source_folder.is_dir(),
        "files_seen": 0,
        "skipped_audio_video": 0,
        "skipped_archives": 0,
        "converted_pdf_count": 0,
        "deduplicated_pdf_count": 0,
        "duplicate_pdf_count": 0,
        "organized_pdf_count": 0,
        "film_packet_count": 0,
        "film_error_count": 0,
        "conversion_errors": [],
        "film_errors": [],
        "workers": max(1, int(workers)),
        "writes_allowed": dict(NO_WRITE_POLICY),
    }
    if not source_folder.is_dir():
        report["seconds"] = round(time.perf_counter() - started, 6)
        _write_json(layout["reports"] / "folder_report.json", report)
        return report

    completed_sources = _completed_source_paths(layout["conversion_manifests"])
    candidates = [path for path in sorted(source_folder.iterdir(), key=lambda item: item.name.lower()) if path.is_file()]
    conversion_tasks: list[str] = []
    for source_path in candidates:
        if output_root in source_path.parents:
            continue
        report["files_seen"] += 1
        if source_path.suffix.lower() in AUDIO_VIDEO_EXTENSIONS:
            report["skipped_audio_video"] += 1
            continue
        if _is_archive_path(source_path):
            report["skipped_archives"] += 1
            continue
        if str(source_path.resolve()).lower() in completed_sources:
            continue
        conversion_tasks.append(str(source_path))

    report["conversion_tasks"] = len(conversion_tasks)
    conversion_results = _run_conversion_tasks(conversion_tasks, layout["converted"], max(1, int(workers)))
    report["converted_pdf_count"] = sum(1 for row in conversion_results if row.get("status") == "converted")
    report["conversion_errors"].extend(row for row in conversion_results if row.get("status") == "error")

    dedup_rows = deduplicate_pdfs(layout["converted"], layout["deduplicated"])
    report["deduplicated_pdf_count"] = sum(1 for row in dedup_rows if row["status"] == "kept")
    report["duplicate_pdf_count"] = sum(1 for row in dedup_rows if row["status"] == "duplicate")
    _write_json(layout["reports"] / "dedupe_report.json", {"schema_version": "anchorworks_pdf_dedupe_report@1", "rows": dedup_rows})

    organized_rows = organize_pdfs(layout["deduplicated"], layout["organized"])
    report["organized_pdf_count"] = len(organized_rows)
    _write_json(layout["reports"] / "organization_report.json", {"schema_version": "anchorworks_pdf_organization_report@1", "rows": organized_rows})

    for row in organized_rows:
        pdf_path = Path(row["organized_pdf_path"])
        try:
            packet = build_one_doc_five_frame_packet(pdf_path, layout["films"], doc_frames=doc_frames, frame_rate=frame_rate)
            report["film_packet_count"] += 1
            _write_json(layout["films"] / f"{pdf_path.stem}.document_film.json", packet)
        except Exception as exc:
            report["film_error_count"] += 1
            report["film_errors"].append({"pdf_path": str(pdf_path), "error": str(exc)})

    report["seconds"] = round(time.perf_counter() - started, 6)
    _write_json(layout["reports"] / "folder_report.json", report)
    return report


def convert_to_pdf(source_path: Path, output_dir: Path, *, output_stem: str | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = source_path.suffix.lower()
    if _is_archive_path(source_path):
        raise ValueError("archive files are skipped by the PDF dataset pipeline")
    output_path = _unique_path(output_dir / f"{output_stem or source_path.stem}.pdf")
    if suffix == ".pdf":
        shutil.copy2(source_path, output_path)
        if not _pdf_has_extractable_image(output_path):
            _prepared_text_to_pdf(source_path, output_path)
        return output_path
    if suffix in IMAGE_EXTENSIONS:
        _image_to_pdf(source_path, output_path)
        return output_path
    if suffix in TEXT_EXTENSIONS:
        _prepared_text_to_pdf(source_path, output_path)
        return output_path
    if suffix in OFFICE_EXTENSIONS:
        if _convert_with_soffice(source_path, output_dir):
            produced = output_dir / f"{source_path.stem}.pdf"
            if produced.exists():
                if produced != output_path:
                    produced.replace(output_path)
                return output_path
        _prepared_text_to_pdf(source_path, output_path)
        return output_path
    _prepared_text_to_pdf(source_path, output_path)
    return output_path


def _run_conversion_tasks(source_paths: list[str], output_dir: Path, workers: int) -> list[dict[str, Any]]:
    if not source_paths:
        return []
    if workers <= 1:
        return [_convert_source_worker((source_path, str(output_dir))) for source_path in source_paths]
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_convert_source_worker, (source_path, str(output_dir))) for source_path in source_paths]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def _convert_source_worker(args: tuple[str, str]) -> dict[str, Any]:
    source_path = Path(args[0])
    output_dir = Path(args[1])
    try:
        output_stem = _safe_output_stem(source_path)
        pdf_path = convert_to_pdf(source_path, output_dir, output_stem=output_stem)
        record = {
            "schema_version": "anchorworks_pdf_conversion_record@1",
            "source_path": str(source_path),
            "pdf_path": str(pdf_path),
            "source_sha256": _sha256_file(source_path),
            "pdf_sha256": _sha256_file(pdf_path),
            "content_sha256": _content_sha256(source_path),
            "conversion_kind": _conversion_kind(source_path),
        }
        _write_json(output_dir / "_conversion_manifests" / f"{pdf_path.stem}.conversion.json", record)
        return {"status": "converted", "source_path": str(source_path), "pdf_path": str(pdf_path)}
    except Exception as exc:
        return {"status": "error", "source_path": str(source_path), "error": str(exc)}


def deduplicate_pdfs(input_dir: Path, output_dir: Path) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    content_hashes = _conversion_content_hashes(input_dir / "_conversion_manifests")
    seen: dict[str, Path] = {}
    rows: list[dict[str, Any]] = []
    for pdf_path in sorted(input_dir.glob("*.pdf"), key=lambda item: item.name.lower()):
        digest = content_hashes.get(str(pdf_path.resolve()), _content_sha256(pdf_path))
        if digest in seen:
            rows.append(
                {
                    "status": "duplicate",
                    "pdf_path": str(pdf_path),
                    "duplicate_of": str(seen[digest]),
                    "content_sha256": digest,
                }
            )
            continue
        target = _unique_path(output_dir / pdf_path.name)
        shutil.copy2(pdf_path, target)
        seen[digest] = target
        rows.append({"status": "kept", "pdf_path": str(pdf_path), "deduplicated_pdf_path": str(target), "content_sha256": digest})
    return rows


def organize_pdfs(input_dir: Path, output_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pdf_path in sorted(input_dir.glob("*.pdf"), key=lambda item: item.name.lower()):
        text = _pdf_text_preview(pdf_path).lower()
        category = _content_category(pdf_path.name.lower(), text)
        category_dir = output_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)
        target = _unique_path(category_dir / pdf_path.name)
        shutil.copy2(pdf_path, target)
        rows.append(
            {
                "pdf_path": str(pdf_path),
                "organized_pdf_path": str(target),
                "category": category,
                "context_terms": _context_terms(text),
            }
        )
    return rows


def build_one_doc_five_frame_packet(pdf_path: Path, output_dir: Path, *, doc_frames: int, frame_rate: float) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_bytes, source_ref = _first_pdf_embedded_image(pdf_path)
    source_hash = _sha256_file(pdf_path)
    frames = [
        {
            "page_index": 0,
            "page_number": 1,
            "frame_index": index,
            "frame_timestamp_ms": int(round((index * 1000.0) / frame_rate)) if frame_rate else index,
            "source_name": f"{pdf_path.stem}_docfilm_frame_{index:04d}{Path(source_ref).suffix or '.image'}",
            "source_path_ref": f"{pdf_path}#page=1#frame={index}#source={source_ref}",
            "image_bytes": image_bytes,
        }
        for index in range(doc_frames)
    ]
    packet = build_document_film_from_images(
        source_document_id="docfilm_batch_" + hashlib.sha256(str(pdf_path).encode("utf-8")).hexdigest()[:16],
        source_path=str(pdf_path),
        source_hash=source_hash,
        frames=frames,
        frame_rate=frame_rate,
        duplicate_policy="one_doc_five_frames_expected",
    )
    packet["batch_ingest_mode"] = "truevision_only_document_film"
    packet["writes_allowed"] = dict(NO_WRITE_POLICY)
    return packet


def _first_pdf_embedded_image(pdf_path: Path) -> tuple[bytes, str]:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - optional runtime package
        raise ValueError("TrueVision film needs pypdf to extract embedded PDF images") from exc
    reader = PdfReader(str(pdf_path))
    for page_index, page in enumerate(reader.pages):
        try:
            images = list(page.images)
        except Exception:
            images = []
        if images:
            image = images[0]
            image_name = Path(str(getattr(image, "name", "") or f"page_{page_index + 1:04d}.image")).name
            return bytes(image.data), image_name
    raise ValueError("PDF document film found no extractable page images")


def _pdf_has_extractable_image(pdf_path: Path) -> bool:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            try:
                if list(page.images):
                    return True
            except Exception:
                continue
    except Exception:
        return False
    return False


def _image_to_pdf(source_path: Path, output_path: Path) -> None:
    from PIL import Image

    with Image.open(source_path) as image:
        if image.mode in {"RGBA", "LA", "P"}:
            image = image.convert("RGB")
        image.save(output_path, "PDF", resolution=100.0)


def _prepared_text_to_pdf(source_path: Path, output_path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    prepared = prepare_bytes(source_path.read_bytes(), source_name=source_path.name)
    font = ImageFont.load_default()
    width = 1700
    height = 2200
    margin = 80
    line_height = 18
    max_chars = 150
    lines: list[str] = []
    for raw_line in prepared.prepared_text.splitlines():
        wrapped = textwrap.wrap(raw_line, width=max_chars) or [""]
        lines.extend(wrapped)
    pages: list[Image.Image] = []
    for start in range(0, max(len(lines), 1), (height - 2 * margin) // line_height):
        page = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(page)
        y = margin
        for line in lines[start : start + ((height - 2 * margin) // line_height)]:
            draw.text((margin, y), line, fill="black", font=font)
            y += line_height
        pages.append(page)
    pages[0].save(output_path, "PDF", save_all=True, append_images=pages[1:], resolution=150.0)


def _convert_with_soffice(source_path: Path, output_dir: Path) -> bool:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return False
    result = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(source_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _pdf_text_preview(pdf_path: Path) -> str:
    try:
        prepared = prepare_bytes(pdf_path.read_bytes(), source_name=pdf_path.name)
        return prepared.prepared_text[:20000]
    except Exception:
        return ""


def _content_category(name: str, text: str) -> str:
    haystack = f"{name}\n{text}"
    if any(term in haystack for term in ("call of duty", "rendering pipeline", "3d data", "game")):
        return "game_rendering"
    if any(term in haystack for term in ("theatre", "theater", "mode", "findings")):
        return "theatre_mode"
    if any(term in haystack for term in ("patent", "claim", "invent", "us20")):
        return "patents"
    if any(term in haystack for term in ("anchorworks", "citation", "introspection", "system")):
        return "anchorworks_system"
    return "general_documents"


def _context_terms(text: str) -> list[str]:
    candidates = ("anchorworks", "citation", "introspection", "theatre", "call of duty", "rendering", "patent", "visual", "truevision")
    return [term for term in candidates if term in text]


def _conversion_kind(source_path: Path) -> str:
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        return "copied_existing_pdf"
    if suffix in IMAGE_EXTENSIONS:
        return "image_to_pdf"
    if suffix in OFFICE_EXTENSIONS and (shutil.which("soffice") or shutil.which("libreoffice")):
        return "office_to_pdf_or_text_fallback"
    return "prepared_text_to_image_pdf"


def _is_archive_path(path: Path) -> bool:
    name = path.name.lower()
    return path.suffix.lower() in ARCHIVE_EXTENSIONS or any(name.endswith(ext) for ext in (".tar.gz", ".tar.bz2", ".tar.xz"))


def _layout(output_root: Path) -> dict[str, Path]:
    return {
        "root": output_root,
        "converted": output_root / "01_converted_pdfs",
        "conversion_manifests": output_root / "01_converted_pdfs" / "_conversion_manifests",
        "deduplicated": output_root / "02_deduplicated_pdfs",
        "organized": output_root / "03_organized_by_content",
        "films": output_root / "04_truevision_document_films",
        "reports": output_root / "reports",
    }


def _reset_output_dirs(layout: dict[str, Path], *, preserve_conversions: bool = False) -> None:
    root = layout["root"]
    root.mkdir(parents=True, exist_ok=True)
    for key, path in layout.items():
        if key == "root":
            continue
        if preserve_conversions and key in {"converted", "conversion_manifests"}:
            path.mkdir(parents=True, exist_ok=True)
            continue
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 10000):
        candidate = path.with_name(f"{path.stem}_{index:04d}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError(f"could not create unique path for {path}")


def _safe_output_stem(path: Path) -> str:
    stem = "".join(char if char.isalnum() or char in (" ", "-", "_", ".", "(", ")") else "_" for char in path.stem).strip()
    stem = stem[:120] or "document"
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
    return f"{stem}__{digest}"


def _completed_source_paths(manifest_dir: Path) -> set[str]:
    completed: set[str] = set()
    if not manifest_dir.exists():
        return completed
    for manifest_path in manifest_dir.glob("*.conversion.json"):
        try:
            record = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        source_path = str(record.get("source_path") or "")
        if source_path:
            completed.add(str(Path(source_path).resolve()).lower())
    return completed


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _content_sha256(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image:" + _sha256_file(path)
    try:
        prepared = prepare_bytes(path.read_bytes(), source_name=path.name)
        normalized = "\n".join(line.strip() for line in prepared.prepared_text.lower().splitlines() if line.strip())
        if normalized:
            return "text:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    except Exception:
        pass
    return "bytes:" + _sha256_file(path)


def _conversion_content_hashes(manifest_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if not manifest_dir.exists():
        return hashes
    for manifest_path in manifest_dir.glob("*.conversion.json"):
        try:
            record = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        pdf_path = str(record.get("pdf_path") or "")
        content_hash = str(record.get("content_sha256") or "")
        if pdf_path and content_hash:
            hashes[str(Path(pdf_path).resolve())] = content_hash
    return hashes


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
