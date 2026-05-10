# AnchorWorks Native Symbol Counts Spine

Status: first native AWSC v1.1 construction branch.

## Hardware Read

Observed from the active Windows shell:

```text
CPU: AMD Ryzen 9 9950X3D 16-Core Processor
Windows-exposed logical processors: 8
Windows-exposed physical cores: 8
ThreadCount reported by Win32_Processor: 32
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
```

## Law

```text
Strings are I/O.
Symbols are computation.
Binary cells are memory.
```
