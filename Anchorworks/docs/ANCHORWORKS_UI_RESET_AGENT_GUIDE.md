# AnchorWorks UI Reset Agent Guide

Status: agent-facing documentation. This file does not authorize implementation by itself.

## Purpose

This guide is for Codex-style agents working on the UI reset. It explains what is intentionally left out, what must remain untouched, and how to avoid rebuilding another haunted dashboard.

## Operating Rule

```text
Do less, but make it true.
```

The UI reset is not a backend migration. It is a serving-path and surface-truth cleanup.

## Phase 1 Scope

Only these tabs are in Phase 1:

```text
Chat | Evidence | Lexicon | System
```

Everything else is parked:

```text
Intake | Counts | Visual
```

Do not implement parked tabs while working Phase 1. At most, create clearly disabled placeholders marked:

```text
NOT WIRED
```

## Legacy Handling

Existing UI files move to:

```text
ui_legacy_locked/
```

Rules:

- preserve legacy files
- do not delete legacy files
- do not serve legacy files
- do not import scripts from legacy
- do not copy forward behavior without naming the backend route or runtime contract it depends on

Verification must prove:

```text
UI2/ does not import, reference, or load ui_legacy_locked/
```

## Active UI Root

The only served UI root should be:

```text
UI2/
```

If server code points to any other UI root, the reset is not complete.

## Control Admission Test

Before adding any button, switch, slider, dropdown, or setting, answer:

```text
What backend route or runtime setting honors this control?
What does it change?
How do we verify the change happened?
What happens if the backend is unavailable?
```

If those answers are not known, do not render the control.

## Display Admission Test

Before adding any status card, badge, count, or report:

```text
Where does the value come from?
Is it live runtime truth, saved report truth, or diagnostic-only?
Can the user tell which one it is?
```

If not, label it or leave it out.

## Chat Memory Requirements

Chat is not just UI text. It is a memory lane.

Each saved chat row should support:

```text
conversation_id
message_id
timestamp
role
mode
route
content
evidence_refs
stop_requested
finalized_status
```

Rules:

- live chat saves rows unless the action is explicitly read-only
- read-only ClearSpeak queries stay read-only unless the user chooses to save them
- Stop Response records `stop_requested`
- archive import is not live chat
- finalize preview and finalize are explicit actions
- citations and notes attach to message ids or trace ids

## Phase 1 Backend Surfaces

Use existing backend surfaces only. Do not create new backend capability during the UI reset.

Likely Phase 1 surfaces:

```text
/api/health
/api/user/storage/status
/api/settings/inventory
/api/chat/status
/api/chat/history
/api/chat/send
/api/chat/stop
/api/clearspeak/status
/api/clearspeak/query
/api/lexicon/entry
/api/search_lexicon
/api/lexicon/browse
/api/symbol-genome/status
```

Only use an endpoint after confirming it exists in `app.py`.

## Parked Items

These are intentionally out of Phase 1:

- full Intake workflow
- OpenStax ingest control
- AWSC rebuild UI
- TrueVision film UI
- graph visualization UI
- dangerous lexicon bulk actions
- auth enrollment
- service mesh controls
- fake provider/model routing
- Tree-Brain knobs that runtime does not read
- Symbol policy controls that runtime does not read

## Agent Checklist

Before completing any UI reset work:

```text
server serves UI2/
legacy is preserved under ui_legacy_locked/
no served route points to ui_legacy_locked/
UI2 does not import legacy files
no fake auth gate appears
Phase 1 tabs render
Chat can send or honestly reports backend unavailable
Evidence is read-only
Lexicon only shows authority controls backed by endpoints
System only shows runtime facts or clearly labeled diagnostics
tests pass
git tree clean
```

## Anti-Patterns

Do not do these:

- copy the old UI and rename it
- keep dead settings because they look impressive
- add a switch before finding the runtime reader
- make auth visible without working auth routes
- hide backend errors behind optimistic UI text
- show graph/count/intake tabs as active before they are wired
- mutate data from Evidence
- expose dangerous lexicon actions in the normal browser

## Agent Law

```text
Trace first.
Serve one UI.
Render only truth.
Park everything else.
```
