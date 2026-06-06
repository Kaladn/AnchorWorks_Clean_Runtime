from __future__ import annotations

import json
import struct

import pytest

from AnchorWorks.symbol_count_native import (
    build_native_symbol_counts,
    intake_text_to_awss,
    native_executable_path,
)


def _read_awss(path):
    raw = path.read_bytes()
    assert len(raw) % 24 == 0
    rows = []
    for index in range(0, len(raw), 24):
        root, neighbor, offset, lane, flags, root_lane, _reserved, count = struct.unpack(
            "<5s5sbBBBHQ",
            raw[index : index + 24],
        )
        rows.append({
            "root": f"0x{int.from_bytes(root, 'big'):010X}",
            "neighbor": f"0x{int.from_bytes(neighbor, 'big'):010X}",
            "offset": offset,
            "lane": lane,
            "flags": flags,
            "root_lane": root_lane,
            "count": count,
        })
    return rows


def test_native_intake_text_writes_concrete_awss_and_missing_sidecar(tmp_path):
    source = tmp_path / "prepared.txt"
    source.write_text("force blorxium\n\nforce mystery blorxium", encoding="utf-8")
    authority = tmp_path / "authority.json"
    authority.write_text(
        json.dumps({
            "schema_version": "anchorworks_symbol_authority_snapshot@1",
            "anchors": [
                {"anchor": "force", "symbol": "0x0000000001", "authority": "canonical"},
                {"anchor": "blorxium", "symbol": "0xE000000001", "authority": "user_lexicon"},
            ],
        }),
        encoding="utf-8",
    )
    output = tmp_path / "out.awss"
    manifest = tmp_path / "manifest.json"
    missing = tmp_path / "missing.json"

    exe = native_executable_path()
    if not exe.exists():
        exe = build_native_symbol_counts()

    import subprocess

    result = subprocess.run(
        [
            str(exe),
            "intake-text",
            "--input",
            str(source),
            "--authority",
            str(authority),
            "--output",
            str(output),
            "--manifest",
            str(manifest),
            "--missing",
            str(missing),
            "--window-radius",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout)["ok"] is True
    rows = _read_awss(output)
    assert rows == [
        {
            "root": "0x0000000001",
            "neighbor": "0xE000000001",
            "offset": 1,
            "lane": 5,
            "flags": 0,
            "root_lane": 0,
            "count": 1,
        },
        {
            "root": "0xE000000001",
            "neighbor": "0x0000000001",
            "offset": -1,
            "lane": 0,
            "flags": 0,
            "root_lane": 5,
            "count": 1,
        },
    ]
    assert json.loads(missing.read_text(encoding="utf-8")) == {
        "schema_version": "anchorworks_native_intake_missing@1",
        "missing": [{"anchor": "mystery", "observations": 1}],
    }
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["record_count"] == 2
    assert manifest_payload["missing_anchor_count"] == 1
    assert manifest_payload["raw_text_in_count_spine"] is False


def test_python_wrapper_exposes_native_intake_receipt(tmp_path):
    source = tmp_path / "prepared.txt"
    source.write_text("force blorxium", encoding="utf-8")
    authority = tmp_path / "authority.json"
    authority.write_text(
        json.dumps({
            "anchors": [
                {"anchor": "force", "symbol": "0x0000000001", "authority": "canonical"},
                {"anchor": "blorxium", "symbol": "0xE000000001", "authority": "user_lexicon"},
            ],
        }),
        encoding="utf-8",
    )
    output = tmp_path / "out.awss"
    manifest = tmp_path / "manifest.json"
    missing = tmp_path / "missing.json"
    exe = native_executable_path()
    if not exe.exists():
        pytest.skip("native symbol count executable is not built")

    receipt = intake_text_to_awss(
        source,
        authority,
        output,
        manifest_path=manifest,
        missing_path=missing,
        window_radius=1,
        executable=exe,
    )

    assert receipt["ok"] is True
    assert receipt["command"] == "intake-text"
    assert receipt["record_count"] == 2
    assert output.exists()
