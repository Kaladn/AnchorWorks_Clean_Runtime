import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from AnchorWorks.chat_memory_system import ChatMemorySystem, ImmutabilityError
from AnchorWorks.chat_models import L2Context, L3Lesson, L4ReasoningHooks, SubContextPointer
from AnchorWorks.chatlog_reader import ChatLogReader, chat_entry_integrity_hash
from AnchorWorks.mirror_reader import MirrorReader
from AnchorWorks.mirror_writer import MirrorWriter


class _StoreStub:
    def __init__(self):
        self.calls = []

    def build_intake_mapping(self, *, source_name, content, count_target):
        self.calls.append(("build_intake_mapping", source_name, count_target, content))
        return {
            "ok": True,
            "saved_map_name": "chat_day.awmap.json",
            "count_target": count_target,
        }

    def build_source_local_symbol_counts(self, observed_map_name):
        self.calls.append(("build_source_local_symbol_counts", observed_map_name))
        return {
            "ok": True,
            "symbol_counts_name": "chat_day.awss.json",
        }

    def build_binary_symbol_counts_from_source_local(self, *, artifact_names):
        self.calls.append(("build_binary_symbol_counts_from_source_local", list(artifact_names)))
        return {
            "ok": True,
            "artifact_names": list(artifact_names),
            "binary_counts_path": "State/symbol_counts_binary/current.awsc",
        }


class _ClearspeakStub:
    def __init__(self, store=None):
        self.store = store or _StoreStub()

    def status(self):
        return {"ok": True}

    def query(self, text):
        return _ClearSpeakResultStub(text)


@dataclass
class _ClearSpeakResultStub:
    query: str

    def to_dict(self):
        return {
            "query": self.query,
            "query_anchors": ["truevision"],
            "represented_anchors": ["truevision"],
            "missing_anchors": [],
            "lexicon_recognition": {},
            "speech": "TrueVision is a visual state path.",
            "response": "TrueVision is a visual state path.",
            "evidence": [],
            "citations": [],
            "answer_assembly": {},
        }


class ChatMemoryScaffoldTests(unittest.TestCase):
    def test_chatlog_reader_quarantines_integrity_mismatch_on_read(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            chat_dir = root / "State" / "chat_memory" / "chats"
            chat_dir.mkdir(parents=True)
            row = {
                "id": 1,
                "parent": None,
                "branch": "main",
                "sender": "user",
                "actor": "user",
                "seat": "operator",
                "content": "original",
                "timestamp": "2026-05-27T00:00:00Z",
                "message_uuid": "msg-1",
                "conversation_uuid": "2026-05-27:main",
                "kind": "CHAT",
                "envelope_version": "anchorworks-chat-memory-v1",
                "day": "2026-05-27",
            }
            row["hash"] = chat_entry_integrity_hash(row)[:12]
            row["integrity_hash"] = chat_entry_integrity_hash(row)
            tampered = dict(row)
            tampered["content"] = "mutated"
            (chat_dir / "2026-05-27.jsonl").write_text(json.dumps(tampered, sort_keys=True) + "\n", encoding="utf-8")

            result = ChatLogReader(root).get_conversation(day="2026-05-27")

        self.assertEqual(result["entries"], [])
        self.assertEqual(len(result["quarantine"]), 1)
        self.assertEqual(result["quarantine"][0]["reason"], "integrity_hash_mismatch")

    def test_chat_memory_history_returns_quarantine_and_excludes_bad_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            system = ChatMemorySystem(root, _ClearspeakStub())
            good = system.log_message(sender="user", content="good")
            path = root / "State" / "chat_memory" / "chats" / f"{good['day']}.jsonl"
            bad = dict(good)
            bad["id"] = 2
            bad["message_uuid"] = "bad-row"
            bad["content"] = "bad"
            path.write_text(path.read_text(encoding="utf-8") + json.dumps(bad, sort_keys=True) + "\n", encoding="utf-8")

            history = system.history(day=good["day"])

        self.assertEqual([row["content"] for row in history["messages"]], ["good"])
        self.assertEqual(len(history["quarantine"]), 1)

    def test_chat_memory_refuses_duplicate_l1_id_or_uuid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            system = ChatMemorySystem(root, _ClearspeakStub())
            first = system.log_message(sender="user", content="first")
            path = root / "State" / "chat_memory" / "chats" / f"{first['day']}.jsonl"
            duplicate = dict(first)
            duplicate["content"] = "duplicate id"
            duplicate["hash"] = chat_entry_integrity_hash(duplicate)[:12]
            duplicate["integrity_hash"] = chat_entry_integrity_hash(duplicate)
            path.write_text(path.read_text(encoding="utf-8") + json.dumps(duplicate, sort_keys=True) + "\n", encoding="utf-8")

            with self.assertRaises(ImmutabilityError):
                system.log_message(sender="user", content="blocked")

    def test_mirror_writer_keeps_l2_l3_l4_separate_from_source_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            writer = MirrorWriter(root)
            writer.write_l2(
                "msg-1",
                L2Context(
                    citation_hooks=["op_00491"],
                    context_summary="operator marked this as important",
                    subcontext_pointers=[
                        SubContextPointer(ref_type="chat", ref_id="msg-0", description="lead-in"),
                    ],
                ),
                day="2026-05-27",
            )
            writer.write_l3(
                "msg-1",
                L3Lesson(
                    lesson_text="memory is selected, not automatic",
                    significance="prevents fake continuity",
                    change="daily chat remains L1 only",
                    evidence_refs=["msg-1"],
                ),
                day="2026-05-27",
            )
            writer.write_l4(
                "msg-1",
                L4ReasoningHooks(reasoning_step_ids=["reason-1"], external_data_pointers=["doc://x"]),
                day="2026-05-27",
            )
            mirror = MirrorReader(root).get_entry_mirror("msg-1", day="2026-05-27")

        self.assertEqual(mirror["l2_context"]["citation_hooks"], ["op_00491"])
        self.assertEqual(mirror["l3_lessons"][0]["lesson_text"], "memory is selected, not automatic")
        self.assertEqual(mirror["l4_reasoning"]["reasoning_step_ids"], ["reason-1"])
        self.assertFalse((Path(tmpdir) / "State" / "chat_memory" / "chats").exists())

    def test_mirror_writer_rejects_more_than_five_subcontext_pointers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pointers = [
                SubContextPointer(ref_type="chat", ref_id=f"msg-{index}")
                for index in range(6)
            ]
            with self.assertRaises(ValueError):
                MirrorWriter(Path(tmpdir)).write_l2(
                    "msg-1",
                    L2Context(subcontext_pointers=pointers),
                    day="2026-05-27",
                )

    def test_finalize_day_maps_permanent_jsonl_chat_into_binary_source_local_counts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store = _StoreStub()
            system = ChatMemorySystem(root, _ClearspeakStub(store))
            message = system.log_message(sender="user", content="SecureCore and AnchorWorks daily memory lock.")

            result = system.finalize_day(day=message["day"])

        self.assertEqual(result["count_target"], "binary_source_local")
        self.assertEqual(result["symbol_counts"]["symbol_counts_name"], "chat_day.awss.json")
        self.assertEqual(result["binary_counts"]["artifact_names"], ["chat_day.awss.json"])
        self.assertEqual(
            [call[0] for call in store.calls],
            [
                "build_intake_mapping",
                "build_source_local_symbol_counts",
                "build_binary_symbol_counts_from_source_local",
            ],
        )
        self.assertEqual(store.calls[0][2], "binary_source_local")
        self.assertIn("[CONTENT_START]", store.calls[0][3])

    def test_user_rows_get_identity_provenance_and_human_input_shape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            system = ChatMemorySystem(Path(tmpdir), _ClearspeakStub())
            row = system.log_message(sender="user", content="short human note", actor="user", seat="operator")

        self.assertEqual(row["speaker_identity"]["speaker_id"], "operator.local")
        self.assertEqual(row["speaker_identity"]["speaker_kind"], "human")
        self.assertEqual(row["speaker_identity"]["input_origin"]["classification"], "human_language_input")
        self.assertEqual(row["speaker_identity"]["input_origin"]["content_source"], "operator")
        self.assertIn("logged_at_utc", row["speaker_identity"])

    def test_wall_of_ai_shaped_text_is_marked_as_operator_ai_pasted_text(self):
        ai_wall = "\n".join([
            "Here is the implementation plan:",
            "```text",
            "Step 1: Analyze the repository.",
            "Step 2: Implement the module.",
            "Step 3: Run tests.",
            "```",
            "This output should be treated as pasted AI text, not normal typing.",
        ] * 18)
        with tempfile.TemporaryDirectory() as tmpdir:
            system = ChatMemorySystem(Path(tmpdir), _ClearspeakStub())
            row = system.log_message(sender="user", content=ai_wall, actor="user", seat="operator")

        origin = row["speaker_identity"]["input_origin"]
        self.assertEqual(origin["classification"], "operator_ai_pasted_text")
        self.assertIn("ai_shaped_format", origin["signals"])
        self.assertIn("humanly_unlikely_wall_without_typing_timing", origin["signals"])

    def test_typing_speed_metadata_marks_humanly_impossible_input_as_pasted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            system = ChatMemorySystem(Path(tmpdir), _ClearspeakStub())
            row = system.log_message(
                sender="user",
                content="a" * 1200,
                actor="user",
                seat="operator",
                input_timing={"duration_ms": 1000},
            )

        origin = row["speaker_identity"]["input_origin"]
        self.assertEqual(origin["classification"], "operator_pasted_text")
        self.assertGreater(origin["typing_speed"]["chars_per_second"], 500)

    def test_assistant_rows_get_ai_identity_from_model_identity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            system = ChatMemorySystem(Path(tmpdir), _ClearspeakStub())
            row = system.log_message(
                sender="assistant",
                content="ClearSpeak answer.",
                actor="clearspeak",
                seat="local",
                model_identity={"provider": "anchorworks", "engine": "clearspeak_counts"},
            )

        identity = row["speaker_identity"]
        self.assertEqual(identity["speaker_kind"], "ai")
        self.assertEqual(identity["speaker_id"], "anchorworks:clearspeak_counts")
        self.assertEqual(identity["output_origin"]["classification"], "ai_generated_output")

    def test_chat_workbench_actions_include_copy_share_retry_and_wipe_contracts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            system = ChatMemorySystem(Path(tmpdir), _ClearspeakStub())
            result = system.send("what is truevision?", mode="counts")

        action_ids = {row["id"] for row in result.actions or []}
        self.assertTrue({"copy_message", "share_message", "retry_message", "wipe_message"}.issubset(action_ids))


if __name__ == "__main__":
    unittest.main()
