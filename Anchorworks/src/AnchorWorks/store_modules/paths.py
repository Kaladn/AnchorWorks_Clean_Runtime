from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def anchor_maps_root_for(data_root: Path) -> Path:
    configured = os.environ.get("ANCHORWORKS_MAP_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path(data_root).expanduser().resolve().parent / "AnchorMaps").resolve()


@dataclass
class StorePaths:
    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root).expanduser().resolve()
        self.canonical_dir = self.root / "Canonical"
        self.spare_dir = self.root / "Spare_Slots"
        self.spare_slots_path = self.spare_dir / "spare_slots.json"
        self.structural_file = self.root / "Structural" / "structural.json"
        self.state_dir = self.root / "State"
        self.user_state_dir = self.state_dir / "user"
        self.user_lexicon_dir = self.user_state_dir / "user_lexicon"
        self.user_counts_dir = self.user_state_dir / "user_counts"
        self.chat_counts_dir = self.user_state_dir / "chat_counts"
        self.ingest_staging_dir = self.user_state_dir / "ingest_staging"
        self.rejected_or_literal_clusters_dir = self.user_state_dir / "rejected_or_literal_clusters"
        self.anchor_maps_root = anchor_maps_root_for(self.root)
        self.observed_maps_dir = self.anchor_maps_root / "observed_maps"
        self.symbolic_maps_dir = self.anchor_maps_root / "symbolic_maps"
        self.misspelled_reviews_dir = self.state_dir / "misspelled_reviews"
        self.temp_lexicons_dir = self.state_dir / "temp_lexicons" / "source_local"
        self.source_local_symbol_counts_dir = self.state_dir / "source_local_symbol_counts"
        self.symbol_counts_binary_dir = self.state_dir / "symbol_counts_binary"
        self.symbol_streams_dir = self.state_dir / "symbol_streams"
        self.source_local_occurrences_dir = self.state_dir / "source_local_occurrences"
        self.source_local_resonance_dir = self.state_dir / "source_local_resonance"
        self.visual_intake_dir = self.state_dir / "visual_intake"
        self.visual_intake_packets_dir = self.visual_intake_dir / "packets"
        self.visual_intake_manifests_dir = self.visual_intake_dir / "manifests"
        self.visual_intake_region_maps_dir = self.visual_intake_dir / "region_maps"
        self.visual_intake_recognition_layers_dir = self.visual_intake_dir / "recognition_layers"
        self.flat_documents_dir = self.state_dir / "flat_documents"
        self.flat_documents_raw_dir = self.flat_documents_dir / "raw"
        self.flat_documents_symbolic_dir = self.flat_documents_dir / "symbolic"
        self.flat_documents_block_index_dir = self.flat_documents_dir / "block_index"
        self.flat_documents_visual_links_dir = self.flat_documents_dir / "visual_links"
        self.flat_documents_occurrence_index_dir = self.flat_documents_dir / "occurrence_index"
        self.flat_documents_local_overlays_dir = self.flat_documents_dir / "local_overlays"
        self.intake_uploads_dir = self.state_dir / "intake_uploads"
        self.lifetime_counts_path = self.state_dir / "lifetime_co_occurrence_counts.json"
        self.missing_anchor_registry_path = self.state_dir / "missing_anchor_registry.json"
        self.unmatched_path = self.state_dir / "unmatched_words.json"
        self.pending_path = self.state_dir / "pending_words.json"
        self.ignored_path = self.state_dir / "ignored_words.json"
        self.custom_entries_path = self.user_state_dir / "custom_entries.json"
        self.user_lexicon_path = self.user_lexicon_dir / "anchors.json"
        self.user_counts_path = self.user_counts_dir / "lifetime_co_occurrence_counts.json"
        self.chat_counts_path = self.chat_counts_dir / "chat_co_occurrence_counts.json"
        self.ingest_staging_manifest_path = self.ingest_staging_dir / "manifest.json"
        self.rejected_or_literal_clusters_path = self.rejected_or_literal_clusters_dir / "clusters.json"

    def directory_paths(self) -> tuple[Path, ...]:
        return (
            self.spare_dir,
            self.state_dir,
            self.user_state_dir,
            self.user_lexicon_dir,
            self.user_counts_dir,
            self.chat_counts_dir,
            self.ingest_staging_dir,
            self.rejected_or_literal_clusters_dir,
            self.observed_maps_dir,
            self.symbolic_maps_dir,
            self.misspelled_reviews_dir,
            self.temp_lexicons_dir,
            self.source_local_symbol_counts_dir,
            self.symbol_counts_binary_dir,
            self.symbol_streams_dir,
            self.source_local_occurrences_dir,
            self.source_local_resonance_dir,
            self.visual_intake_packets_dir,
            self.visual_intake_manifests_dir,
            self.visual_intake_region_maps_dir,
            self.visual_intake_recognition_layers_dir,
            self.flat_documents_raw_dir,
            self.flat_documents_symbolic_dir,
            self.flat_documents_block_index_dir,
            self.flat_documents_visual_links_dir,
            self.flat_documents_occurrence_index_dir,
            self.flat_documents_local_overlays_dir,
            self.intake_uploads_dir,
        )

    def ensure_directories(self) -> None:
        for path in self.directory_paths():
            path.mkdir(parents=True, exist_ok=True)
