# AnchorWorks UI Reset Plan

Status: plan only. No implementation is authorized by this document.

## Purpose

AnchorWorks needs a new active UI that behaves like an operating surface, not a historical dashboard. The current UI files contain useful work, but the active surface is carrying old assumptions, dead controls, fake auth, stale service paths, and settings that look powerful while not steering runtime.

The reset goal is simple:

```text
Preserve old UI.
Remove old UI from active serving path.
Build new served UI from truth-first tabs.
No fake controls.
No dead switches.
No setting appears unless runtime actually reads it.
```

## Core Laws

```text
A UI control is a promise. If runtime cannot honor it, do not render it.
```

```text
Chat works.
Evidence proves.
Lexicon governs.
System tells the truth.
```

```text
If backend does not read it, UI does not show it as a control.
```

## Non-Goal

This reset does not redesign AnchorWorks architecture.
This reset does not migrate runtime systems.
This reset does not add new backend capability.
This reset only changes the active UI surface and removes fake or stale controls from the served path.

## Companion Docs

Agent implementation and review guide:

```text
ANCHORWORKS_UI_RESET_AGENT_GUIDE.md
```

User command and phrase cheat sheet:

```text
ANCHORWORKS_USER_COMMAND_CHEATSHEET.md
```

## Directory Shape

Active path:

```text
UI2/
```

This is the only served UI root. It should be small, direct, and readable.

Preserved legacy path:

```text
ui_legacy_locked/
```

This contains existing UI files moved out of the serving path. Nothing in the server should route to it. Legacy files are preserved for reference only. No deletion.

## Active Tabs

The full new UI has seven tabs:

```text
Chat | Evidence | Lexicon | Intake | Counts | Visual | System
```

Phase 1 builds only:

```text
Chat | Evidence | Lexicon | System
```

Do not build Intake, Counts, or Visual in Phase 1. If placeholders are necessary for navigation continuity, they must be visibly labeled:

```text
NOT WIRED
```

## Phase 1 Tab Contracts

### Chat

Purpose: primary work surface.

Displays:

- active conversation
- message input
- assistant responses
- route/mode label for each assistant response
- stop state when a response is stopped

Controls:

- Send
- Stop Response
- mode selector only for backend-supported modes:
  - ClearSpeak
  - Counts Only
  - Documents + Counts, only if backend route is wired
- evidence toggle:
  - Show Evidence
  - Hide Evidence

Temporary action buttons under assistant messages may appear only from approved action recipes:

- Continue Working
- Review Evidence
- Open Lexicon
- Run Counts Query
- Stop

Rules:

- No fake model provider switch.
- No fake auth.
- No hidden count writes from chat.
- ClearSpeak read-only queries must be labeled read-only if not saved.

### Evidence

Purpose: show why an answer was allowed to speak.

Displays:

- selected answer trace
- chosen symbols
- rejected symbols
- rejection reasons
- count support
- local overlay support
- document/source support
- locator references
- evidence lane labels

Evidence lanes:

- lexicon
- local overlay
- AWSC counts
- flat document
- visual packet
- none

Controls:

- select current/previous answer trace
- copy trace/report, if implemented

Rules:

- read-only
- no promotion
- no lexicon mutation
- no map/count writes

### Lexicon

Purpose: authority browser.

Displays:

- word anchors
- phrase anchors
- symbol
- pack/lane
- status
- source or migration note when present
- genome status summary

Controls:

- toggle: Words | Phrases
- search by word, phrase, or symbol
- inspect entry
- allocate new genome symbol, only if backend endpoint exists
- checkpoint genome, only if backend endpoint exists

Rules:

- no old spare-slot language in active UI
- no tone signature as identity
- no dangerous bulk lexicon actions in normal browsing
- dangerous actions, if retained, belong behind an explicit admin gate later

### System

Purpose: tell runtime truth.

Displays:

- data root
- active UI path
- served UI root
- server health
- current branch/commit if available
- binary substrate paths/status
- chat memory path/status
- settings inventory with runtime-active vs diagnostic-only labels

Controls:

- refresh status
- open diagnostics report, if backend endpoint exists

Rules:

- no fake service status
- no Windows Hello/auth gate unless `auth.required` is explicitly true and backend auth routes exist
- diagnostic-only settings are collapsed or labeled, not presented as active runtime steering

## Chat Memory Contract

Chat memory must be treated as a real system lane.

Each chat row should carry:

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

Expected behavior:

- live chat rows are saved unless the UI explicitly marks a query read-only
- ClearSpeak direct/read-only queries are not silently mixed into saved chat memory
- Stop Response records `stop_requested`, not fake completion
- archive import remains separate from live chat
- finalize preview and finalize remain explicit user actions
- citations and notes attach to specific message ids or trace ids

## Legacy Lock Rules

- Existing UI is moved into `ui_legacy_locked/`.
- Nothing is deleted.
- No route serves `ui_legacy_locked/`.
- No new active UI imports scripts from `ui_legacy_locked/` by accident.
- Any legacy behavior copied forward must be inspected, renamed if needed, and owned by `UI2/`.

## Forbidden Moves

- Do not show a control unless a backend route or runtime setting honors it.
- Do not show auth as active unless auth is actually implemented and enabled.
- Do not show settings as active when `settings_inventory` says diagnostic-only.
- Do not route active UI to historical production shell.
- Do not expose dangerous lexicon operations in the main Lexicon browser.
- Do not turn the reset into Intake, Counts, or Visual implementation.

## Verification

Phase 1 is complete only when:

```text
server serves UI2/
no served route points to ui_legacy_locked/
UI2/ does not import, reference, or load files from ui_legacy_locked/
no Windows Hello/auth gate appears unless auth.required is explicitly true
Chat tab renders
Evidence tab renders read-only
Lexicon tab can search/inspect when backend endpoint exists
System tab shows real runtime facts only
diagnostic-only settings are labeled or hidden
tests pass
git tree clean
```

## Implementation Order

1. Move existing UI files to `ui_legacy_locked/` without deletion.
2. Create `UI2/` with a minimal shell.
3. Wire server static serving to `UI2/`.
4. Build Chat tab.
5. Build Evidence tab.
6. Build Lexicon tab.
7. Build System tab.
8. Verify no active route touches `ui_legacy_locked/`.
9. Run tests.
10. Commit.

## Later Tabs

After Phase 1 is stable:

- Intake
- Counts
- Visual

These should be added one at a time, with the same law:

```text
No fake controls.
No dead switches.
No setting appears unless runtime actually reads it.
```
