# Symbol System Next Handoff

Status: checkpoint for making phrase and future symbolic authority lexicon-native through the Symbol Genome Protocol.

## Current Truth

Phrase candidate review exists, phrase authority wiring exists, and ClearSpeak can use approved phrase authority when records are present.

Phrase authority now has a clear symbolic split:

```text
candidate phrase id = deterministic review fingerprint
approved phrase symbol = Symbol Genome identity
```

## Next Work

Make all future symbolic authority use the same lexicon-shaped identity discipline:

```text
Symbol Genome allocation
-> 5-byte symbol
-> binary / hex / font_symbol / visual rune / integrity hash / tone label fields
-> Phrase_Lexicon record
-> Lexicon Explorer Words | Phrases toggle
```

Generator pool is now the replacement for copied spare lexicon rows:

```text
capacity = 15,000,000
State/symbol_genome_pool/manifest.json
generated on need
checkpointed by cursor
not browsed as a lexicon pack
```

## Rules

```text
Do not hash approved phrase symbols.
Do not mutate Canonical for phrase authority.
Do not overload status with phrase roles.
Do not use tone_signature as TTS tone.
Do preserve Symbol Genome byte structure.
Do preserve 8x8 visual rune metadata.
Do not materialize generated spares as lexicon entries.
Human display is text.
Internal authority is symbols.
```

Tone work starts empty:

```text
tone_label = ""
tone_profile = null
```

Legacy `tone_signature` should be retired or migrated only through an explicit, tested step.
