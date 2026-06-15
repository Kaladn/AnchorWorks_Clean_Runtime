# TrueVision And TrueAudio System

TrueVision and TrueAudio are witness systems. Their job is to observe state, package evidence, and hand reviewed material to the rest of the stack. They do not own AnchorWorks count memory and they do not replace the answer renderer.

## Shared Role

The witness systems capture state that plain text intake may miss:

```text
TrueVision = visual state, glyphs, regions, frames, layouts, documents
TrueAudio = audio state, speech, timing, acoustic events, transcript evidence
```

The common shape is:

```text
source media
-> state witness packet
-> manifest and provenance
-> optional reviewed text or anchor intake
-> AnchorWorks native count path
```

## TrueVision In This Workspace

The active TrueVision surface is under:

```text
src/AnchorWorks/truevision_language/
```

It includes contracts, method boundaries, glyph frame intake, state movie support, visual transforms, tensor storage, and tensor indexing.

TrueVision should be understood as a support witness:

```text
observe
segment
profile
record state
produce evidence packets
```

It should not directly write AnchorWorks user counts.

## TrueAudio Boundary

This workspace does not currently expose a full TrueAudio runtime package equivalent to the TrueVision module. For now, TrueAudio is documented as the audio-side witness contract for the same stack.

When active, TrueAudio should handle audio intake, timing, transcript evidence, and acoustic state packets. It may produce reviewed text for AnchorWorks intake, but it must not become an AnchorWorks count writer.

## Storage Pattern

Witness systems may use binary payloads for dense media state and JSON metadata for manifests, indexes, receipts, and provenance.

That pattern is valid because witness media is not AnchorWorks user count memory.

The boundary is:

```text
media state payloads = witness-owned
manifests and receipts = metadata
reviewed text or anchors = candidate intake
AnchorWorks counts = one native binary count spine
```

## Promotion Path

Witness evidence becomes AnchorWorks knowledge only through explicit admission:

```text
state packet
-> reviewed textual/anchor content
-> user lexicon admission if needed
-> native count intake
-> binary count spine
```

No witness packet should silently promote itself into the user lexicon or count spine.

## System Contract

TrueVision and TrueAudio may observe, measure, package, and explain state.

They may not mutate AnchorWorks count authority, claim final answers, or bypass native count intake.

That keeps the stack clean:

```text
witness systems gather evidence
AnchorWorks stores language evidence
SecureCore guards promotion
ClearSpeak renders what the evidence supports
```
