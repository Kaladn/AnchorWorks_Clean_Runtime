from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CANONICAL_LANE = 0
MATH_COMPANION_LANE = 1
STRUCTURAL_COMPANION_LANE = 2
SOURCE_LOCAL_TEMP_LANE = 4
USER_LEXICON_LANE = 5

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]
NATIVE_ROOT = PACKAGE_ROOT / "native" / "symbol_counts"
DEFAULT_BUILD_ROOT = REPO_ROOT / "build" / "native_symbol_counts"
VS_CMAKE = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
)
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


def score_binary_count_stream(
    input_path: str | Path,
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
        USER_LEXICON_LANE,
    ]
    result = subprocess.run(
        [
            str(exe),
            "score-stream",
            "--input",
            str(input_path),
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


def write_authority_snapshot(
    authority_by_anchor: dict[str, tuple[str, str]],
    output_path: str | Path,
) -> dict[str, Any]:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    anchors = [
        {"anchor": anchor, "symbol": symbol, "authority": authority}
        for anchor, (symbol, authority) in sorted(authority_by_anchor.items())
        if anchor and symbol
    ]
    payload = {
        "schema_version": "anchorworks_symbol_authority_snapshot@1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "anchor_count": len(anchors),
        "anchors": anchors,
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return {"ok": True, "authority_path": str(out), "anchor_count": len(anchors)}


def native_text_intake_to_counts(
    *,
    input_path: str | Path,
    authority_path: str | Path,
    output_path: str | Path,
    manifest_path: str | Path,
    missing_path: str | Path,
    source_id: str,
    window_radius: int = 6,
    source_local_missing: bool = False,
    aw_md_copy_path: str | Path | None = None,
    executable: str | Path | None = None,
) -> dict[str, Any]:
    exe = Path(executable) if executable else native_executable_path()
    if not exe.exists():
        exe = build_native_symbol_counts()
    command = [
        str(exe),
        "intake-text",
        "--input",
        str(input_path),
        "--authority",
        str(authority_path),
        "--manifest",
        str(manifest_path),
        "--missing",
        str(missing_path),
        "--source-id",
        str(source_id),
        "--window-radius",
        str(int(window_radius)),
        "--output",
        str(output_path),
    ]
    if aw_md_copy_path:
        command.extend(["--aw-md-copy", str(aw_md_copy_path)])
    if source_local_missing:
        command.append("--source-local-missing")
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def native_directory_intake_to_counts(
    *,
    input_dir: str | Path,
    authority_path: str | Path,
    output_path: str | Path,
    manifest_path: str | Path,
    missing_path: str | Path,
    source_id: str,
    window_radius: int = 6,
    source_local_missing: bool = False,
    executable: str | Path | None = None,
) -> dict[str, Any]:
    exe = Path(executable) if executable else native_executable_path()
    if not exe.exists():
        exe = build_native_symbol_counts()
    command = [
        str(exe),
        "intake-dir",
        "--input-dir",
        str(input_dir),
        "--authority",
        str(authority_path),
        "--manifest",
        str(manifest_path),
        "--missing",
        str(missing_path),
        "--source-id",
        str(source_id),
        "--window-radius",
        str(int(window_radius)),
        "--output",
        str(output_path),
    ]
    if source_local_missing:
        command.append("--source-local-missing")
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)
