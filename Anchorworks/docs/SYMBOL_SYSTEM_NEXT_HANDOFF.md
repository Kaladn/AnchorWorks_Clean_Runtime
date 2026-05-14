# Symbol System Next Handoff

Status: checkpoint before making phrase and future symbolic authority lexicon-native.

## Current Truth

The repo is clean at this handoff. Phrase candidate review exists, phrase authority wiring exists, and ClearSpeak can use approved phrase authority when records are present.

Current phrase authority still needs the symbolic correction:

```text
candidate phrase id = deterministic review fingerprint
approved phrase symbol = real assigned lexicon identity
```

## Next Work

Make phrase authority use the same identity discipline as word anchors:

```text
Spare_Slots allocation
-> binary / hex / font_symbol / tone label fields
-> Phrase_Lexicon record
-> Lexicon Explorer Words | Phrases toggle
```

## Rules

```text
Do not hash approved phrase symbols.
Do not mutate Canonical for phrase authority.
Do not overload status with phrase roles.
Do not use tone_signature as TTS tone.
Human display is text.
Internal authority is symbols.
```

Tone work starts empty:

```text
tone_label = ""
tone_profile = null
```

Legacy `tone_signature` should be retired or migrated only through an explicit, tested step.
