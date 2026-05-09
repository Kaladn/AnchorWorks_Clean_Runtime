from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


OCCURRENCE_CONTRACT = "anchorworks_symbol_occurrence@1"
POSITIONAL_RESONANCE_CONTRACT = "anchorworks_positional_resonance@1"
DIRECTIONAL_RESONANCE_CONTRACT = "anchorworks_directional_resonance@1"
CONTEXT_CLOUD_CONTRACT = "anchorworks_context_cloud@1"
RESONANCE_SUMMARY_CONTRACT = "anchorworks_source_local_resonance_summary@1"
DEFAULT_CLOUD_THRESHOLD = 0.3
DEFAULT_TOP_K = 12


def source_id_for_observed_map(payload: dict[str, Any]) -> str:
    seed = str(payload.get("source_path") or payload.get("source_name") or payload.get("saved_map_name") or "source")
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def safe_source_stem(payload: dict[str, Any]) -> str:
    value = str(payload.get("source_name") or payload.get("saved_map_name") or payload.get("source_path") or "source")
    stem = Path(value).stem or "source"
    safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in stem).strip("._")
    return safe or "source"


def build_source_local_resonance_index(
    observed_map: dict[str, Any],
    *,
    cloud_threshold: float = DEFAULT_CLOUD_THRESHOLD,
    top_k: int = DEFAULT_TOP_K,
) -> dict[str, Any]:
    source_id = source_id_for_observed_map(observed_map)
    window_radius = int(observed_map.get("window_radius", 6) or 6)
    occurrence_records = build_occurrence_records(observed_map, source_id=source_id)
    positional_profiles = build_positional_profiles(
        observed_map.get("co_occurrence_counts") or [],
        source_id=source_id,
        window_radius=window_radius,
        top_k=top_k,
    )
    directional_resonance = build_directional_resonance(
        observed_map.get("co_occurrence_counts") or [],
        source_id=source_id,
        top_k=top_k,
    )
    context_clouds = build_context_clouds(
        observed_map.get("co_occurrence_counts") or [],
        source_id=source_id,
        threshold=cloud_threshold,
        top_k=top_k,
    )
    summary = {
        "contract": RESONANCE_SUMMARY_CONTRACT,
        "source_id": source_id,
        "source_name": observed_map.get("source_name") or "",
        "source_path": observed_map.get("source_path") or "",
        "scope": "source_local",
        "window_radius": window_radius,
        "occurrence_records": len(occurrence_records),
        "positional_profile_rows": len(positional_profiles),
        "directional_resonance_rows": len(directional_resonance),
        "context_cloud_rows": len(context_clouds),
        "cloud_threshold": cloud_threshold,
        "top_k": top_k,
        "writes_allowed": {
            "maps": False,
            "counts": False,
            "lifetime": False,
            "lexicon": False,
        },
        "authority": "source_local_retrieval_shape",
        "law": "Resonance finds neighborhoods; occurrences prove addresses.",
    }
    return {
        "source_id": source_id,
        "safe_source_stem": safe_source_stem(observed_map),
        "occurrences": occurrence_records,
        "positional_profiles": positional_profiles,
        "directional_resonance": directional_resonance,
        "context_clouds": context_clouds,
        "summary": summary,
    }


def build_occurrence_records(observed_map: dict[str, Any], *, source_id: str) -> list[dict[str, Any]]:
    source_name = str(observed_map.get("source_name") or "")
    source_path = str(observed_map.get("source_path") or "")
    rows: list[dict[str, Any]] = []
    for index, occurrence in enumerate(observed_map.get("occurrences") or []):
        if not isinstance(occurrence, dict):
            continue
        anchor = str(occurrence.get("anchor") or "")
        if not anchor:
            continue
        paragraph_id = int(occurrence.get("paragraph_id", 0) or 0)
        position = int(occurrence.get("position", index) or 0)
        occurrence_id = _stable_id("occ", source_id, paragraph_id, position, anchor)
        locator = {
            "source": source_name,
            "source_path": source_path,
            "paragraph_id": paragraph_id,
            "token_index": position,
            "char_start": int(occurrence.get("start", 0) or 0),
            "char_end": int(occurrence.get("end", 0) or 0),
            "line_start": occurrence.get("line_start"),
            "line_end": occurrence.get("line_end"),
            "line_reason": "line_locator_not_available_in_current_map"
            if occurrence.get("line_start") is None and occurrence.get("line_end") is None
            else "",
        }
        window = occurrence.get("window") if isinstance(occurrence.get("window"), dict) else {}
        rows.append({
            "contract": OCCURRENCE_CONTRACT,
            "occurrence_id": occurrence_id,
            "source_id": source_id,
            "source_name": source_name,
            "source_path": source_path,
            "paragraph_id": paragraph_id,
            "token_index": position,
            "anchor_position": position,
            "surface": occurrence.get("surface") or anchor,
            "anchor": anchor,
            "symbol": anchor,
            "observed_anchor": occurrence.get("observed_anchor") or anchor,
            "kind": occurrence.get("kind") or "anchor",
            "authority": "source_local_occurrence",
            "scope": "source_local",
            "count_eligible": bool(occurrence.get("count_eligible", True)),
            "evidence_eligible": True,
            "retrieval_eligible": True,
            "speak_eligible": False,
            "window_radius": _max_window_radius(window),
            "left_window_symbols": _window_side(window, before=True),
            "right_window_symbols": _window_side(window, before=False),
            "locator": locator,
        })
    return rows


def build_positional_profiles(
    relation_rows: list[dict[str, Any]],
    *,
    source_id: str,
    window_radius: int,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    by_anchor_offset: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in relation_rows:
        anchor, offset, neighbor, observations = _relation_parts(row)
        if not anchor or not offset or not neighbor or observations <= 0:
            continue
        if offset == "0" or abs(int(offset)) > window_radius:
            continue
        by_anchor_offset[(anchor, offset)][neighbor] += observations

    out: list[dict[str, Any]] = []
    for (anchor, offset), neighbors in sorted(by_anchor_offset.items()):
        max_count = max(neighbors.values()) if neighbors else 0
        ranked = sorted(neighbors.items(), key=lambda item: (-item[1], item[0]))[:top_k]
        for rank, (neighbor, observations) in enumerate(ranked, start=1):
            out.append({
                "contract": POSITIONAL_RESONANCE_CONTRACT,
                "profile_id": _stable_id("pos", source_id, anchor, offset, neighbor),
                "source_id": source_id,
                "scope": "source_local",
                "center_anchor": anchor,
                "center_symbol": anchor,
                "offset": offset,
                "neighbor_anchor": neighbor,
                "neighbor_symbol": neighbor,
                "observations": int(observations),
                "support_occurrence_count": int(observations),
                "score": _safe_ratio(observations, max_count),
                "rank_at_offset": rank,
                "window_radius": window_radius,
                "retrieval_eligible": True,
                "evidence_eligible": False,
                "speak_eligible": False,
                "reason": "positional resonance guides retrieval; occurrence records provide proof.",
            })
    return out


def build_directional_resonance(
    relation_rows: list[dict[str, Any]],
    *,
    source_id: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    totals: Counter[str] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()
    pair_offsets: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in relation_rows:
        anchor, offset, neighbor, observations = _relation_parts(row)
        if not anchor or not offset or not neighbor or observations <= 0:
            continue
        totals[anchor] += observations
        pair_counts[(anchor, neighbor)] += observations
        pair_offsets[(anchor, neighbor)][offset] += observations

    grouped: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for (anchor, neighbor), count in pair_counts.items():
        grouped[anchor].append((neighbor, count))

    out: list[dict[str, Any]] = []
    for anchor, neighbors in sorted(grouped.items()):
        for neighbor, count in sorted(neighbors, key=lambda item: (-item[1], item[0]))[:top_k]:
            offsets = [
                offset
                for offset, _ in sorted(pair_offsets[(anchor, neighbor)].items(), key=lambda item: (-item[1], item[0]))
            ]
            out.append({
                "contract": DIRECTIONAL_RESONANCE_CONTRACT,
                "resonance_id": _stable_id("dir", source_id, anchor, neighbor),
                "source_id": source_id,
                "scope": "source_local",
                "from_anchor": anchor,
                "from_symbol": anchor,
                "to_anchor": neighbor,
                "to_symbol": neighbor,
                "directional_score": _safe_ratio(count, totals[anchor]),
                "method": "source_local_positional_frequency@1",
                "support_offsets": offsets,
                "support_occurrence_count": int(count),
                "retrieval_eligible": True,
                "evidence_eligible": False,
                "speak_eligible": False,
                "reason": "directional resonance ranks expansion candidates; it is not citation proof.",
            })
    return out


def build_context_clouds(
    relation_rows: list[dict[str, Any]],
    *,
    source_id: str,
    threshold: float = DEFAULT_CLOUD_THRESHOLD,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    member_counts: dict[str, Counter[str]] = defaultdict(Counter)
    member_offsets: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in relation_rows:
        anchor, offset, neighbor, observations = _relation_parts(row)
        if not anchor or not offset or not neighbor or observations <= 0:
            continue
        member_counts[anchor][neighbor] += observations
        member_offsets[(anchor, neighbor)][offset] += observations

    clouds: list[dict[str, Any]] = []
    for anchor, counter in sorted(member_counts.items()):
        max_count = max(counter.values()) if counter else 0
        members: list[dict[str, Any]] = []
        for neighbor, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
            strength = _safe_ratio(count, max_count)
            if strength < threshold:
                continue
            offsets = [
                offset
                for offset, _ in sorted(member_offsets[(anchor, neighbor)].items(), key=lambda item: (-item[1], item[0]))
            ]
            members.append({
                "anchor": neighbor,
                "symbol": neighbor,
                "strength": strength,
                "best_offsets": offsets[:3],
                "support_occurrence_count": int(count),
            })
            if len(members) >= top_k:
                break
        if not members:
            continue
        clouds.append({
            "contract": CONTEXT_CLOUD_CONTRACT,
            "cloud_id": _stable_id("cloud", source_id, anchor),
            "source_id": source_id,
            "scope": "source_local",
            "center_anchor": anchor,
            "center_symbol": anchor,
            "threshold": threshold,
            "members": members,
            "retrieval_eligible": True,
            "evidence_eligible": False,
            "speak_eligible": False,
            "reason": "context cloud membership expands search only; it cannot cite.",
        })
    return clouds


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def _relation_parts(row: dict[str, Any]) -> tuple[str, str, str, int]:
    anchor = row.get("anchor")
    offset = row.get("offset")
    neighbor = row.get("neighbor")
    observations = int(row.get("observations", 0) or 0)
    if not isinstance(anchor, str) or not isinstance(offset, str) or not isinstance(neighbor, str):
        return "", "", "", 0
    try:
        int(offset)
    except ValueError:
        return "", "", "", 0
    return anchor, offset, neighbor, observations


def _stable_id(prefix: str, *parts: object) -> str:
    seed = "::".join(str(part) for part in parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _safe_ratio(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(float(value) / float(total), 6)


def _max_window_radius(window: dict[str, Any]) -> int:
    distances: list[int] = []
    for key in window:
        try:
            distances.append(abs(int(key)))
        except (TypeError, ValueError):
            continue
    return max(distances) if distances else 0


def _window_side(window: dict[str, Any], *, before: bool) -> list[str]:
    values: list[tuple[int, str]] = []
    for key, value in window.items():
        if value is None:
            continue
        try:
            offset = int(key)
        except (TypeError, ValueError):
            continue
        if offset == 0:
            continue
        if before and offset >= 0:
            continue
        if not before and offset <= 0:
            continue
        values.append((offset, str(value)))
    values.sort(key=lambda item: item[0])
    return [value for _, value in values]
