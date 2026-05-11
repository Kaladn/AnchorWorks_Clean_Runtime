from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from AnchorWorks.document_film import (
    build_document_film_from_images,
    extract_pdf_document_film,
)
from AnchorWorks.symbolic_map_binary import read_symbolic_map_visual_sidecar
from AnchorWorks.store import LexiconStore

from test_visual_manifest import _png_bytes
from test_mapping import _write_json


class DocumentFilmTests(unittest.TestCase):
    def test_document_film_builder_preserves_order_and_reports_duplicate_hashes(self) -> None:
        frames = [
            {"page_number": 1, "image_bytes": _png_bytes(4, 3), "source_name": "page-1.png"},
            {"page_number": 2, "image_bytes": _png_bytes(4, 3), "source_name": "page-2.png"},
        ]

        packet = build_document_film_from_images(
            source_document_id="doc_test",
            source_path="doc.pdf",
            source_hash="abc123",
            frames=frames,
            frame_rate=1.0,
            duplicate_policy="repeated_frames_expected",
        )

        self.assertEqual(packet["schema_version"], "anchorworks_document_film@1")
        self.assertEqual(packet["frame_count"], 2)
        self.assertEqual(packet["frames"][0]["page_number"], 1)
        self.assertEqual(packet["frames"][0]["frame_index"], 0)
        self.assertEqual(packet["frames"][0]["frame_timestamp_ms"], 0)
        self.assertEqual(packet["frames"][1]["page_number"], 2)
        self.assertEqual(packet["frames"][1]["frame_index"], 1)
        self.assertEqual(packet["frames"][1]["frame_timestamp_ms"], 1000)
        self.assertTrue(packet["duplicate_frame_hashes"])
        self.assertEqual(packet["duplicate_policy"], "repeated_frames_expected")
        self.assertEqual(packet["frames"][0]["visual_region_map"]["regions"], [])
        self.assertEqual(packet["frames"][0]["visual_recognition_layer"]["candidates"], [])
        self.assertEqual(packet["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})

    def test_pdf_film_adapter_reports_pages_when_pdf_has_no_extractable_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "empty.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")

            with self.assertRaises(ValueError):
                extract_pdf_document_film(pdf_path)

    def test_pdf_mapping_writes_document_film_visual_refs_to_awsv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Lexical Data"
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                _write_json(root / "Canonical" / f"canonical_{letter}.json", [])
            _write_json(root / "Canonical" / "canonical_A.json", [{"word": "alpha", "status": "ASSIGNED"}])
            _write_json(root / "Spare_Slots" / "spare_slots.json", [])

            source_path = Path(temp_dir) / "sample.pdf"
            source_path.write_bytes(_minimal_pdf_with_png_image())
            store = LexiconStore(root)

            result = store.build_observed_map(source_path)
            visual_rows = read_symbolic_map_visual_sidecar(result["symbolic_visual_path"])

            self.assertGreaterEqual(result["symbolic_visual_count"], 1)
            self.assertEqual(visual_rows[0]["kind"], "pdf_page_frame")
            self.assertEqual(visual_rows[0]["page_number"], 1)
            self.assertEqual(visual_rows[0]["frame_index"], 0)
            self.assertEqual(visual_rows[0]["frame_timestamp_ms"], 0)
            self.assertEqual(visual_rows[0]["recognition_status"], "not_run")
            self.assertEqual(visual_rows[0]["writes_allowed"], {"maps": False, "counts": False, "lifetime": False, "lexicon": False})


def _minimal_pdf_with_png_image() -> bytes:
    image_data = bytes([255, 0, 0] * 12)
    content = b"q 4 0 0 3 0 0 cm /Im1 Do Q\nBT /F1 12 Tf 10 10 Td (alpha) Tj ET\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] "
        b"/Resources << /XObject << /Im1 4 0 R >> /Font << /F1 6 0 R >> >> /Contents 5 0 R >>",
        (
            b"<< /Type /XObject /Subtype /Image /Width 4 /Height 3 /ColorSpace /DeviceRGB "
            b"/BitsPerComponent 8 /Length " + str(len(image_data)).encode("ascii") + b" >>\n"
            b"stream\n" + image_data + b"\nendstream"
        ),
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_number, pdf_object in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_number} 0 obj\n".encode("ascii"))
        output.extend(pdf_object)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


if __name__ == "__main__":
    unittest.main()
