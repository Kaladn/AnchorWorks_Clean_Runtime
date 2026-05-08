# Spare Slots

`spare_slots.json` is the local spare symbol pool used when assigning new anchors.

The full single-file local pool is not committed because it is too large for normal GitHub use. Instead, GitHub tracks `pool_*.json` shard files when they are generated from the same slot records.

The tracked `spare_slots.example.json` is only a shape marker. Production expansion uses either local `spare_slots.json` or tracked `pool_*.json` shards.

