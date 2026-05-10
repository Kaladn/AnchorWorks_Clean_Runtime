# AnchorWorks Symbol Counts Binary Contract

Status: AWSC v1.1 active contract

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

No B+tree, mmap, Bloom filter, compression, WAL recovery, or C spine is required in this contract step.

The native C++ spine consumes compact binary symbol streams and writes AWSC v1.1 cells.

## AWSS Source Stream v1

The native merge input is an AnchorWorks Symbol Stream (`.awss`). It is not JSON.

Record size: 24 bytes.

```text
0   root_symbol[5]      raw 5-byte symbol
5   neighbor_symbol[5]  raw 5-byte symbol
10  offset_i8           observed relative position
11  lane_u8             relation lane
12  flags_u8            relation flags
13  root_lane_u8        root symbol lane
14  reserved_u16        future
16  count_u64           observed relation count
```

The C++ merge groups by `root_symbol`, merges duplicate relation rows, applies AWSC row ordering, and writes one cell per root symbol.

## AWSC Cell Format v1.1

All multi-byte values are little endian. Symbols are raw 5-byte identities and are not text.

Header:

```text
0   magic[4]             AWSC
4   version_u16          0x0101
6   header_size_u16      64
8   total_size_u64       full cell file size
16  generation_u64       write generation / rebuild generation
24  wal_frame_u64        0 until WAL frames are active
32  root_symbol[5]       raw 5-byte symbol
37  root_lane_u8         root symbol lane
38  flags_u16            cell flags
40  row_count_u32        number of relation rows
44  row_size_u16         16
46  reserved_u16         future
48  payload_size_u32     row_count * 16
52  payload_crc32_u32    CRC of relation-row payload
56  overflow_offset_u64  0 until overflow chains are active
```

Relation row:

```text
0   neighbor_symbol[5]  raw 5-byte symbol
5   offset_i8           observed relative position
6   lane_u8             relation lane
7   flags_u8            relation flags
8   count_u64           observed relation count
```

Row size: 16 bytes.

Rows are sorted deterministically:

```text
offset ascending
count descending
neighbor_symbol ascending
lane ascending
```

## Lanes

```text
0 canonical
1 math_companion
2 structural_companion
3 source_specific
4 source_local_temp
5 user_lexicon
255 reserved_error
```

NULL never enters AWSC relation memory. NULL lives in exact coordinate indexes only.

NULL coordinate rows use:

```text
source_id
block_id
line
anchor_position
surface
reason
```

## Flags

Relation flags describe restrictions/properties, not permissions:

```text
bit 0 speak_blocked
bit 1 source_local_only
bit 2 companion
bit 3 user_scope
bit 4 audit_only
bit 5 overflow_related
bit 6 reserved
bit 7 reserved
```

## WAL Direction

`wal.bin` records pending cell merges before cell files are replaced.

The v1.1 header reserves `wal_frame` and `overflow_offset`, but full WAL recovery and overflow chains are not active until later implementation phases.

## Not In Scope Yet

```text
B+tree indexes
Bloom filters
mmap pinning
V-cache pinning
native C/C++ writer
global lifetime merge switch
JSON relation rows in the hot path
```

Those come after the cell format is proven.

## Law

```text
Strings are I/O.
Symbols are computation.
Binary cells are memory.
```
