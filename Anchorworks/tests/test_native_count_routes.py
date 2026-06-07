from __future__ import annotations

from pathlib import Path
import json

from fastapi.testclient import TestClient

from AnchorWorks.app import create_app


def test_binary_count_build_route_fails_hard_until_native_orchestrator_exists(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    response = client.post("/api/symbol-counts/binary/build", json={"limit": None, "generation": 0})

    assert response.status_code == 410
    assert "native-only" in response.json()["detail"]


def test_mapping_run_route_uses_native_user_count_pipeline(tmp_path: Path) -> None:
    canonical = tmp_path / "Canonical"
    canonical.mkdir()
    (canonical / "canonical_F.json").write_text(
        json.dumps([{"word": "force", "symbol": "0x0000000001"}]),
        encoding="utf-8",
    )
    structural = tmp_path / "Structural"
    structural.mkdir()
    (structural / "structural.json").write_text("[]", encoding="utf-8")
    source = tmp_path / "source.txt"
    source.write_text("force blorxium", encoding="utf-8")
    client = TestClient(create_app(tmp_path))

    response = client.post(
        "/api/lexicon/mapping/run",
        json={"file_path": str(source), "window_radius": 1, "generation": 0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"] == "native_cpp_intake_text"
    assert payload["raw_text_in_count_spine"] is False
    assert payload["receipt"]["updated_cell_count"] == 2


def test_legacy_intake_map_route_now_uses_native_user_count_pipeline(tmp_path: Path) -> None:
    canonical = tmp_path / "Canonical"
    canonical.mkdir()
    (canonical / "canonical_F.json").write_text(
        json.dumps([{"word": "force", "symbol": "0x0000000001"}]),
        encoding="utf-8",
    )
    structural = tmp_path / "Structural"
    structural.mkdir()
    (structural / "structural.json").write_text("[]", encoding="utf-8")
    client = TestClient(create_app(tmp_path))

    response = client.post(
        "/api/lexicon/intake/map",
        json={"source_name": "chat_doc.txt", "content": "force blorxium", "intake_edits": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"] == "native_cpp_intake_text"
    assert payload["raw_text_in_count_spine"] is False
    assert payload["receipt"]["updated_cell_count"] == 2


def test_mapping_run_route_accepts_directory_for_native_user_count_pipeline(tmp_path: Path) -> None:
    canonical = tmp_path / "Canonical"
    canonical.mkdir()
    (canonical / "canonical_F.json").write_text(
        json.dumps([{"word": "force", "symbol": "0x0000000001"}]),
        encoding="utf-8",
    )
    structural = tmp_path / "Structural"
    structural.mkdir()
    (structural / "structural.json").write_text("[]", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "one.txt").write_text("force blorxium", encoding="utf-8")
    (docs / "two.md").write_text("force graph", encoding="utf-8")
    client = TestClient(create_app(tmp_path))

    response = client.post(
        "/api/lexicon/mapping/run",
        json={"file_path": str(docs), "window_radius": 1, "generation": 0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"] == "native_cpp_directory_mapping"
    assert payload["ok"] is True
    assert payload["receipt"]["command"] == "intake-dir"
    assert payload["file_count"] == 2


def test_directory_mapping_reports_and_skips_non_source_paths(tmp_path: Path) -> None:
    canonical = tmp_path / "Canonical"
    canonical.mkdir()
    (canonical / "canonical_F.json").write_text(
        json.dumps([{"word": "force", "symbol": "0x0000000001"}]),
        encoding="utf-8",
    )
    structural = tmp_path / "Structural"
    structural.mkdir()
    (structural / "structural.json").write_text("[]", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "source.txt").write_text("force blorxium", encoding="utf-8")
    (docs / "image.png").write_bytes(b"\x89PNG\r\n")
    generated = docs / "State" / "cache"
    generated.mkdir(parents=True)
    (generated / "generated.txt").write_text("force should skip", encoding="utf-8")
    client = TestClient(create_app(tmp_path))

    response = client.post(
        "/api/lexicon/mapping/run",
        json={"file_path": str(docs), "window_radius": 1, "generation": 0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"] == "native_cpp_directory_mapping"
    assert payload["receipt"]["command"] == "intake-dir"
    assert payload["file_count"] == 1
    assert payload["skipped_file_count"] == 2
    assert sorted(row["reason"] for row in payload["skipped_files"]) == [
        "generated_runtime_path",
        "unsupported_suffix",
    ]


def test_legacy_observed_map_api_mouths_are_locked(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    get_routes = [
        "/api/lexicon/observed-maps",
        "/api/lexicon/observed-map/example.observed.json",
        "/api/lexicon/symbolic-maps",
        "/api/lexicon/symbolic-map/example.awsm",
        "/api/awsg/graphs",
        "/api/awsg/graph/example",
        "/api/awsg/graph/example/slice",
    ]
    for route in get_routes:
        response = client.get(route)
        assert response.status_code == 410, route
        assert "legacy-observed-map" in response.json()["detail"]

    post_routes = [
        "/api/resonance/source-local/build",
        "/api/flat-documents/runtime/build",
    ]
    for route in post_routes:
        response = client.post(route, json={"observed_map_name": "example.observed.json"})
        assert response.status_code == 410, route
        assert "legacy-observed-map" in response.json()["detail"]
