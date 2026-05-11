from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any


class ObservedMapGraphViewer:
    def __init__(self, graph_roots: list[Path]) -> None:
        self.graph_roots = [Path(root).expanduser().resolve() for root in graph_roots]

    def list_graphs(self) -> dict[str, Any]:
        graphs: list[dict[str, Any]] = []
        for graph_root in self.graph_roots:
            manifest_path = graph_root / "graph_manifest.json"
            if not manifest_path.is_file():
                continue
            manifest = _read_json(manifest_path)
            graphs.append(_graph_summary(manifest, graph_root))
        return {
            "ok": True,
            "schema_version": "anchorworks_awsg_graph_listing@1",
            "graph_count": len(graphs),
            "graphs": sorted(graphs, key=lambda row: str(row.get("graph_name") or "")),
            "read_only": True,
        }

    def graph_summary(self, graph_name: str) -> dict[str, Any]:
        graph_root, manifest = self._load_manifest(graph_name)
        summary = _graph_summary(manifest, graph_root)
        summary["ok"] = True
        return summary

    def graph_slice(self, graph_name: str, *, node_id: str = "", radius: int = 1, limit: int = 500) -> dict[str, Any]:
        graph_root, manifest = self._load_manifest(graph_name)
        nodes = _read_jsonl(graph_root / "nodes.jsonl")
        edges = _read_jsonl(graph_root / "edges.jsonl")
        node_by_id = {str(node.get("node_id") or ""): node for node in nodes}
        if not node_by_id:
            return _empty_slice(manifest, graph_name, node_id, radius, limit)

        selected_id = node_id if node_id in node_by_id else _default_node_id(nodes)
        capped_limit = max(1, min(int(limit or 500), 2000))
        capped_radius = max(0, min(int(radius or 0), 4))
        selected_ids = _walk_node_ids(selected_id, edges, capped_radius, capped_limit)
        selected_nodes = [node_by_id[item] for item in selected_ids if item in node_by_id]
        selected_set = {str(node.get("node_id") or "") for node in selected_nodes}
        selected_edges = [
            edge for edge in edges
            if str(edge.get("from") or "") in selected_set and str(edge.get("to") or "") in selected_set
        ]
        return {
            "ok": True,
            "schema_version": "anchorworks_awsg_graph_slice@1",
            "graph_name": manifest.get("graph_name") or graph_name,
            "source_id": manifest.get("source_id") or "",
            "nodes": selected_nodes,
            "edges": selected_edges[: max(0, capped_limit * 3)],
            "slice": {
                "selected_node_id": selected_id,
                "radius": capped_radius,
                "limit": capped_limit,
                "node_count": len(selected_nodes),
                "edge_count": min(len(selected_edges), max(0, capped_limit * 3)),
                "read_only": True,
            },
            "writes_allowed": manifest.get("writes_allowed") or {},
        }

    def _load_manifest(self, graph_name: str) -> tuple[Path, dict[str, Any]]:
        clean_name = Path(str(graph_name or "")).name
        for graph_root in self.graph_roots:
            manifest_path = graph_root / "graph_manifest.json"
            if not manifest_path.is_file():
                continue
            manifest = _read_json(manifest_path)
            if str(manifest.get("graph_name") or "") == clean_name:
                return graph_root, manifest
        raise FileNotFoundError(clean_name)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _graph_summary(manifest: dict[str, Any], graph_root: Path) -> dict[str, Any]:
    return {
        "graph_name": manifest.get("graph_name") or graph_root.name,
        "source_id": manifest.get("source_id") or "",
        "source_path": manifest.get("source_path") or "",
        "source_hash": manifest.get("source_hash") or "",
        "node_count": int(manifest.get("node_count") or 0),
        "edge_count": int(manifest.get("edge_count") or 0),
        "writes_allowed": manifest.get("writes_allowed") or {},
        "graph_root": str(graph_root),
        "read_only": True,
    }


def _default_node_id(nodes: list[dict[str, Any]]) -> str:
    for node in nodes:
        if node.get("node_type") == "document":
            return str(node.get("node_id") or "")
    return str(nodes[0].get("node_id") or "")


def _walk_node_ids(start_id: str, edges: list[dict[str, Any]], radius: int, limit: int) -> list[str]:
    neighbors: dict[str, list[str]] = {}
    for edge in edges:
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        if not source or not target:
            continue
        neighbors.setdefault(source, []).append(target)
        neighbors.setdefault(target, []).append(source)

    seen = {start_id}
    ordered = [start_id]
    queue: deque[tuple[str, int]] = deque([(start_id, 0)])
    while queue and len(ordered) < limit:
        current, depth = queue.popleft()
        if depth >= radius:
            continue
        for neighbor in sorted(neighbors.get(current, [])):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            ordered.append(neighbor)
            if len(ordered) >= limit:
                break
            queue.append((neighbor, depth + 1))
    return ordered


def _empty_slice(manifest: dict[str, Any], graph_name: str, node_id: str, radius: int, limit: int) -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": "anchorworks_awsg_graph_slice@1",
        "graph_name": manifest.get("graph_name") or graph_name,
        "source_id": manifest.get("source_id") or "",
        "nodes": [],
        "edges": [],
        "slice": {
            "selected_node_id": node_id,
            "radius": radius,
            "limit": limit,
            "node_count": 0,
            "edge_count": 0,
            "read_only": True,
        },
        "writes_allowed": manifest.get("writes_allowed") or {},
    }
