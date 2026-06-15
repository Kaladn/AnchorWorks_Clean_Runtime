from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from aw_inference_kernel import solve_formula_question
from aw_inference_kernel.frame_builder import build_frame


CONVERSATION_RECEIPT_SCHEMA = "anchorworks_conversation_receipt@1"


@dataclass
class ConversationEngine:
    store: Any
    clearspeak: Any
    document_answer: Any

    def answer(
        self,
        input_text: str,
        *,
        mode: str = "auto",
        evidence_mode: str = "auto",
        conversation_id: str | None = None,
        record_chat: bool = False,
    ) -> dict[str, Any]:
        text = str(input_text or "").strip()
        recognition = self._recognize(text)
        input_kind = self._input_kind(text, recognition)
        frame = self._frame(text, recognition, mode=mode)
        chat_record = None
        if record_chat:
            chat_record = self.store.memory.append_chat_turn(text, conversation_id=str(conversation_id or "default"))
        memory_status = self._memory_status(
            record_chat=record_chat,
            conversation_id=conversation_id,
            chat_record=chat_record,
        )

        if input_kind in {"conversation", "continue", "stop"}:
            speech = self._conversation_speech(input_kind, text=text)
            return self._receipt(
                text=text,
                recognition=recognition,
                frame=frame,
                input_kind=input_kind,
                selected_engine_path=f"conversation_{input_kind}",
                evidence_lane="conversation_style",
                speech=speech,
                response=speech,
                memory_status=memory_status,
            )

        if input_kind in {"info_transfer", "correction", "planning_note"}:
            result = self.clearspeak.query(text).to_dict()
            return self._receipt(
                text=text,
                recognition=recognition,
                frame=frame,
                input_kind=input_kind,
                selected_engine_path="conversation_context_ack",
                evidence_lane="no_source_support",
                speech=str(result.get("speech") or ""),
                response=str(result.get("response") or ""),
                answer_payload=result,
                memory_status=memory_status,
            )

        payload = self._answer_payload(text, evidence_mode=evidence_mode)
        lane = self._evidence_lane(payload)
        return self._receipt(
            text=text,
            recognition=recognition,
            frame=frame,
            input_kind=input_kind,
            selected_engine_path=str(payload.get("engine") or "conversation_answer_route"),
            evidence_lane=lane,
            speech=str(payload.get("speech") or payload.get("response") or ""),
            response=str(payload.get("response") or payload.get("speech") or ""),
            answer_payload=payload,
            memory_status=memory_status,
        )

    def _answer_payload(self, text: str, *, evidence_mode: str) -> dict[str, Any]:
        mode = str(evidence_mode or "auto").strip().casefold()
        formula_payload = solve_formula_question(text)
        if formula_payload and mode in {"auto", "counts", "count", "documents", "document", "maps", "mapped", "mapped_documents"}:
            return dict(formula_payload)

        if mode in {"documents", "document", "maps", "mapped", "mapped_documents", "rag"}:
            document_result = self.document_answer.answer(text).to_dict()
            if document_result.get("ok"):
                return document_result
            if mode in {"documents", "document", "maps", "mapped", "mapped_documents", "rag"}:
                document_result["engine"] = "document_answer_no_map_support"
                document_result["speech"] = "Document Mode found no source-local map support for that question."
                document_result["response"] = document_result["speech"]
                return document_result

        result = self.clearspeak.query(text).to_dict()
        result["evidence_mode"] = "counts"
        result["engine"] = "clearspeak_counts"
        return result

    def _recognize(self, text: str) -> dict[str, Any]:
        if hasattr(self.store, "recognize_query_anchors"):
            return self.store.recognize_query_anchors(text)
        return {
            "schema_version": "anchorworks_lexicon_recognition@1",
            "query": text,
            "query_anchors": [],
            "represented_anchors": [],
            "missing_anchors": [],
            "input_kind": "conversation",
        }

    def _input_kind(self, text: str, recognition: dict[str, Any]) -> str:
        lower = text.casefold().strip()
        if lower in {"continue", "go on", "keep going", "continue working"}:
            return "continue"
        if lower in {"stop", "stop response", "halt"}:
            return "stop"
        if lower.startswith("/") or lower.startswith("aw "):
            return "operator_command"
        if len(text) > 4000:
            return "intake_payload"
        kind = str(recognition.get("input_kind") or "conversation").strip().casefold()
        if kind in {"statement"} and not text.endswith("?"):
            return "conversation"
        return kind or "conversation"

    def _frame(self, text: str, recognition: dict[str, Any], *, mode: str) -> dict[str, Any]:
        anchors = list(recognition.get("query_anchors") or recognition.get("observed_anchors") or [])
        try:
            return build_frame(text, anchors, mode=mode)
        except Exception:
            return {"schema_version": "aw_inference_frame@1", "frame_type": "conversation", "activity": "conversation"}

    def _receipt(
        self,
        *,
        text: str,
        recognition: dict[str, Any],
        frame: dict[str, Any],
        input_kind: str,
        selected_engine_path: str,
        evidence_lane: str,
        speech: str,
        response: str,
        memory_status: dict[str, Any],
        answer_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = answer_payload or {}
        inference_plan = {}
        answer_assembly = payload.get("answer_assembly") if isinstance(payload.get("answer_assembly"), dict) else {}
        if isinstance(answer_assembly, dict):
            inference_plan = answer_assembly.get("inference_plan") if isinstance(answer_assembly.get("inference_plan"), dict) else {}
        receipt = {
            "schema_version": CONVERSATION_RECEIPT_SCHEMA,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "query": text,
            "input_kind": input_kind,
            "represented_anchors": list(payload.get("represented_anchors") or recognition.get("represented_anchors") or []),
            "missing_anchors": list(payload.get("missing_anchors") or recognition.get("missing_anchors") or []),
            "frame_type": str(frame.get("frame_type") or frame.get("question_type") or input_kind),
            "frame": frame,
            "selected_engine_path": selected_engine_path,
            "evidence_lane": evidence_lane,
            "accepted_candidates": list(inference_plan.get("accepted_candidates") or []),
            "rejected_candidates": list(inference_plan.get("rejected_candidates") or []),
            "speech": speech,
            "response": response,
            "evidence": list(payload.get("evidence") or []),
            "citations": list(payload.get("citations") or []),
            "lexicon_recognition": recognition,
            "answer_payload": payload,
            "memory_write_status": memory_status,
            "writes_allowed": {"chat": bool(memory_status.get("chat_recorded")), "counts": False, "lifetime": False, "lexicon": False},
        }
        return receipt

    def _memory_status(
        self,
        *,
        record_chat: bool,
        conversation_id: str | None,
        chat_record: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        status = {
            "chat_record_requested": bool(record_chat),
            "chat_recorded": bool(chat_record and chat_record.get("chat_recorded")),
            "conversation_id": str(conversation_id or ""),
            "counts_written": False,
            "lifetime_written": False,
            "daily_consolidation_required": bool(chat_record and chat_record.get("chat_recorded")),
            "requires_finalize_for_intake": bool(chat_record and chat_record.get("chat_recorded")),
        }
        if chat_record:
            status.update({
                "day_id": chat_record.get("day_id"),
                "chat_log_path": chat_record.get("chat_log_path"),
                "turn_id": chat_record.get("turn_id"),
                "block_id": chat_record.get("block_id"),
                "line_id": chat_record.get("line_id"),
                "record_count": chat_record.get("record_count"),
                "write_rule": "jsonl_only_until_daily_consolidation",
            })
        return status

    def _evidence_lane(self, payload: dict[str, Any]) -> str:
        engine = str(payload.get("engine") or "").casefold()
        evidence_mode = str(payload.get("evidence_mode") or "").casefold()
        if "document" in engine or evidence_mode in {"documents", "document", "maps", "mapped", "mapped_documents"}:
            return "document_evidence" if payload.get("ok") else "no_source_support"
        if "formula" in engine:
            return "phrase_authority"
        if evidence_mode == "counts" or "clearspeak" in engine:
            return "count_pressure"
        if payload.get("evidence"):
            return "document_evidence"
        return "no_source_support"

    def _conversation_speech(self, input_kind: str, *, text: str = "") -> str:
        if input_kind == "continue":
            return "I can continue from the current context, but I need a live subject or trace to extend."
        if input_kind == "stop":
            return "Stopped. I will not continue that response."
        greeting = self._greeting_reply(text)
        if greeting:
            return f"{greeting}. I am here and ready to work the local AnchorWorks system."
        return "I am here and ready to work the local AnchorWorks system."

    def _greeting_reply(self, text: str) -> str:
        lower = str(text or "").casefold()
        if "afternoon" in lower:
            return "Good afternoon"
        if "evening" in lower:
            return "Good evening"
        if "morning" in lower:
            return "Good morning"
        if "hello" in lower:
            return "Hello"
        if lower.strip() in {"hi", "hey", "yo"}:
            return lower.strip().capitalize()
        return ""
