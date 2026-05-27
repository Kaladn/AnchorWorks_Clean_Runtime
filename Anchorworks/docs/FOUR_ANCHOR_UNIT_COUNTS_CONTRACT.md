# Four Anchor Unit Counts Contract

## Purpose

Add a sibling count layer beside normal AnchorWorks solo-anchor counts.

## Law

```text
Do not replace solo counts.
Solo stream = anchors.
Unit4 stream = fixed ordered groups of 4 anchors.
Same positional count idea.
Separate outputs.
```

## Shape

Input anchor stream:

```text
A0 A1 A2 A3 A4 A5 A6 A7 ...
```

Unit stream:

```text
U0 = A0 A1 A2 A3
U1 = A4 A5 A6 A7
U2 = A8 A9 A10 A11
```

Window:

```text
6-1-6 over unit4
```

Meaning:

```text
left = 6 unit4 anchors
center = 1 unit4 anchor
right = 6 unit4 anchors
```

Each unit4 anchor preserves the exact original order of its four anchors.

## Rules

```text
Do not change solo-anchor count output.
Do not reinterpret the four anchors.
Do not use sentence splitting.
Do not use embeddings.
Do not use semantic grouping.
Do not promote unit4 anchors into canonical lexicon automatically.
Drop partial tails by default.
Write unit4 counts only to the unit4 sibling layer.
```

## Output Boundary

```text
normal lifetime counts = unchanged
four_anchor_unit_counts = sibling count layer
binary AWU4 files = unit4 relation rows only
```
