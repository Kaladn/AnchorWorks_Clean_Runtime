# Symbol Genome Protocol Contract

Source PDFs:

```text
symbol_genome_generator.pdf
symbol_genome_visual_samples.pdf
SYMBOL_GENOME_PROTOCOL.pdf
```

## Runtime Law

```text
Human display is text.
Internal authority is a 5-byte symbol.
Symbol identity carries a visual rune.
Tone starts empty until real TTS tone exists.
```

## 5-Byte Symbol Layout

Symbol Genome identities are exactly 5 bytes / 40 bits.

```text
byte 1:
  bits 7..5 = category code
  bits 4..2 = priority
  bits 1..0 = reserved

bytes 2..5:
  first 32 bits of SHA-256(label)
```

Current category codes:

```text
0 = core
1 = specialized
2 = future
```

Priority is `0..7`, where `0` is highest priority.

## Visual Rune

Each 5-byte symbol can render as an 8x8 visual grid.

The visual rune is verification/display metadata, not evidence by itself.

```text
symbol bytes -> deterministic 8x8 grid -> visual_rune
```

## Phrase Authority

Phrase candidates may keep deterministic review fingerprints.

Approved phrase authority must use Symbol Genome identity fields:

```text
binary
hex
symbol
font_symbol
visual_grid
visual_rune
integrity_hash
tone_label
tone_profile
```

Phrase records remain external to Canonical and do not write counts.

## Symbol Genome Pool

Generated symbols are not a lexicon pack.

The live pool is a checkpointed generator:

```text
State/symbol_genome_pool/manifest.json
```

Default capacity:

```text
15,000,000 symbols
```

The pool does not materialize 15 million JSON rows. The manifest cursor is
authority:

```text
capacity
next_index
assigned_count
checkpoints
last_allocation
```

When a new identity is needed, the backend advances the cursor and generates
one Symbol Genome identity. The generated identity may then be written into the
proper authority lane, such as `Canonical` or `Phrase_Lexicon`.

Law:

```text
Do not copy generated spares into a lexicon.
Generate on need.
Checkpoint the cursor.
Authority records receive symbols after allocation.
```

## Tone

Retired `tone_signature` is not TTS tone.

New authority records start with:

```json
{
  "tone_label": "",
  "tone_profile": null
}
```

Real tone labels must be added later through explicit TTS/rendering work.

