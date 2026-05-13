# Phrases And Rendering Todo

Status: mini todo for the next POC cleanup.

## Purpose

AnchorWorks should add phrase authority as an external lexicon lane shaped like the existing lexicon, not as hidden renderer hard-codes.

The current Newton/laws/motion renderer pressure is a useful proof probe, but it must not become permanent architecture. Phrase tightening belongs in a phrase lexicon that the system can browse, review, approve, and use the same way it already treats anchor authority.

Core law:

```text
Words and phrases share the browser shape.
Anchors and phrase anchors stay separate authority lanes.
Renderer uses approved phrase authority; it does not hard-code meaning.
```

## Phrase Lexicon Shape

The phrase lexicon should live beside the existing lexicon as its own external authority, not inside counts, maps, overlays, or renderer code.

Expected browser behavior:

```text
Lexicon Browser
  toggle: Words | Phrases
```

Word view keeps the current Canonical/user/structural shape.

Phrase view should use the same browsing concepts:

```text
letter/group index
search
status
review queue
authority lane
display value
symbol value
source/review metadata
```

Minimum phrase record:

```json
{
  "schema_version": "anchorworks_phrase_lexicon@1",
  "phrase": "newton laws of motion",
  "status": "ASSIGNED",
  "authority": "PHRASE",
  "hex": "0x0000000000",
  "anchor_sequence": ["newton", "laws", "of", "motion"],
  "symbol_sequence": ["0x...", "0x...", "0x...", "0x..."],
  "phrase_type": "concept",
  "source_support": {
    "occurrences": 0,
    "source_count": 0,
    "last_built_from": ""
  },
  "notes": ""
}
```

Symbol width rule:

```text
Phrase symbols use the same fixed-width identity discipline as anchors.
No odd phrase-only symbol size.
```

## Phrase Candidate Build

Phrase candidates should be pulled from already observed anchor/symbol streams.

First source inputs:

```text
symbolized flat documents
local meta-count overlays
AWSM/AWSS streams where available
```

Do not build phrase candidates from raw observed-map JSON in chat/runtime.

Candidate extraction:

```text
anchor stream
-> 2..6 anchor spans
-> reject all-glue spans
-> count repeated spans
-> track source diversity
-> track left/right boundaries
-> track phrase field neighbors
-> write phrase review candidates
```

Phrase candidate types:

```text
concept
method
director
structural
source_specific
```

Important correction:

```text
Director phrases can exist, but they do not become content concepts by default.
```

## Weighting

Phrase weighting should resemble anchor mapping, but score bonded sequences instead of single anchors.

Initial formula:

```text
phrase_candidate_score =
  occurrence_weight
+ source_diversity_weight
+ boundary_confidence
+ internal_cohesion
+ field_specificity
- all_glue_penalty
- overbroad_penalty
- unstable_order_penalty
```

Where:

```text
occurrence_weight = repeated observed phrase count
source_diversity_weight = support across different source ids
boundary_confidence = stable left/right boundary behavior
internal_cohesion = sequence anchors repeatedly occur together in order
field_specificity = phrase narrows meaning compared with loose anchors
```

Example:

```text
laws
  broad anchor

laws motion
  partial field

newton laws of motion
  phrase authority candidate
```

## Rendering Cleanup

Replace POC hard-codes with phrase authority.

Remove or generalize:

```text
NEWTON_MOTION_FIELD_TERMS
newton/laws/motion-specific required slot logic
newton/laws/motion-specific domain drift penalty
```

Renderer should instead do:

```text
query anchors
-> phrase candidate recognition
-> active phrase field
-> anchor count walk inside phrase field
-> min/target/max anchor policy
-> slot satisfaction
-> final human rendering
```

If an approved phrase exists:

```text
phrase authority narrows the field
global AWSC supplies memory pressure
local overlays supply source-local pressure
renderer walks symbols
display text renders at the edge
```

## Mini Todo

1. Define phrase lexicon storage beside Canonical.
2. Add Lexicon Browser `Words | Phrases` toggle.
3. Add phrase candidate extraction from symbolized flat docs or overlays.
4. Add phrase review records without mutating Canonical.
5. Add phrase assignment/promotion using the same authority discipline as words.
6. Add phrase lookup before renderer field selection.
7. Replace Newton/laws/motion hard-code with phrase-derived field pressure.
8. Add renderer tests:
   - broad `laws` does not lock physics by itself
   - `laws motion` creates a partial field
   - approved `newton laws of motion` creates a concept phrase field
   - min/target/max anchor policy still applies
   - renderer trace names phrase field source
9. Keep observed maps out of chat/runtime.
10. Keep phrase lexicon out of AWSC relation payloads.

## Done For This Mini Todo When

```text
Phrase lexicon exists externally.
UI can browse words or phrases with one toggle.
Phrase candidates can be reviewed.
Renderer can use approved phrase authority.
Newton/laws/motion hard-code is removed.
Tests prove phrase tightening replaces hard-coded field pressure.
```

