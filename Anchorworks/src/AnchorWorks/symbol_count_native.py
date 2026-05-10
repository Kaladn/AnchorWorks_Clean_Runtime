from __future__ import annotations

import json
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any

from .symbol_count_cells import (
    CANONICAL_LANE,
    MATH_COMPANION_LANE,
    SOURCE_LOCAL_TEMP_LANE,
    STRUCTURAL_COMPANION_LANE,
    symbol_to_bytes,
)

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]
NATIVE_ROOT = PACKAGE_ROOT / "native" / "symbol_counts"
DEFAULT_BUILD_ROOT = REPO_ROOT / "build" / "native_symbol_counts"
VS_CMAKE = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
)
AWSS_RECORD_SIZE = 24


def cmake_path() -> Path:
    if VS_CMAKE.exists():
        return VS_CMAKE
    discovered = shutil.which("cmake")
    if discovered:
        return Path(discovered)
    raise RuntimeError("CMake is required to build the native symbol count spine")


def native_executable_path(build_root: Path | None = None, *, config: str = "Release") -> Path:
    root = Path(build_root or DEFAULT_BUILD_ROOT)
    return root / config / "anchorworks-symbol-counts.exe"


def build_native_symbol_counts(build_root: Path | None = None, *, config: str = "Release") -> Path:
    root = Path(build_root or DEFAULT_BUILD_ROOT)
    cmake = cmake_path()
    subprocess.run(
        [
            str(cmake),
            "-S",
            str(NATIVE_ROOT),
            "-B",
            str(root),
            "-G",
            "Visual Studio 18 2026",
            "-A",
            "x64",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [str(cmake), "--build", str(root), "--config", config],
        check=True,
        capture_output=True,
        text=True,
    )
    exe = native_executable_path(root, config=config)
    if not exe.exists():
        raise RuntimeError(f"native symbol count executable was not built: {exe}")
    return exe


def merge_symbol_stream(
    input_path: str | Path,
    output_root: str | Path,
    *,
    generation: int = 0,
    executable: str | Path | None = None,
) -> dict[str, Any]:
    exe = Path(executable) if executable else native_executable_path()
    if not exe.exists():
        exe = build_native_symbol_counts()
    result = subprocess.run(
        [
            str(exe),
            "merge-stream",
            "--input",
            str(input_path),
            "--output",
            str(output_root),
            "--generation",
            str(generation),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def verify_binary_counts(root: str | Path, *, executable: str | Path | None = None) -> dict[str, Any]:
    exe = Path(executable) if executable else native_executable_path()
    if not exe.exists():
        exe = build_native_symbol_counts()
    result = subprocess.run(
        [str(exe), "verify", "--root", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def inspect_cell(path: str | Path, *, executable: str | Path | None = None) -> dict[str, Any]:
    exe = Path(executable) if executable else native_executable_path()
    if not exe.exists():
        exe = build_native_symbol_counts()
    result = subprocess.run(
        [str(exe), "inspect", "--cell", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def score_binary_counts(
    root: str | Path,
    *,
    context_symbols: list[str],
    top_k: int = 32,
    allowed_lanes: list[int] | None = None,
    executable: str | Path | None = None,
) -> dict[str, Any]:
    exe = Path(executable) if executable else native_executable_path()
    if not exe.exists():
        exe = build_native_symbol_counts()
    lane_values = allowed_lanes if allowed_lanes is not None else [
        CANONICAL_LANE,
        MATH_COMPANION_LANE,
        STRUCTURAL_COMPANION_LANE,
        SOURCE_LOCAL_TEMP_LANE,
    ]
    result = subprocess.run(
        [
            str(exe),
            "score",
            "--root",
            str(root),
            "--context",
            ",".join(context_symbols),
            "--top-k",
            str(top_k),
            "--allowed-lanes",
            ",".join(str(int(lane)) for lane in lane_values),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def write_awss_from_symbol_count_artifacts(
    artifact_paths: list[str | Path],
    output_path: str | Path,
) -> dict[str, Any]:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    record_count = 0
    observation_count = 0
    with out.open("wb") as handle:
        for artifact_path in artifact_paths:
            payload = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
            authority_by_symbol = _authority_by_symbol(payload)
            for row in payload.get("symbol_relation_counts") or []:
                root_symbol = str(row.get("symbol_anchor") or "").strip()
                neighbor_symbol = str(row.get("neighbor_symbol_anchor") or "").strip()
                if not root_symbol or not neighbor_symbol:
                    continue
                observations = int(row.get("observations", 0) or 0)
                if observations <= 0:
                    continue
                lane = _lane_for_authority(authority_by_symbol.get(neighbor_symbol, "source_local"))
                root_lane = _lane_for_authority(authority_by_symbol.get(root_symbol, "source_local"))
                handle.write(_pack_awss_record(
                    root_symbol=root_symbol,
                    neighbor_symbol=neighbor_symbol,
                    offset=_parse_offset(row.get("offset")),
                    lane=lane,
                    flags=0,
                    root_lane=root_lane,
                    count=observations,
                ))
                record_count += 1
                observation_count += observations
    return {
        "ok": True,
        "stream_path": str(out),
        "record_count": record_count,
        "observation_count": observation_count,
        "record_size": AWSS_RECORD_SIZE,
    }


def _authority_by_symbol(payload: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in payload.get("symbol_authority") or []:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").strip()
        authority = str(row.get("authority") or "").strip()
        if symbol:
            out[symbol] = authority
    return out


def _lane_for_authority(authority: str) -> int:
    normalized = authority.lower()
    if normalized == "canonical":
        return CANONICAL_LANE
    if normalized == "math_companion":
        return MATH_COMPANION_LANE
    if normalized == "structural_companion":
        return STRUCTURAL_COMPANION_LANE
    return SOURCE_LOCAL_TEMP_LANE


def _parse_offset(value: Any) -> int:
    text = str(value or "").strip()
    if text.startswith("+"):
        text = text[1:]
    offset = int(text)
    if offset == 0 or offset < -128 or offset > 127:
        raise ValueError(f"invalid AWSS offset: {value}")
    return offset


def _pack_awss_record(
    *,
    root_symbol: str,
    neighbor_symbol: str,
    offset: int,
    lane: int,
    flags: int,
    root_lane: int,
    count: int,
) -> bytes:
    return struct.pack(
        "<5s5sbBBBHQ",
        symbol_to_bytes(root_symbol),
        symbol_to_bytes(neighbor_symbol),
        offset,
        lane,
        flags,
        root_lane,
        0,
        count,
    )
