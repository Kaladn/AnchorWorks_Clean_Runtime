from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]
NATIVE_ROOT = PACKAGE_ROOT / "native" / "symbol_genome"
DEFAULT_BUILD_ROOT = REPO_ROOT / "build" / "native_symbol_genome"
VS_CMAKE = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
)


def cmake_path() -> Path:
    if VS_CMAKE.exists():
        return VS_CMAKE
    discovered = shutil.which("cmake")
    if discovered:
        return Path(discovered)
    raise RuntimeError("CMake is required to build the native symbol genome allocator")


def native_symbol_genome_executable_path(build_root: str | Path | None = None, *, config: str = "Release") -> Path:
    root = Path(build_root or DEFAULT_BUILD_ROOT)
    return root / config / "anchorworks-symbol-genome.exe"


def build_native_symbol_genome(build_root: str | Path | None = None, *, config: str = "Release") -> Path:
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
    exe = native_symbol_genome_executable_path(root, config=config)
    if not exe.exists():
        raise RuntimeError(f"native symbol genome executable was not built: {exe}")
    return exe


def allocate_symbol_genome_batch(
    input_path: str | Path,
    output_path: str | Path,
    *,
    start_index: int = 0,
    category: str = "core",
    priority: int = 4,
    executable: str | Path | None = None,
) -> dict[str, Any]:
    exe = Path(executable) if executable else native_symbol_genome_executable_path()
    if not exe.exists():
        exe = build_native_symbol_genome()
    result = subprocess.run(
        [
            str(exe),
            "allocate",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--start-index",
            str(int(start_index)),
            "--category",
            category,
            "--priority",
            str(int(priority)),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)
