# AnchorWorks Main System Wrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AnchorWorks the main usable system, with SecureCore and TrueVision treated as callable support systems instead of parallel centers of gravity.

**Architecture:** AnchorWorks owns user-facing language, intake, counts, rules, render, and chat flow. SecureCore is called later for safety, policy, logging, and runtime coordination. TrueVision is called later for visual/audio/state tooling. New ideas after this wrap become tools, workers, or agents behind registered interfaces.

**Tech Stack:** Python/FastAPI AnchorWorks backend, existing ClearSpeak/ChatMemorySystem, canonical/genome lexicon, existing tests, future adapters for SecureCore and TrueVision.

---

## Current Hierarchy Lock

```text
AnchorWorks = main attraction / face / language-count brain
SecureCore = support safety and runtime coordination
TrueVision = support state/media/tool stack
```

Hard laws:

```text
AW first.
SC second.
TV third.
New ideas become tools, agents, or workers.
No side system becomes the main interface unless AW calls it.
```

## Files In Scope

- Existing: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\chat_memory_system.py`
  - Owns chat send, model API message construction, and first-prompt injection.
- Existing: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\clearspeak.py`
  - Owns ClearSpeak count/render behavior and non-question flow responses.
- Existing: `D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\store.py`
  - Owns lexicon recognition, engagement classification, and canonical/genome identity.
- Existing: `D:\AnchorWorks_Clean_Runtime\Canonical\canonical_T.json`
  - Contains new canonical `truedepth` anchor.
- Existing: `D:\AnchorWorks_Clean_Runtime\Anchorworks\docs\ANCHORWORKS_INTAKE_RENDER_RULEBOOK.md`
  - Current AW intake/render authority.
- Existing: `D:\AnchorWorks_Clean_Runtime\Anchorworks\docs\ANCHORWORKS_AGENT_FIRST_PROMPT.md`
  - First message external model lane must see.
- Existing: `D:\AnchorWorks_Clean_Runtime\Anchorworks\docs\ANCHORWORKS_RULES_OF_ENGAGEMENT.md`
  - Conversation/input classification contract.
- Existing: `D:\AnchorWorks_Clean_Runtime\Anchorworks\tests\test_anchorworks_rulebook_docs.py`
  - Proves rulebook and first prompt exist and are injected.
- Existing: `D:\AnchorWorks_Clean_Runtime\Anchorworks\tests\test_conversation_input_type.py`
  - Proves info transfer and corrections do not force count answers.

## Task 1: Commit The Current AW Rule And Lexicon Lock

**Files:**
- Include current modified/untracked files listed above.
- Exclude unrelated TrueVision/SecureCore work.

- [ ] **Step 1: Verify current AW test suite**

Run:

```powershell
cd D:\AnchorWorks_Clean_Runtime\Anchorworks
python -m unittest discover -s tests -v
```

Expected:

```text
41 tests OK
```

- [ ] **Step 2: Inspect diff**

Run:

```powershell
git diff --stat
git status --short --branch
```

Expected:

```text
Only AW rule/prompt/chat/lexicon/conversation changes are staged for commit.
```

- [ ] **Step 3: Commit**

Run:

```powershell
git add src/AnchorWorks/chat_memory_system.py `
        src/AnchorWorks/clearspeak.py `
        src/AnchorWorks/store.py `
        docs/ANCHORWORKS_AGENT_FIRST_PROMPT.md `
        docs/ANCHORWORKS_INTAKE_RENDER_RULEBOOK.md `
        docs/ANCHORWORKS_RULES_OF_ENGAGEMENT.md `
        docs/superpowers/plans/2026-05-26-anchorworks-main-system-wrap.md `
        tests/test_anchorworks_rulebook_docs.py `
        tests/test_conversation_input_type.py `
        ..\Canonical\canonical_T.json

git commit -m "Lock AnchorWorks intake render rules and TrueDepth anchor"
```

Expected:

```text
Commit created with rulebook, first-prompt injection, conversation classification, and truedepth canonical anchor.
```

## Task 2: AW Usability Smoke Test

**Files:**
- No source changes unless a test fails.

- [ ] **Step 1: Start AW backend**

Run:

```powershell
cd D:\AnchorWorks_Clean_Runtime\Anchorworks
python -m uvicorn AnchorWorks.app:create_app --factory --host 127.0.0.1 --port 8081
```

Expected:

```text
Server starts on 127.0.0.1:8081.
```

- [ ] **Step 2: Verify health**

Run in a second terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8081/api/health
```

Expected:

```text
ok = true
```

- [ ] **Step 3: Verify non-question flow**

Run:

```powershell
Invoke-RestMethod http://127.0.0.1:8081/api/chat/send `
  -Method POST `
  -ContentType 'application/json' `
  -Body '{"message":"now keep in mind that we talk, not everything is a question","mode":"clearspeak","branch":"main"}'
```

Expected:

```text
mode = clearspeak
response mentions context
clearspeak.answer_assembly.stop_reason = info_transfer
```

- [ ] **Step 4: Verify TrueDepth recognition**

Run:

```powershell
Invoke-RestMethod http://127.0.0.1:8081/api/clearspeak/query `
  -Method POST `
  -ContentType 'application/json' `
  -Body '{"query":"what is TrueDepth?","limit":6}'
```

Expected:

```text
represented_content_anchors includes truedepth
missing_content_anchors is empty
```

## Task 3: AW/SC Boundary Stub, No Behavior Expansion

**Files:**
- Create later only after Task 1 and Task 2 pass.

Purpose:

```text
Define how AW will call SC without importing SC as the face.
```

First contract:

```text
AW asks for support.
SC returns receipt/status/action boundary.
AW displays or uses it.
```

Allowed future adapter calls:

```text
securecore.health
securecore.policy_check
securecore.runtime_receipts
securecore.worker_status
securecore.incident_summary
```

Forbidden:

```text
SC taking over chat UI
SC becoming the primary assistant
AW writing SC runtime state directly
hardcoded local paths
```

## Task 4: AW/SC/TV Harness Stub, No Tool Explosion

**Files:**
- Create later only after AW/SC boundary is verified.

Purpose:

```text
Define how AW will ask TV for state/media/tool support.
```

Allowed future adapter calls:

```text
truevision.health
truevision.manifest_lookup
truevision.state_profile_summary
truevision.render_job_status
truevision.tool_receipt
```

Forbidden:

```text
TV becoming AW
TV generation experiments changing AW contracts
AW treating generated media as evidence
binary lexicon detours
```

## Task 5: New Idea Intake Rule

Every new idea after this wrap must be classified before implementation:

```text
tool
worker
agent
rule
lexicon addition
renderer heuristic
external lab experiment
parking lot
```

If it is not one of those, it does not enter the build.

## Acceptance

This wrap is complete when:

```text
1. Current AW rules and TrueDepth anchor are committed.
2. AW test suite passes.
3. AW backend smoke test passes.
4. TrueDepth recognition works through API.
5. Non-question input does not force count answering.
6. SC and TV are explicitly treated as future support adapters.
7. No new side architecture is added.
```

## Final Lock

```text
AnchorWorks speaks.
SecureCore protects.
TrueVision sees and renders state.
Workers do the new work.
Agents coordinate only when registered.
Tools expose capability.
```
