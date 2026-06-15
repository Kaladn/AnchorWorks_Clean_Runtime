# SecureCore System

SecureCore is the governance and protection boundary for the stack. In this AnchorWorks workspace it should be treated as a system contract, not as an AnchorWorks count subsystem.

## Role

SecureCore answers these questions:

```text
is this write allowed
is this source trusted enough
is this promotion permitted
is this receipt valid
is this runtime boundary intact
```

It does not answer user questions, compute AnchorWorks counts, mutate the user lexicon, or replace native runtimes.

## Position In The Stack

SecureCore sits around the active systems:

```text
AnchorWorks = language, lexicon, count evidence, answer rendering
TrueVision = visual/state witness
TrueAudio = audio/state witness
SecureCore = permission, provenance, boundary enforcement
```

That means SecureCore is allowed to approve, block, label, sign, or audit a transition. It is not allowed to become the transition.

## Allowed Records

SecureCore may keep policy records, provenance receipts, run approvals, boundary failures, and promotion decisions.

Those records are metadata. They are not AnchorWorks count authority and they are not user lexicon entries.

## AnchorWorks Boundary

For AnchorWorks, SecureCore should enforce:

```text
user lexicon remains JSON
user counts remain one native binary file
count compute remains native
Python remains orchestration
answer claims trace to evidence
no silent promotion from witness data
```

If a future SecureCore adapter is added here, it should wrap admission and promotion decisions. It should not write count data directly.

## TrueVision And TrueAudio Boundary

For witness systems, SecureCore should enforce:

```text
witness packets are not truth by themselves
media-derived observations require provenance
promotion into AnchorWorks requires explicit intake
binary payloads and metadata stay separate
```

## Current Workspace Status

This AnchorWorks repository does not currently expose a full SecureCore runtime package as an active first-class subsystem. The current document therefore defines the boundary that future integration must obey.

Until that runtime exists here, SecureCore should be considered external governance, not internal count logic.
