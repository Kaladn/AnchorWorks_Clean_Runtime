from __future__ import annotations

import io
import json
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path

from AnchorWorks.app import IntakeAuditBody, RebuildReadinessBody, create_app
from AnchorWorks.document_prep import prepare_bytes
from AnchorWorks.intake_audit import audit_source_directory, rebuild_readiness_report
from AnchorWorks.ocr_backend import create_ocr_backend_capability, validate_ocr_candidate_layer
from AnchorWorks.visual_region_generation import generate_basic_visual_regions


def _zip_bytes(entries: dict[str, str | bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return buffer.getvalue()


def _tiny_png(width: int = 3, height: int = 2) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
        + (0).to_bytes(4, "big")
        + b"IEND"
        + b"\x00\x00\x00\x00"
    )


def _tiny_wav() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 800)
    return buffer.getvalue()


class IntakeCompletionPlanTests(unittest.TestCase):
    def test_epub_spine_extracts_ordered_chapters_and_visual_references(self) -> None:
        raw = _zip_bytes(
            {
                "META-INF/container.xml": """<?xml version="1.0"?><container><rootfiles><rootfile full-path="OPS/package.opf"/></rootfiles></container>""",
                "OPS/package.opf": """<package xmlns="http://www.idpf.org/2007/opf"><manifest><item id="c1" href="chapter1.xhtml" media-type="application/xhtml+xml"/><item id="c2" href="chapter2.xhtml" media-type="application/xhtml+xml"/><item id="fig" href="images/fig.png" media-type="image/png"/></manifest><spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>""",
                "OPS/chapter1.xhtml": "<html><body><h1>Alpha</h1><p>First chapter.</p><img src=\"images/fig.png\" alt=\"Alpha figure\"/></body></html>",
                "OPS/chapter2.xhtml": "<html><body><p>Second chapter.</p></body></html>",
                "OPS/images/fig.png": _tiny_png(),
            }
        )

        doc = prepare_bytes(raw, source_name="book.epub")

        self.assertEqual(doc.converter, "epub-spine")
        self.assertIn("[EPUB_SPINE_ITEM: 1 OPS/chapter1.xhtml]", doc.prepared_text)
        self.assertLess(doc.prepared_text.index("First chapter"), doc.prepared_text.index("Second chapter"))
        self.assertEqual(doc.metadata["spine_count"], 2)
        self.assertEqual(doc.metadata["visual_refs"][0]["source_path"], "OPS/images/fig.png")

    def test_pptx_extracts_slide_text_tables_notes_and_image_placeholders(self) -> None:
        raw = _zip_bytes(
            {
                "ppt/slides/slide1.xml": """<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Launch Plan</a:t></a:r></a:p><a:p><a:r><a:t>First bullet</a:t></a:r></a:p></p:txBody></p:sp><p:pic><p:nvPicPr><p:cNvPr id="2" name="Picture 1"/></p:nvPicPr></p:pic></p:spTree></p:cSld></p:sld>""",
                "ppt/notesSlides/notesSlide1.xml": """<p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Speaker note</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:notes>""",
            }
        )

        doc = prepare_bytes(raw, source_name="deck.pptx")

        self.assertEqual(doc.converter, "pptx-text")
        self.assertIn("[SLIDE: 1]", doc.prepared_text)
        self.assertIn("Launch Plan", doc.prepared_text)
        self.assertIn("[NOTES: 1]", doc.prepared_text)
        self.assertEqual(doc.metadata["slides"], 1)
        self.assertEqual(doc.metadata["embedded_media"][0]["source_path"], "ppt/slides/slide1.xml#Picture 1")

    def test_eml_extracts_body_and_routes_attachments_to_child_records(self) -> None:
        boundary = "BOUNDARY"
        raw = (
            "Subject: Intake Evidence\r\n"
            "From: a@example.com\r\n"
            "To: b@example.com\r\n"
            "Date: Sat, 09 May 2026 12:00:00 -0400\r\n"
            "MIME-Version: 1.0\r\n"
            f"Content-Type: multipart/mixed; boundary=\"{boundary}\"\r\n\r\n"
            f"--{boundary}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nBody evidence.\r\n"
            f"--{boundary}\r\nContent-Type: text/plain; name=\"note.txt\"\r\nContent-Disposition: attachment; filename=\"note.txt\"\r\n\r\nAttached text.\r\n"
            f"--{boundary}\r\nContent-Type: image/png; name=\"fig.png\"\r\nContent-Disposition: attachment; filename=\"fig.png\"\r\nContent-Transfer-Encoding: base64\r\n\r\n"
            "iVBORw0KGgoAAAANSUhEUgAAAAMAAAACCAIAAAD91JpzAAAAAElFTkSuQmCC\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        doc = prepare_bytes(raw, source_name="message.eml")

        self.assertEqual(doc.converter, "email-message")
        self.assertIn("Subject: Intake Evidence", doc.prepared_text)
        self.assertIn("Body evidence.", doc.prepared_text)
        self.assertEqual(doc.metadata["attachments"][0]["filename"], "note.txt")
        self.assertEqual(doc.metadata["attachments"][1]["visual_manifest"]["source"]["width"], 3)

    def test_html_sidecars_capture_attributes_without_mixing_them_into_visible_text(self) -> None:
        raw = b'<html><body><a href="https://example.test">Visible Link</a><img src="fig.png" alt="Figure caption" title="Figure title"><label aria-label="Search Box">Search</label></body></html>'

        doc = prepare_bytes(raw, source_name="page.html")

        self.assertEqual(doc.converter, "html-text")
        self.assertIn("Visible Link", doc.prepared_text)
        self.assertNotIn("https://example.test", doc.prepared_text)
        self.assertEqual(doc.metadata["attribute_sidecars"][0]["attribute"], "href")
        self.assertEqual(doc.metadata["visual_refs"][0]["alt_text"], "Figure caption")
        self.assertEqual(doc.metadata["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})

    def test_zip_intake_routes_supported_children_and_blocks_executable_members(self) -> None:
        raw = _zip_bytes({"docs/readme.txt": "Archive text.", "image.png": _tiny_png(), "run.exe": b"MZ"})

        doc = prepare_bytes(raw, source_name="bundle.zip")

        self.assertEqual(doc.converter, "archive-zip")
        self.assertIn("[ARCHIVE_CHILD: docs/readme.txt]", doc.prepared_text)
        self.assertIn("Archive text.", doc.prepared_text)
        self.assertEqual(doc.metadata["children"][1]["converter"], "image-metadata")
        self.assertEqual(doc.metadata["blocked_children"][0]["path"], "run.exe")

    def test_media_manifests_are_source_local_evidence_only(self) -> None:
        video = prepare_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64, source_name="clip.mp4")
        audio = prepare_bytes(_tiny_wav(), source_name="sound.wav")

        self.assertEqual(video.converter, "video-evidence-manifest")
        self.assertEqual(video.metadata["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})
        self.assertEqual(audio.converter, "audio-evidence-manifest")
        self.assertEqual(audio.metadata["sample_rate"], 8000)
        self.assertIn("[AUDIO_END]", audio.prepared_text)

    def test_ocr_contract_and_basic_visual_regions_are_write_locked(self) -> None:
        image = prepare_bytes(_tiny_png(9, 5), source_name="scan.png")
        manifest = image.metadata["visual_manifest"]
        region_map = generate_basic_visual_regions(manifest, captions=[{"text": "Figure caption", "line_start": 4, "line_end": 4}])
        capability = create_ocr_backend_capability("mock_ocr", "local")
        layer = {
            "schema_version": "anchorworks_ocr_candidate_layer@1",
            "backend": capability,
            "visual_record_id": manifest["source"]["visual_record_id"],
            "candidates": [
                {
                    "candidate_id": "ocr_1",
                    "region_id": region_map["regions"][0]["region_id"],
                    "text": "Figure caption",
                    "confidence": 0.95,
                    "coordinate_space": "native_pixels",
                }
            ],
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        }

        validate_ocr_candidate_layer(layer)

        self.assertEqual(region_map["regions"][0]["kind_candidate"], "full_image")
        self.assertEqual(region_map["regions"][1]["kind_candidate"], "caption")
        self.assertFalse(layer["writes_allowed"]["counts"])

    def test_audit_and_readiness_reports_summarize_without_mutating_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "sources"
            state_dir = root / "State"
            source_dir.mkdir()
            (source_dir / "a.txt").write_text("alpha beta", encoding="utf-8")
            (source_dir / "b.html").write_text("<p>gamma</p>", encoding="utf-8")
            (state_dir / "observed_maps").mkdir(parents=True)
            (state_dir / "flat_documents" / "symbolic").mkdir(parents=True)
            (state_dir / "ingest_staging" / "cleanup_ledger").mkdir(parents=True)
            (state_dir / "ingest_staging" / "cleanup_ledger" / "cleanup_ledger.json").write_text('{"entries":[]}', encoding="utf-8")

            audit = audit_source_directory(source_dir)
            readiness = rebuild_readiness_report(source_dir=source_dir, state_dir=state_dir)

            self.assertEqual(audit["files_seen"], 2)
            self.assertEqual(audit["by_converter"]["plain-text"], 1)
            self.assertEqual(audit["by_converter"]["html-text"], 1)
            self.assertTrue(readiness["cleanup_ledger"]["exists"])
            self.assertEqual(readiness["raw_sources"]["file_count"], 2)

    def test_audit_and_readiness_routes_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "sources"
            source_dir.mkdir()
            (source_dir / "a.txt").write_text("alpha beta", encoding="utf-8")
            app = create_app(root / "Lexical Data")
            paths = {getattr(route, "path", ""): route.endpoint for route in app.routes if hasattr(route, "endpoint")}

            audit = paths["/api/intake/audit"](IntakeAuditBody(source_dir=str(source_dir)))
            readiness = paths["/api/intake/rebuild-readiness"](
                RebuildReadinessBody(source_dir=str(source_dir), state_dir=str(root / "Lexical Data" / "State"))
            )

            self.assertEqual(audit["files_seen"], 1)
            self.assertEqual(readiness["manual_map_move"], "manual_only")


if __name__ == "__main__":
    unittest.main()
