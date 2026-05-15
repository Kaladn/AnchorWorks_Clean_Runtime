# AnchorWorks User Command Cheat Sheet

Status: user-facing draft for future UI display. This file is documentation only.

## Purpose

This cheat sheet gives users simple phrases that AnchorWorks can map to known intents. The assistant should treat these as phrase matches, not magic words. If the requested action is not wired, the assistant must say what is unavailable instead of pretending.

## Core Commands

| User phrase | Intended action | Notes |
|---|---|---|
| `continue working` | Continue the current workflow | Always safe as a chat action if a workflow is active. |
| `stop` / `stop response` | Stop the current response | Records stop state; does not pretend the answer completed. |
| `show evidence` | Reveal evidence panel for current answer | Display-only. |
| `hide evidence` | Collapse evidence display | Does not remove evidence metadata. |
| `review evidence` | Open current answer trace/evidence | Read-only. |
| `open lexicon` | Open Lexicon tab | Authority inspection. |
| `search lexicon for <word>` | Lookup anchor/word | Uses lexicon authority first. |
| `inspect symbol <symbol>` | Lookup symbol if backend supports it | Should show unavailable if no endpoint exists. |
| `ask counts only: <question>` | Run ClearSpeak counts lane | No document substitution. |
| `ask documents and counts: <question>` | Run document + counts lane if wired | Must label evidence lanes. |
| `save this chat` | Save current chat row/thread | Only if chat memory is active. |
| `read only query: <question>` | Query without saving memory | Must be clearly labeled read-only. |

## Chat Phrases

| User phrase | Meaning |
|---|---|
| `ask clearspeak` | Use ClearSpeak route. |
| `counts only` | Do not call documents; use count evidence only. |
| `no maps` | Avoid observed-map runtime lookup; use overlay/count path if available. |
| `use evidence` | Include evidence trace metadata. |
| `no evidence on screen` | Hide evidence UI but keep backend evidence refs. |
| `make it shorter` | Reduce displayed answer length if renderer supports it. |
| `expand the answer` | Ask renderer for more anchors/details if supported. |
| `why did it choose that` | Show chosen/rejected symbol trace. |

## Lexicon Phrases

| User phrase | Meaning |
|---|---|
| `find word <word>` | Search word anchor authority. |
| `find phrase <phrase>` | Search phrase authority. |
| `show symbol for <word>` | Show assigned symbol. |
| `show phrase anchors` | Switch Lexicon to phrase view. |
| `show word anchors` | Switch Lexicon to word view. |
| `genome status` | Show symbol genome status. |
| `checkpoint genome` | Run checkpoint only if backend endpoint exists. |
| `allocate symbol for <word>` | Allocate only through approved genome endpoint. |

## Evidence Phrases

| User phrase | Meaning |
|---|---|
| `show chosen symbols` | Display answer path symbols. |
| `show rejected symbols` | Display rejected candidates and reasons. |
| `show count support` | Display AWSC/count support. |
| `show source support` | Display flat document/source support if present. |
| `show locator refs` | Display block/line/source coordinates. |
| `what lane is this` | Display evidence lane label. |

## System Phrases

| User phrase | Meaning |
|---|---|
| `system status` | Show runtime facts only. |
| `where is data root` | Show data root. |
| `what UI is served` | Show active UI root. |
| `what commit am I on` | Show branch/commit if available. |
| `what settings are real` | Show runtime-active vs diagnostic-only settings. |
| `show diagnostics` | Display latest diagnostics if available. |

## Phrases That Must Not Mutate Data

These are inspection-only unless the user explicitly approves a write:

```text
review
show
inspect
open
explain
why
trace
status
preview
```

## Phrases That Require Confirmation

These may write or mutate and must require an explicit confirmation flow:

```text
delete
clear
reset
rebuild
approve all
deny all
return to pool
import
finalize
promote
rewrite
replace
```

## Honest Unavailable Response

If a command maps to an intent but the backend route is not wired, the assistant should say:

```text
That command is understood, but this UI/backend path is not wired yet.
```

Then it should offer only valid next actions.

## User Law

```text
Tell AnchorWorks what you want in plain words.
If it can do it, it should show the control.
If it cannot do it, it should say so plainly.
```
