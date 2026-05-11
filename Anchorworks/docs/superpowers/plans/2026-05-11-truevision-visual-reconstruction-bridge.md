# TrueVision Visual Reconstruction Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the next TrueVision layer after document-film preservation: page render frames, page-region maps, line/glyph candidate scaffolds, and dual-path verification records without OCR or truth writes.

**Architecture:** Current TrueVision document film preserves page/frame identity, geometry, hashes, order, and timing, but cannot reconstruct prose because region maps and recognition candidates are empty. This plan adds a render fallback for vector/text PDFs, then adds source-local visual reconstruction scaffolds that locate page/line/glyph candidates without claiming recognized text. PDF source text remains the authority when present; visual layers witness the rendered page and feed verification only.

**Tech Stack:** Python 3, `pypdf`, existing AnchorForge image probing, existing TrueVision visual manifest/region/recognition modules, AWSV sidecars, `unittest`. Optional PDF render backend is isolated behind an adapter; no OCR, no CV model, no lifetime writes.

---

## Current Proof State

TrueVision currently proves:

```text
preserves page/frame visual identity: yes
preserves geometry/hash/order/timing: yes
reconstructs prose from vision alone: no
```

The generated vision-only reconstruction file proves the boundary:

```text
D:\AnchorWorks_Clean_Runtime\Anchorworks\experiments\truevision_document_film_probe\runtime\reports\recreated_text_from_vision_only.txt
```

It can reconstruct frame identity and geometry only because:

```text
region maps: empty
recognition candidates: empty
OCR/recognition: not run
```

Hard law for this plan:

```text
A frame is evidence of pixels, not evidence of words until recognition exists.
```

---

## Files

- Modify: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\document_film.py`
  - Add PDF render fallback adapter interface and packet metadata.
- Create: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\pdf_page_render.py`
  - Isolated PDF page render backend selection and page-image rendering contract.
- Modify: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\visual_region_map.py`
  - Add full-page and source-layout line-region helpers.
- Create: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\visual_text_scaffold.py`
  - Build line/glyph candidate scaffolds from source layout and rendered frame geometry without recognized text.
- Modify: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\document_prep.py`
  - Attach rendered document film when embedded page images are unavailable.
- Modify: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\store.py`
  - Carry region status and visual text scaffold status into AWSV rows.
- Test: `D:\AnchorWorks_Clean_Runtime\Anchorworks\tests\test_document_film.py`
  - Extend existing document-film tests.
- Test: `D:\AnchorWorks_Clean_Runtime\Anchorworks\tests\test_pdf_page_render.py`
  - New render adapter tests.
- Test: `D:\AnchorWorks_Clean_Runtime\Anchorworks\tests\test_visual_text_scaffold.py`
  - New reconstruction scaffold tests.

---

### Task 1: Add PDF Render Adapter Contract

**Files:**
- Create: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\pdf_page_render.py`
- Test: `D:\AnchorWorks_Clean_Runtime\Anchorworks\tests\test_pdf_page_render.py`

- [ ] **Step 1: Write failing tests for backend availability and no-render fallback**

Create `D:\AnchorWorks_Clean_Runtime\Anchorworks\tests\test_pdf_page_render.py`:

```python
from __future__ import annotations

import unittest

from AnchorWorks.pdf_page_render import (
    PdfRenderBackendUnavailable,
    available_pdf_render_backend,
    render_pdf_pages_to_images,
)


class PdfPageRenderTests(unittest.TestCase):
    def test_backend_probe_returns_known_shape(self) -> None:
        probe = available_pdf_render_backend()

        self.assertIn("backend_id", probe)
        self.assertIn("available", probe)
        self.assertIn("reason", probe)
        self.assertIsInstance(probe["available"], bool)

    def test_render_raises_clear_error_when_no_backend_available(self) -> None:
        probe = available_pdf_render_backend()
        if probe["available"]:
            self.skipTest(f"render backend available: {probe['backend_id']}")

        with self.assertRaises(PdfRenderBackendUnavailable):
            render_pdf_pages_to_images(b"%PDF-1.4\n%%EOF\n", source_name="empty.pdf")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
python -m unittest discover -s tests -p "test_pdf_page_render.py"
```

Expected:

```text
ModuleNotFoundError: No module named 'AnchorWorks.pdf_page_render'
```

- [ ] **Step 3: Implement backend probe and explicit unavailable error**

Create `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\pdf_page_render.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PdfRenderBackendUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class RenderedPdfPage:
    page_index: int
    page_number: int
    image_bytes: bytes
    source_name: str
    source_path_ref: str
    backend_id: str
    width: int | None = None
    height: int | None = None

    def to_frame(self, frame_index: int, frame_timestamp_ms: int) -> dict[str, Any]:
        return {
            "page_index": self.page_index,
            "page_number": self.page_number,
            "frame_index": frame_index,
            "frame_timestamp_ms": frame_timestamp_ms,
            "source_name": self.source_name,
            "source_path_ref": self.source_path_ref,
            "image_bytes": self.image_bytes,
            "render_backend_id": self.backend_id,
        }


def available_pdf_render_backend() -> dict[str, Any]:
    try:
        import fitz  # type: ignore  # pragma: no cover - optional backend

        _ = fitz
        return {"backend_id": "pymupdf_fitz", "available": True, "reason": ""}
    except Exception as fitz_exc:
        try:
            import pypdfium2  # type: ignore  # pragma: no cover - optional backend

            _ = pypdfium2
            return {"backend_id": "pypdfium2", "available": True, "reason": ""}
        except Exception as pdfium_exc:
            return {
                "backend_id": "",
                "available": False,
                "reason": f"no PDF render backend available; fitz={type(fitz_exc).__name__}; pypdfium2={type(pdfium_exc).__name__}",
            }


def render_pdf_pages_to_images(
    raw: bytes,
    *,
    source_name: str,
    dpi: int = 144,
    image_format: str = "png",
) -> list[RenderedPdfPage]:
    probe = available_pdf_render_backend()
    if not probe["available"]:
        raise PdfRenderBackendUnavailable(str(probe["reason"]))
    raise PdfRenderBackendUnavailable("PDF render backend contract exists, but backend implementation is not enabled yet")
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```powershell
python -m unittest discover -s tests -p "test_pdf_page_render.py"
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add src\AnchorWorks\pdf_page_render.py tests\test_pdf_page_render.py
git commit -m "Add PDF page render adapter contract"
```

---

### Task 2: Wire Render Fallback Into Document Film Metadata

**Files:**
- Modify: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\document_film.py`
- Test: `D:\AnchorWorks_Clean_Runtime\Anchorworks\tests\test_document_film.py`

- [ ] **Step 1: Add failing test for render fallback status**

Add to `DocumentFilmTests` in `D:\AnchorWorks_Clean_Runtime\Anchorworks\tests\test_document_film.py`:

```python
    def test_pdf_film_adapter_reports_render_backend_when_no_embedded_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "empty.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")

            with self.assertRaises(ValueError) as raised:
                extract_pdf_document_film(pdf_path)

            self.assertIn("no extractable page images", str(raised.exception))
```

This preserves current behavior until a render backend exists.

- [ ] **Step 2: Run the focused test**

Run:

```powershell
python -m unittest discover -s tests -p "test_document_film.py"
```

Expected:

```text
OK
```

- [ ] **Step 3: Update error message to name render fallback requirement**

In `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\document_film.py`, change the no-frames error to:

```python
    if not frames:
        raise ValueError("PDF document film found no extractable page images; PDF page render backend is required")
```

Update the test assertion:

```python
            self.assertIn("PDF page render backend is required", str(raised.exception))
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m unittest discover -s tests -p "test_document_film.py"
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add src\AnchorWorks\document_film.py tests\test_document_film.py
git commit -m "Report PDF render requirement for vector pages"
```

---

### Task 3: Add Full-Page Region Map Helper

**Files:**
- Modify: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\visual_region_map.py`
- Test: `D:\AnchorWorks_Clean_Runtime\Anchorworks\tests\test_visual_text_scaffold.py`

- [ ] **Step 1: Write failing test for full-page region**

Create `D:\AnchorWorks_Clean_Runtime\Anchorworks\tests\test_visual_text_scaffold.py`:

```python
from __future__ import annotations

import unittest

from AnchorWorks.visual_manifest import manifest_from_image_bytes
from AnchorWorks.visual_region_map import create_full_page_region_map

from test_visual_manifest import _png_bytes


class VisualTextScaffoldTests(unittest.TestCase):
    def test_full_page_region_map_creates_one_page_region(self) -> None:
        manifest = manifest_from_image_bytes(
            _png_bytes(8, 6),
            "page.png",
            frame_index=0,
            frame_timestamp_ms=0,
            page_index=0,
            page_number=1,
            source_document_id="doc_test",
        )

        region_map = create_full_page_region_map(manifest).to_dict()

        self.assertEqual(len(region_map["regions"]), 1)
        self.assertEqual(region_map["regions"][0]["kind_candidate"], "page")
        self.assertEqual(region_map["regions"][0]["bounds"], {"x": 0, "y": 0, "width": 8, "height": 6})
        self.assertEqual(region_map["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
python -m unittest discover -s tests -p "test_visual_text_scaffold.py"
```

Expected:

```text
ImportError: cannot import name 'create_full_page_region_map'
```

- [ ] **Step 3: Implement full-page region helper**

In `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\visual_region_map.py`, add:

```python
def create_full_page_region_map(manifest: VisualIntakeManifest) -> VisualRegionMap:
    source = manifest.source
    region = VisualRegion(
        region_id=f"{source.visual_record_id}_full_page",
        shape="box",
        bounds={
            "x": 0,
            "y": 0,
            "width": int(source.width or 0),
            "height": int(source.height or 0),
        },
        kind_candidate="page",
        confidence=1.0 if source.width and source.height else None,
        approval_status="candidate",
    )
    return VisualRegionMap(
        contract_version=REGION_MAP_CONTRACT_VERSION,
        visual_record_id=source.visual_record_id,
        region_map_id=_region_map_id(source.visual_record_id, source.sha256),
        source_hash=source.sha256,
        regions=[region],
        notes=[
            "Full-page region was generated from preserved visual frame geometry.",
            "No text/object recognition has been run.",
        ],
    )
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m unittest discover -s tests -p "test_visual_text_scaffold.py"
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add src\AnchorWorks\visual_region_map.py tests\test_visual_text_scaffold.py
git commit -m "Add full-page visual region scaffold"
```

---

### Task 4: Add Source-Layout Line Candidate Scaffold

**Files:**
- Create: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\visual_text_scaffold.py`
- Modify: `D:\AnchorWorks_Clean_Runtime\Anchorworks\tests\test_visual_text_scaffold.py`

- [ ] **Step 1: Add failing test for line candidate records**

Append to `VisualTextScaffoldTests`:

```python
    def test_line_scaffold_creates_candidate_without_text_claim(self) -> None:
        manifest = manifest_from_image_bytes(
            _png_bytes(100, 200),
            "page.png",
            frame_index=0,
            frame_timestamp_ms=0,
            page_index=0,
            page_number=1,
            source_document_id="doc_test",
        )
        source_lines = [
            {"line_number": 1, "text": "Alpha beta", "line_start": 1},
            {"line_number": 2, "text": "Gamma delta", "line_start": 2},
        ]

        from AnchorWorks.visual_text_scaffold import build_source_layout_line_scaffold

        scaffold = build_source_layout_line_scaffold(manifest, source_lines)

        self.assertEqual(scaffold["schema_version"], "anchorworks_visual_text_scaffold@1")
        self.assertEqual(scaffold["visual_record_id"], manifest.source.visual_record_id)
        self.assertEqual(len(scaffold["line_candidates"]), 2)
        self.assertEqual(scaffold["line_candidates"][0]["candidate_type"], "source_layout_line")
        self.assertEqual(scaffold["line_candidates"][0]["recognized_text"], "")
        self.assertEqual(scaffold["line_candidates"][0]["source_text_available"], True)
        self.assertEqual(scaffold["line_candidates"][0]["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
python -m unittest discover -s tests -p "test_visual_text_scaffold.py"
```

Expected:

```text
ModuleNotFoundError: No module named 'AnchorWorks.visual_text_scaffold'
```

- [ ] **Step 3: Implement source-layout line scaffold**

Create `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\visual_text_scaffold.py`:

```python
from __future__ import annotations

import hashlib
from typing import Any

from .visual_manifest import VisualIntakeManifest


SCAFFOLD_VERSION = "anchorworks_visual_text_scaffold@1"
NO_WRITE_POLICY = {"maps": False, "counts": False, "lifetime": False, "lexicon": False}


def build_source_layout_line_scaffold(
    manifest: VisualIntakeManifest,
    source_lines: list[dict[str, Any]],
) -> dict[str, Any]:
    source = manifest.source
    height = int(source.height or 0)
    width = int(source.width or 0)
    line_count = max(len(source_lines), 1)
    candidate_rows: list[dict[str, Any]] = []
    for index, line in enumerate(source_lines):
        y0 = int(round((index / line_count) * height)) if height else 0
        y1 = int(round(((index + 1) / line_count) * height)) if height else 0
        seed = f"{source.visual_record_id}::{index}::{line.get('line_number', index + 1)}"
        candidate_rows.append(
            {
                "candidate_id": "visual_line_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
                "candidate_type": "source_layout_line",
                "page_number": source.page_number,
                "line_number": int(line.get("line_number", index + 1) or index + 1),
                "bounds": {"x": 0, "y": y0, "width": width, "height": max(0, y1 - y0)},
                "recognized_text": "",
                "source_text_available": bool(str(line.get("text") or "").strip()),
                "source_text_hash": hashlib.sha256(str(line.get("text") or "").encode("utf-8")).hexdigest(),
                "recognition_status": "not_run",
                "approval_status": "candidate",
                "writes_allowed": dict(NO_WRITE_POLICY),
            }
        )
    return {
        "schema_version": SCAFFOLD_VERSION,
        "visual_record_id": source.visual_record_id,
        "source_hash": source.sha256,
        "source_document_id": source.source_document_id,
        "page_number": source.page_number,
        "line_candidates": candidate_rows,
        "writes_allowed": dict(NO_WRITE_POLICY),
        "notes": [
            "Line candidates are scaffolds from source layout and visual frame geometry.",
            "No visual text recognition has been run.",
        ],
    }
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m unittest discover -s tests -p "test_visual_text_scaffold.py"
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add src\AnchorWorks\visual_text_scaffold.py tests\test_visual_text_scaffold.py
git commit -m "Add visual text scaffold records"
```

---

### Task 5: Attach Reconstruction Status To AWSV

**Files:**
- Modify: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\store.py`
- Modify: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\symbolic_map_binary.py`
- Test: `D:\AnchorWorks_Clean_Runtime\Anchorworks\tests\test_document_film.py`

- [ ] **Step 1: Add failing AWSV status test**

In `test_pdf_mapping_writes_document_film_visual_refs_to_awsv`, add:

```python
            self.assertEqual(visual_rows[0]["region_status"], "empty")
            self.assertEqual(visual_rows[0]["visual_text_scaffold_status"], "not_run")
```

- [ ] **Step 2: Run focused test and verify failure**

Run:

```powershell
python -m unittest discover -s tests -p "test_document_film.py"
```

Expected:

```text
KeyError: 'region_status'
```

- [ ] **Step 3: Carry optional fields through AWSV normalization**

In `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\store.py`, add to the document-film `visual_rows.append({...})` row:

```python
                    "region_status": str(frame.get("region_status") or "empty"),
                    "visual_text_scaffold_status": str(frame.get("visual_text_scaffold_status") or "not_run"),
```

In `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\symbolic_map_binary.py`, add to `_normalize_visual_row` optional string fields:

```python
    for key in ("region_status", "visual_text_scaffold_status"):
        if key in row:
            normalized[key] = str(row.get(key) or "")
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m unittest discover -s tests -p "test_document_film.py"
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add src\AnchorWorks\store.py src\AnchorWorks\symbolic_map_binary.py tests\test_document_film.py
git commit -m "Carry visual reconstruction status in AWSV"
```

---

### Task 6: Real Fixture Proof And Report

**Files:**
- Create: `D:\AnchorWorks_Clean_Runtime\Anchorworks\tools\probe_truevision_pdf_reconstruction.py`
- Create report output at runtime only: `D:\AnchorWorks_Clean_Runtime\Anchorworks\reports\truevision_pdf_reconstruction_probe.json`

- [ ] **Step 1: Create probe script**

Create `D:\AnchorWorks_Clean_Runtime\Anchorworks\tools\probe_truevision_pdf_reconstruction.py`:

```python
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from AnchorWorks.document_film import extract_pdf_document_film
from AnchorWorks.pdf_page_render import available_pdf_render_backend


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python tools/probe_truevision_pdf_reconstruction.py <pdf> [<pdf> ...]", file=sys.stderr)
        return 2
    rows = []
    for item in argv:
        path = Path(item).expanduser().resolve()
        started = time.perf_counter()
        row = {"path": str(path), "exists": path.exists()}
        if not path.exists():
            row["ok"] = False
            row["error"] = "missing"
            rows.append(row)
            continue
        try:
            packet = extract_pdf_document_film(path)
            row.update(
                {
                    "ok": True,
                    "elapsed_sec": round(time.perf_counter() - started, 6),
                    "frame_count": packet.get("frame_count"),
                    "source_page_count": packet.get("source_page_count"),
                    "duplicate_frame_hashes": len(packet.get("duplicate_frame_hashes") or {}),
                    "first_frame": (packet.get("frames") or [{}])[0],
                    "writes_allowed": packet.get("writes_allowed"),
                }
            )
        except Exception as exc:
            row.update(
                {
                    "ok": False,
                    "elapsed_sec": round(time.perf_counter() - started, 6),
                    "error": f"{type(exc).__name__}: {exc}",
                    "render_backend": available_pdf_render_backend(),
                }
            )
        rows.append(row)
    report = {"schema_version": "anchorworks_truevision_pdf_reconstruction_probe@1", "rows": rows}
    output = Path("reports") / "truevision_pdf_reconstruction_probe.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 2: Run probe on known PDFs**

Run:

```powershell
python tools\probe_truevision_pdf_reconstruction.py `
  "C:\Users\mydyi\Downloads\How to Read and Follow Uploaded File Content_\US20190091581A1.pdf" `
  "C:\Users\mydyi\Downloads\How to Read and Follow Uploaded File Content_\COD_FINAL_ARTICLE.pdf" `
  "C:\Users\mydyi\Downloads\How to Read and Follow Uploaded File Content_\THEATRE_MODE_FINDINGS.pdf" `
  "C:\Users\mydyi\Downloads\How to Read and Follow Uploaded File Content_\CALLOFDUTYRENDERINGPIPELINE_3DDATAACCESSIBILITYASSESSMENT.pdf"
```

Expected before render backend exists:

```text
US20190091581A1.pdf ok true with 29 frames
the three vector/text PDFs ok false with PDF page render backend required
```

- [ ] **Step 3: Compile and run full tests**

Run:

```powershell
python -m py_compile src\AnchorWorks\pdf_page_render.py src\AnchorWorks\visual_text_scaffold.py tools\probe_truevision_pdf_reconstruction.py
python -m unittest discover -s tests
```

Expected:

```text
OK
```

- [ ] **Step 4: Commit probe**

```powershell
git add tools\probe_truevision_pdf_reconstruction.py
git commit -m "Add TrueVision PDF reconstruction probe"
```

---

## Acceptance

This plan is complete when:

```text
PDF render backend contract exists: yes
embedded raster PDF path still works: yes
vector/text PDF failure names render requirement: yes
full-page region helper exists: yes
line scaffold exists without recognized text claims: yes
AWSV carries reconstruction status: yes
OCR/recognition remains not_run: yes
truth writes remain blocked: yes
tests pass: yes
```

This plan does not finish visual text recognition. It makes the missing bridge explicit and gives the system the next lawful sockets.

---

## Next Plan After This One

After this plan passes, write a separate plan for one of these:

```text
Option A: Install/use a local PDF render backend and render vector PDFs into TrueVision frames.
Option B: Build deterministic glyph/line reconstruction over rendered bitmap frames.
Option C: Build dual-path verification between source text and visual line scaffolds.
```

Recommended next: Option A, because vector/text PDFs cannot become visual frames without page rendering.

