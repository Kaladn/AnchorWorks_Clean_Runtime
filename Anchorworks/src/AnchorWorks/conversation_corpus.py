from __future__ import annotations

import csv
import json
import re
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .intake import extract_anchor_rows


CORPUS_MANIFEST_SCHEMA = "anchorworks_conversation_corpus_manifest@1"
TURN_SCHEMA = "anchorworks_conversation_turn@1"
HF_DATASET_SERVER = "https://datasets-server.huggingface.co"
STYLE_ONLY_SOURCE_KINDS = {
    "hf_verbalized_sampling_dialogue",
    "soda_dialogue",
    "ultrachat_dialogue",
    "openassistant_tree_message",
    "prosocial_dialogue",
}


@dataclass
class ConversationCorpusNormalizer:
    default_title: str = ""

    def normalize(self, path_or_dir: str | Path) -> dict[str, Any]:
        root = Path(path_or_dir).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(root)
        files = [root] if root.is_file() else sorted((path for path in root.rglob("*") if path.is_file()), key=lambda item: str(item).lower())
        turns: list[dict[str, Any]] = []
        rejected_or_unknown_lines: list[dict[str, Any]] = []
        for source in files:
            for turn in self._normalize_file(source):
                turn_index = len(turns)
                turn["turn_index"] = turn_index
                turn["turn_id"] = f"{turn['source_id']}:turn:{turn_index:06d}"
                turn["conversation_id"] = str(turn["source_id"])
                turn["reply_to_turn_id"] = turns[-1]["turn_id"] if turns and turns[-1]["conversation_id"] == turn["conversation_id"] else ""
                turn["speaker_changed"] = bool(turn["reply_to_turn_id"] and turns[-1].get("speaker") != turn.get("speaker"))
                if turn.get("line_shape") == "unknown":
                    rejected_or_unknown_lines.append({
                        "source_id": turn["source_id"],
                        "turn_id": turn["turn_id"],
                        "reason": "unknown_line_shape",
                        "clean_text": turn["utterance"],
                    })
                turns.append(turn)
        return {
            "schema_version": CORPUS_MANIFEST_SCHEMA,
            "source_root": str(root),
            "file_count": len(files),
            "turn_count": len(turns),
            "turns": turns,
            "rejected_or_unknown_line_count": len(rejected_or_unknown_lines),
            "rejected_or_unknown_lines": rejected_or_unknown_lines,
            "lane_policy": {
                "private_local": True,
                "style_allowed": True,
                "count_allowed_after_normalization": True,
                "evidence_requires_provenance": True,
            },
        }

    def _normalize_file(self, path: Path) -> list[dict[str, Any]]:
        suffix = path.suffix.casefold()
        if suffix == ".srt":
            return self._from_subtitle_blocks(path, time_separator="-->")
        if suffix == ".vtt":
            return self._from_vtt(path)
        if suffix == ".jsonl":
            return self._from_jsonl(path)
        if suffix == ".json":
            return self._from_json(path)
        if suffix == ".csv":
            return self._from_csv(path)
        return self._from_plain_text(path)

    def _from_subtitle_blocks(self, path: Path, *, time_separator: str) -> list[dict[str, Any]]:
        text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        blocks = [block.strip() for block in re.split(r"\n\s*\n+", text) if block.strip()]
        rows: list[dict[str, Any]] = []
        for block in blocks:
            lines = [line.strip() for line in block.split("\n") if line.strip()]
            if lines and lines[0].isdigit():
                lines = lines[1:]
            timestamp = ""
            if lines and time_separator in lines[0]:
                timestamp = lines.pop(0)
            utterance = _clean_subtitle_text(" ".join(line for line in lines if not line.startswith("WEBVTT")))
            if utterance:
                rows.append(self._turn(path, utterance, timestamp=timestamp))
        return rows

    def _from_vtt(self, path: Path) -> list[dict[str, Any]]:
        rows = self._from_subtitle_blocks(path, time_separator="-->")
        return [row for row in rows if row["utterance"].casefold() != "webvtt"]

    def _from_jsonl(self, path: Path) -> list[dict[str, Any]]:
        rows = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            loaded = json.loads(line)
            if isinstance(loaded, dict):
                rows.extend(self._turns_from_mapping_or_dialogue_row(path, loaded))
        return rows

    def _from_json(self, path: Path) -> list[dict[str, Any]]:
        loaded = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if isinstance(loaded, list):
            rows: list[dict[str, Any]] = []
            for row in loaded:
                if isinstance(row, dict):
                    rows.extend(self._turns_from_mapping_or_dialogue_row(path, row))
            return rows
        if isinstance(loaded, dict):
            for key in ("turns", "dialogue", "lines", "rows"):
                value = loaded.get(key)
                if isinstance(value, list):
                    rows: list[dict[str, Any]] = []
                    for row in value:
                        if isinstance(row, dict):
                            rows.extend(self._turns_from_mapping_or_dialogue_row(path, row, defaults=loaded))
                    return rows
            return self._turns_from_mapping_or_dialogue_row(path, loaded)
        return []

    def _from_csv(self, path: Path) -> list[dict[str, Any]]:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            return [self._turn_from_mapping(path, row) for row in csv.DictReader(handle)]

    def _from_plain_text(self, path: Path) -> list[dict[str, Any]]:
        lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        return [self._turn(path, line) for line in lines]

    def _turn_from_mapping(self, path: Path, row: dict[str, Any], defaults: dict[str, Any] | None = None) -> dict[str, Any]:
        base = defaults or {}
        utterance = _first(row, "utterance", "dialogue", "line", "text", "content")
        return self._turn(
            path,
            str(utterance),
            speaker=str(_first(row, "speaker", "character", "name") or ""),
            title=str(_first(row, "title", "show", "movie") or _first(base, "title", "show", "movie") or self.default_title),
            season=str(_first(row, "season") or _first(base, "season") or ""),
            episode=str(_first(row, "episode") or _first(base, "episode") or ""),
            scene=str(_first(row, "scene") or _first(base, "scene") or ""),
            timestamp=str(_first(row, "timestamp", "time", "timecode") or ""),
            provenance=str(_first(row, "provenance", "license", "source_license") or _first(base, "provenance", "license", "source_license") or ""),
            source_kind=str(_first(row, "source_kind") or _first(base, "source_kind") or ""),
            model=str(_first(row, "model") or _first(base, "model") or ""),
            method=str(_first(row, "method") or _first(base, "method") or ""),
            speaker_role=_first(row, "role"),
            external_turn_id=str(_first(row, "utterance_id") or ""),
            conversation_id=str(_first(row, "conversation_id") or _first(base, "conversation_id") or ""),
        )

    def _turns_from_mapping_or_dialogue_row(
        self,
        path: Path,
        row: dict[str, Any],
        defaults: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        dialogue = row.get("dialogue")
        if isinstance(dialogue, list) and all(not isinstance(item, (dict, list)) for item in dialogue):
            speakers = row.get("speakers")
            if not isinstance(speakers, list):
                speakers = []
            base = dict(defaults or {})
            conversation_id = str(row.get("original_index") or row.get("dialogue_id") or row.get("conversation_id") or path.stem)
            base.update({
                "conversation_id": conversation_id,
                "source_kind": "soda_dialogue",
                "title": row.get("head") or row.get("narrative") or base.get("title", ""),
                "method": row.get("relation") or base.get("method", ""),
            })
            turns: list[dict[str, Any]] = []
            for index, utterance in enumerate(dialogue):
                item = {
                    "utterance": str(utterance),
                    "speaker": str(speakers[index]) if index < len(speakers) else "",
                    "utterance_id": str(index),
                }
                turns.append(self._turn_from_mapping(path, item, defaults=base))
            return turns

        data = row.get("data")
        if isinstance(data, list) and all(not isinstance(item, (dict, list)) for item in data):
            base = dict(defaults or {})
            conversation_id = str(row.get("id") or row.get("conversation_id") or path.stem)
            base.update({
                "conversation_id": conversation_id,
                "source_kind": "ultrachat_dialogue",
                "title": row.get("title") or base.get("title", ""),
            })
            turns: list[dict[str, Any]] = []
            for index, utterance in enumerate(data):
                item = {
                    "utterance": str(utterance),
                    "speaker": "user" if index % 2 == 0 else "assistant",
                    "utterance_id": str(index),
                }
                turns.append(self._turn_from_mapping(path, item, defaults=base))
            return turns

        utterances = row.get("utterances")
        if isinstance(utterances, str) and utterances.strip().startswith("["):
            try:
                loaded = json.loads(utterances)
            except json.JSONDecodeError:
                loaded = None
            if isinstance(loaded, list):
                base = dict(defaults or {})
                base.update({
                    "conversation_id": row.get("conversation_id", ""),
                    "model": row.get("model", ""),
                    "method": row.get("method", ""),
                    "source_kind": "hf_verbalized_sampling_dialogue",
                })
                return [
                    self._turn_from_mapping(path, item, defaults=base)
                    for item in loaded
                    if isinstance(item, dict)
                ]
        return [self._turn_from_mapping(path, row, defaults=defaults)]

    def _turn(
        self,
        path: Path,
        utterance: str,
        *,
        speaker: str = "",
        title: str = "",
        season: str = "",
        episode: str = "",
        scene: str = "",
        timestamp: str = "",
        provenance: str = "",
        source_kind: str = "",
        model: str = "",
        method: str = "",
        speaker_role: Any = "",
        external_turn_id: str = "",
        conversation_id: str = "",
    ) -> dict[str, Any]:
        speaker, clean = _split_speaker(utterance, speaker=speaker)
        clean = _clean_subtitle_text(clean)
        source_id = conversation_id or path.stem
        has_provenance = bool(str(provenance or "").strip())
        evidence_allowed = has_provenance and (source_kind or "local_conversation_source") not in STYLE_ONLY_SOURCE_KINDS
        anchors = [
            str(row.get("anchor") or "")
            for row in extract_anchor_rows(clean)
            if row.get("anchor") and bool(row.get("count_eligible", True))
        ]
        shape = classify_conversation_line_shape(clean)
        return {
            "schema_version": TURN_SCHEMA,
            "source_id": source_id,
            "source_kind": source_kind or "local_conversation_source",
            "source_path": str(path),
            "title": title or self.default_title or path.stem,
            "season": season,
            "episode": episode,
            "scene": scene,
            "timestamp": timestamp,
            "speaker": speaker,
            "speaker_id": speaker or "unknown_speaker",
            "speaker_role": speaker_role,
            "utterance": clean,
            "raw_text": utterance,
            "clean_text": clean,
            "turn_index": 0,
            "turn_id": "",
            "external_turn_id": external_turn_id,
            "conversation_id": source_id,
            "reply_to_turn_id": "",
            "speaker_changed": False,
            "scene_boundary": False,
            "line_shape": shape,
            "anchors": anchors,
            "anchor_count": len(anchors),
            "confidence": 0.85 if speaker else 0.65,
            "provenance": provenance,
            "model": model,
            "method": method,
            "lane_flags": {
                "private_local": True,
                "style": True,
                "count": True,
                "evidence": evidence_allowed,
            },
        }


def classify_conversation_line_shape(text: str) -> str:
    clean = str(text or "").strip().casefold()
    if not clean:
        return "unknown"
    words = set(re.findall(r"[a-z']+", clean))
    if clean.endswith("?"):
        return "question"
    if words & {"hello", "hi", "hey", "morning", "goodbye", "bye"}:
        if words & {"goodbye", "bye"}:
            return "closing"
        return "greeting"
    if words & {"yes", "yeah", "yep", "ok", "okay", "sure", "right", "agreed"}:
        return "agreement"
    if words & {"no", "nah", "wrong", "incorrect"}:
        return "disagreement"
    if words & {"what", "why", "how", "when", "where", "who"}:
        return "question"
    if words & {"please", "bring", "give", "tell", "show", "stop", "wait"}:
        return "command_request"
    if words & {"thanks", "thank"}:
        return "acknowledgment"
    if len(words) <= 3:
        return "acknowledgment"
    return "unknown"


def build_conversation_flow_artifacts(manifest: dict[str, Any], output_root: str | Path) -> dict[str, Any]:
    root = Path(output_root).expanduser().resolve()
    stores = {
        "conversation_flow_counts": root / "conversation_flow_counts",
        "speaker_turn_maps": root / "speaker_turn_maps",
        "source_manifests": root / "source_manifests",
        "rejected_or_unknown_lines": root / "rejected_or_unknown_lines",
    }
    for path in stores.values():
        path.mkdir(parents=True, exist_ok=True)

    turns = [turn for turn in manifest.get("turns") or [] if isinstance(turn, dict)]
    flow_counts: Counter[str] = Counter()
    anchor_counts: Counter[str] = Counter()
    speaker_rows: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for turn in turns:
        shape = str(turn.get("line_shape") or "unknown")
        speaker_rows.append({
            "conversation_id": str(turn.get("conversation_id") or ""),
            "turn_id": str(turn.get("turn_id") or ""),
            "reply_to_turn_id": str(turn.get("reply_to_turn_id") or ""),
            "speaker_id": str(turn.get("speaker_id") or ""),
            "speaker_changed": bool(turn.get("speaker_changed")),
            "line_shape": shape,
            "timestamp": str(turn.get("timestamp") or ""),
        })
        for anchor in turn.get("anchors") or []:
            anchor_counts[str(anchor)] += 1
        if previous and previous.get("conversation_id") == turn.get("conversation_id"):
            flow_counts[f"{previous.get('line_shape', 'unknown')} -> {shape}"] += 1
        previous = turn

    flow_payload = {
        "schema_version": "anchorworks_conversation_flow_counts@1",
        "flow_counts": dict(sorted(flow_counts.items())),
        "anchor_counts": dict(sorted(anchor_counts.items())),
        "law": "conversation flow counts shape rendering only; they are not source truth",
    }
    speaker_payload = {
        "schema_version": "anchorworks_speaker_turn_maps@1",
        "turn_count": len(speaker_rows),
        "turns": speaker_rows,
    }
    rejected_payload = {
        "schema_version": "anchorworks_rejected_or_unknown_lines@1",
        "rows": manifest.get("rejected_or_unknown_lines") or [],
    }

    _write_json(stores["conversation_flow_counts"] / "conversation_flow_counts.json", flow_payload)
    _write_json(stores["speaker_turn_maps"] / "speaker_turn_maps.json", speaker_payload)
    write_conversation_manifest(manifest, stores["source_manifests"])
    _write_json(stores["rejected_or_unknown_lines"] / "rejected_or_unknown_lines.json", rejected_payload)

    return {
        "ok": True,
        "schema_version": "anchorworks_conversation_flow_artifacts@1",
        "stores": {name: str(path) for name, path in stores.items()},
        "turn_count": len(turns),
        "flow_count": len(flow_counts),
        "anchor_count": len(anchor_counts),
        "writes_allowed": {
            "core_anchor_counts": False,
            "conversation_flow_counts": True,
            "speaker_turn_maps": True,
            "source_manifests": True,
            "rejected_or_unknown_lines": True,
            "truth_evidence": False,
            "lexicon": False,
            "lifetime": False,
        },
    }


def write_conversation_manifest(manifest: dict[str, Any], output_root: str | Path) -> Path:
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / "conversation_manifest.json"
    _write_json(path, manifest)
    return path


def import_hf_dialogue_rows(
    rows_payload: dict[str, Any],
    *,
    output_root: str | Path,
    dataset: str,
    config: str,
    split: str,
) -> dict[str, Any]:
    normalizer = ConversationCorpusNormalizer()
    turns: list[dict[str, Any]] = []
    synthetic_path = Path(f"{_safe_name(dataset)}_{_safe_name(config)}_{_safe_name(split)}.jsonl")
    for wrapper in rows_payload.get("rows") or []:
        row = wrapper.get("row") if isinstance(wrapper, dict) else None
        if isinstance(row, dict):
            for turn in normalizer._turns_from_mapping_or_dialogue_row(synthetic_path, row):
                turn_index = len(turns)
                turn["turn_index"] = turn_index
                turn["turn_id"] = f"{turn['source_id']}:turn:{turn_index:06d}"
                turn["conversation_id"] = str(turn["source_id"])
                turn["reply_to_turn_id"] = turns[-1]["turn_id"] if turns and turns[-1]["conversation_id"] == turn["conversation_id"] else ""
                turn["speaker_changed"] = bool(turn["reply_to_turn_id"] and turns[-1].get("speaker") != turn.get("speaker"))
                turns.append(turn)

    manifest = {
        "schema_version": CORPUS_MANIFEST_SCHEMA,
        "source_root": f"hf://datasets/{dataset}/{config}/{split}",
        "dataset": dataset,
        "config": config,
        "split": split,
        "file_count": 0,
        "turn_count": len(turns),
        "turns": turns,
        "rejected_or_unknown_line_count": sum(1 for turn in turns if turn.get("line_shape") == "unknown"),
        "rejected_or_unknown_lines": [
            {
                "source_id": turn.get("source_id", ""),
                "turn_id": turn.get("turn_id", ""),
                "reason": "unknown_line_shape",
                "clean_text": turn.get("utterance", ""),
            }
            for turn in turns
            if turn.get("line_shape") == "unknown"
        ],
        "lane_policy": {
            "private_local": True,
            "style_allowed": True,
            "count_allowed_after_normalization": True,
            "evidence_requires_provenance": True,
            "simulated_dialogue_not_truth": True,
        },
    }
    root = Path(output_root).expanduser().resolve()
    manifest_path = write_conversation_manifest(manifest, root / "source_manifests")
    artifacts = build_conversation_flow_artifacts(manifest, root)
    return {
        "ok": True,
        "schema_version": "anchorworks_hf_dialogue_import@1",
        "dataset": dataset,
        "config": config,
        "split": split,
        "manifest_path": str(manifest_path),
        "manifest": manifest,
        "artifacts": artifacts,
        "writes_allowed": artifacts["writes_allowed"],
    }


def fetch_hf_dataset_rows(
    *,
    dataset: str,
    config: str,
    split: str,
    offset: int = 0,
    length: int = 100,
) -> dict[str, Any]:
    params = urllib.parse.urlencode({
        "dataset": dataset,
        "config": config,
        "split": split,
        "offset": int(offset),
        "length": max(1, min(100, int(length))),
    })
    url = f"{HF_DATASET_SERVER}/rows?{params}"
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def import_hf_dataset_sample(
    *,
    output_root: str | Path,
    dataset: str = "CHATS-Lab/Verbalized-Sampling-Dialogue-Simulation",
    config: str = "Direct",
    split: str = "gpt_4_1",
    offset: int = 0,
    length: int = 100,
) -> dict[str, Any]:
    payload = fetch_hf_dataset_rows(dataset=dataset, config=config, split=split, offset=offset, length=length)
    return import_hf_dialogue_rows(payload, output_root=output_root, dataset=dataset, config=config, split=split)


def import_hf_dataset_chunked(
    *,
    output_root: str | Path,
    dataset: str,
    config: str,
    split: str,
    offset: int = 0,
    page_length: int = 100,
    rows_per_chunk: int = 50_000,
    max_rows: int | None = None,
    target_ram_gb: float = 40.0,
    fetcher: Callable[..., dict[str, Any]] = fetch_hf_dataset_rows,
) -> dict[str, Any]:
    root = Path(output_root).expanduser().resolve()
    chunks_root = root / "chunks"
    root.mkdir(parents=True, exist_ok=True)
    chunks_root.mkdir(parents=True, exist_ok=True)

    page_length = max(1, min(100, int(page_length)))
    rows_per_chunk = max(1, int(rows_per_chunk))
    start_offset = max(0, int(offset))
    total_limit = None if max_rows is None else max(0, int(max_rows))
    started_at = datetime.now(timezone.utc).isoformat()

    source_rows_seen = 0
    total_turns = 0
    chunk_summaries: list[dict[str, Any]] = []
    chunk_rows: list[dict[str, Any]] = []
    next_offset = start_offset
    total_available: int | None = None

    while True:
        remaining = None if total_limit is None else total_limit - source_rows_seen
        if remaining is not None and remaining <= 0:
            break
        length = page_length if remaining is None else min(page_length, remaining)
        payload = fetcher(dataset=dataset, config=config, split=split, offset=next_offset, length=length)
        rows = [row for row in payload.get("rows") or [] if isinstance(row, dict)]
        if total_available is None and payload.get("num_rows_total") is not None:
            total_available = int(payload.get("num_rows_total") or 0)
        if not rows:
            break
        chunk_rows.extend(rows)
        source_rows_seen += len(rows)
        next_offset += len(rows)

        if len(chunk_rows) >= rows_per_chunk:
            summary = _flush_hf_import_chunk(
                chunk_rows,
                output_root=chunks_root / f"chunk_{len(chunk_summaries):06d}",
                dataset=dataset,
                config=config,
                split=split,
            )
            chunk_summaries.append(summary)
            total_turns += int(summary.get("turn_count") or 0)
            chunk_rows = []

        if total_available is not None and next_offset >= total_available:
            break

    if chunk_rows:
        summary = _flush_hf_import_chunk(
            chunk_rows,
            output_root=chunks_root / f"chunk_{len(chunk_summaries):06d}",
            dataset=dataset,
            config=config,
            split=split,
        )
        chunk_summaries.append(summary)
        total_turns += int(summary.get("turn_count") or 0)

    result = {
        "ok": True,
        "schema_version": "anchorworks_hf_conversation_chunked_import@1",
        "dataset": dataset,
        "config": config,
        "split": split,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "source_root": f"hf://datasets/{dataset}/{config}/{split}",
        "start_offset": start_offset,
        "next_offset": next_offset,
        "total_available_rows": total_available,
        "source_row_count": source_rows_seen,
        "turn_count": total_turns,
        "chunk_count": len(chunk_summaries),
        "page_length": page_length,
        "rows_per_chunk": rows_per_chunk,
        "target_ram_gb": float(target_ram_gb),
        "chunks_root": str(chunks_root),
        "chunks": chunk_summaries,
        "writes_allowed": _conversation_flow_writes_allowed(),
    }
    _write_json(root / "manifest.json", result)
    return result


def fetch_hf_parquet_files(*, dataset: str, config: str, split: str) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"dataset": dataset})
    url = f"{HF_DATASET_SERVER}/parquet?{params}"
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [
        item
        for item in payload.get("parquet_files") or []
        if isinstance(item, dict)
        and str(item.get("config") or "") == str(config)
        and str(item.get("split") or "") == str(split)
    ]


def import_hf_dataset_parquet_chunked(
    *,
    output_root: str | Path,
    dataset: str,
    config: str,
    split: str,
    batch_size: int = 100_000,
    rows_per_chunk: int = 100_000,
    max_rows: int | None = None,
    target_ram_gb: float = 40.0,
) -> dict[str, Any]:
    parquet_files = fetch_hf_parquet_files(dataset=dataset, config=config, split=split)
    return import_hf_parquet_files_chunked(
        output_root=output_root,
        dataset=dataset,
        config=config,
        split=split,
        parquet_files=parquet_files,
        batch_size=batch_size,
        rows_per_chunk=rows_per_chunk,
        max_rows=max_rows,
        target_ram_gb=target_ram_gb,
    )


def import_hf_parquet_files_chunked(
    *,
    output_root: str | Path,
    dataset: str,
    config: str,
    split: str,
    parquet_files: list[dict[str, Any]],
    batch_size: int = 100_000,
    rows_per_chunk: int = 100_000,
    max_rows: int | None = None,
    target_ram_gb: float = 40.0,
) -> dict[str, Any]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("pyarrow is required for parquet-backed HF conversation import") from exc

    root = Path(output_root).expanduser().resolve()
    cache_root = root / "parquet_cache"
    chunks_root = root / "chunks"
    cache_root.mkdir(parents=True, exist_ok=True)
    chunks_root.mkdir(parents=True, exist_ok=True)

    batch_size = max(1, int(batch_size))
    rows_per_chunk = max(1, int(rows_per_chunk))
    total_limit = None if max_rows is None else max(0, int(max_rows))
    started_at = datetime.now(timezone.utc).isoformat()

    source_rows_seen = 0
    total_turns = 0
    chunk_rows: list[dict[str, Any]] = []
    chunk_summaries: list[dict[str, Any]] = []
    cached_files: list[dict[str, Any]] = []

    for item in parquet_files:
        if total_limit is not None and source_rows_seen >= total_limit:
            break
        local_path = _local_parquet_path(item, cache_root)
        cached_files.append({
            "filename": item.get("filename") or local_path.name,
            "path": str(local_path),
            "size": int(item.get("size") or local_path.stat().st_size if local_path.exists() else 0),
        })
        parquet = pq.ParquetFile(local_path)
        for batch in parquet.iter_batches(batch_size=batch_size):
            rows = batch.to_pylist()
            for row in rows:
                if total_limit is not None and source_rows_seen >= total_limit:
                    break
                if isinstance(row, dict):
                    chunk_rows.append({"row_idx": source_rows_seen, "row": row})
                    source_rows_seen += 1
                if len(chunk_rows) >= rows_per_chunk:
                    summary = _flush_hf_import_chunk(
                        chunk_rows,
                        output_root=chunks_root / f"chunk_{len(chunk_summaries):06d}",
                        dataset=dataset,
                        config=config,
                        split=split,
                    )
                    chunk_summaries.append(summary)
                    total_turns += int(summary.get("turn_count") or 0)
                    chunk_rows = []
            if total_limit is not None and source_rows_seen >= total_limit:
                break

    if chunk_rows:
        summary = _flush_hf_import_chunk(
            chunk_rows,
            output_root=chunks_root / f"chunk_{len(chunk_summaries):06d}",
            dataset=dataset,
            config=config,
            split=split,
        )
        chunk_summaries.append(summary)
        total_turns += int(summary.get("turn_count") or 0)

    result = {
        "ok": True,
        "schema_version": "anchorworks_hf_conversation_parquet_import@1",
        "dataset": dataset,
        "config": config,
        "split": split,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "source_root": f"hf://datasets/{dataset}/{config}/{split}",
        "source_row_count": source_rows_seen,
        "turn_count": total_turns,
        "chunk_count": len(chunk_summaries),
        "batch_size": batch_size,
        "rows_per_chunk": rows_per_chunk,
        "target_ram_gb": float(target_ram_gb),
        "parquet_file_count": len(parquet_files),
        "cached_files": cached_files,
        "chunks_root": str(chunks_root),
        "chunks": chunk_summaries,
        "writes_allowed": _conversation_flow_writes_allowed(),
    }
    _write_json(root / "manifest.json", result)
    return result


def export_conversation_flow_symbolic_sources(
    flow_root: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    source_root = Path(flow_root).expanduser().resolve()
    out_root = Path(output_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    chunk_dirs = sorted((source_root / "chunks").glob("chunk_*")) if (source_root / "chunks").exists() else []
    if not chunk_dirs:
        chunk_dirs = [source_root]

    sources: list[dict[str, Any]] = []
    total_turns = 0
    for chunk_dir in chunk_dirs:
        manifest_path = chunk_dir / "source_manifests" / "conversation_manifest.json"
        if not manifest_path.exists() and chunk_dir == source_root:
            manifest_path = source_root / "source_manifests" / "conversation_manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        turns = [turn for turn in manifest.get("turns") or [] if isinstance(turn, dict)]
        if not turns:
            continue
        source_path = out_root / f"{chunk_dir.name}.txt"
        line_count = 0
        with source_path.open("w", encoding="utf-8", newline="\n") as handle:
            for turn in turns:
                text = str(turn.get("clean_text") or turn.get("utterance") or "").strip()
                if not text:
                    continue
                speaker = str(turn.get("speaker") or turn.get("speaker_id") or "").strip()
                if speaker:
                    handle.write(f"{speaker}: {text}\n")
                else:
                    handle.write(f"{text}\n")
                line_count += 1
        total_turns += line_count
        sources.append({
            "chunk_id": chunk_dir.name,
            "source_path": str(source_path),
            "turn_count": line_count,
            "manifest_path": str(manifest_path),
        })

    result = {
        "ok": True,
        "schema_version": "anchorworks_conversation_flow_symbolic_source_export@1",
        "flow_root": str(source_root),
        "output_root": str(out_root),
        "source_count": len(sources),
        "turn_count": total_turns,
        "sources": sources,
        "writes_allowed": {
            "source_exports": True,
            "maps": False,
            "counts": False,
            "lifetime": False,
            "lexicon": False,
        },
    }
    _write_json(out_root / "manifest.json", result)
    return result


def _local_parquet_path(item: dict[str, Any], cache_root: Path) -> Path:
    url = str(item.get("url") or "")
    filename = _safe_name(str(item.get("filename") or Path(urllib.parse.urlparse(url).path).name or "shard.parquet"))
    local_path = cache_root / filename
    if local_path.exists() and local_path.stat().st_size > 0:
        return local_path
    if Path(url).exists():
        return Path(url)
    if not url:
        raise ValueError("parquet file item requires url or local path")
    urllib.request.urlretrieve(url, local_path)
    return local_path


def _flush_hf_import_chunk(
    rows: list[dict[str, Any]],
    *,
    output_root: Path,
    dataset: str,
    config: str,
    split: str,
) -> dict[str, Any]:
    payload = {"rows": rows}
    imported = import_hf_dialogue_rows(payload, output_root=output_root, dataset=dataset, config=config, split=split)
    manifest = imported.get("manifest") or {}
    artifacts = imported.get("artifacts") or {}
    return {
        "chunk_id": output_root.name,
        "source_row_count": len(rows),
        "turn_count": int(manifest.get("turn_count") or 0),
        "flow_count": int(artifacts.get("flow_count") or 0),
        "anchor_count": int(artifacts.get("anchor_count") or 0),
        "manifest_path": imported.get("manifest_path"),
        "stores": artifacts.get("stores") or {},
        "writes_allowed": imported.get("writes_allowed") or _conversation_flow_writes_allowed(),
    }


def _conversation_flow_writes_allowed() -> dict[str, bool]:
    return {
        "core_anchor_counts": False,
        "conversation_flow_counts": True,
        "speaker_turn_maps": True,
        "source_manifests": True,
        "rejected_or_unknown_lines": True,
        "truth_evidence": False,
        "lexicon": False,
        "lifetime": False,
    }


def _first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return ""


def _split_speaker(text: str, *, speaker: str = "") -> tuple[str, str]:
    clean = " ".join(str(text or "").split())
    if speaker:
        return speaker.strip(), clean
    match = re.match(r"^([A-Z][A-Z0-9 _.'-]{1,40}):\s+(.+)$", clean)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "", clean


def _clean_subtitle_text(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", str(text or ""))
    clean = re.sub(r"\{\\[^}]+\}", " ", clean)
    clean = re.sub(r"\[[^\]]*(music|applause|laughs?|sighs?|door|noise|thunder|gunshot|caption)[^\]]*\]", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\([^)]*(music|applause|laughs?|sighs?|door|noise|thunder|gunshot|caption)[^)]*\)", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bWEBVTT\b", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("._") or "source"
