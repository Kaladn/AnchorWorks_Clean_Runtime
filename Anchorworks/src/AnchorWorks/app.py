from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .chat_memory_system import ChatMemorySystem
from .clearspeak import ClearSpeakService
from .model_api_client import ModelApiClient
from .policy_diagnostics_report import build_settings_report, load_queries
from .store import LexiconStore
from .symbol_policy import SymbolPolicy
from .tree_brain_controls import TreeBrainControls


class WordBody(BaseModel):
    word: str


class ImportBody(BaseModel):
    words_dir: str


class MappingRunBody(BaseModel):
    file_path: str


class ResonanceBuildBody(BaseModel):
    observed_map_name: str


class IntakePreviewBody(BaseModel):
    source_name: str
    content: str
    file_size: int = 0
    file_type: str = ""
    source_path: str = ""


class IntakeApproveBody(BaseModel):
    anchors: list[str]
    frequencies: dict[str, int] = {}


class IntakeMapBody(BaseModel):
    source_name: str
    content: str


class IntakeEditBody(BaseModel):
    source_name: str
    content: str
    edits: list[dict[str, Any]]
    file_type: str = "edited-intake-text"
    source_path: str = ""


class ChatArchivePrepareBody(BaseModel):
    archive_root: str


class ClearSpeakQueryBody(BaseModel):
    query: str
    limit: int = 6
    evidence_mode: str = "auto"


class RemixQueryBody(BaseModel):
    query: str
    top_k: int = 4
    max_variants: int = 8
    evaluate: bool = True


class FlatDocumentAnchorizeBody(BaseModel):
    name: str = ""
    path: str = ""


class ChatSendBody(BaseModel):
    message: str
    mode: str = "clearspeak"
    branch: str = "main"
    model: str = ""


class ChatArchiveImportBody(BaseModel):
    archive_root: str


class TreeBrainControlsBody(BaseModel):
    controls: dict[str, Any]


class SymbolPolicyBody(BaseModel):
    policy: dict[str, Any]


class ChatFinalizeBody(BaseModel):
    day: str | None = None
    branch: str = "main"


class ChatCitationBody(BaseModel):
    day: str
    message_id: str
    block_id: str = "b0"
    block_ordinal: int = 0
    coord: str
    subject: str = ""
    note: str = ""
    source: str = "ui"


class ChatNoteBody(BaseModel):
    day: str
    message_id: str
    block_id: str = "b0"
    block_ordinal: int = 0
    text: str


class SideChatBody(BaseModel):
    source_day: str
    message_id: str
    description: str = ""
    main_branch: str = "main"


def _default_data_root() -> Path:
    candidate = Path.home() / "OneDrive" / "Documents" / "Desktop" / "Lexical Data"
    return candidate if candidate.exists() else Path.cwd()


def create_app(data_root: Path | None = None) -> FastAPI:
    package_root = Path(__file__).resolve().parent
    app_root = package_root.parents[1]
    ui_root = package_root / "ui"
    assets_root = ui_root / "assets"
    store = LexiconStore(data_root or _default_data_root())
    tree_brain_controls = TreeBrainControls.load(app_root / "config" / "tree_brain_controls.json")
    clearspeak = ClearSpeakService(store)
    model_api = ModelApiClient()
    chat_memory = ChatMemorySystem(store.root, clearspeak, model_api=model_api)

    app = FastAPI(title="AnchorWorks Lexicon", version=__version__, docs_url="/api/docs")
    app.state.store = store
    app.state.clearspeak = clearspeak
    app.state.tree_brain_controls = tree_brain_controls
    app.state.model_api = model_api
    app.state.chat_memory = chat_memory

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/assets", StaticFiles(directory=assets_root), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(ui_root / "index.html")

    @app.get("/app.js")
    def app_js() -> FileResponse:
        return FileResponse(ui_root / "app.js")

    @app.get("/favicon.ico")
    def favicon() -> FileResponse:
        return FileResponse(assets_root / "icon-256.png")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "version": __version__, "data_root": str(store.root)}

    def _symbol_policy_path() -> Path:
        return app_root / "config" / "symbol_policy.json"

    def _read_symbol_policy() -> dict[str, Any]:
        return store._read_json(_symbol_policy_path(), {})

    @app.get("/api/tree-brain/controls")
    def tree_brain_controls_get() -> dict[str, Any]:
        return {
            "ok": True,
            "tree_brain_controls": tree_brain_controls.to_dict(),
            "active_controls": tree_brain_controls.active_values(),
            "symbol_policy": _read_symbol_policy(),
        }

    @app.post("/api/tree-brain/controls")
    def tree_brain_controls_save(body: TreeBrainControlsBody) -> dict[str, Any]:
        try:
            saved = tree_brain_controls.update(body.controls)
            return {"ok": True, "tree_brain_controls": saved, "active_controls": tree_brain_controls.active_values()}
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/tree-brain/controls/reset")
    def tree_brain_controls_reset() -> dict[str, Any]:
        saved = tree_brain_controls.reset()
        return {"ok": True, "tree_brain_controls": saved, "active_controls": tree_brain_controls.active_values()}

    @app.post("/api/tree-brain/symbol-policy")
    def tree_brain_symbol_policy_save(body: SymbolPolicyBody) -> dict[str, Any]:
        try:
            SymbolPolicy(body.policy)
            _symbol_policy_path().parent.mkdir(parents=True, exist_ok=True)
            _symbol_policy_path().write_text(json.dumps(body.policy, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"ok": True, "symbol_policy": body.policy}
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/tree-brain/validate")
    def tree_brain_validate() -> dict[str, Any]:
        try:
            TreeBrainControls(tree_brain_controls.path, tree_brain_controls.to_dict())
            SymbolPolicy(_read_symbol_policy())
            load_queries(app_root / "config" / "policy_diagnostic_queries.json")
            return {"ok": True, "message": "Tree-Brain controls, symbol policy, and diagnostic query file are valid."}
        except (OSError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/tree-brain/diagnostics/run")
    def tree_brain_diagnostics_run() -> dict[str, Any]:
        queries_path = app_root / "config" / "policy_diagnostic_queries.json"
        report_path = app_root / "reports" / "policy_diagnostics" / "latest.json"
        try:
            report = build_settings_report(load_queries(queries_path), tree_brain_controls.to_dict(), _read_symbol_policy())
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"ok": True, "report": report}
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/tree-brain/diagnostics/latest")
    def tree_brain_diagnostics_latest() -> dict[str, Any]:
        report_path = app_root / "reports" / "policy_diagnostics" / "latest.json"
        if not report_path.exists():
            return {"ok": True, "report": None}
        return {"ok": True, "report": store._read_json(report_path, None)}

    @app.get("/api/user/storage/status")
    def user_storage_status() -> dict[str, Any]:
        return store.user_storage_status()

    @app.get("/api/clearspeak/status")
    def clearspeak_status() -> dict[str, Any]:
        return clearspeak.status()

    @app.post("/api/clearspeak/query")
    def clearspeak_query(body: ClearSpeakQueryBody) -> dict[str, Any]:
        evidence_mode = (body.evidence_mode or "auto").strip().lower()
        if evidence_mode in {"documents", "document", "maps", "mapped", "mapped_documents", "auto"}:
            document_result = chat_memory.document_answer.answer(body.query, limit=body.limit).to_dict()
            if document_result.get("ok"):
                document_result["speech"] = document_result["response"]
                return document_result
            if evidence_mode in {"documents", "document", "maps", "mapped", "mapped_documents"}:
                return {
                    "query": body.query,
                    "query_anchors": document_result.get("query_anchors") or [],
                    "represented_anchors": [],
                    "missing_anchors": [],
                    "speech": "Document Mode found no source-local map support for that question. Counts were not used as a substitute.",
                    "response": "Document Mode found no source-local map support for that question. Counts were not used as a substitute.",
                    "evidence": [],
                    "citations": [],
                    "evidence_mode": "documents",
                    "engine": "document_answer_no_map_support",
                }
        result = clearspeak.query(body.query, limit=body.limit).to_dict()
        result["evidence_mode"] = "counts"
        result["engine"] = "clearspeak_counts"
        return result

    @app.get("/api/clearspeak/cloud")
    def clearspeak_cloud(anchor: str, k: int = 20) -> dict[str, Any]:
        return store.context_map(anchor)

    @app.post("/api/clearspeak/remix")
    def clearspeak_remix(body: RemixQueryBody) -> dict[str, Any]:
        query_anchors = clearspeak.query(body.query, limit=body.top_k).query_anchors
        variants: list[dict[str, Any]] = []
        for anchor in query_anchors:
            retrieved = store.retrieve_from_counts(anchor, limit=max(1, body.top_k * 4))
            for neighbor in retrieved.get("neighbors") or []:
                selected = str(neighbor.get("anchor") or "")
                if not selected or selected in query_anchors:
                    continue
                remixed = " ".join(query_anchors + [selected])
                variants.append({
                    "remixed_query": remixed,
                    "score": int(neighbor.get("observations", 0) or 0),
                    "drift": 1,
                    "operations": [{
                        "type": "append_count_neighbor",
                        "seed_anchor": anchor,
                        "selected_anchor": selected,
                        "observations": int(neighbor.get("observations", 0) or 0),
                    }],
                })
                if len(variants) >= max(1, body.max_variants):
                    break
            if len(variants) >= max(1, body.max_variants):
                break
        evaluations = []
        if body.evaluate:
            for variant in variants:
                result = clearspeak.query(str(variant.get("remixed_query") or ""), limit=body.top_k).to_dict()
                evaluations.append({
                    "remixed_query": variant.get("remixed_query"),
                    "engine": "clearspeak_counts",
                    "evidence_mode": "counts",
                    "speech": result.get("response") or "",
                    "score": sum(int(row.get("total_neighbor_observations", 0) or 0) for row in result.get("evidence") or []),
                })
        winner = max(evaluations, key=lambda row: int(row.get("score", 0) or 0), default=None)
        return {
            "schema_version": "query_remix@1",
            "query": body.query,
            "content_anchors": query_anchors,
            "variants": variants,
            "evaluations": evaluations,
            "winner": winner,
            "blocked": False,
            "contract": {"original_query_is_sacred": True, "remixes_are_read_only": True},
        }

    @app.get("/api/chat/status")
    def chat_status() -> dict[str, Any]:
        return chat_memory.status()

    @app.get("/api/chat/history")
    def chat_history(day: str | None = None, branch: str = "main", limit: int = 200) -> dict[str, Any]:
        return chat_memory.history(day=day, branch=branch, limit=limit)

    @app.post("/api/chat/send")
    def chat_send(body: ChatSendBody) -> dict[str, Any]:
        try:
            return chat_memory.send(body.message, mode=body.mode, branch=body.branch, model=body.model).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/chat/archive/import")
    def chat_archive_import(body: ChatArchiveImportBody) -> dict[str, Any]:
        try:
            return chat_memory.import_archive(Path(body.archive_root))
        except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/chat/finalize/preview")
    def chat_finalize_preview(body: ChatFinalizeBody) -> dict[str, Any]:
        try:
            return chat_memory.preview_finalize(day=body.day, branch=body.branch)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/chat/finalize")
    def chat_finalize(body: ChatFinalizeBody) -> dict[str, Any]:
        try:
            return chat_memory.finalize_day(day=body.day, branch=body.branch)
        except (FileNotFoundError, IsADirectoryError, ValueError, AssertionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/chat/citations/attach")
    def chat_citation_attach(body: ChatCitationBody) -> dict[str, Any]:
        try:
            return chat_memory.attach_citation(
                day=body.day,
                message_id=body.message_id,
                block_id=body.block_id,
                block_ordinal=body.block_ordinal,
                coord=body.coord,
                subject=body.subject,
                note=body.note,
                source=body.source,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/chat/notes/attach")
    def chat_note_attach(body: ChatNoteBody) -> dict[str, Any]:
        try:
            return chat_memory.attach_note(
                day=body.day,
                message_id=body.message_id,
                block_id=body.block_id,
                block_ordinal=body.block_ordinal,
                text=body.text,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/chat/side/start")
    def chat_side_start(body: SideChatBody) -> dict[str, Any]:
        return chat_memory.create_side_chat(
            source_day=body.source_day,
            message_id=body.message_id,
            description=body.description,
            main_branch=body.main_branch,
        )

    @app.get("/api/search_lexicon")
    def search_lexicon(query: str, pack: str = "all") -> list[dict[str, Any]]:
        return store.search(query=query, pack=pack)

    @app.get("/api/lexicon/distribution")
    def lexicon_distribution() -> dict[str, Any]:
        return store.distribution()

    @app.get("/api/lexicon/browse")
    def lexicon_browse(letter: str, limit: int = 50, pack: str = "all") -> dict[str, Any]:
        return store.browse(letter=letter, limit=limit, pack=pack)

    @app.get("/api/lexicon/sample")
    def lexicon_sample(count: int = 24, pack: str = "all") -> dict[str, Any]:
        return store.sample(count=count, pack=pack)

    @app.get("/api/lexicon/top")
    def lexicon_top(count: int = 30, pack: str = "all") -> dict[str, Any]:
        return store.top(count=count, pack=pack)

    @app.get("/api/lexicon/recent")
    def lexicon_recent(count: int = 30) -> dict[str, Any]:
        return store.recent(count=count)

    @app.get("/api/lexicon/files")
    def lexicon_files() -> dict[str, Any]:
        return store.files()

    @app.get("/api/lexicon/observed-maps")
    def lexicon_observed_maps() -> dict[str, Any]:
        return store.observed_map_files()

    @app.get("/api/lexicon/observed-map/{name}")
    def lexicon_observed_map(name: str) -> dict[str, Any]:
        try:
            return store.load_observed_map(name)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/api/visual-intake/files")
    def visual_intake_files() -> dict[str, Any]:
        return store.visual_intake_files()

    @app.get("/api/visual-intake/packet/{name}")
    def visual_intake_packet(name: str) -> dict[str, Any]:
        try:
            return store.load_visual_intake_packet(name)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/api/lexicon/flat-documents")
    def lexicon_flat_documents() -> dict[str, Any]:
        return store.flat_document_files()

    @app.get("/api/lexicon/flat-document/{name}")
    def lexicon_flat_document(name: str) -> dict[str, Any]:
        try:
            return store.load_flat_document(name)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.post("/api/lexicon/flat-documents/anchorize")
    def lexicon_anchorize_flat_document(body: FlatDocumentAnchorizeBody) -> dict[str, Any]:
        try:
            return store.anchorize_flat_document(Path(body.path) if body.path else None, name=body.name)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/lexicon/flat-documents/anchorize-all")
    def lexicon_anchorize_all_flat_documents() -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for row in store.flat_document_files().get("raw_files") or []:
            name = str(row.get("name") or "")
            try:
                results.append(store.anchorize_flat_document(name=name))
            except (FileNotFoundError, ValueError) as exc:
                errors.append({"name": name, "error": str(exc)})
        return {"ok": not errors, "anchorized_count": len(results), "error_count": len(errors), "results": results, "errors": errors}

    @app.get("/api/lexicon/misspelled-reviews")
    def lexicon_misspelled_reviews() -> dict[str, Any]:
        return store.misspelled_review_files()

    @app.get("/api/lexicon/misspelled-review/{name}")
    def lexicon_misspelled_review(name: str) -> dict[str, Any]:
        try:
            return store.load_misspelled_review(name)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/api/lexicon/retrieve")
    def lexicon_retrieve(anchor: str, limit: int = 25) -> dict[str, Any]:
        return store.retrieve_from_counts(anchor=anchor, limit=limit)

    @app.get("/api/lexicon/file/{filename}")
    def lexicon_file(filename: str, offset: int = 0, limit: int = 50) -> dict[str, Any]:
        try:
            return store.preview_file(filename=filename, offset=offset, limit=limit)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="file not found")

    @app.get("/api/lexicon/entry")
    def lexicon_entry(word: str) -> dict[str, Any]:
        entry = store.entry(word)
        if entry is None:
            raise HTTPException(status_code=404, detail="word not found")
        return entry

    @app.post("/api/616")
    def six_one_six(body: WordBody) -> dict[str, Any]:
        return store.context_map(body.word)

    @app.get("/api/lexicon/unmatched")
    def lexicon_unmatched(limit: int = 100, sort: str = "frequency", letter: str | None = None) -> dict[str, Any]:
        return store.unmatched(letter=letter, limit=limit)

    @app.post("/api/lexicon/approve")
    def lexicon_approve(body: WordBody) -> dict[str, Any]:
        try:
            return store.approve_unmatched(body.word)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/lexicon/ignore")
    def lexicon_ignore(body: WordBody) -> dict[str, Any]:
        try:
            return store.ignore_word(body.word)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/lexicon/unmatched/approve-all")
    def lexicon_approve_all() -> dict[str, Any]:
        return store.approve_all_unmatched()

    @app.post("/api/lexicon/unmatched/deny-all")
    def lexicon_deny_all() -> dict[str, Any]:
        return store.deny_all_unmatched()

    @app.get("/api/lexicon/pending")
    def lexicon_pending() -> dict[str, Any]:
        return store.pending()

    @app.post("/api/lexicon/pending/assign")
    def lexicon_pending_assign(body: WordBody) -> dict[str, Any]:
        try:
            return store.assign_pending(body.word)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.delete("/api/lexicon/pending/{word}")
    def lexicon_pending_delete(word: str) -> dict[str, Any]:
        return store.remove_pending(word)

    @app.post("/api/lexicon/pending/assign-all")
    def lexicon_pending_assign_all() -> dict[str, Any]:
        return store.assign_all_pending()

    @app.get("/api/lexicon/ignored")
    def lexicon_ignored(letter: str | None = None) -> dict[str, Any]:
        return store.ignored(letter=letter)

    @app.delete("/api/lexicon/ignore/{word}")
    def lexicon_unignore(word: str) -> dict[str, Any]:
        return store.unignore_word(word)

    @app.delete("/api/lexicon/canonical")
    def lexicon_clear_canonical() -> dict[str, Any]:
        return store.clear_canonical()

    @app.post("/api/lexicon/return-to-pool")
    def lexicon_return_to_pool() -> dict[str, Any]:
        return store.return_to_pool()

    @app.post("/api/lexicon/import")
    def lexicon_import(body: ImportBody) -> dict[str, Any]:
        try:
            return store.import_words_dir(Path(body.words_dir))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/lexicon/mapping/run")
    def lexicon_mapping_run(body: MappingRunBody) -> dict[str, Any]:
        try:
            return store.build_observed_map(Path(body.file_path))
        except (FileNotFoundError, IsADirectoryError, ValueError, AssertionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/resonance/source-local/build")
    def resonance_source_local_build(body: ResonanceBuildBody) -> dict[str, Any]:
        try:
            return store.build_source_local_resonance(body.observed_map_name)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/flat-documents/runtime/build")
    def flat_documents_runtime_build(body: ResonanceBuildBody) -> dict[str, Any]:
        try:
            return store.build_flat_runtime_from_observed_map(body.observed_map_name)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/lexicon/intake/preview")
    def lexicon_intake_preview(body: IntakePreviewBody) -> dict[str, Any]:
        try:
            return store.preview_document_intake(
                source_name=body.source_name,
                content=body.content,
                file_size=body.file_size,
                file_type=body.file_type,
                source_path=body.source_path,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/lexicon/intake/prepare")
    async def lexicon_intake_prepare(file: UploadFile = File(...)) -> dict[str, Any]:
        try:
            raw = await file.read()
            return store.prepare_intake_document(
                raw,
                source_name=file.filename or "document",
                file_type=file.content_type or "",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/lexicon/intake/chat-archive/prepare")
    def lexicon_intake_chat_archive_prepare(body: ChatArchivePrepareBody) -> dict[str, Any]:
        try:
            return store.prepare_chat_archive_intake(Path(body.archive_root))
        except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/lexicon/intake/approve")
    def lexicon_intake_approve(body: IntakeApproveBody) -> dict[str, Any]:
        try:
            result = store.approve_intake_anchors(body.anchors, frequencies=body.frequencies)
            if result.get("failed_count"):
                raise HTTPException(status_code=400, detail=result)
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/lexicon/intake/edit")
    def lexicon_intake_edit(body: IntakeEditBody) -> dict[str, Any]:
        try:
            return store.edit_intake_content(
                source_name=body.source_name,
                content=body.content,
                edits=body.edits,
                file_type=body.file_type,
                source_path=body.source_path,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/lexicon/intake/map")
    def lexicon_intake_map(body: IntakeMapBody) -> dict[str, Any]:
        try:
            return store.build_intake_mapping(source_name=body.source_name, content=body.content)
        except (FileNotFoundError, IsADirectoryError, ValueError, AssertionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/lexicon/unload")
    def lexicon_unload() -> dict[str, Any]:
        return {"ok": True}

    return app


app = create_app()
