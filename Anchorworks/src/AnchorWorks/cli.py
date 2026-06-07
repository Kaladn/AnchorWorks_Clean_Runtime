from __future__ import annotations

import argparse
import json
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


if __name__ == "__main__":
    main()
