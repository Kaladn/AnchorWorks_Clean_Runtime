from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from aw_inference_kernel import solve_formula_question

from .app import _default_data_root
from .document_answer import DocumentAnswerAssembler
from .intake_audit import audit_source_directory
from .store import LexiconStore
from .clearspeak import ClearSpeakService


HELP_TEXT = """
Commands:

`/ask <question>`          ask ClearSpeak through the full local answer route
`/status`                  show local runtime status
`/cloud <anchor>`          show count neighborhood
`/search <text>`           search the lexicon
`/docs`                    list flat documents
`/doc <name>`              inspect one flat document
`/anchorize <name|path>`   anchorize a flat document
`/intake-preview <path>`   preview intake without approval
`/intake-ready <path>`     check whether a file is ready to map
`/intake-audit <dir>`      audit a source directory for intake
`/intake-map <path>`       build an intake map after readiness passes
`/missing`                 show missing-anchor review queue
`/operator`                show operator-worthy runtime variables
`/raw`                     toggle raw JSON output for the last result
`/help`                    show this help
`/quit`                    leave the shell

Plain text is treated as `/ask`.
"""


@dataclass
class ShellCommand:
    command: str
    args: str = ""


@dataclass
class ShellContext:
    store: Any
    clearspeak: Any
    document_answer: Any
    data_root: Path | None
    console: Console | None = None
    raw_enabled: bool = False
    last_result: dict[str, Any] | None = None


def parse_shell_line(line: str) -> ShellCommand:
    text = str(line or "").strip()
    if not text:
        return ShellCommand("empty", "")
    if not text.startswith("/"):
        return ShellCommand("ask", text)
    head, _, tail = text[1:].partition(" ")
    return ShellCommand(head.strip().casefold(), tail.strip())


def build_shell_context(data_root: Path | None = None, *, console: Console | None = None) -> ShellContext:
    root = Path(data_root or _default_data_root()).expanduser().resolve()
    store = LexiconStore(root)
    return ShellContext(
        store=store,
        clearspeak=ClearSpeakService(store),
        document_answer=DocumentAnswerAssembler(store),
        data_root=root,
        console=console or Console(),
    )


def local_answer(ctx: ShellContext, query: str, *, limit: int = 6, evidence_mode: str = "auto") -> dict[str, Any]:
    mode = str(evidence_mode or "auto").strip().casefold()
    formula_payload = solve_formula_question(query)
    if formula_payload and mode in {"auto", "counts", "count", "documents", "document", "maps", "mapped", "mapped_documents"}:
        return dict(formula_payload)

    if mode in {"documents", "document", "maps", "mapped", "mapped_documents", "auto"}:
        document_result = ctx.document_answer.answer(query, limit=limit).to_dict()
        if document_result.get("ok"):
            return document_result
        if mode in {"documents", "document", "maps", "mapped", "mapped_documents"}:
            represented = document_result.get("represented_anchors") or []
            missing = document_result.get("missing_anchors") or []
            shape_note = ""
            if represented or missing:
                represented_text = ", ".join(represented) if represented else "none"
                missing_text = ", ".join(missing) if missing else "none"
                shape_note = f" Lexicon shape was recognized: represented anchors: {represented_text}; missing anchors: {missing_text}."
            return {
                "query": query,
                "query_anchors": document_result.get("query_anchors") or [],
                "represented_anchors": represented,
                "missing_anchors": missing,
                "lexicon_recognition": document_result.get("lexicon_recognition") or {},
                "speech": "Document Mode found no source-local map support for that question. Counts were not used as a substitute." + shape_note,
                "response": "Document Mode found no source-local map support for that question. Counts were not used as a substitute." + shape_note,
                "evidence": [],
                "citations": [],
                "evidence_mode": "documents",
                "engine": "document_answer_no_map_support",
            }

    result = ctx.clearspeak.query(query, limit=limit).to_dict()
    result["evidence_mode"] = "counts"
    result["engine"] = "clearspeak_counts"
    return result


def execute_shell_line(ctx: ShellContext, line: str) -> bool:
    parsed = parse_shell_line(line)
    console = ctx.console or Console()
    command = parsed.command
    args = parsed.args

    if command == "empty":
        return True
    if command in {"quit", "exit", "q"}:
        return False
    if command in {"help", "h", "?"}:
        console.print(Markdown(HELP_TEXT))
        return True
    if command == "raw":
        ctx.raw_enabled = not ctx.raw_enabled
        console.print(f"Raw JSON: {'on' if ctx.raw_enabled else 'off'}")
        if ctx.raw_enabled and ctx.last_result:
            _print_json(console, ctx.last_result)
        return True
    if command == "ask":
        _handle_ask(ctx, args)
        return True
    if command == "status":
        _handle_status(ctx)
        return True
    if command == "cloud":
        _handle_cloud(ctx, args)
        return True
    if command == "search":
        _handle_search(ctx, args)
        return True
    if command == "docs":
        _handle_docs(ctx)
        return True
    if command == "doc":
        _handle_doc(ctx, args)
        return True
    if command == "anchorize":
        _handle_anchorize(ctx, args)
        return True
    if command == "intake-preview":
        _handle_intake_preview(ctx, args)
        return True
    if command == "intake-ready":
        _handle_intake_ready(ctx, args)
        return True
    if command == "intake-audit":
        _handle_intake_audit(ctx, args)
        return True
    if command == "intake-map":
        _handle_intake_map(ctx, args)
        return True
    if command == "missing":
        _handle_missing(ctx)
        return True
    if command == "operator":
        _handle_operator(ctx)
        return True

    console.print(f"[yellow]Unknown command:[/yellow] /{command}")
    console.print("Use /help.")
    return True


def run_shell(data_root: Path | None = None) -> None:
    console = Console()
    ctx = build_shell_context(data_root, console=console)
    console.print(Panel.fit("AnchorWorks Local Shell\nPlain text asks ClearSpeak. Use /help for commands.", title="AW CLI"))
    while True:
        try:
            line = console.input("[bold cyan]aw>[/bold cyan] ")
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if not execute_shell_line(ctx, line):
            break


def _handle_ask(ctx: ShellContext, query: str) -> None:
    console = ctx.console or Console()
    if not query:
        console.print("[yellow]Ask needs a question.[/yellow]")
        return
    try:
        result = local_answer(ctx, query)
    except Exception as exc:
        console.print(Panel(str(exc), title="Answer Error", style="red"))
        return
    ctx.last_result = result
    speech = str(result.get("speech") or result.get("response") or "").strip() or "(no answer text)"
    engine = str(result.get("engine") or "local")
    console.print(Panel(speech, title=f"Answer - {engine}", border_style="green"))
    _print_evidence_summary(console, result)
    if ctx.raw_enabled:
        _print_json(console, result)


def _handle_status(ctx: ShellContext) -> None:
    console = ctx.console or Console()
    clear = ctx.clearspeak.status()
    storage = ctx.store.user_storage_status() if hasattr(ctx.store, "user_storage_status") else {}
    table = Table(title="Local Status")
    table.add_column("Area")
    table.add_column("Value")
    table.add_row("data_root", str(ctx.data_root or ""))
    for key, value in clear.items():
        table.add_row(f"clearspeak.{key}", _short(value))
    for key, value in storage.items():
        table.add_row(f"storage.{key}", _short(value))
    console.print(table)


def _handle_cloud(ctx: ShellContext, anchor: str) -> None:
    console = ctx.console or Console()
    if not anchor:
        console.print("[yellow]/cloud needs an anchor.[/yellow]")
        return
    result = ctx.store.context_map(anchor)
    ctx.last_result = result
    neighbors = result.get("neighbors") or []
    table = Table(title=f"Cloud: {anchor}")
    table.add_column("Anchor")
    table.add_column("Observations", justify="right")
    for row in neighbors[:20]:
        table.add_row(str(row.get("anchor") or ""), str(row.get("observations") or 0))
    if not neighbors:
        table.add_row("(none)", "0")
    console.print(table)
    if ctx.raw_enabled:
        _print_json(console, result)


def _handle_search(ctx: ShellContext, query: str) -> None:
    console = ctx.console or Console()
    if not query:
        console.print("[yellow]/search needs text.[/yellow]")
        return
    rows = ctx.store.search(query=query, pack="all")
    ctx.last_result = {"query": query, "results": rows}
    table = Table(title=f"Search: {query}")
    table.add_column("Word")
    table.add_column("Pack")
    table.add_column("Status")
    for row in rows[:20]:
        table.add_row(str(row.get("word") or ""), str(row.get("pack") or ""), str(row.get("status") or ""))
    if not rows:
        table.add_row("(no matches)", "", "")
    console.print(table)


def _handle_docs(ctx: ShellContext) -> None:
    console = ctx.console or Console()
    result = ctx.store.flat_document_files()
    ctx.last_result = result
    table = Table(title="Flat Documents")
    table.add_column("Kind")
    table.add_column("Name")
    for row in result.get("raw_files") or []:
        table.add_row("raw", str(row.get("name") or ""))
    for row in result.get("symbolic_files") or []:
        table.add_row("symbolic", str(row.get("name") or ""))
    console.print(table)


def _handle_doc(ctx: ShellContext, name: str) -> None:
    console = ctx.console or Console()
    if not name:
        console.print("[yellow]/doc needs a document name.[/yellow]")
        return
    try:
        result = ctx.store.load_flat_document(name)
    except Exception as exc:
        console.print(Panel(str(exc), title="Document Error", style="red"))
        return
    ctx.last_result = result
    text = str(result.get("content") or result.get("raw_text") or result.get("text") or "")
    summary = text[:1200] + ("..." if len(text) > 1200 else "")
    console.print(Panel(summary or "(document loaded; no text preview)", title=name))


def _handle_anchorize(ctx: ShellContext, target: str) -> None:
    console = ctx.console or Console()
    if not target:
        console.print("[yellow]/anchorize needs a raw document name or path.[/yellow]")
        return
    path = Path(target).expanduser()
    try:
        result = ctx.store.anchorize_flat_document(path if path.exists() else None, name="" if path.exists() else target)
    except Exception as exc:
        console.print(Panel(str(exc), title="Anchorize Error", style="red"))
        return
    ctx.last_result = result
    console.print(Panel(_short(result), title="Anchorize", border_style="green"))


def _handle_intake_preview(ctx: ShellContext, path_text: str) -> None:
    console = ctx.console or Console()
    if not path_text:
        console.print("[yellow]/intake-preview needs a file path.[/yellow]")
        return
    path = Path(path_text).expanduser()
    result = _preview_file_for_intake(ctx, path_text)
    if result is None:
        return
    ctx.last_result = result
    table = Table(title=f"Intake Preview: {path.name}")
    table.add_column("Metric")
    table.add_column("Value")
    for key in ["known_anchor_count", "missing_anchor_count", "missing_anchor_observations"]:
        table.add_row(key, str(result.get(key, 0)))
    console.print(table)
    missing = result.get("missing_anchors") or []
    if missing:
        console.print("Missing preview: " + ", ".join(str(row.get("anchor") or "") for row in missing[:20]))


def _handle_intake_ready(ctx: ShellContext, path_text: str) -> None:
    console = ctx.console or Console()
    if not path_text:
        console.print("[yellow]/intake-ready needs a file path.[/yellow]")
        return
    result = _preview_file_for_intake(ctx, path_text)
    if result is None:
        return
    readiness = intake_readiness_from_preview(result)
    ctx.last_result = {"preview": result, "readiness": readiness}
    title = f"Intake Ready: {Path(path_text).expanduser().name}"
    style = "green" if readiness["ready"] else "yellow"
    table = Table(title=title)
    table.add_column("Item")
    table.add_column("Value")
    for key in [
        "status",
        "paragraph_count",
        "known_anchor_count",
        "missing_anchor_count",
        "missing_anchor_observations",
    ]:
        table.add_row(key, str(readiness.get(key, "")))
    console.print(table)
    console.print(Panel(readiness["message"], title="Readiness", border_style=style))
    _print_missing_preview(console, result)


def _handle_intake_audit(ctx: ShellContext, path_text: str) -> None:
    console = ctx.console or Console()
    if not path_text:
        console.print("[yellow]/intake-audit needs a directory path.[/yellow]")
        return
    path = Path(path_text).expanduser()
    if not path.exists() or not path.is_dir():
        console.print(Panel(str(path), title="Directory Not Found", style="red"))
        return
    result = audit_source_directory(path)
    ctx.last_result = result
    table = Table(title=f"Intake Audit: {path}")
    table.add_column("Item")
    table.add_column("Value")
    for key in ["ok", "files_seen", "files_prepared", "failure_count"]:
        table.add_row(key, str(result.get(key, "")))
    console.print(table)
    _print_dict_table(console, "By Extension", result.get("by_extension") or {})
    _print_dict_table(console, "By Converter", result.get("by_converter") or {})
    warnings = result.get("warnings") or []
    failures = result.get("failures") or []
    if warnings:
        console.print(Panel("\n".join(_short(row) for row in warnings[:10]), title="Warnings", border_style="yellow"))
    if failures:
        console.print(Panel("\n".join(_short(row) for row in failures[:10]), title="Failures", border_style="red"))


def _handle_intake_map(ctx: ShellContext, path_text: str) -> None:
    console = ctx.console or Console()
    if not path_text:
        console.print("[yellow]/intake-map needs a file path.[/yellow]")
        return
    preview = _preview_file_for_intake(ctx, path_text)
    if preview is None:
        return
    readiness = intake_readiness_from_preview(preview)
    if not readiness["ready"]:
        ctx.last_result = {"preview": preview, "readiness": readiness}
        console.print(Panel(readiness["message"], title="Intake Map Blocked", border_style="yellow"))
        _print_missing_preview(console, preview)
        return
    path = Path(path_text).expanduser()
    content = path.read_text(encoding="utf-8", errors="replace")
    result = ctx.store.build_intake_mapping(source_name=path.name, content=content)
    ctx.last_result = {"preview": preview, "readiness": readiness, "mapping": result}
    console.print(Panel(_short(result), title="Intake Map Built", border_style="green"))


def _handle_missing(ctx: ShellContext) -> None:
    console = ctx.console or Console()
    result = ctx.store.missing_anchor_review_queue(limit=25)
    ctx.last_result = result
    table = Table(title="Missing Anchor Review")
    table.add_column("Anchor")
    table.add_column("Observations", justify="right")
    table.add_column("Status")
    for row in result.get("entries") or []:
        table.add_row(str(row.get("anchor") or ""), str(row.get("observations") or 0), str(row.get("review_status") or ""))
    if not result.get("entries"):
        table.add_row("(empty)", "0", "")
    console.print(table)


def _handle_operator(ctx: ShellContext) -> None:
    console = ctx.console or Console()
    result = operator_surface_snapshot(ctx)
    ctx.last_result = result
    table = Table(title="Operator Surface")
    table.add_column("Area")
    table.add_column("Item")
    table.add_column("Value")
    for area, payload in result.items():
        if isinstance(payload, dict):
            for key, value in payload.items():
                table.add_row(area, str(key), _short(value))
        else:
            table.add_row(area, "", _short(payload))
    console.print(table)


def _preview_file_for_intake(ctx: ShellContext, path_text: str) -> dict[str, Any] | None:
    console = ctx.console or Console()
    path = Path(path_text).expanduser()
    if not path.exists() or not path.is_file():
        console.print(Panel(str(path), title="File Not Found", style="red"))
        return None
    content = path.read_text(encoding="utf-8", errors="replace")
    return ctx.store.preview_document_intake(
        source_name=path.name,
        content=content,
        file_size=path.stat().st_size,
        file_type=path.suffix.lstrip("."),
        source_path=str(path),
    )


def intake_readiness_from_preview(preview: dict[str, Any]) -> dict[str, Any]:
    missing_count = int(preview.get("missing_anchor_count") or 0)
    missing_observations = int(preview.get("missing_anchor_observations") or 0)
    known_count = int(preview.get("known_anchor_count") or 0)
    paragraph_count = int(preview.get("paragraph_count") or len(preview.get("paragraphs") or []) or 0)
    visual_preview_only = bool(preview.get("visual_preview_only"))

    if visual_preview_only:
        status = "visual_held"
        ready = False
        message = "Visual preview only. This needs a text-bearing intake path before mapping."
    elif missing_count > 0:
        status = "blocked_missing_anchors"
        ready = False
        message = f"Blocked: {missing_count} missing anchors across {missing_observations} observations need review."
    else:
        status = "ready"
        ready = True
        message = "Ready: all previewed anchors are known, and this file can be mapped."

    return {
        "ready": ready,
        "status": status,
        "message": message,
        "paragraph_count": paragraph_count,
        "known_anchor_count": known_count,
        "missing_anchor_count": missing_count,
        "missing_anchor_observations": missing_observations,
        "visual_preview_only": visual_preview_only,
    }


def operator_surface_snapshot(ctx: ShellContext) -> dict[str, Any]:
    docs = _call_or_empty(ctx.store, "flat_document_files")
    missing = _call_or_empty(ctx.store, "missing_anchor_review_queue", limit=1)
    return {
        "runtime": {
            "data_root": str(ctx.data_root or ""),
        },
        "clearspeak": _call_or_empty(ctx.clearspeak, "status"),
        "storage": _call_or_empty(ctx.store, "user_storage_status"),
        "counts": _call_or_empty(ctx.store, "counts_status"),
        "binary": _call_or_empty(ctx.store, "binary_substrate_status"),
        "documents": {
            "raw_files": len(docs.get("raw_files") or []),
            "symbolic_files": len(docs.get("symbolic_files") or []),
        },
        "missing_review": {
            "queued_preview": len(missing.get("entries") or []),
            "total_registry_anchors": missing.get("total_registry_anchors", 0),
        },
        "intake": {
            "readiness_command": "/intake-ready <path>",
            "audit_command": "/intake-audit <dir>",
            "map_command": "/intake-map <path>",
        },
    }


def _call_or_empty(target: Any, name: str, **kwargs: Any) -> dict[str, Any]:
    method = getattr(target, name, None)
    if not callable(method):
        return {}
    try:
        result = method(**kwargs)
    except TypeError:
        result = method()
    except Exception as exc:
        return {"error": str(exc)}
    return result if isinstance(result, dict) else {"value": result}


def _print_missing_preview(console: Console, preview: dict[str, Any]) -> None:
    missing = preview.get("missing_anchors") or []
    if missing:
        console.print("Missing preview: " + ", ".join(str(row.get("anchor") or "") for row in missing[:20]))


def _print_dict_table(console: Console, title: str, rows: dict[str, Any]) -> None:
    if not rows:
        return
    table = Table(title=title)
    table.add_column("Name")
    table.add_column("Value", justify="right")
    for key, value in rows.items():
        table.add_row(str(key), str(value))
    console.print(table)


def _print_evidence_summary(console: Console, result: dict[str, Any]) -> None:
    rows = render_evidence_rows(result)
    if not rows:
        return
    table = Table(title="Evidence")
    table.add_column("Kind")
    table.add_column("Source")
    table.add_column("Detail")
    for kind, source, detail in rows:
        table.add_row(kind, source, detail)
    console.print(table)


def render_evidence_rows(result: dict[str, Any], *, limit: int = 5) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for row in _coerce_rows(result.get("evidence"))[:limit]:
        rows.append((
            "evidence",
            str(row.get("source") or row.get("source_name") or row.get("anchor") or ""),
            _short(row),
        ))
    for row in _coerce_rows(result.get("citations"))[:limit]:
        rows.append((
            "citation",
            str(row.get("source") or row.get("coord") or ""),
            _short(row),
        ))
    return rows


def _coerce_rows(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    return []


def _print_json(console: Console, payload: Any) -> None:
    console.print_json(json.dumps(payload, ensure_ascii=False, default=str))


def _short(value: Any, limit: int = 160) -> str:
    if isinstance(value, (dict, list, tuple)):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."
