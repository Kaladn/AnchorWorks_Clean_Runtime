# AnchorWorks UI Buildout Plan

Status: planning only. No implementation in this document.

Purpose: rebuild the active UI around only what AnchorWorks V1 currently supports, with no fake authentication, no fake cockpit switches, no dead panels, and no ClearBox god-file carryover.

Core law:

```text
A UI control is a promise.
If runtime cannot honor it, do not render it.
```

## Current Truth

The previous active UI root was `UI2`, but that folder has been removed from the working tree. `app.py` still points at `UI2`, so the served UI path is currently broken until the active UI root is corrected.

The strongest remaining visual candidate is:

```text
D:\AnchorWorks_Clean_Runtime\Anchorworks\ui_archived_locked\production_shell\anchorworks_production.html
```

That file is a ClearBox-style production cockpit. It can be mined for layout ideas, but it must not be treated as already supported AnchorWorks runtime.

ClearBox source material lives at:

```text
F:\ClearboxAI-V2.5-main (2)
```

ClearBox contains useful technical ideas, especially chained intelligence and multi-model collaboration, but much of it lives in broad/god-file-style systems. AnchorWorks should copy the contract shape, not the god files.

## Supported Phase 1 Scope

Only these surfaces belong in the first authoritative UI:

```text
Chat
Evidence
Lexicon lookup/read-only authority
System truth/status
Block notes/citations
External API model lane
AnchorWorks local lane
```

Everything else is hidden or parked until the backend route exists and is verified.

## Active Backend Routes To Use

Chat and workbench:

```text
GET  /api/chat/status
GET  /api/chat/history
POST /api/chat/send
POST /api/chat/stop
POST /api/chat/side/start
POST /api/chat/citations/attach
POST /api/chat/notes/attach
```

AnchorWorks/ClearSpeak:

```text
GET  /api/clearspeak/status
POST /api/clearspeak/query
POST /api/clearspeak/cloud
POST /api/clearspeak/remix
```

Lexicon/status:

```text
POST /api/search_lexicon
GET  /api/lexicon/browse
GET  /api/lexicon/sample
GET  /api/lexicon/top
GET  /api/lexicon/recent
GET  /api/lexicon/distribution
GET  /api/symbol-genome/status
```

System/evidence:

```text
GET /api/health
GET /api/settings/inventory
GET /api/binary-substrate/status
GET /api/awsg/graphs
GET /api/awsg/graph/{graph_name}
GET /api/awsg/graph/{graph_name}/slice
```

Visual routes exist, but visual recognition is not Phase 1 UI:

```text
GET /api/visual-intake/files
GET /api/visual-intake/packet/{name}
```

## Phase 1 Tabs

### Chat

The Chat tab is the work surface.

Visible controls:

```text
message input
send
stop response
continue working
mode selector
evidence visibility toggle
side chat / branch, if route returns success
```

Supported modes:

```text
AnchorWorks
Documents
ClearSpeak / counts
External API
```

Do not show offline provider runners as active or planned model choices. AnchorWorks local means the deterministic local AnchorWorks/ClearSpeak path only. OpenAI API session support is the approved external model-assistance direction.

Chat display must show:

```text
user message
assistant response
mode used
evidence lane
citations attached
notes attached
available next actions
warnings/errors
```

### Evidence

Evidence is read-only proof, not a second chat.

Visible display:

```text
route used
source or count lane
represented anchors/symbols
missing anchors/symbols
citations
coordinates
blocked evidence
reason for refusal/no support
```

Evidence may be hidden from the chat view, but the backend evidence metadata must still be preserved.

### Lexicon

Lexicon is authority inspection.

Visible controls:

```text
word lookup
symbol lookup
pack/lane filter if supported by endpoint
genome status readout
```

Do not expose write controls until the backend path is explicitly verified for the new genome lexicon standard.

Visible display:

```text
word
symbol
authority lane
pack/source
status
row validity
```

### System

System tells the truth about runtime.

Visible display:

```text
server status
chat memory status
ClearSpeak status
binary substrate status
external API configured/unconfigured
active UI root
warnings
```

No fake Windows Hello/auth page. No fake service cards. No buttons for process control unless the backend route exists.

## Block Notes And Citations

Block note/cite is supported through chat memory sidecars.

UI behavior:

```text
Each assistant block may expose Note and Cite actions.
Note attaches user/user-authored context to the block.
Cite attaches a citation/evidence reference to the block.
The chat row remains the anchor for the sidecar data.
```

Backend routes:

```text
POST /api/chat/notes/attach
POST /api/chat/citations/attach
```

Card fields:

```text
message_id
block_id
note_text or citation_payload
source route
created_at
```

Hard rule:

```text
Notes and citations annotate.
They do not mutate lexicon, counts, maps, or Canonical.
```

## External Flagship Model Lane

AnchorWorks currently supports one OpenAI-compatible external API endpoint through `ModelApiClient`.

Configuration:

```text
ANCHORWORKS_MODEL_API_KEY or OPENAI_API_KEY
ANCHORWORKS_MODEL_API_BASE_URL
ANCHORWORKS_MODEL_API_MODEL
ANCHORWORKS_MODEL_API_TIMEOUT
```

Default base URL:

```text
https://api.openai.com/v1
```

Default model:

```text
gpt-4.1-mini
```

UI must show:

```text
configured / not configured
base URL
default model
endpoint
```

Hard rule:

```text
External model lane may render/explain.
It may not claim to update lexicon, counts, citations, notes, or ingestion.
```

## AnchorWorks Local Lane

AnchorWorks local lane means:

```text
lexicon recognition
document evidence lookup
ClearSpeak/count walk
local chat memory
local citation/note sidecars
```

It does not mean a local neural model until a backend route proves that provider exists.

UI label should be:

```text
AnchorWorks Local
```

Not:

```text
Offline provider runner
```

OpenAI API session support is the approved model-assistance direction.

## Chained Intelligence Contract

ClearBox had a useful chain pattern. AnchorWorks should keep the pattern as a future contract, not copy ClearBox god files.

Clean chain idea:

```text
AnchorWorks produces evidence frame.
External flagship model renders or critiques within that frame.
AnchorWorks verifies/gates the result.
User can continue, stop, or branch.
```

Minimum future chain lanes:

```text
anchorworks
external_api
resolver
```

Proposed future request shape:

```json
{
  "message": "user request",
  "lanes": [
    {"id": "anchorworks", "enabled": true},
    {"id": "external_api", "enabled": true, "model": "configured-default"}
  ],
  "interrupt_after": null,
  "resume_state": null,
  "evidence_required": true
}
```

Proposed future contribution shape:

```json
{
  "author": "anchorworks",
  "provider": "local",
  "model": "clearspeak",
  "content": "rendered contribution",
  "evidence_refs": [],
  "blocked_writes": [],
  "ms": 0,
  "usage": null
}
```

Proposed future chain state:

```json
{
  "run_id": "chain_...",
  "status": "running|interrupted|complete|failed",
  "contributions": [],
  "resume_allowed": true,
  "next_allowed_actions": ["continue_working", "stop", "branch"]
}
```

The lab protocol should remain:

```text
Read prior work.
Build on it.
Fix gaps in place.
Do not restart unless asked.
Move toward a finished artifact or closed answer.
```

Hard rule:

```text
Chained intelligence is not active UI until AnchorWorks has a verified chain route.
```

## Chat-Invoked UI Cards

The UI may render temporary controls inside chat, but only from approved recipes.

Approved first recipes:

```text
chat.continue
evidence.trace
note.attach
citation.attach
model.external_status
command.result
```

Recipe law:

```text
Dynamic UI, static recipes.
The assistant may request a known recipe.
The backend validates allowed actions.
The UI renders only known controls.
```

Temporary cards may be:

```text
closed
pinned
completed
```

They may not invent new backend actions.

## Panels To Hide Or Park

Do not show these as active Phase 1 UI:

```text
auth / Windows Hello
plugin manager
network/nodes
provider zoo
chain builder
inference cockpit
routing profiles
monitoring hub
mesh controls
tool workshop
visual recognition
intake batch runner
count rebuild controls
symbol migration writer
```

They may return later only when a verified backend route exists.

## Bridge Files To Build Later

When implementation begins, prefer small bridges instead of god files:

```text
chat_ui_bridge
note_cite_ui_bridge
evidence_ui_bridge
model_api_ui_bridge
lexicon_ui_bridge
system_status_ui_bridge
future_chain_ui_bridge
```

Each bridge should have one job:

```text
read backend shape
normalize for UI
render supported controls
report unsupported state honestly
```

## Non-Goals

This reset does not redesign AnchorWorks architecture.

This reset does not migrate runtime systems.

This reset does not add new backend capability.

This reset does not copy ClearBox god files.

This reset does not build V2.

This reset only defines the active UI surface that current AnchorWorks V1 can honestly support.

## Verification Before Implementation Is Called Done

Required checks:

```text
Only one UI root is served.
No served route points to deleted UI2.
No served route points into locked archived UI unless intentionally chosen as the new active root.
No active UI imports files from inactive UI folders.
No auth gate appears.
Chat send works.
Chat stop works.
Continue working action renders when returned.
Note attach works.
Citation attach works.
Evidence display renders read-only proof.
External API status shows configured/unconfigured truth.
Unsupported panels are hidden or clearly parked.
Tests pass.
```

## First Build Order

1. Pick the one authoritative UI root.
2. Make `/` serve that root.
3. Remove auth gate and unsupported panels from active display.
4. Wire chat send/history/stop only.
5. Wire continue/evidence action cards from returned workbench actions.
6. Wire note/citation cards.
7. Wire external API status and mode.
8. Wire read-only evidence tab.
9. Wire read-only lexicon lookup.
10. Add chain contract display later, but no active chain controls until backend exists.

Tiny lock:

```text
Chat works.
Evidence proves.
Lexicon governs.
System tells the truth.
```

