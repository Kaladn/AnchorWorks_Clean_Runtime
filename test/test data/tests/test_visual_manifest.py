from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from AnchorWorks.document_prep import prepare_bytes
from AnchorWorks.store import LexiconStore
from AnchorWorks.anchor_forge_visual import probe_image_bytes
from AnchorWorks.visual_manifest import (
    AUTHORITY_SOURCE_LOCAL_VISUAL,
    VISUAL_CONTRACT_VERSION,
    compucog_yolo_a_capability,
    manifest_from_image_bytes,
)
from AnchorWorks.visual_dual_path_verification import (
    DUAL_PATH_VERIFICATION_CONTRACT_VERSION,
    SourceTextSpan,
    build_dual_path_verification_report,
    validate_dual_path_verification_report,
)
from AnchorWorks.visual_recognition_layer import (
    RECOGNITION_LAYER_CONTRACT_VERSION,
    create_empty_recognition_layer,
    validate_recognition_layer,
)
from AnchorWorks.visual_region_map import (
    REGION_MAP_CONTRACT_VERSION,
    create_empty_region_map,
    validate_region_map,
)


def _png_bytes(width: int = 6, height: int = 4) -> bytes:
    ihdr = (
        b"\x00\x00\x00\x0d"
        b"IHDR"
        + struct.pack(">II", width, height)
        + bytes([8, 2, 0, 0, 0])
        + b"\x00\x00\x00\x00"
    )
    return b"\x89PNG\r\n\x1a\n" + ihdr + b"\x00\x00\x00\x00IEND\x00\x00\x00\x00"


def _gif_bytes(width: int = 11, height: int = 9) -> bytes:
    return b"GIF89a" + struct.pack("<HH", width, height) + b"\x00\x00\x00"


def _bmp_bytes(width: int = 13, height: int = 10) -> bytes:
    dib = (
        struct.pack("<IiiHH", 40, width, height, 1, 24)
        + b"\x00" * 20
    )
    file_size = 14 + len(dib)
    return b"BM" + struct.pack("<IHHI", file_size, 0, 0, 54) + dib


class VisualManifestTests(unittest.TestCase):
    def test_anchorforge_native_probe_reads_common_headers_without_pillow(self) -> None:
        png = probe_image_bytes(_png_bytes(6, 4), "figure.png")
        gif = probe_image_bytes(_gif_bytes(11, 9), "motion.gif")
        bmp = probe_image_bytes(_bmp_bytes(13, 10), "scan.bmp")

        self.assertEqual((png.file_format, png.width, png.height, png.color_mode), ("PNG", 6, 4, "RGB"))
        self.assertEqual((gif.file_format, gif.width, gif.height, gif.color_mode), ("GIF", 11, 9, "P"))
        self.assertEqual((bmp.file_format, bmp.width, bmp.height, bmp.color_mode), ("BMP", 13, 10, "RGB"))

    def test_image_manifest_preserves_native_geometry_and_blocks_writes(self) -> None:
        raw = _png_bytes(6, 4)
        manifest = manifest_from_image_bytes(raw, "figure.png").to_dict()

        self.assertEqual(manifest["contract_version"], VISUAL_CONTRACT_VERSION)
        self.assertEqual(manifest["authority"], AUTHORITY_SOURCE_LOCAL_VISUAL)
        self.assertEqual(manifest["approval_status"], "preview_only")
        self.assertEqual(manifest["source"]["media_type"], "image")
        self.assertEqual(manifest["source"]["width"], 6)
        self.assertEqual(manifest["source"]["height"], 4)
        self.assertEqual(manifest["source"]["aspect_ratio"], "3:2")
        self.assertEqual(
            manifest["writes_allowed"],
            {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        )

    def test_image_manifest_preserves_document_film_frame_metadata(self) -> None:
        raw = _png_bytes(6, 4)
        manifest = manifest_from_image_bytes(
            raw,
            "page-0003.png",
            frame_index=2,
            frame_timestamp_ms=2000,
            page_index=2,
            page_number=3,
            source_document_id="doc_abc",
        ).to_dict()

        self.assertEqual(manifest["source"]["frame_index"], 2)
        self.assertEqual(manifest["source"]["frame_timestamp_ms"], 2000)
        self.assertEqual(manifest["source"]["page_index"], 2)
        self.assertEqual(manifest["source"]["page_number"], 3)
        self.assertEqual(manifest["source"]["source_document_id"], "doc_abc")

    def test_compucog_backend_declares_resize_as_derived_only(self) -> None:
        backend = compucog_yolo_a_capability().to_dict()

        self.assertEqual(backend["backend_id"], "compucog_vision_yolo_a")
        self.assertEqual(backend["coordinate_space"], "native_pixels")
        self.assertFalse(backend["distorts_source"])
        self.assertTrue(backend["may_resize_for_model"])
        self.assertTrue(backend["resize_is_derived"])
        self.assertEqual(
            backend["writes_allowed"],
            {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        )

    def test_document_prep_attaches_visual_manifest_for_images(self) -> None:
        raw = _png_bytes(8, 5)
        prepared = prepare_bytes(raw, source_name="diagram.png")

        self.assertEqual(prepared.converter, "image-metadata")
        self.assertIn("[TYPE: image]", prepared.prepared_text)
        self.assertIn("Visual_Record_ID:", prepared.prepared_text)
        self.assertIn("Authority: source_local_visual_evidence", prepared.prepared_text)
        self.assertIn("Writes_Allowed: maps=false counts=false lifetime=false lexicon=false", prepared.prepared_text)
        self.assertEqual(prepared.metadata["visual_manifest"]["source"]["width"], 8)
        self.assertEqual(prepared.metadata["visual_manifest"]["source"]["height"], 5)
        self.assertEqual(
            prepared.metadata["visual_manifest"]["writes_allowed"],
            {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        )

    def test_store_blocks_visual_preview_from_map_count_route(self) -> None:
        raw = _png_bytes()
        prepared = prepare_bytes(raw, source_name="figure.png")

        with tempfile.TemporaryDirectory() as temp_dir:
            store = LexiconStore(Path(temp_dir))
            preview = store.preview_document_intake(
                source_name=prepared.source_name,
                content=prepared.prepared_text,
                file_size=prepared.original_size,
                file_type=prepared.file_type,
            )

            self.assertTrue(preview["visual_preview_only"])
            self.assertEqual(preview["total_anchor_observations"], 0)
            self.assertEqual(preview["missing_anchors"], [])
            with self.assertRaisesRegex(ValueError, "visual intake preview"):
                store.build_intake_mapping(source_name=prepared.source_name, content=prepared.prepared_text)

    def test_store_prepare_persists_visual_intake_packet(self) -> None:
        raw = _png_bytes(17, 9)

        with tempfile.TemporaryDirectory() as temp_dir:
            store = LexiconStore(Path(temp_dir))
            prepared = store.prepare_intake_document(raw, source_name="plate.png", file_type="image/png")

            visual_intake = prepared["metadata"]["visual_intake"]
            packet_path = Path(visual_intake["packet_path"])
            manifest_path = Path(visual_intake["manifest_path"])
            region_map_path = Path(visual_intake["region_map_path"])
            recognition_layer_path = Path(visual_intake["recognition_layer_path"])

            self.assertTrue(packet_path.exists())
            self.assertTrue(manifest_path.exists())
            self.assertTrue(region_map_path.exists())
            self.assertTrue(recognition_layer_path.exists())

            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            self.assertEqual(packet["schema_version"], "anchorworks_visual_intake_packet@1")
            self.assertEqual(packet["visual_record_id"], prepared["metadata"]["visual_manifest"]["source"]["visual_record_id"])
            self.assertEqual(packet["visual_manifest"]["source"]["width"], 17)
            self.assertEqual(packet["visual_manifest"]["source"]["height"], 9)
            self.assertEqual(packet["visual_region_map"]["regions"], [])
            self.assertEqual(packet["visual_recognition_layer"]["candidates"], [])
            self.assertEqual(
                packet["writes_allowed"],
                {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
            )

            inventory = store.visual_intake_files()
            self.assertEqual(inventory["packet_count"], 1)
            self.assertEqual(inventory["packets"][0]["visual_record_id"], packet["visual_record_id"])

    def test_region_map_schema_creates_empty_native_coordinate_record(self) -> None:
        manifest = manifest_from_image_bytes(_png_bytes(21, 13), "figure.png")

        region_map = create_empty_region_map(manifest).to_dict()
        validate_region_map(region_map)

        self.assertEqual(region_map["contract_version"], REGION_MAP_CONTRACT_VERSION)
        self.assertEqual(region_map["visual_record_id"], manifest.source.visual_record_id)
        self.assertEqual(region_map["source_hash"], manifest.source.sha256)
        self.assertEqual(region_map["coordinate_space"], "native_pixels")
        self.assertEqual(region_map["regions"], [])
        self.assertEqual(region_map["relations"], [])
        self.assertEqual(
            region_map["writes_allowed"],
            {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        )

    def test_recognition_layer_schema_points_to_region_map_without_promoting_truth(self) -> None:
        manifest = manifest_from_image_bytes(_png_bytes(21, 13), "figure.png")
        region_map = create_empty_region_map(manifest)

        recognition = create_empty_recognition_layer(manifest, region_map).to_dict()
        validate_recognition_layer(recognition)

        self.assertEqual(recognition["contract_version"], RECOGNITION_LAYER_CONTRACT_VERSION)
        self.assertEqual(recognition["visual_record_id"], manifest.source.visual_record_id)
        self.assertEqual(recognition["region_map_id"], region_map.region_map_id)
        self.assertEqual(recognition["candidates"], [])
        self.assertEqual(recognition["approval_status"], "candidate")
        self.assertEqual(
            recognition["writes_allowed"],
            {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        )

    def test_document_prep_attaches_empty_region_and_recognition_records(self) -> None:
        prepared = prepare_bytes(_png_bytes(21, 13), source_name="diagram.png")

        region_map = prepared.metadata["visual_region_map"]
        recognition = prepared.metadata["visual_recognition_layer"]

        validate_region_map(region_map)
        validate_recognition_layer(recognition)
        self.assertEqual(
            prepared.metadata["visual_manifest"]["source"]["visual_record_id"],
            region_map["visual_record_id"],
        )
        self.assertEqual(region_map["region_map_id"], recognition["region_map_id"])

    def test_dual_path_verification_reports_clean_source_visual_agreement(self) -> None:
        manifest = manifest_from_image_bytes(_png_bytes(21, 13), "typed-page.png")
        region_map = create_empty_region_map(manifest).to_dict()
        recognition = create_empty_recognition_layer(manifest, create_empty_region_map(manifest)).to_dict()
        recognition["region_map_id"] = region_map["region_map_id"]
        recognition["candidates"] = [
            {
                "candidate_id": "vcand_1",
                "candidate_type": "ocr_text",
                "region_id": "r1",
                "value": {"text": "Velocity"},
                "confidence": 0.96,
                "backend_id": "test_ocr",
                "evidence_refs": ["r1"],
                "approval_status": "candidate",
            },
            {
                "candidate_id": "vcand_2",
                "candidate_type": "ocr_text",
                "region_id": "r2",
                "value": {"text": "Time"},
                "confidence": 0.93,
                "backend_id": "test_ocr",
                "evidence_refs": ["r2"],
                "approval_status": "candidate",
            },
        ]

        report = build_dual_path_verification_report(
            source_id="module_test",
            source_spans=[
                SourceTextSpan(span_id="s1", text="velocity", reading_order=0, region_id="r1"),
                SourceTextSpan(span_id="s2", text="time", reading_order=1, region_id="r2"),
            ],
            region_map=region_map,
            recognition_layer=recognition,
        ).to_dict()

        validate_dual_path_verification_report(report)
        self.assertEqual(report["contract_version"], DUAL_PATH_VERIFICATION_CONTRACT_VERSION)
        self.assertEqual(report["exact_match_count"], 2)
        self.assertEqual(report["agreement_ratio"], 1.0)
        self.assertTrue(report["reading_order_match"])
        self.assertEqual(report["issues"], [])
        self.assertEqual(len(report["bilateral_text_regions"]), 2)
        self.assertEqual(report["bilateral_text_regions"][0]["agreement"]["status"], "exact")
        self.assertEqual(
            report["writes_allowed"],
            {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        )

    def test_dual_path_verification_flags_missing_extra_and_low_confidence_text(self) -> None:
        manifest = manifest_from_image_bytes(_png_bytes(21, 13), "typed-page.png")
        region_map_obj = create_empty_region_map(manifest)
        region_map = region_map_obj.to_dict()
        recognition = create_empty_recognition_layer(manifest, region_map_obj).to_dict()
        recognition["candidates"] = [
            {
                "candidate_id": "vcand_position",
                "candidate_type": "ocr_text",
                "region_id": "r1",
                "value": {"text": "position"},
                "confidence": 0.92,
                "backend_id": "test_ocr",
                "evidence_refs": ["r1"],
                "approval_status": "candidate",
            },
            {
                "candidate_id": "vcand_noise",
                "candidate_type": "ocr_text",
                "region_id": "r_noise",
                "value": {"text": "gar8age"},
                "confidence": 0.41,
                "backend_id": "test_ocr",
                "evidence_refs": ["r_noise"],
                "approval_status": "candidate",
            },
        ]

        report = build_dual_path_verification_report(
            source_id="module_test",
            source_spans=[
                SourceTextSpan(span_id="s1", text="position", reading_order=0, region_id="r1"),
                SourceTextSpan(span_id="s2", text="time", reading_order=1, region_id="r2"),
            ],
            region_map=region_map,
            recognition_layer=recognition,
        ).to_dict()

        validate_dual_path_verification_report(report)
        issue_types = {issue["issue_type"] for issue in report["issues"]}
        self.assertIn("missing_visual_text", issue_types)
        self.assertIn("extra_visual_text", issue_types)
        self.assertIn("low_confidence_visual_text", issue_types)
        agreement_statuses = {region["agreement"]["status"] for region in report["bilateral_text_regions"]}
        self.assertIn("exact", agreement_statuses)
        self.assertIn("source_layout_only", agreement_statuses)
        self.assertIn("visual_rescue_candidate", agreement_statuses)
        self.assertEqual(report["exact_match_count"], 1)
        self.assertEqual(report["agreement_ratio"], 0.5)
        self.assertFalse(report["reading_order_match"])


if __name__ == "__main__":
    unittest.main()
