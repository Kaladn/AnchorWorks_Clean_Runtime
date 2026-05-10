# AnchorWorks Chat Teaching Event Later

Last updated: 2026-05-09
Status: parked for later

## Purpose

This note parks the chat teaching-event idea so current work can stay focused on
answer fluency.

The idea is useful, but it is not the next speaking fix.

## Parked Shape

When the user explains something important to the system, chat may eventually
offer guided next actions instead of silently changing durable state.

Possible actions:

```text
Map This
Create Citation
Add Note
Review Anchors
Continue Working
```

## Four-Level Record

```text
L1 raw statement
L2 anchorized statement
L3 framed meaning
L4 citation/evidence link
```

Example:

```text
this is how I sear meat
```

Potential frame:

```json
{
  "frame_type": "method_declaration",
  "actor": "I",
  "action": "sear",
  "object": "meat",
  "approval_status": "candidate"
}
```

## Hard Boundary

This idea should not block the current ClearSpeak fluency work.

Current priority:

```text
classify anchor roles
detect query frame
use glue anchors as direction
search counts through shaped anchor pairs
rank context clouds by the frame
render from selected anchors only
```

Tiny law:

```text
Teaching events can wait.
Fluent answer rendering comes first.
```
