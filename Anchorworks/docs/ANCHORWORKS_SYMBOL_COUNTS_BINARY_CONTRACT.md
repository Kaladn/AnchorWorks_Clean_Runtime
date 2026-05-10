# AnchorWorks Symbol Counts Binary Contract

Status: v0 implementation target

AnchorWorks adopts the PBHMS storage instinct, not its payload.

```text
PBHMS gives:
append-only discipline
WAL
CRC
binary records
index direction
dirty recovery
hot-cache direction

AnchorWorks defines:
symbol relation cells
source-local evidence rules
promotion gates
renderer edge decoding
```

## Core Law

```text
Symbol is identity.
String is display.
Canonical remains authority.
Binary counts are runtime memory.
Promotion remains above storage.
```

## First Implementation Scope

The first binary target is intentionally small:

```text
State/symbol_counts_binary/
  cells/
  wal.bin
  indexes/
  metadata.json
```

It must prove:

```text
write one symbol cell
read one symbol cell
merge counts into one symbol cell
detect CRC corruption
serve neighbors to Python
```

No B+tree, mmap, Bloom filter, compression, or C spine is required in v0.

## AWSC Cell Format v1

All multi-byte values are big endian.

Header:

```text
magic                4 bytes   AWSC
version              uint16
header_size          uint16
symbol               5 bytes
flags                uint8
anchor_observations  uint64
relation_count       uint32
payload_crc32        uint32
reserved             8 bytes
```

Relation row:

```text
offset               int8
neighbor_symbol      5 bytes
count                uint64
lane                 uint8
flags                uint8
```

Row size: 16 bytes.

## Lanes

```text
0 canonical
1 companion
2 source_local
3 null_exclusion
```

NULL/exclusion rows may be present for audit, but they are not speakable and are not promotion truth.

## WAL Direction

`wal.bin` records pending cell merges before cell files are replaced.

v0 may write a JSONL-style audit entry beside binary cell writes if needed for debugging, but the binary cell is the runtime artifact.

## Not In Scope Yet

```text
B+tree indexes
Bloom filters
mmap pinning
V-cache pinning
native C/C++ writer
global lifetime merge switch
```

Those come after the cell format is proven.
