# TrueVision Language State Branch

This branch adapts the TrueVision reverse-state method to language.

The source method is copied as read-only reference under:

```text
external_methods/truevision_generation_lab/
```

Those files are not AnchorWorks runtime imports. They preserve the proven
capture/render chain so the language branch can translate the method cleanly.

## Purpose

```text
visual source
-> glyph-state capture
-> glyph recognition
-> glyph state records
-> textual state cloud
-> reverse-state renderer
```

This is state-method transfer, not prompt generation.

The goal is not OCR-as-text-copy. The goal is to record what the visual
language state proves, then let AnchorWorks build language from replayable
state.

## Hard Boundary

```text
Glyphs are observed marks.
Glyph records are state.
Text is reconstructed from state.
Counts/clouds assemble from accepted state.
Renderer speaks only replayable state.
```

## Non-Goals

```text
No raw text copy as truth.
No OCR authority.
No generated facts.
No prompt-only reconstruction.
No TrueVision video-generation artifacts in AnchorWorks.
No generated video/media artifacts live in AnchorWorks.
No legacy TrueVision worker import.
```

## Directory Shape

```text
src/AnchorWorks/truevision_language/
  contracts.py       shared state object constructors
  method_boundary.py external method manifest validator
  glyphs/            glyph recognition/state adapters
  intake/            visual frame/page to glyph-state intake
  state/             recorded language state packets
  cloud/             textual cloud construction from state
  rendering/         reverse-state language rendering
```

## Method

TrueVision video taught the key rule:

```text
stored state -> replay only what state supports -> report missing state
```

Exact method chain:

```text
capture observed state
-> write compact state chunks
-> SegmentField A-to-B transition
-> render replay from stored state
```

Language version:

```text
glyph marks -> glyph state -> ordered symbol/textual state -> cloud -> walked answer
```

AnchorWorks translation:

```text
SegmentField becomes LanguageSegmentField.
.tvcells becomes glyph/language state chunks.
Video replay becomes reverse-state language rendering.
```

If a page or frame has no recognized glyph state, AnchorWorks must not pretend
text exists. If a count walk has no replayable answer state, ClearSpeak must not
fill the gap with raw top-K terms.

## First Proof

```text
controlled visual glyph page
-> recognized glyph states
-> ordered textual state
-> cloud terms
-> replayable language-state receipt
```

Current first ingest path:

```text
glyph pattern rows
-> VisualGlyphLexicon match
-> glyph_state records
-> ordered language symbols
-> AnchorWorks render transform rules
-> textual cloud terms
```

Transform rules are reused from:

```text
AnchorWorks.anchor_field.build_query_frame
```

That means the language-state intake follows the same split as the renderer:

```text
content symbols feed the cloud
director/glue symbols shape rendering
punctuation is direction, not content
unknown glyphs block render until named
```

## Document-As-Movie State Recording

The live document path uses the same recording idea as TrueVision still-image
capture:

```text
document/page image
-> one page frame
-> repeat page as 3 state frames
-> write records JSONL
-> write summary JSON
-> write manifest JSON
-> write cell_state_npz tensor
```

Default proof shape:

```text
1 page/document x 3 frames
```

The repeated frames make the document a short, stable movie. Speed can be
adjusted by FPS, but the first pass keeps `frames_per_page = 3`.

Recognition boundary:

```text
source page pixels
-> recorded state tensor
-> black-cell glyph extraction from stored luma_mean
-> VisualGlyphLexicon match
-> language-state packet
```

No recognition step is allowed to read source page pixels directly after the
state movie has been written. Recognition derives from stored state.

## Next TODO: Editable Visual-State Layer

TrueVision reverse output currently replays observed state. It does not yet
manipulate scene content because the recorded state is cell evidence, not a
separated scene model.

Next build target:

```text
stored cell state
-> derived editable layers
-> object/region masks
-> motion/depth/occlusion hints
-> controlled state edits
-> reverse replay from edited state
-> fidelity/change receipt
```

Hard boundary:

```text
Replay is evidence from recorded state.
Manipulation is a derived edit layer.
Edited output must be labeled generated/derived, not source evidence.
```

Expected receipt:

```json
{
  "state_recorded_not_copied": true,
  "glyph_authority": "visual_glyph_lexicon",
  "text_authority": "derived_from_glyph_state",
  "render_allowed": true
}
```

## Law

```text
Vision records state.
Glyphs name marks.
Clouds assemble language pressure.
Renderer reverses only replayable state.
```
