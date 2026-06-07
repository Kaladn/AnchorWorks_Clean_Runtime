from __future__ import annotations

from .store_support import *
from .store_runtime import (
    CountsMixin,
    IntakeMixin,
    InventoryMixin,
    LexiconMixin,
    StateMixin,
    VisualFlatMixin,
)


class LexiconStore(
    VisualFlatMixin,
    InventoryMixin,
    CountsMixin,
    IntakeMixin,
    LexiconMixin,
    StateMixin,
):
    def __init__(self, data_root: Path) -> None:
        self.root = Path(data_root).expanduser().resolve()
        if self.root.name.lower() == "anchorworks" and self.root.parent.name == "AnchorWorks_Clean_Runtime":
            raise RuntimeError(
                "code folder cannot be used as AnchorWorks data root; "
                "use D:\\AnchorWorks_Clean_Runtime or an explicit temp/integration root"
            )
        self.paths = StorePaths(self.root)
        self.canonical_dir = self.root / "Canonical"
        self.spare_dir = self.root / "Spare_Slots"
        self.spare_slots_path = self.spare_dir / "spare_slots.json"
        self.structural_file = self.root / "Structural" / "structural.json"
        self.state_dir = self.root / "State"
        self.user_state_dir = self.state_dir / "user"
        self.user_lexicon_dir = self.user_state_dir / "user_lexicon"
        self.user_counts_dir = self.user_state_dir / "user_counts"
        self.chat_logs_dir = self.user_state_dir / "chat_logs"
        self.chat_log_receipts_dir = self.chat_logs_dir / "receipts"
        self.chat_log_prepared_dir = self.chat_logs_dir / "prepared"
        self.ingest_staging_dir = self.user_state_dir / "ingest_staging"
        self.rejected_or_literal_clusters_dir = self.user_state_dir / "rejected_or_literal_clusters"
        self.anchor_maps_root = _anchor_maps_root_for(self.root)
        self.observed_maps_dir = self.anchor_maps_root / "observed_maps"
        self.symbolic_maps_dir = self.anchor_maps_root / "symbolic_maps"
        self.misspelled_reviews_dir = self.state_dir / "misspelled_reviews"
        self.temp_lexicons_dir = self.state_dir / "temp_lexicons" / "source_local"
        self.source_local_symbol_counts_dir = self.state_dir / "source_local_symbol_counts"
        self.canonical_symbol_counts_binary_dir = self.state_dir / "symbol_counts_binary"
        self.symbol_counts_binary_dir = self.user_counts_dir / "symbol_counts_binary"
        self.user_counts_acknowledgement_path = self.symbol_counts_binary_dir / "user_count_acknowledgement.json"
        self.symbol_genome_pool_dir = self.user_lexicon_dir / "symbol_genome_pool"
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
        self.phrase_candidates_dir = self.state_dir / "phrase_candidates"
        self.intake_uploads_dir = self.state_dir / "intake_uploads"
        self.missing_anchor_registry_path = self.state_dir / "missing_anchor_registry.json"
        self.unmatched_path = self.state_dir / "unmatched_words.json"
        self.pending_path = self.state_dir / "pending_words.json"
        self.ignored_path = self.state_dir / "ignored_words.json"
        self.custom_entries_path = self.user_state_dir / "custom_entries.json"
        self.user_lexicon_path = self.user_lexicon_dir / "anchors.json"
        self.ingest_staging_manifest_path = self.ingest_staging_dir / "manifest.json"
        self.rejected_or_literal_clusters_path = self.rejected_or_literal_clusters_dir / "clusters.json"
        self._known_anchor_index: set[str] | None = None
        self._canonical_anchor_index: set[str] | None = None
        self._canonical_symbol_index: dict[str, str] | None = None
        self._known_anchor_spell_index: dict[tuple[str, tuple[bool, int], int], list[str]] | None = None
        self._spare_entries_cache: list[dict[str, Any]] | None = None
        self._spare_entries_cache_key: tuple[tuple[str, int | None, int | None], ...] | None = None
        self._lock = threading.RLock()
        self.authority = AuthorityStore(self)
        self.evidence = EvidenceStore(self)
        self.memory = MemoryStore(self)
        self.intake_power = IntakeStore(self)
        self.visual = VisualStore(self)
        self.admin = AdminStore(self)
        self.phrases = PhraseLexiconStore(self.root, self)

        self.spare_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.user_state_dir.mkdir(parents=True, exist_ok=True)
        self.user_lexicon_dir.mkdir(parents=True, exist_ok=True)
        self.user_counts_dir.mkdir(parents=True, exist_ok=True)
        self.chat_logs_dir.mkdir(parents=True, exist_ok=True)
        self.chat_log_receipts_dir.mkdir(parents=True, exist_ok=True)
        self.chat_log_prepared_dir.mkdir(parents=True, exist_ok=True)
        self.ingest_staging_dir.mkdir(parents=True, exist_ok=True)
        self.rejected_or_literal_clusters_dir.mkdir(parents=True, exist_ok=True)
        self.observed_maps_dir.mkdir(parents=True, exist_ok=True)
        self.symbolic_maps_dir.mkdir(parents=True, exist_ok=True)
        self.misspelled_reviews_dir.mkdir(parents=True, exist_ok=True)
        self.temp_lexicons_dir.mkdir(parents=True, exist_ok=True)
        self.source_local_symbol_counts_dir.mkdir(parents=True, exist_ok=True)
        self.canonical_symbol_counts_binary_dir.mkdir(parents=True, exist_ok=True)
        self.symbol_counts_binary_dir.mkdir(parents=True, exist_ok=True)
        self.symbol_genome_pool_dir.mkdir(parents=True, exist_ok=True)
        self.symbol_streams_dir.mkdir(parents=True, exist_ok=True)
        self.source_local_occurrences_dir.mkdir(parents=True, exist_ok=True)
        self.source_local_resonance_dir.mkdir(parents=True, exist_ok=True)
        self.visual_intake_packets_dir.mkdir(parents=True, exist_ok=True)
        self.visual_intake_manifests_dir.mkdir(parents=True, exist_ok=True)
        self.visual_intake_region_maps_dir.mkdir(parents=True, exist_ok=True)
        self.visual_intake_recognition_layers_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_raw_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_symbolic_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_block_index_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_visual_links_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_occurrence_index_dir.mkdir(parents=True, exist_ok=True)
        self.flat_documents_local_overlays_dir.mkdir(parents=True, exist_ok=True)
        self.phrase_candidates_dir.mkdir(parents=True, exist_ok=True)
        self.intake_uploads_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_state_file(self.unmatched_path, [])
        self._ensure_state_file(self.pending_path, [])
        self._ensure_state_file(self.ignored_path, [])
        self._ensure_state_file(self.missing_anchor_registry_path, [])
        self._ensure_state_file(self.custom_entries_path, {})
        self._ensure_state_file(self.user_lexicon_path, [])
        self._ensure_state_file(self.ingest_staging_manifest_path, {"items": []})
        self._ensure_state_file(self.rejected_or_literal_clusters_path, [])
