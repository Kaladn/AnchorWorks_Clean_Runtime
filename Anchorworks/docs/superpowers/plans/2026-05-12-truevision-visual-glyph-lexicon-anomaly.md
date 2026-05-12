# TrueVision Visual Glyph Lexicon With Anomaly Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first TrueVision recognition bridge: deterministic black-pixel glyph matching through a VisualGlyphLexicon with anomaly detection, producing an ordered text candidate only when marks are named by approved glyph patterns.

**Architecture:** TrueVision keeps visual proof first. Black/white page frames are segmented into line bands and connected mark components, each component is normalized into a glyph pattern, then matched against a VisualGlyphLexicon. Anomaly detection runs beside matching and reports unknown marks, malformed components, spacing anomalies, line-order anomalies, duplicate/overlap anomalies, and low-confidence matches before any text candidate can move toward AnchorWorks anchorization.

**Tech Stack:** Python 3, stdlib `unittest`, existing reports directory for proof outputs, no OCR backend, no CV model, no Canonical writes, no map/count/lifetime writes.

---

## Core Law

```text
Vision sees marks.
Glyph lexicon names marks.
Language lexicon names words.
Counts learn positions.
```

Safety law:

```text
Unknown mark does not become text.
Unknown mark becomes visual_unknown_glyph.
```

Anomaly law:

```text
Every visual anomaly is preserved as evidence.
No anomaly silently enters text.
```

## First Proof Target

```text
controlled black/white visual page
A-Z
0-9
basic punctuation .,:;!?()-/
blank separator frames supported by policy
black-pixel extraction
glyph lexicon lookup
exact text rebuild after spacing repair
0 unknown glyphs on controlled page
0 blocking anomalies on controlled page
```

## Files

Create:

```text
src/AnchorWorks/visual_glyph_lexicon.py
src/AnchorWorks/visual_mark_anomaly.py
src/AnchorWorks/visual_black_pixel_reconstruction.py
tools/probe_visual_glyph_reconstruction.py
tests/test_visual_glyph_lexicon.py
tests/test_visual_mark_anomaly.py
tests/test_visual_black_pixel_reconstruction.py
```

Runtime report output only:

```text
reports/truevision/visual_glyph_reconstruction/
```

Do not create production data under:

```text
State
D:\AnchorMaps
Canonical
Spare_Slots
Structural
```

---

### Task 1: VisualGlyphLexicon Contract

**Files:**
- Create: `src/AnchorWorks/visual_glyph_lexicon.py`
- Create: `tests/test_visual_glyph_lexicon.py`

- [ ] **Step 1: Write failing tests**

```python
from __future__ import annotations

import unittest

from AnchorWorks.visual_glyph_lexicon import (
    GlyphMatch,
    VisualGlyphLexicon,
    normalize_trim_pattern,
)


class VisualGlyphLexiconTests(unittest.TestCase):
    def test_exact_pattern_match_names_mark(self) -> None:
        lexicon = VisualGlyphLexicon.from_records(
            [
                {
                    "schema_version": "anchorworks_visual_glyph_lexicon@1",
                    "glyph_id": "vglyph_A_0001",
                    "display": "A",
                    "class": "letter_upper",
                    "width": 5,
                    "height": 7,
                    "trim_pattern": [
                        "01110",
                        "10001",
                        "10001",
                        "11111",
                        "10001",
                        "10001",
                        "10001",
                    ],
                    "match_policy": {"max_hamming_distance": 0},
                    "promotion_status": "approved",
                }
            ]
        )
        match = lexicon.match(
            [
                "01110",
                "10001",
                "10001",
                "11111",
                "10001",
                "10001",
                "10001",
            ]
        )
        self.assertEqual(match, GlyphMatch("vglyph_A_0001", "A", 1.0, "exact"))

    def test_unknown_pattern_does_not_become_text(self) -> None:
        lexicon = VisualGlyphLexicon.from_records([])
        match = lexicon.match(["1"])
        self.assertEqual(match.display, "visual_unknown_glyph")
        self.assertEqual(match.confidence, 0.0)
        self.assertEqual(match.match_type, "unknown")

    def test_normalize_trim_pattern_removes_empty_border(self) -> None:
        self.assertEqual(
            normalize_trim_pattern(["0000", "0110", "0110", "0000"]),
            ("11", "11"),
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test and verify failure**

```powershell
python -m unittest tests.test_visual_glyph_lexicon -v
```

Expected: fail because `AnchorWorks.visual_glyph_lexicon` does not exist.

- [ ] **Step 3: Implement minimal glyph lexicon**

```python
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any


def normalize_trim_pattern(rows: list[str]) -> tuple[str, ...]:
    cleaned = [str(row) for row in rows if "1" in str(row)]
    if not cleaned:
        return tuple()
    left = min(row.index("1") for row in cleaned)
    right = max(row.rindex("1") for row in cleaned)
    return tuple(row[left : right + 1] for row in cleaned)


def pattern_hash(pattern: tuple[str, ...]) -> str:
    return sha256("\n".join(pattern).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GlyphMatch:
    glyph_id: str
    display: str
    confidence: float
    match_type: str


class VisualGlyphLexicon:
    def __init__(self, by_hash: dict[str, GlyphMatch]) -> None:
        self._by_hash = dict(by_hash)

    @classmethod
    def from_records(cls, records: list[dict[str, Any]]) -> "VisualGlyphLexicon":
        by_hash: dict[str, GlyphMatch] = {}
        for record in records:
            if record.get("promotion_status") != "approved":
                continue
            pattern = normalize_trim_pattern(list(record.get("trim_pattern") or []))
            if not pattern:
                continue
            by_hash[pattern_hash(pattern)] = GlyphMatch(
                str(record["glyph_id"]),
                str(record["display"]),
                1.0,
                "exact",
            )
        return cls(by_hash)

    def match(self, rows: list[str]) -> GlyphMatch:
        pattern = normalize_trim_pattern(rows)
        found = self._by_hash.get(pattern_hash(pattern))
        if found:
            return found
        return GlyphMatch("visual_unknown_glyph", "visual_unknown_glyph", 0.0, "unknown")
```

- [ ] **Step 4: Run test and verify pass**

```powershell
python -m unittest tests.test_visual_glyph_lexicon -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/AnchorWorks/visual_glyph_lexicon.py tests/test_visual_glyph_lexicon.py
git commit -m "Add TrueVision visual glyph lexicon"
```

---

### Task 2: Visual Mark Anomaly Detection

**Files:**
- Create: `src/AnchorWorks/visual_mark_anomaly.py`
- Create: `tests/test_visual_mark_anomaly.py`

- [ ] **Step 1: Write failing tests**

```python
from __future__ import annotations

import unittest

from AnchorWorks.visual_mark_anomaly import (
    MarkComponent,
    detect_visual_mark_anomalies,
)


class VisualMarkAnomalyTests(unittest.TestCase):
    def test_unknown_glyph_is_blocking_anomaly(self) -> None:
        anomalies = detect_visual_mark_anomalies(
            [
                MarkComponent(
                    component_id="c1",
                    bounds=(0, 0, 5, 7),
                    pattern=("1",),
                    display="visual_unknown_glyph",
                    confidence=0.0,
                )
            ]
        )
        self.assertEqual(anomalies[0]["kind"], "visual_unknown_glyph")
        self.assertTrue(anomalies[0]["blocking"])

    def test_overlapping_components_are_anomalies(self) -> None:
        anomalies = detect_visual_mark_anomalies(
            [
                MarkComponent("c1", (0, 0, 5, 7), ("1",), "A", 1.0),
                MarkComponent("c2", (4, 0, 9, 7), ("1",), "B", 1.0),
            ]
        )
        self.assertEqual(anomalies[0]["kind"], "component_overlap")
        self.assertTrue(anomalies[0]["blocking"])

    def test_clean_components_have_no_anomalies(self) -> None:
        anomalies = detect_visual_mark_anomalies(
            [
                MarkComponent("c1", (0, 0, 5, 7), ("1",), "A", 1.0),
                MarkComponent("c2", (8, 0, 13, 7), ("1",), "B", 1.0),
            ]
        )
        self.assertEqual(anomalies, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test and verify failure**

```powershell
python -m unittest tests.test_visual_mark_anomaly -v
```

Expected: fail because module does not exist.

- [ ] **Step 3: Implement anomaly detection**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MarkComponent:
    component_id: str
    bounds: tuple[int, int, int, int]
    pattern: tuple[str, ...]
    display: str
    confidence: float


def _overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1


def detect_visual_mark_anomalies(components: list[MarkComponent]) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    for component in components:
        if component.display == "visual_unknown_glyph":
            anomalies.append(
                {
                    "kind": "visual_unknown_glyph",
                    "component_id": component.component_id,
                    "blocking": True,
                    "reason": "unknown mark cannot become text",
                }
            )
        if component.confidence < 1.0 and component.display != "visual_unknown_glyph":
            anomalies.append(
                {
                    "kind": "low_confidence_glyph",
                    "component_id": component.component_id,
                    "blocking": True,
                    "reason": "foundation pass requires exact glyph matches",
                }
            )
    for index, left in enumerate(components):
        for right in components[index + 1 :]:
            if _overlaps(left.bounds, right.bounds):
                anomalies.append(
                    {
                        "kind": "component_overlap",
                        "component_id": left.component_id,
                        "other_component_id": right.component_id,
                        "blocking": True,
                        "reason": "overlapping visual marks cannot be ordered safely",
                    }
                )
    return anomalies
```

- [ ] **Step 4: Run test and verify pass**

```powershell
python -m unittest tests.test_visual_mark_anomaly -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/AnchorWorks/visual_mark_anomaly.py tests/test_visual_mark_anomaly.py
git commit -m "Add visual mark anomaly detection"
```

---

### Task 3: Controlled Black-Pixel Reconstruction Through Lexicon

**Files:**
- Create: `src/AnchorWorks/visual_black_pixel_reconstruction.py`
- Create: `tests/test_visual_black_pixel_reconstruction.py`

- [ ] **Step 1: Write failing tests**

```python
from __future__ import annotations

import unittest

from AnchorWorks.visual_black_pixel_reconstruction import reconstruct_from_known_components
from AnchorWorks.visual_glyph_lexicon import VisualGlyphLexicon


class VisualBlackPixelReconstructionTests(unittest.TestCase):
    def test_reconstructs_ordered_text_from_known_components(self) -> None:
        lexicon = VisualGlyphLexicon.from_records(
            [
                {
                    "schema_version": "anchorworks_visual_glyph_lexicon@1",
                    "glyph_id": "vglyph_A_0001",
                    "display": "A",
                    "class": "letter_upper",
                    "width": 1,
                    "height": 1,
                    "trim_pattern": ["1"],
                    "match_policy": {"max_hamming_distance": 0},
                    "promotion_status": "approved",
                }
            ]
        )
        result = reconstruct_from_known_components(
            lexicon,
            [
                {"component_id": "c1", "bounds": (0, 0, 1, 1), "pattern": ["1"]},
                {"component_id": "c2", "bounds": (3, 0, 4, 1), "pattern": ["1"]},
            ],
            word_gap_pixels=2,
        )
        self.assertEqual(result["text_candidate"], "A A")
        self.assertEqual(result["unknown_glyphs"], 0)
        self.assertEqual(result["blocking_anomalies"], 0)

    def test_unknown_glyph_blocks_text_candidate(self) -> None:
        result = reconstruct_from_known_components(
            VisualGlyphLexicon.from_records([]),
            [{"component_id": "c1", "bounds": (0, 0, 1, 1), "pattern": ["1"]}],
            word_gap_pixels=2,
        )
        self.assertEqual(result["text_candidate"], "")
        self.assertEqual(result["unknown_glyphs"], 1)
        self.assertEqual(result["blocking_anomalies"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test and verify failure**

```powershell
python -m unittest tests.test_visual_black_pixel_reconstruction -v
```

Expected: fail because module does not exist.

- [ ] **Step 3: Implement reconstruction adapter**

```python
from __future__ import annotations

from typing import Any

from .visual_glyph_lexicon import VisualGlyphLexicon
from .visual_mark_anomaly import MarkComponent, detect_visual_mark_anomalies


def _line_key(component: dict[str, Any]) -> tuple[int, int]:
    x1, y1, _x2, _y2 = component["bounds"]
    return int(y1), int(x1)


def reconstruct_from_known_components(
    lexicon: VisualGlyphLexicon,
    components: list[dict[str, Any]],
    *,
    word_gap_pixels: int,
) -> dict[str, Any]:
    ordered = sorted(components, key=_line_key)
    matched: list[MarkComponent] = []
    output_parts: list[str] = []
    previous_bounds: tuple[int, int, int, int] | None = None
    for raw in ordered:
        bounds = tuple(int(value) for value in raw["bounds"])
        pattern = list(raw["pattern"])
        match = lexicon.match(pattern)
        matched.append(
            MarkComponent(
                component_id=str(raw["component_id"]),
                bounds=bounds,
                pattern=tuple(pattern),
                display=match.display,
                confidence=match.confidence,
            )
        )
        if match.display != "visual_unknown_glyph":
            if previous_bounds is not None:
                gap = bounds[0] - previous_bounds[2]
                if gap >= word_gap_pixels:
                    output_parts.append(" ")
            output_parts.append(match.display)
        previous_bounds = bounds
    anomalies = detect_visual_mark_anomalies(matched)
    blocking = [row for row in anomalies if row.get("blocking")]
    unknown_count = sum(1 for row in matched if row.display == "visual_unknown_glyph")
    text_candidate = "" if blocking else "".join(output_parts)
    return {
        "schema_version": "anchorworks_visual_text_candidate@1",
        "text_candidate": text_candidate,
        "components_seen": len(components),
        "unknown_glyphs": unknown_count,
        "anomalies": anomalies,
        "blocking_anomalies": len(blocking),
    }
```

- [ ] **Step 4: Run tests and verify pass**

```powershell
python -m unittest tests.test_visual_black_pixel_reconstruction -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/AnchorWorks/visual_black_pixel_reconstruction.py tests/test_visual_black_pixel_reconstruction.py
git commit -m "Add lexicon-backed visual text reconstruction"
```

---

### Task 4: Controlled Proof Probe And Report

**Files:**
- Create: `tools/probe_visual_glyph_reconstruction.py`
- Runtime output only: `reports/truevision/visual_glyph_reconstruction/`

- [ ] **Step 1: Write probe**

Create a probe that builds an in-memory glyph lexicon for `A`, `B`, `.`, and `:` using tiny deterministic patterns, runs reconstruction on ordered known components, and writes a report.

Report shape:

```json
{
  "schema_version": "anchorworks_visual_glyph_reconstruction_probe@1",
  "exact_match": true,
  "unknown_glyphs": 0,
  "blocking_anomalies": 0,
  "text_candidate": "A:B.",
  "expected_text": "A:B."
}
```

- [ ] **Step 2: Run probe**

```powershell
python tools\probe_visual_glyph_reconstruction.py
```

Expected:

```text
exact_match: true
unknown_glyphs: 0
blocking_anomalies: 0
```

- [ ] **Step 3: Run full tests**

```powershell
python -m unittest discover -s tests
```

Expected: pass.

- [ ] **Step 4: Commit**

```powershell
git add tools/probe_visual_glyph_reconstruction.py
git commit -m "Add visual glyph reconstruction probe"
```

---

## Acceptance

```text
VisualGlyphLexicon exists.
Unknown marks become visual_unknown_glyph.
Anomaly detection is built in.
Unknown glyph anomalies block text candidate output.
Overlap anomalies block text candidate output.
Controlled exact glyph lookup succeeds.
Controlled reconstruction exact-matches expected text.
0 unknown glyphs on controlled proof.
0 blocking anomalies on controlled proof.
No Canonical writes.
No map/count/lifetime writes.
Tests pass.
```

## Next Plan After This One

```text
1. Build full controlled glyph lexicon for A-Z, 0-9, and punctuation .,:;!?()-/
2. Render one real PDF page to thresholded black/white frame.
3. Segment black pixels into line bands and mark components.
4. Match against VisualGlyphLexicon.
5. Emit visual_unknown_glyph records for missing patterns.
6. Build a glyph-catalog review UI or report.
7. Add dual-path verification against source text when source text exists.
```

## Self-Review

Spec coverage:

```text
VisualGlyphLexicon: Task 1
Unknown mark safety: Tasks 1-3
Anomaly detection: Task 2
Reconstruction bridge: Task 3
Probe/report: Task 4
No production writes: file scope and acceptance
```

Placeholder scan:

```text
No task depends on an undefined module or unspecified function.
The probe scope is intentionally tiny and exact.
```

Type consistency:

```text
GlyphMatch, VisualGlyphLexicon, MarkComponent, and reconstruct_from_known_components use the same names across tests and implementation.
```
