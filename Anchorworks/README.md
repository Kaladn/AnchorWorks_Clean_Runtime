# Anchorworks

AnchorWorks is a deterministic anchor, symbol, source, and count runtime.

The authoritative current system document is:

```text
docs/ANCHORWORKS_CURRENT_REALITY.md
```

## Install

```bash
pip install -e .
```

## Run

```bash
anchorworks shell
anchorworks operator
anchorworks serve --data-root D:\AnchorWorks_Clean_Runtime
```

## Tests

From this folder:

```bash
python -m pytest -q
python -m compileall src\AnchorWorks -q
```

## Core Runtime Truth

Canonical is a locked base. User lexicon and user-side binary counts are the active writable layers. Generated `State` runtime data is local unless intentionally snapshotted.
