import tempfile
import unittest
from pathlib import Path

from AnchorWorks.symbol_genome_pool import SymbolGenomePool
from AnchorWorks.store import LexiconStore
from AnchorWorks.app import SymbolGenomeAllocateBody, SymbolGenomeCheckpointBody, create_app


class SymbolGenomePoolTests(unittest.TestCase):
    def test_pool_starts_with_15_million_capacity_and_checkpoints_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pool = SymbolGenomePool(Path(temp_dir) / "pool")

            status = pool.status()
            self.assertEqual(status["capacity"], 15_000_000)
            self.assertEqual(status["next_index"], 0)
            self.assertEqual(status["remaining"], 15_000_000)
            self.assertFalse(status["lexicon_pack"])

            first = pool.allocate("newton laws of motion", authority="phrase")
            second = pool.allocate("separation of powers", authority="phrase")
            self.assertNotEqual(first["hex"], second["hex"])
            self.assertEqual(first["allocation_index"], 0)
            self.assertEqual(second["allocation_index"], 1)
            self.assertEqual(len(first["symbol_bytes"]), 5)
            self.assertEqual(first["symbol_bytes"][0], 0x28)

            checkpoint = pool.checkpoint("test checkpoint")
            self.assertEqual(checkpoint["next_index"], 2)
            self.assertEqual(checkpoint["assigned_count"], 2)
            self.assertEqual(checkpoint["last_checkpoint_reason"], "test checkpoint")

            reopened = SymbolGenomePool(Path(temp_dir) / "pool")
            self.assertEqual(reopened.status()["next_index"], 2)

    def test_lexicon_store_exposes_symbol_genome_status_and_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = LexiconStore(Path(temp_dir))

            status = store.symbol_genome_status()
            self.assertEqual(status["capacity"], 15_000_000)
            self.assertEqual(status["remaining"], 15_000_000)
            self.assertFalse(status["lexicon_pack"])

            allocated = store.allocate_symbol_genome_identity("alpha beta", authority="phrase")
            self.assertEqual(allocated["allocation_index"], 0)
            checkpoint = store.checkpoint_symbol_genome("after alpha beta")
            self.assertEqual(checkpoint["next_index"], 1)
            self.assertEqual(checkpoint["last_checkpoint_reason"], "after alpha beta")

    def test_symbol_genome_api_routes_expose_status_allocate_and_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(Path(temp_dir))
            status_route = next(route for route in app.routes if getattr(route, "path", "") == "/api/symbol-genome/status")
            allocate_route = next(route for route in app.routes if getattr(route, "path", "") == "/api/symbol-genome/allocate")
            checkpoint_route = next(route for route in app.routes if getattr(route, "path", "") == "/api/symbol-genome/checkpoint")

            status = status_route.endpoint()
            self.assertEqual(status["capacity"], 15_000_000)

            allocated = allocate_route.endpoint(SymbolGenomeAllocateBody(label="alpha beta", authority="phrase"))
            self.assertEqual(allocated["allocation_index"], 0)

            checkpoint = checkpoint_route.endpoint(SymbolGenomeCheckpointBody(reason="ui checkpoint"))
            self.assertEqual(checkpoint["next_index"], 1)
            self.assertEqual(checkpoint["last_checkpoint_reason"], "ui checkpoint")


if __name__ == "__main__":
    unittest.main()
