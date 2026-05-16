# Lexical Data Data Flow Map

Date: 2026-05-07
Root mapped: `C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data`
Git repo: no

This map describes the current `Lexical Data` folder as it exists on disk. It is not a cleanup plan and it does not declare what should be deleted. It names the active-looking entry points, data roots, reads, writes, and cross-service calls so the system can be consolidated without guessing.

## Current Operating Boundary

As of the current operator instruction, this folder is the only allowed working root:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data
```

Do not leave this root while auditing, mapping, editing, or preserving AnchorWorks/AnchorWorks material.

Forbidden without a new explicit operator instruction:

```text
C:\Users\mydyi\OneDrive\Documents\Desktop\AnchorWorks
D:\AnchorWorks
any downloaded/extracted copy outside Lexical Data
```

This means the live system is currently treated as split-but-contained here:

```text
Lexical Data/
+- Anchorworks/      nested app/runtime source copy
+- ui/               outer UI surface
+- Canonical/        lexicon payload
+- Spare_Slots/      spare symbol pools
+- State/            runtime state/counts/maps/chat memory
+- data/             older chat/citation/library data
+- docs/             local maps, recovery notes, and source docs
```

Operational law:

```text
Lexical Data is the working boundary.
Do not use outside folders as authority.
Do not copy outward.
Do not pull inward from outside without explicit approval.
Map first, then decide.
```

## Boundary

```text
Lexical Data/
+- Anchorworks/          nested AnchorWorks/AnchorWorks FastAPI app copy
+- ui/                   outer production-style browser UI
+- Canonical/            external canonical lexicon payload
+- Spare_Slots/          external spare-slot pools/monolith
+- State/                external runtime state and counts
+- data/                 old chat/citation/library-style data
+- config/               outer config payloads
+- runtime/              runtime support
+- openvino_env/         Python/OpenVINO environment
+- docs/                 root docs and source docs
```

Important distinction:

```text
Anchorworks/ is an app copy.
Lexical Data/State, Canonical, Spare_Slots are runtime/data roots.
Lexical Data/ui is a separate outer UI that talks to bridge-style APIs.
Lexical Data/data is old/library/chat/citation data, not the same as Anchorworks/State.
```

## Top-Level Systems

| Area | Classification | Entry points | Main reads | Main writes | Notes |
|---|---|---|---|---|---|
| `Anchorworks/` | nested non-git FastAPI app copy | `Anchorworks/src/AnchorWorks/app.py`, `Anchorworks/src/AnchorWorks/cli.py`, `launch_anchorworks.ps1` | parent `Lexical Data` root | parent `State`, `Canonical`, `Spare_Slots` | README says this app lives inside active `Lexical Data` and uses parent as data root. |
| `ui/` | outer browser UI | `ui/anchorworks_production.html`, `ui/js/core.js`, panel JS files | bridge/auth/citation/documap APIs, localStorage | browser localStorage, remote bridge services | This UI is not the same as `Anchorworks/src/.../ui`. |
| `Canonical/` | external lexicon | `Canonical/*.json`, `Canonical/structural.json` | lexicon lookup, coverage, assignment | lexicon promotion/assignment | Must be treated as runtime data until migrated. |
| `Spare_Slots/` | external spare slot authority | `Spare_Slots/spare_slots.json`, `pool_*.json` | slot assignment | spare slot depletion/return | Large external authority. Do not delete without proof. |
| `State/` | external runtime state | counts, observed maps, chat memory, reviews | ClearSpeak, mapping, chat, intake | counts, maps, chat rows, reviews | Heavy runtime state. |
| `data/` | old library/chat/citation data | `data/citations.db`, `data/chats`, `data/citations`, `data/notes`, `data/maps` | citation/library UI and old chat flows | citation DB and sidecars | Separate from `State/chat_memory`. |
| `openvino_env/` | local Python environment | executable env files | package imports | package installs/caches | Runtime support, not source. |

## Nested Anchorworks App Flow

Evidence:

- `Anchorworks/README.md` says the app operates against `C:\Users\mydyi\OneDrive\Documents\Desktop\Lexical Data` and expects `Canonical`, `Spare_Slots`, `Structural`, and `State` paths.
- `Anchorworks/src/AnchorWorks/app.py:100` defines `_default_data_root`.
- `Anchorworks/src/AnchorWorks/app.py:105` defines `create_app`.
- `Anchorworks/src/AnchorWorks/app.py:114` creates `FastAPI(title="AnchorWorks Lexicon")`.
- `Anchorworks/src/AnchorWorks/app.py:121-122` installs CORS with `allow_origins=["*"]`.

Startup flow:

```text
launch_anchorworks.ps1 or anchorworks CLI
-> Anchorworks/src/AnchorWorks/cli.py
-> create_app(data_root)
-> LexiconStore(data_root)
-> ClearSpeakService(LexiconStore)
-> ModelApiClient()
-> ChatMemorySystem(data_root, ClearSpeakService, ModelApiClient)
-> FastAPI routes
-> browser UI or direct API callers
```

Shared startup objects:

```text
LexiconStore
ClearSpeakService
ModelApiClient
ChatMemorySystem
```

## Nested Anchorworks API Routes

Evidence from `Anchorworks/src/AnchorWorks/app.py`:

| Route group | Lines | Main service | Reads | Writes |
|---|---:|---|---|---|
| Static UI | `129`, `133`, `137` | `FileResponse` | nested UI assets | none |
| Health | `141` | app/store state | data root | none |
| User storage status | `145` | `LexiconStore.user_storage_status` | user state scaffold | creates/checks user state |
| ClearSpeak status/query | `149`, `153` | `ClearSpeakService` | lexicon + lifetime counts | none expected |
| Chat status/history/send | `157`, `161`, `165` | `ChatMemorySystem` | chat sidecars, counts | chat JSONL; possible citations |
| Chat archive import | `172` | `ChatMemorySystem.import_archive` | external archive path | chat imports + system row |
| Chat finalize preview/finalize | `179`, `186` | `ChatMemorySystem.preview_finalize/finalize_day` | chat history + lexicon | user-side counts and reasoning memory on finalize |
| Citation/note attach | `193`, `209` | `ChatMemorySystem.attach_citation/attach_note` | chat sidecar | citation/note sidecars |
| Lexicon browse/search/status | `231-299` | `LexiconStore` | Canonical, State, counts, maps | mostly read |
| Lexicon approve/ignore/pending | `303-352` | `LexiconStore` | unmatched/pending/ignored | Canonical, State, Spare_Slots |
| Destructive lexicon routes | `356`, `360` | `clear_canonical`, `return_to_pool` | Canonical, Spare_Slots | destructive rewrite |
| Import/mapping | `364`, `371` | `import_words_dir`, `build_observed_map` | local paths, lexicon | Canonical, maps, counts |
| Intake | `378`, `391`, `403`, `410`, `420` | preview/prepare/archive/approve/map | uploads, text, archive path | prepared docs, lexicon approval, maps/counts |

## Nested Anchorworks Store Data Flow

Evidence from `Anchorworks/src/AnchorWorks/store.py`:

- `store.py:39` sets `Canonical` as canonical directory.
- `store.py:41` sets `Spare_Slots` directory.
- `store.py:44` sets `State` directory.
- `store.py:51-54` sets `observed_maps`, `misspelled_reviews`, `intake_uploads`, and `lifetime_co_occurrence_counts.json`.
- `store.py:61` sets user counts path.
- `store.py:79-85` creates state directories/files.

Store root paths:

```text
Canonical/
Spare_Slots/
State/
State/observed_maps/
State/misspelled_reviews/
State/intake_uploads/
State/lifetime_co_occurrence_counts.json
State/user/user_counts/lifetime_co_occurrence_counts.json
```

Read lanes:

```text
Canonical/*.json
Canonical/structural.json
Spare_Slots/spare_slots.json and/or pool files
State/lifetime_co_occurrence_counts.json
State/observed_maps/*.observed.json
State/misspelled_reviews/*.misspellings.json
State/intake_uploads/*.prepared.txt
```

Write lanes:

```text
Canonical/*.json                    lexicon approval/import/assignment
Spare_Slots/*                       slot assignment or return
State/unmatched_words.json          unresolved anchors
State/pending_words.json            review queue
State/ignored_words.json            ignored anchors
State/intake_uploads/*              prepared intake text
State/observed_maps/*               source-local map payloads
State/misspelled_reviews/*          spelling/review reports
State/lifetime_co_occurrence_counts.json
State/user/user_counts/*
State/user/chat_counts/*
```

Important methods:

| Method | Evidence | Role | Side effects |
|---|---:|---|---|
| `preview_document_intake` | `store.py:431` | compares prepared text to lexicon | should be preview-only |
| `prepare_intake_document` | `store.py:759` | converts/stages uploaded content | writes prepared/review artifacts |
| `build_observed_map` | `store.py:1330` | builds map and counts | writes observed map and count target |
| `_update_lifetime_relation_counts` | `store.py:944` | base count update | mutates lifetime counts |
| `observed_map_files` | `store.py:1004-1018` | map inventory | read-only |
| `misspelled_review_files` | `store.py:1020-1036` | review inventory | read-only |

## ClearSpeak / Counts Flow

Evidence:

- `Anchorworks/src/AnchorWorks/app.py:149` exposes `/api/clearspeak/status`.
- `Anchorworks/src/AnchorWorks/app.py:153` exposes `/api/clearspeak/query`.
- `Anchorworks/src/AnchorWorks/chat_memory_system.py:503` tells non-ClearSpeak chat users to switch to ClearSpeak mode to answer directly from lifetime anchor counts.

Flow:

```text
UI or chat mode
-> /api/clearspeak/query
-> ClearSpeakService.query()
-> LexiconStore retrieval
-> State/lifetime_co_occurrence_counts.json
-> response with represented anchors, evidence/count coordinates
-> UI display or chat response
```

Allowed side effects:

```text
none for direct query
chat rows only when called through ChatMemorySystem.send
```

Forbidden side effects:

```text
no lexicon promotion
no map write
no lifetime count write from query
```

## Chat Memory Flow

Evidence from `Anchorworks/src/AnchorWorks/chat_memory_system.py`:

- `chat_memory_system.py:36` roots chat memory at `State/chat_memory`.
- `chat_memory_system.py:136` defines `send`.
- `chat_memory_system.py:115` defines `finalize_day`.
- `chat_memory_system.py:365` defines `attach_citation`.
- `chat_memory_system.py:457` defines `import_archive`.

Chat write paths:

```text
State/chat_memory/chats/YYYY-MM-DD.jsonl
State/chat_memory/citations/YYYY-MM-DD.citations.json
State/chat_memory/notes/YYYY-MM-DD.notes.json
State/chat_memory/summaries/YYYY-MM-DD.txt
State/chat_memory/memory/lessons/*.jsonl
State/chat_memory/memory/reasoning/*.jsonl
State/chat_memory/memory/side_chats.json
State/chat_memory/imports/*
```

Chat send flow:

```text
UI chat composer
-> /api/chat/send
-> ChatMemorySystem.send(message, mode, branch, model)
-> append user row
-> if mode=clearspeak: call ClearSpeakService
-> if mode=api/model: call ModelApiClient
-> else: chat_memory fallback response
-> append assistant row
-> optional citation sidecar if ClearSpeak evidence exists
-> return messages + evidence payload
```

Finalize flow:

```text
/api/chat/finalize/preview
-> build prepared transcript from chat rows
-> preview lexicon coverage
-> no count write

/api/chat/finalize
-> build prepared transcript
-> build intake mapping with user_chat target
-> write user-side counts
-> write reasoning memory row
-> do not update base lifetime counts if user_chat target is honored
```

Archive import flow:

```text
/api/chat/archive/import
-> prepare_anchorworks_chat_archive(archive_root)
-> copy/archive fragments under State/chat_memory/imports
-> write prepared import metadata
-> append system chat row
-> no lifetime count write by design
```

## External Model Flow

Evidence:

- `Anchorworks/src/AnchorWorks/model_api_client.py:20` reads `ANCHORWORKS_MODEL_API_KEY` or `OPENAI_API_KEY`.
- Chat send can enter model mode through `/api/chat/send` and `ChatMemorySystem.send`.

Flow:

```text
UI chat mode=api/model
-> /api/chat/send
-> ChatMemorySystem.send
-> ModelApiClient.chat
-> OpenAI-compatible /chat/completions endpoint
-> append normal chat rows
```

Allowed writes:

```text
chat JSONL only
```

Forbidden writes:

```text
no lexicon writes
no counts writes
no map writes
no citations unless separately attached
```

## Outer Production UI Flow

This is the separate `ui/` folder at the `Lexical Data` root, not the nested `Anchorworks/src/.../ui`.

Evidence:

- `ui/js/core.js:302-304` defines `bridgeApi(path)` and routes `/api/*` calls to `ANCHORWORKS_CONFIG.bridge` or `http://localhost:5050`.
- `ui/js/init.js:170-215` probes `/api/boot` and bridge origins.
- `ui/js/console.js` contains many direct calls to chat, citations, lexicon, system, and model endpoints.
- `ui/js/panel-mapping.js` calls DocuMap and citation/library APIs.
- `ui/js/panel-network.js:8-12` documents file browse/read/write endpoints.

Outer UI shared flow:

```text
ui/anchorworks_production.html
-> ui/js/core.js
-> bridgeApi('/api/...')
-> bridge server at configured localhost port, usually 5050
-> specialist panels call bridge/citation/documap/auth/llm endpoints
-> responses render in browser
-> localStorage stores UI preferences, model selections, active panels, routes
```

Outer UI local browser state examples:

```text
anchorworks_bridge_url
anchorworks_chat_mode
gptModel
gptEndpoint
anchorworks_explorer_mode
anchorworks_tools_enabled
customContractRules
panel-specific selected run IDs and modes
```

Outer UI major panel lanes:

| Panel/file | Calls | Meaning |
|---|---|---|
| `ui/js/core.js` | `bridgeApi('/api/...')`, auth, boot, genesis, lexicon unload | bridge bootstrap and global helpers |
| `ui/js/console.js` | `/api/chat/send`, `/api/lexicon/*`, `/api/citations/*`, `/api/notes/*`, `/api/map*`, `/api/system*` | main chat, lexicon explorer, citations, notes, mapping, system status |
| `ui/js/panel-mapping.js` | `/api/documap/*`, library citation map APIs | document map/browser/top-k/intake UI |
| `ui/js/panel-network.js` | `/api/network/files/*` | browse/read/write remote node files |
| `ui/js/panel-help.js` | `/api/help/content/*`, `/api/help/search` | help lookup |
| `ui/js/panel-tools.js` | `/api/tools/*`, `/api/providers`, LLM tag endpoint | tool maker and provider/model UI |
| `ui/js/panel-nodes.js` | `/api/nodes/*` | node discovery, heartbeat, pairing |
| `ui/js/panel-routing.js` | `/api/routing/*` | route profile config |
| `ui/js/panel-settings-config.js` | `/api/config`, `/api/lakespeak/config` | config editing |
| `ui/js/panel-monitoring.js` | `/api/observe/*` | sensors/monitoring |

Outer UI writes are mostly remote bridge writes, not direct filesystem writes from browser. Local browser writes are preferences and session state in `localStorage`.

## Outer Runtime/Data Folders

### `State/`

Observed current contents include:

```text
State/lifetime_co_occurrence_counts.json
State/lifetime_co_occurrence_counts.zip
State/lifetime_by_symbol/**
State/observed_maps/*.observed.json
State/misspelled_reviews/*.misspellings.json
State/intake_uploads/*
State/chat_memory/**
State/user/**
State/ingest_staging/*
State/unmatched_words.json
State/pending_words.json
State/ignored_words.json
State/missing_anchor_registry.json
```

Classification:

```text
runtime memory and evidence state
must be backed up before consolidation
must not be deleted during source cleanup
```

### `Canonical/`

Classification:

```text
external live lexicon payload
contains canonical letter files and structural.json
must not be deleted until D-drive repo/runtime plan proves a replacement
```

### `Spare_Slots/`

Classification:

```text
external spare slot source
contains spare_slots.json, pool_*.json, pools_manifest.json
must not be deleted until authority is chosen
```

### `data/`

Observed current contents include:

```text
data/citations.db
data/chats
data/citations
data/notes
data/maps
data/memory
data/summaries
data/chat_packs
data/packs
data/raw
data/secrets
data/staging
```

Classification:

```text
Archived/library/chat/citation data lane
not the same as State/chat_memory
must be inventoried separately before migration
```

## Critical Cross-Boundary Edges

These are the places where this folder crosses from one subsystem into another.

| Edge | Source | Target | Risk |
|---|---|---|---|
| Nested app to parent data root | `Anchorworks/src/AnchorWorks/app.py`, `store.py` | `Lexical Data/Canonical`, `Spare_Slots`, `State` | source code and runtime state live side-by-side |
| Outer UI to bridge server | `ui/js/core.js:302-304` | `http://localhost:5050/api/*` by default | UI can mutate services outside this folder |
| Outer UI to citation service | `ui/js/console.js` citation calls | citation/notes APIs | citations may live in `data/citations.db` or remote service |
| Outer UI to DocuMap | `ui/js/panel-mapping.js` | `/api/documap/*` | mapping jobs may write outside root depending bridge config |
| Chat to external model | `model_api_client.py:20` | OpenAI-compatible API | data leaves local machine if configured |
| Network panel file writes | `ui/js/panel-network.js:8-12` | `/api/network/files/{nodeId}/write` | remote file write capability if backend allows |

## Fresh-Run Questions

Before this folder can be made clean, answer these:

1. Is `Lexical Data/Anchorworks` still used, or is it fossil code?
2. Is `Lexical Data/ui` the real UI, or is the nested `Anchorworks/src/.../ui` the real UI?
3. Which runtime lane is authoritative for chat memory: `State/chat_memory` or `data/chats` plus `data/citations.db`?
4. Which spare-slot source is authoritative: `Spare_Slots/spare_slots.json` or `Spare_Slots/pool_*.json`?
5. Should `Canonical/structural.json` replace old `Structural/structural.json` everywhere?
6. Which services are required at runtime: bridge `5050`, citations `5052`, LLM `11435`, nested FastAPI `8081`, or all of them?
7. Which data folders are private runtime backup and must never be committed?

## Safe Consolidation Law

```text
Source code goes to one repo.
Runtime state goes to one runtime root.
Historical fossils go to quarantine.
No deletion until copied, verified, and approved.
```

Recommended next map action:

```text
Create a migration inventory table:
path -> classification -> owner -> keep/migrate/quarantine/delete-later -> proof file count/size -> approval status
```

## Migration Inventory Seed

This map says the real issue is not lost code. The issue is that `Lexical Data` became a mixed working boundary where source, runtime state, model/env support, old data lanes, and history sit side-by-side.

The next step is not deletion. The next step is deciding authority.

Inventory contract:

```text
path -> classification -> owner -> action -> proof size/count -> approval status
```

Allowed actions:

```text
keep
migrate
quarantine
delete-later
do-not-touch
unknown
```

Approval states:

```text
unreviewed
operator-approved
blocked
verified
```

Seed inventory:

| Path | Classification | Owner | Action | Proof size/count | Approval status | Notes |
|---|---|---|---|---|---|---|
| `Anchorworks/` | nested app/source copy | source/runtime boundary | unknown | pending | unreviewed | Decide whether this is the live app or fossil copy. |
| `Anchorworks/recovered_workspace/` | combined code/support bundle | recovery/source boundary | keep | manifest present | unreviewed | Combines loose `ui/`, `app/docs`, `docs`, and root support files inside the allowed boundary without activating them. |
| `ui/` | outer browser UI | UI boundary | unknown | pending | unreviewed | Decide whether this is the real UI or old bridge UI. |
| `Canonical/` | canonical lexicon payload | lexicon authority candidate | do-not-touch | pending | unreviewed | Must not be deleted until lexicon authority is proven. |
| `Canonical/structural.json` | structural lexicon payload | structural lexicon authority candidate | do-not-touch | pending | unreviewed | Candidate replacement for old `Structural/structural.json` paths. |
| `Spare_Slots/` | spare symbol pools | spare-slot authority candidate | do-not-touch | pending | unreviewed | Decide pool files vs monolith authority. |
| `State/` | runtime state/counts/maps/chat memory | runtime authority candidate | do-not-touch | pending | unreviewed | Contains machine state; must not be committed blindly. |
| `data/` | old chat/citation/library lane | Archived data authority candidate | unknown | pending | unreviewed | Must be inventoried separately from `State/`. |
| `config/` | outer config payloads | config boundary | unknown | pending | unreviewed | Empty or inactive until proven otherwise. |
| `runtime/` | runtime support | runtime boundary | unknown | pending | unreviewed | Empty or inactive until proven otherwise. |
| `openvino_env/` | Python/OpenVINO environment | local environment | quarantine | pending | unreviewed | Runtime support only; not source. |
| `docs/` | local docs/maps/recovery notes | documentation boundary | keep | pending | unreviewed | This map lives here. |
| `launch_anchorworks.ps1` | launch script | runtime entry candidate | unknown | pending | unreviewed | Must be checked against actual live app path. |
| `ui_server_stderr.log` | runtime log | runtime artifact | quarantine | pending | unreviewed | Log file, not source. |
| `ui_server_stdout.log` | runtime log | runtime artifact | quarantine | pending | unreviewed | Log file, not source. |

Authority questions to resolve before migration:

1. Which UI is real: `ui/` or `Anchorworks/src/AnchorWorks/ui/`?
2. Which chat memory lane is real: `State/chat_memory` or `data/chats` plus `data/citations.db`?
3. Which spare-slot source is real: `Spare_Slots/spare_slots.json` or `Spare_Slots/pool_*.json`?
4. Which app source is real: `Anchorworks/` inside this boundary, or an outside git repo that must be re-imported later by explicit approval?
5. Which services are required: nested FastAPI `8081`, bridge `5050`, citations `5052`, local model `11435`, or only a subset?
6. Which data must never be committed: private docs, observed maps, counts, chat memory, model envs, runtime logs, and generated state?

Decision law:

```text
One source repo.
One runtime root.
Fossils in quarantine.
No deletion until copied, verified, and approved.
```

## Combined Code Bundle

The loose code/support material has been copied into:

```text
Anchorworks/recovered_workspace/
```

This is a preservation bundle, not a live runtime switch.

Bundle contents:

| Bundle path | Original path | Role |
|---|---|---|
| `Anchorworks/recovered_workspace/outer_ui/` | `ui/` | outer browser UI snapshot |
| `Anchorworks/recovered_workspace/loose_app_docs/` | `app/docs/` | loose app documentation |
| `Anchorworks/recovered_workspace/root_docs/` | `docs/` | root maps and docs |
| `Anchorworks/recovered_workspace/root_support/` | root files | loose support docs/scripts |
| `Anchorworks/recovered_workspace/COMBINED_CODE_MANIFEST.json` | generated | copy manifest and exclusions |

Not merged into code:

```text
Canonical/
Spare_Slots/
State/
data/
openvino_env/
runtime/
logs
```

Reason:

```text
Code can be combined.
Runtime authority must be decided.
Memory/counts/maps must not be merged blindly.
```

