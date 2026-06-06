from __future__ import annotations

import json

from AnchorWorks.conversation_corpus import (
    ConversationCorpusNormalizer,
    build_conversation_flow_artifacts,
    export_conversation_flow_symbolic_sources,
    import_hf_dataset_chunked,
    import_hf_parquet_files_chunked,
    import_hf_dialogue_rows,
    write_conversation_manifest,
)


def test_normalizer_reads_srt_turns(tmp_path):
    source = tmp_path / "sample.srt"
    source.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nALICE: Hello there.\n\n"
        "2\n00:00:04,000 --> 00:00:05,000\nBOB: General Kenobi.\n",
        encoding="utf-8",
    )

    result = ConversationCorpusNormalizer().normalize(source)

    assert result["turn_count"] == 2
    assert result["turns"][0]["speaker"] == "ALICE"
    assert result["turns"][0]["timestamp"] == "00:00:01,000 --> 00:00:03,000"
    assert result["turns"][0]["lane_flags"]["style"] is True
    assert result["turns"][0]["lane_flags"]["evidence"] is False


def test_normalizer_reads_jsonl_turns_with_provenance(tmp_path):
    source = tmp_path / "sample.jsonl"
    source.write_text(
        json.dumps({"speaker": "RIPLEY", "utterance": "Believe me.", "title": "Example", "provenance": "licensed-local"}) + "\n",
        encoding="utf-8",
    )

    result = ConversationCorpusNormalizer().normalize(source)

    assert result["turn_count"] == 1
    turn = result["turns"][0]
    assert turn["speaker"] == "RIPLEY"
    assert turn["title"] == "Example"
    assert turn["lane_flags"]["evidence"] is True


def test_normalizer_reads_csv_turns(tmp_path):
    source = tmp_path / "sample.csv"
    source.write_text("speaker,dialogue,title\nMARTY,This is heavy.,Example\n", encoding="utf-8")

    result = ConversationCorpusNormalizer().normalize(source)

    assert result["turn_count"] == 1
    assert result["turns"][0]["utterance"] == "This is heavy."


def test_subtitle_normalizer_strips_caption_junk_and_classifies_shape(tmp_path):
    source = tmp_path / "sample.vtt"
    source.write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:03.000\n"
        "[MUSIC]\n"
        "ALICE: Good morning!\n\n"
        "00:00:04.000 --> 00:00:05.000\n"
        "BOB: Morning, how are you?\n\n"
        "00:00:06.000 --> 00:00:07.000\n"
        "(door slams)\n",
        encoding="utf-8",
    )

    result = ConversationCorpusNormalizer().normalize(source)

    assert result["turn_count"] == 2
    assert result["rejected_or_unknown_line_count"] == 0
    assert result["turns"][0]["utterance"] == "Good morning!"
    assert result["turns"][0]["line_shape"] == "greeting"
    assert result["turns"][1]["line_shape"] == "question"
    assert result["turns"][1]["reply_to_turn_id"] == "sample:turn:000000"


def test_unknown_line_shape_is_valid_and_still_counts_anchors(tmp_path):
    source = tmp_path / "sample.txt"
    source.write_text("A quiet blue staircase under static.", encoding="utf-8")

    result = ConversationCorpusNormalizer().normalize(source)
    turn = result["turns"][0]

    assert turn["line_shape"] == "unknown"
    assert "quiet" in turn["anchors"]
    assert turn["anchor_count"] > 0


def test_conversation_flow_artifacts_are_separate_from_core_counts(tmp_path):
    source = tmp_path / "sample.srt"
    source.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nALICE: Good morning.\n\n"
        "2\n00:00:04,000 --> 00:00:05,000\nBOB: Good morning.\n",
        encoding="utf-8",
    )
    manifest = ConversationCorpusNormalizer().normalize(source)

    artifacts = build_conversation_flow_artifacts(manifest, tmp_path / "flow")

    assert artifacts["writes_allowed"]["core_anchor_counts"] is False
    assert artifacts["writes_allowed"]["conversation_flow_counts"] is True
    assert "conversation_flow_counts" in artifacts["stores"]
    assert "speaker_turn_maps" in artifacts["stores"]
    assert "source_manifests" in artifacts["stores"]
    assert "rejected_or_unknown_lines" in artifacts["stores"]
    assert (tmp_path / "flow" / "conversation_flow_counts" / "conversation_flow_counts.json").exists()


def test_normalizer_reads_hf_verbalized_sampling_dialogue_rows(tmp_path):
    source = tmp_path / "vs_dialogue.jsonl"
    utterances = [
        {
            "conversation_id": "8448",
            "utterance_id": "8448",
            "speaker": "A23D8",
            "role": 0,
            "text": "Hey there! Hope your day is going well.",
        },
        {
            "conversation_id": "8448",
            "utterance_id": "8449",
            "speaker": "A12D",
            "role": 1,
            "text": "Hey! Yeah, it is going alright. How about you?",
        },
    ]
    source.write_text(
        json.dumps({
            "conversation_id": "8448",
            "utterances": json.dumps(utterances),
            "model": "GPT-4.1",
            "method": "Direct",
            "num_turns": 2,
        }) + "\n",
        encoding="utf-8",
    )

    result = ConversationCorpusNormalizer().normalize(source)

    assert result["turn_count"] == 2
    assert result["turns"][0]["source_kind"] == "hf_verbalized_sampling_dialogue"
    assert result["turns"][0]["conversation_id"] == "8448"
    assert result["turns"][0]["speaker_role"] == 0
    assert result["turns"][0]["model"] == "GPT-4.1"
    assert result["turns"][0]["method"] == "Direct"
    assert result["turns"][0]["lane_flags"]["style"] is True
    assert result["turns"][0]["lane_flags"]["evidence"] is False
    assert result["turns"][1]["reply_to_turn_id"] == "8448:turn:000000"


def test_normalizer_reads_soda_dialogue_and_speakers_as_turns(tmp_path):
    source = tmp_path / "soda.jsonl"
    source.write_text(
        json.dumps({
            "head": "PersonX asks about a storm",
            "relation": "xWant",
            "tail": "to know what happened",
            "narrative": "A simple conversation about weather.",
            "dialogue": ["Good morning.", "Did the storm pass?", "Yes, it moved east."],
            "speakers": ["PersonX", "PersonY", "PersonX"],
            "original_index": 123,
            "split": "train",
        }) + "\n",
        encoding="utf-8",
    )

    result = ConversationCorpusNormalizer().normalize(source)

    assert result["turn_count"] == 3
    assert result["turns"][0]["source_kind"] == "soda_dialogue"
    assert result["turns"][0]["conversation_id"] == "123"
    assert result["turns"][0]["speaker"] == "PersonX"
    assert result["turns"][0]["title"] == "PersonX asks about a storm"
    assert result["turns"][0]["line_shape"] == "greeting"
    assert result["turns"][1]["speaker"] == "PersonY"
    assert result["turns"][1]["line_shape"] == "question"
    assert result["turns"][1]["reply_to_turn_id"] == "123:turn:000000"
    assert result["turns"][2]["speaker_changed"] is True
    assert result["turns"][0]["lane_flags"]["style"] is True
    assert result["turns"][0]["lane_flags"]["count"] is True
    assert result["turns"][0]["lane_flags"]["evidence"] is False


def test_normalizer_reads_ultrachat_data_list_as_alternating_turns(tmp_path):
    source = tmp_path / "ultrachat.jsonl"
    source.write_text(
        json.dumps({
            "id": "uc-1",
            "data": [
                "What is magnetism?",
                "Magnetism is a noncontact force.",
                "Can you keep that simple?",
            ],
        }) + "\n",
        encoding="utf-8",
    )

    result = ConversationCorpusNormalizer().normalize(source)

    assert result["turn_count"] == 3
    assert result["turns"][0]["source_kind"] == "ultrachat_dialogue"
    assert result["turns"][0]["conversation_id"] == "uc-1"
    assert result["turns"][0]["speaker"] == "user"
    assert result["turns"][1]["speaker"] == "assistant"
    assert result["turns"][2]["speaker"] == "user"
    assert result["turns"][1]["reply_to_turn_id"] == "uc-1:turn:000000"
    assert result["turns"][0]["lane_flags"]["style"] is True
    assert result["turns"][0]["lane_flags"]["count"] is True
    assert result["turns"][0]["lane_flags"]["evidence"] is False


def test_import_hf_dialogue_rows_writes_manifest_and_flow_artifacts(tmp_path):
    rows_payload = {
        "rows": [
            {
                "row_idx": 0,
                "row": {
                    "conversation_id": "8448",
                    "utterances": json.dumps([
                        {"conversation_id": "8448", "utterance_id": "8448", "speaker": "A", "role": 0, "text": "Hey there!"},
                        {"conversation_id": "8448", "utterance_id": "8449", "speaker": "B", "role": 1, "text": "Hey, how are you?"},
                    ]),
                    "model": "GPT-4.1",
                    "method": "Direct",
                    "num_turns": 2,
                },
            }
        ]
    }

    result = import_hf_dialogue_rows(
        rows_payload,
        output_root=tmp_path / "hf_import",
        dataset="CHATS-Lab/Verbalized-Sampling-Dialogue-Simulation",
        config="Direct",
        split="gpt_4_1",
    )

    assert result["ok"] is True
    assert result["manifest"]["turn_count"] == 2
    assert result["manifest"]["turns"][0]["source_kind"] == "hf_verbalized_sampling_dialogue"
    assert result["artifacts"]["writes_allowed"]["core_anchor_counts"] is False
    assert (tmp_path / "hf_import" / "source_manifests" / "conversation_manifest.json").exists()
    assert (tmp_path / "hf_import" / "conversation_flow_counts" / "conversation_flow_counts.json").exists()


def test_chunked_hf_import_flushes_large_batches_without_truth_writes(tmp_path):
    pages = [
        {
            "num_rows_total": 3,
            "rows": [
                {
                    "row_idx": 0,
                    "row": {
                        "dialogue": ["Good morning.", "How are you?"],
                        "speakers": ["A", "B"],
                        "original_index": 10,
                    },
                },
                {
                    "row_idx": 1,
                    "row": {
                        "dialogue": ["Fine.", "Keep going."],
                        "speakers": ["A", "B"],
                        "original_index": 11,
                    },
                },
            ],
        },
        {
            "num_rows_total": 3,
            "rows": [
                {
                    "row_idx": 2,
                    "row": {
                        "dialogue": ["Last one."],
                        "speakers": ["A"],
                        "original_index": 12,
                    },
                }
            ],
        },
    ]

    def fetcher(**kwargs):
        return pages[kwargs["offset"] // 2]

    result = import_hf_dataset_chunked(
        output_root=tmp_path / "chunked",
        dataset="allenai/soda",
        config="default",
        split="train",
        page_length=2,
        rows_per_chunk=2,
        max_rows=3,
        fetcher=fetcher,
    )

    assert result["ok"] is True
    assert result["source_row_count"] == 3
    assert result["turn_count"] == 5
    assert result["chunk_count"] == 2
    assert result["target_ram_gb"] == 40.0
    assert result["writes_allowed"]["truth_evidence"] is False
    assert (tmp_path / "chunked" / "chunks" / "chunk_000000" / "source_manifests" / "conversation_manifest.json").exists()
    assert (tmp_path / "chunked" / "chunks" / "chunk_000001" / "source_manifests" / "conversation_manifest.json").exists()
    assert (tmp_path / "chunked" / "manifest.json").exists()


def test_parquet_hf_import_reads_local_shards_in_large_batches(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    parquet_path = tmp_path / "ultrachat.parquet"
    table = pa.table({
        "id": ["uc-1", "uc-2"],
        "data": [
            ["What is magnetism?", "Magnetism is a noncontact force."],
            ["Good morning.", "Morning."],
        ],
    })
    pq.write_table(table, parquet_path)

    result = import_hf_parquet_files_chunked(
        output_root=tmp_path / "parquet_import",
        dataset="openbmb/UltraChat",
        config="default",
        split="train",
        parquet_files=[{"url": str(parquet_path), "filename": "ultrachat.parquet", "size": parquet_path.stat().st_size}],
        batch_size=2,
        rows_per_chunk=2,
        target_ram_gb=40,
    )

    assert result["ok"] is True
    assert result["source_row_count"] == 2
    assert result["turn_count"] == 4
    assert result["chunk_count"] == 1
    assert result["target_ram_gb"] == 40.0
    assert result["parquet_file_count"] == 1
    assert result["writes_allowed"]["truth_evidence"] is False
    assert (tmp_path / "parquet_import" / "manifest.json").exists()


def test_export_conversation_flow_symbolic_sources_writes_turn_text_files(tmp_path):
    chunk_root = tmp_path / "flow" / "chunks" / "chunk_000000" / "source_manifests"
    chunk_root.mkdir(parents=True)
    (chunk_root / "conversation_manifest.json").write_text(
        json.dumps({
            "schema_version": "anchorworks_conversation_corpus_manifest@1",
            "turn_count": 2,
            "turns": [
                {"speaker": "user", "clean_text": "What is magnetism?", "line_shape": "question"},
                {"speaker": "assistant", "clean_text": "Magnetism is a noncontact force.", "line_shape": "unknown"},
            ],
        }),
        encoding="utf-8",
    )

    result = export_conversation_flow_symbolic_sources(tmp_path / "flow", tmp_path / "symbolic_sources")

    assert result["ok"] is True
    assert result["source_count"] == 1
    assert result["turn_count"] == 2
    source_path = tmp_path / "symbolic_sources" / "chunk_000000.txt"
    assert source_path.exists()
    assert "user: What is magnetism?" in source_path.read_text(encoding="utf-8")
    assert result["writes_allowed"] == {
        "source_exports": True,
        "maps": False,
        "counts": False,
        "lifetime": False,
        "lexicon": False,
    }


def test_write_conversation_manifest_round_trips(tmp_path):
    manifest = {"schema_version": "anchorworks_conversation_corpus_manifest@1", "turn_count": 0, "turns": []}

    path = write_conversation_manifest(manifest, tmp_path)

    assert path.name == "conversation_manifest.json"
    assert json.loads(path.read_text(encoding="utf-8"))["turn_count"] == 0
