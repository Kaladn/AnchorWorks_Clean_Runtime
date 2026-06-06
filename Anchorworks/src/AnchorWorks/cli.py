from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import uvicorn

from .app import create_app, _default_data_root
from .cli_shell import run_shell
from .conversation_corpus import (
    export_conversation_flow_symbolic_sources,
    import_hf_dataset_chunked,
    import_hf_dataset_parquet_chunked,
    import_hf_dataset_sample,
)
from .store import LexiconStore
from .terminal_operator import run_operator


def main() -> None:
    parser = argparse.ArgumentParser(prog="anchorworks")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the standalone lexicon server")
    serve.add_argument("--data-root", type=Path, default=_default_data_root())
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)

    shell = sub.add_parser("shell", help="Run the local AnchorWorks CLI shell")
    shell.add_argument("--data-root", type=Path, default=_default_data_root())

    operator = sub.add_parser("operator", help="Run the AnchorWorks terminal operator console")
    operator.add_argument("--data-root", type=Path, default=_default_data_root())

    hf_dialogue = sub.add_parser("hf-dialogue-import", help="Import HF dialogue rows into conversation-flow artifacts")
    hf_dialogue.add_argument("--output-root", type=Path, required=True)
    hf_dialogue.add_argument("--dataset", default="CHATS-Lab/Verbalized-Sampling-Dialogue-Simulation")
    hf_dialogue.add_argument("--config", default="Direct")
    hf_dialogue.add_argument("--split", default="gpt_4_1")
    hf_dialogue.add_argument("--offset", type=int, default=0)
    hf_dialogue.add_argument("--length", type=int, default=100)
    hf_dialogue.add_argument("--full-json", action="store_true")

    hf_chunked = sub.add_parser("hf-conversation-import-chunked", help="Import HF conversation rows in RAM-sized chunks")
    hf_chunked.add_argument("--output-root", type=Path, required=True)
    hf_chunked.add_argument("--dataset", default="openbmb/UltraChat")
    hf_chunked.add_argument("--config", default="default")
    hf_chunked.add_argument("--split", default="train")
    hf_chunked.add_argument("--offset", type=int, default=0)
    hf_chunked.add_argument("--page-length", type=int, default=100)
    hf_chunked.add_argument("--rows-per-chunk", type=int, default=50000)
    hf_chunked.add_argument("--max-rows", type=int, default=None)
    hf_chunked.add_argument("--target-ram-gb", type=float, default=40.0)
    hf_chunked.add_argument("--full-json", action="store_true")

    hf_parquet = sub.add_parser("hf-conversation-import-parquet", help="Import HF conversation parquet shards in large RAM-sized batches")
    hf_parquet.add_argument("--output-root", type=Path, required=True)
    hf_parquet.add_argument("--dataset", default="openbmb/UltraChat")
    hf_parquet.add_argument("--config", default="default")
    hf_parquet.add_argument("--split", default="train")
    hf_parquet.add_argument("--batch-size", type=int, default=100000)
    hf_parquet.add_argument("--rows-per-chunk", type=int, default=100000)
    hf_parquet.add_argument("--max-rows", type=int, default=None)
    hf_parquet.add_argument("--target-ram-gb", type=float, default=40.0)
    hf_parquet.add_argument("--full-json", action="store_true")

    conversation_export = sub.add_parser("conversation-flow-export-sources", help="Export conversation-flow manifests as symbolic-intake text sources")
    conversation_export.add_argument("--flow-root", type=Path, required=True)
    conversation_export.add_argument("--output-root", type=Path, required=True)
    conversation_export.add_argument("--full-json", action="store_true")

    symbolic_batch = sub.add_parser("symbolic-batch-intake", help="Build maps, symbol streams, and AWSC cells for a source group")
    symbolic_batch.add_argument("--data-root", type=Path, required=True)
    symbolic_batch.add_argument("--source-dir", type=Path, required=True)
    symbolic_batch.add_argument("--pattern", default="*")
    symbolic_batch.add_argument("--map-root", type=Path, default=None)
    symbolic_batch.add_argument("--max-workers", type=int, default=None)
    symbolic_batch.add_argument("--generation", type=int, default=0)

    chunked_batch = sub.add_parser("symbolic-batch-intake-chunked", help="Build symbolic intake in RAM-governed chunks")
    chunked_batch.add_argument("--data-root", type=Path, required=True)
    chunked_batch.add_argument("--source-dir", type=Path, required=True)
    chunked_batch.add_argument("--pattern", default="*")
    chunked_batch.add_argument("--map-root", type=Path, default=None)
    chunked_batch.add_argument("--max-workers", type=int, default=None)
    chunked_batch.add_argument("--generation", type=int, default=0)
    chunked_batch.add_argument("--run-id", default=None)
    chunked_batch.add_argument("--chunk-file-limit", type=int, default=250)
    chunked_batch.add_argument("--soft-warning-gb", type=float, default=32.0)
    chunked_batch.add_argument("--emergency-flush-gb", type=float, default=36.0)
    chunked_batch.add_argument("--abort-gb", type=float, default=39.0)
    chunked_batch.add_argument("--no-chunk-binaries", action="store_true")

    openstax = sub.add_parser("ingest-openstax-chunked", help="Manage detached RAM-governed OpenStax ingest jobs")
    openstax_sub = openstax.add_subparsers(dest="action", required=True)

    openstax_start = openstax_sub.add_parser("start", help="Start a detached OpenStax chunked ingest job")
    openstax_start.add_argument("--data-root", type=Path, default=_default_data_root())
    openstax_start.add_argument("--source-dir", type=Path, default=Path(r"D:\curated data\raw_sources\openstax\extracted"))
    openstax_start.add_argument("--pattern", default="*.cnxml")
    openstax_start.add_argument("--map-root", type=Path, default=Path(r"D:\AnchorMaps"))
    openstax_start.add_argument("--max-workers", type=int, default=24)
    openstax_start.add_argument("--generation", type=int, default=0)
    openstax_start.add_argument("--run-id", default=None)
    openstax_start.add_argument("--chunk-file-limit", type=int, default=250)
    openstax_start.add_argument("--max-ram-gb", type=float, default=40.0)
    openstax_start.add_argument("--soft-warning-gb", type=float, default=32.0)
    openstax_start.add_argument("--emergency-flush-gb", type=float, default=36.0)
    openstax_start.add_argument("--no-chunk-binaries", action="store_true")

    openstax_status = openstax_sub.add_parser("status", help="Read detached OpenStax ingest status")
    openstax_status.add_argument("--data-root", type=Path, default=_default_data_root())
    openstax_status.add_argument("--run-id", required=True)

    openstax_resume = openstax_sub.add_parser("resume", help="Resume a detached OpenStax chunked ingest job")
    openstax_resume.add_argument("--data-root", type=Path, default=_default_data_root())
    openstax_resume.add_argument("--source-dir", type=Path, default=Path(r"D:\curated data\raw_sources\openstax\extracted"))
    openstax_resume.add_argument("--pattern", default="*.cnxml")
    openstax_resume.add_argument("--map-root", type=Path, default=Path(r"D:\AnchorMaps"))
    openstax_resume.add_argument("--max-workers", type=int, default=24)
    openstax_resume.add_argument("--generation", type=int, default=0)
    openstax_resume.add_argument("--run-id", required=True)
    openstax_resume.add_argument("--chunk-file-limit", type=int, default=250)
    openstax_resume.add_argument("--max-ram-gb", type=float, default=40.0)
    openstax_resume.add_argument("--soft-warning-gb", type=float, default=32.0)
    openstax_resume.add_argument("--emergency-flush-gb", type=float, default=36.0)
    openstax_resume.add_argument("--no-chunk-binaries", action="store_true")

    openstax_stop = openstax_sub.add_parser("stop", help="Request a safe stop for an OpenStax chunked ingest job")
    openstax_stop.add_argument("--data-root", type=Path, default=_default_data_root())
    openstax_stop.add_argument("--run-id", required=True)
    openstax_stop.add_argument("--kill", action="store_true", help="Also terminate the recorded process id")

    args = parser.parse_args()

    if args.command == "serve":
        app = create_app(args.data_root)
        uvicorn.run(app, host=args.host, port=args.port)
    elif args.command == "shell":
        run_shell(args.data_root)
    elif args.command == "operator":
        run_operator(args.data_root)
    elif args.command == "hf-dialogue-import":
        result = import_hf_dataset_sample(
            output_root=args.output_root,
            dataset=args.dataset,
            config=args.config,
            split=args.split,
            offset=args.offset,
            length=args.length,
        )
        if args.full_json:
            print(json.dumps(result, ensure_ascii=True))
        else:
            print(json.dumps({
                "ok": result.get("ok"),
                "schema_version": result.get("schema_version"),
                "dataset": result.get("dataset"),
                "config": result.get("config"),
                "split": result.get("split"),
                "manifest_path": result.get("manifest_path"),
                "turn_count": (result.get("manifest") or {}).get("turn_count"),
                "flow_count": (result.get("artifacts") or {}).get("flow_count"),
                "anchor_count": (result.get("artifacts") or {}).get("anchor_count"),
                "writes_allowed": result.get("writes_allowed"),
            }, ensure_ascii=True))
    elif args.command == "hf-conversation-import-chunked":
        result = import_hf_dataset_chunked(
            output_root=args.output_root,
            dataset=args.dataset,
            config=args.config,
            split=args.split,
            offset=args.offset,
            page_length=args.page_length,
            rows_per_chunk=args.rows_per_chunk,
            max_rows=args.max_rows,
            target_ram_gb=args.target_ram_gb,
        )
        if args.full_json:
            print(json.dumps(result, ensure_ascii=True))
        else:
            print(json.dumps({
                "ok": result.get("ok"),
                "schema_version": result.get("schema_version"),
                "dataset": result.get("dataset"),
                "config": result.get("config"),
                "split": result.get("split"),
                "source_row_count": result.get("source_row_count"),
                "turn_count": result.get("turn_count"),
                "chunk_count": result.get("chunk_count"),
                "page_length": result.get("page_length"),
                "rows_per_chunk": result.get("rows_per_chunk"),
                "target_ram_gb": result.get("target_ram_gb"),
                "next_offset": result.get("next_offset"),
                "total_available_rows": result.get("total_available_rows"),
                "chunks_root": result.get("chunks_root"),
                "writes_allowed": result.get("writes_allowed"),
            }, ensure_ascii=True))
    elif args.command == "hf-conversation-import-parquet":
        result = import_hf_dataset_parquet_chunked(
            output_root=args.output_root,
            dataset=args.dataset,
            config=args.config,
            split=args.split,
            batch_size=args.batch_size,
            rows_per_chunk=args.rows_per_chunk,
            max_rows=args.max_rows,
            target_ram_gb=args.target_ram_gb,
        )
        if args.full_json:
            print(json.dumps(result, ensure_ascii=True))
        else:
            print(json.dumps({
                "ok": result.get("ok"),
                "schema_version": result.get("schema_version"),
                "dataset": result.get("dataset"),
                "config": result.get("config"),
                "split": result.get("split"),
                "source_row_count": result.get("source_row_count"),
                "turn_count": result.get("turn_count"),
                "chunk_count": result.get("chunk_count"),
                "batch_size": result.get("batch_size"),
                "rows_per_chunk": result.get("rows_per_chunk"),
                "target_ram_gb": result.get("target_ram_gb"),
                "parquet_file_count": result.get("parquet_file_count"),
                "chunks_root": result.get("chunks_root"),
                "writes_allowed": result.get("writes_allowed"),
            }, ensure_ascii=True))
    elif args.command == "conversation-flow-export-sources":
        result = export_conversation_flow_symbolic_sources(args.flow_root, args.output_root)
        if args.full_json:
            print(json.dumps(result, ensure_ascii=True))
        else:
            print(json.dumps({
                "ok": result.get("ok"),
                "schema_version": result.get("schema_version"),
                "flow_root": result.get("flow_root"),
                "output_root": result.get("output_root"),
                "source_count": result.get("source_count"),
                "turn_count": result.get("turn_count"),
                "writes_allowed": result.get("writes_allowed"),
            }, ensure_ascii=True))
    elif args.command == "symbolic-batch-intake":
        source_dir = args.source_dir.expanduser().resolve()
        if not source_dir.exists():
            raise FileNotFoundError(source_dir)
        if not source_dir.is_dir():
            raise NotADirectoryError(source_dir)
        if args.map_root is not None:
            os.environ["ANCHORWORKS_MAP_ROOT"] = str(args.map_root.expanduser().resolve())
        source_paths = sorted(
            (path for path in source_dir.rglob(args.pattern) if path.is_file()),
            key=lambda path: str(path).lower(),
        )
        store = LexiconStore(args.data_root)
        result = store.build_symbolic_intake_batch(
            source_paths,
            max_workers=args.max_workers,
            generation=args.generation,
        )
        print(json.dumps(result, ensure_ascii=True))
    elif args.command == "symbolic-batch-intake-chunked":
        source_dir = args.source_dir.expanduser().resolve()
        if not source_dir.exists():
            raise FileNotFoundError(source_dir)
        if not source_dir.is_dir():
            raise NotADirectoryError(source_dir)
        if args.map_root is not None:
            os.environ["ANCHORWORKS_MAP_ROOT"] = str(args.map_root.expanduser().resolve())
        source_paths = sorted(
            (path for path in source_dir.rglob(args.pattern) if path.is_file()),
            key=lambda path: str(path).lower(),
        )
        store = LexiconStore(args.data_root)
        result = store.build_symbolic_intake_batch_chunked(
            source_paths,
            max_workers=args.max_workers,
            generation=args.generation,
            run_id=args.run_id,
            chunk_file_limit=args.chunk_file_limit,
            soft_warning_gb=args.soft_warning_gb,
            emergency_flush_gb=args.emergency_flush_gb,
            abort_gb=args.abort_gb,
            write_chunk_binaries=not args.no_chunk_binaries,
        )
        print(json.dumps(result, ensure_ascii=True))
    elif args.command == "ingest-openstax-chunked":
        if args.action == "status":
            print(json.dumps(_openstax_job_status(args.data_root, args.run_id), ensure_ascii=True))
        elif args.action == "stop":
            print(json.dumps(_openstax_job_stop(args.data_root, args.run_id, kill=args.kill), ensure_ascii=True))
        elif args.action in {"start", "resume"}:
            run_id = args.run_id or _default_openstax_run_id()
            print(json.dumps(_openstax_job_start(args, run_id, resume=args.action == "resume"), ensure_ascii=True))


def _default_openstax_run_id() -> str:
    return "openstax_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _openstax_run_root(data_root: Path, run_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(run_id)).strip("._") or "openstax"
    return Path(data_root).expanduser().resolve() / "user" / "ingest_staging" / "chunked_symbolic_intake" / safe


def _openstax_job_start(args: argparse.Namespace, run_id: str, *, resume: bool) -> dict[str, object]:
    data_root = Path(args.data_root).expanduser().resolve()
    run_root = _openstax_run_root(data_root, run_id)
    run_root.mkdir(parents=True, exist_ok=True)
    stop_path = run_root / "STOP"
    if stop_path.exists():
        stop_path.unlink()
    stdout_path = run_root / "stdout.json"
    stderr_path = run_root / "stderr.log"
    job_path = run_root / "job.json"
    command = [
        sys.executable,
        "-m",
        "AnchorWorks",
        "symbolic-batch-intake-chunked",
        "--data-root",
        str(data_root),
        "--source-dir",
        str(Path(args.source_dir).expanduser().resolve()),
        "--pattern",
        str(args.pattern),
        "--map-root",
        str(Path(args.map_root).expanduser().resolve()),
        "--max-workers",
        str(int(args.max_workers)),
        "--generation",
        str(int(args.generation)),
        "--run-id",
        run_id,
        "--chunk-file-limit",
        str(int(args.chunk_file_limit)),
        "--soft-warning-gb",
        str(float(args.soft_warning_gb)),
        "--emergency-flush-gb",
        str(float(args.emergency_flush_gb)),
        "--abort-gb",
        str(float(args.max_ram_gb)),
    ]
    if args.no_chunk_binaries:
        command.append("--no-chunk-binaries")
    env = os.environ.copy()
    src = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
        process = subprocess.Popen(
            command,
            cwd=str(Path(__file__).resolve().parents[2]),
            env=env,
            stdout=stdout,
            stderr=stderr,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
    job = {
        "schema_version": "anchorworks_detached_ingest_job@1",
        "job_id": run_id,
        "run_id": run_id,
        "action": "resume" if resume else "start",
        "pid": process.pid,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "run_root": str(run_root),
        "manifest_path": str(run_root / "manifest.json"),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stop_path": str(stop_path),
    }
    job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")
    return {"ok": True, "detached": True, **job}


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
            capture_output=True,
            text=True,
        )
        return str(pid) in completed.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _openstax_job_status(data_root: Path, run_id: str) -> dict[str, object]:
    run_root = _openstax_run_root(data_root, run_id)
    job_path = run_root / "job.json"
    manifest_path = run_root / "manifest.json"
    job = json.loads(job_path.read_text(encoding="utf-8")) if job_path.exists() else {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    pid = int(job.get("pid", 0) or 0)
    return {
        "ok": run_root.exists(),
        "run_id": run_id,
        "run_root": str(run_root),
        "pid": pid,
        "running": _pid_running(pid),
        "stop_requested": (run_root / "STOP").exists(),
        "job": job,
        "manifest": {
            "status": manifest.get("status"),
            "ok": manifest.get("ok"),
            "source_count": manifest.get("source_count"),
            "chunk_count": manifest.get("chunk_count"),
            "completed_chunks": manifest.get("completed_chunks"),
            "files_ok": manifest.get("files_ok"),
            "files_failed": manifest.get("files_failed"),
            "stopped_reason": manifest.get("stopped_reason"),
            "elapsed_seconds": manifest.get("elapsed_seconds"),
        },
    }


def _openstax_job_stop(data_root: Path, run_id: str, *, kill: bool = False) -> dict[str, object]:
    run_root = _openstax_run_root(data_root, run_id)
    run_root.mkdir(parents=True, exist_ok=True)
    stop_path = run_root / "STOP"
    stop_path.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    status = _openstax_job_status(data_root, run_id)
    killed = False
    if kill and int(status.get("pid", 0) or 0) > 0 and status.get("running"):
        pid = int(status["pid"])
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)
        else:
            os.kill(pid, 15)
        killed = True
    return {"ok": True, "run_id": run_id, "stop_path": str(stop_path), "kill_requested": kill, "killed": killed}


if __name__ == "__main__":
    main()
