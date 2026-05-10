# AnchorWorks Native Symbol Counts Spine

Status: symbolic binary spine branch.

## Hardware Read

Current confirmed hardware:

```text
CPU: AMD Ryzen 9 9950X3D 16-Core Processor
Windows-exposed physical cores: 16
Windows-exposed logical processors: 32
RAM: 61.56 GB
OS: Windows 11 Pro
```

Storage:

```text
C: 930.54 GB, 516.69 GB free
D: 1.86 TB, 1.79 TB free
E: 931.5 GB, 877.87 GB free
F: 4.66 TB, 4.56 TB free
```

Toolchain:

```text
Visual Studio Community 2026
MSVC 14.50
Bundled CMake
Generator: Visual Studio 18 2026
Architecture: x64
```

Plain shell PATH does not expose `cl` or `cmake`, so AnchorWorks uses the Visual Studio bundled CMake path when available.

## Engineering Choice

The native path is MSVC x64.

The first C++ target is intentionally direct:

```text
AWSS binary symbol stream in
group by root symbol
merge duplicate relation rows
write AWSC v1.1 cells
verify AWSC v1.1 cells
inspect one AWSC cell
score active context symbols against AWSC cells
```

This avoids the known slow design:

```text
read giant JSON
merge one document
rewrite giant JSON
repeat
```

## Native Paths

Source:

```text
src/AnchorWorks/native/symbol_counts/CMakeLists.txt
src/AnchorWorks/native/symbol_counts/include/awsc.h
src/AnchorWorks/native/symbol_counts/src/awsc.cpp
src/AnchorWorks/native/symbol_counts/src/awsc_cli.cpp
```

Python bridge:

```text
src/AnchorWorks/symbol_count_native.py
```

Build output:

```text
build/native_symbol_counts/Release/anchorworks-symbol-counts.exe
```

Runtime output:

```text
State/symbol_counts_binary/
  cells/
  indexes/
  metadata.json
```

## CLI

```text
anchorworks-symbol-counts merge-stream --input <stream.awss> --output <State/symbol_counts_binary> --generation <n>
anchorworks-symbol-counts verify --root <State/symbol_counts_binary>
anchorworks-symbol-counts inspect --cell <cell>
anchorworks-symbol-counts score --root <State/symbol_counts_binary> --context <hex,hex> --top-k <n>
```

## Symbolic Binary Map Substrate

The current branch also introduces AWSM:

```text
AWSM = AnchorWorks Symbolic Map
```

AWSM is the binary source-local symbolic map layer. It is written beside JSON observed maps for now.

Current AWSM contract:

```text
64-byte header
24-byte relation rows
5-byte root symbol
5-byte neighbor symbol
offset
lane
flags
count
metadata CRC
relation payload CRC
```

Current measured proof on 35 mixed source documents:

```text
JSON observed maps total: 3,715,106 bytes
AWSM binary maps total:    201,830 bytes
AWSM size reduction: about 18.4x
AWSM read scan: about 3.36x faster than JSON parse/scan
Shape/data mismatches: 0
AWSC verify errors: 0
```

## Next Up

The active direction is full symbolic binary beyond original document intake.

Do not jump straight to GPU. Build one piece at a time with tests and verification.

Ordered next items:

```text
1. Build source-local symbol count artifacts directly from AWSM instead of JSON observed maps.
2. Add AWSM sidecar sections for block/line locators and NULL indexes.
3. Make JSON observed maps optional debug output, not the hot path.
4. Add binary read APIs for source-local symbolic maps.
5. Run 100-doc and 1000-doc AWSM parity checks against JSON debug maps.
6. Move native top-k attention scoring from proof CLI into the ClearSpeak read path.
7. Add batch-aware native scoring for many active contexts.
8. Design GPU sparse scoring only after CPU-native scoring is stable.
```

GPU direction:

```text
AWSM maps and AWSC count cells become the compiled symbolic substrate.
GPU memory may later hold sparse relation fields and metadata views.
GPU scores candidate fields.
AnchorWorks still owns authority, evidence gates, approval, and rendering.
```

Hard law:

```text
Observed weights can be multiplied.
Truth cannot.
```

No lexicon/meta binary implementation is part of this note. Canonical remains JSON authority until a separate tested lexicon-binary contract exists.

## Law

```text
Strings are I/O.
Symbols are computation.
Binary cells are memory.
GPU is acceleration, not authority.
```
