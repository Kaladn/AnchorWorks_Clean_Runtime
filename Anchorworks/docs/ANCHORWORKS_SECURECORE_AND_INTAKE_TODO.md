# AnchorWorks Finish-Line TODO: Intake, Counts, SecureCore

Updated: 2026-05-16

This TODO is the current lock for AnchorWorks before the next work lane moves to SecureCore. The goal is to stop pretending partial paths are complete, remove security confusion, and finish the intake/count substrate with receipts.

## Current Receipts

Map archive:

```text
Archive: D:\AnchorMaps_archive_20260516_AnchorMaps.zip
Readable: yes
Contains: observed_maps/, symbolic_maps/
Size at verification: 2,111,749,107 bytes
```

Map roots still present:

```text
D:\AnchorMaps\observed_maps   2,672 files, 40,224,741,771 bytes
D:\AnchorMaps\symbolic_maps  10,688 files,  5,678,477,907 bytes
```

Active count root is not full:

```text
D:\AnchorWorks_Clean_Runtime\State\symbol_counts_binary
985 files
785,843 bytes
```

Known AWSM identity issue:

```text
AWSM maps read OK: 2,672 / 2,672
canonical rows: 12,283
canonical genome-style rows: 10,938
canonical non-genome rows: 1,345
source-local rows: 57,498
```

Therefore the full count rebuild must be genome-corrected during native merge.

## Hard Laws

```text
No security theater.
No fake auth.
No unverified network claims.
No legacy runtime bridges.
No Python bulk count processing.
No JSON lifetime monolith in the hot path.
No giant observed map JSON in chat runtime.
No map merge unless canonical symbols are corrected to genome authority.
No deleting original curation/data until archive verification and explicit approval.
No raw top-K speech.
```

## Phase 1 - Archive and Clean Start Receipts

Status: in progress

Tasks:

```text
1. Verify D:\AnchorMaps_archive_20260516_AnchorMaps.zip lists both observed_maps/ and symbolic_maps/.
2. Record archive size and verification command.
3. Do not delete D:\AnchorMaps until explicitly approved.
4. Identify disposable bad run:
   D:\AnchorWorks_Clean_Runtime\State\State
5. Remove disposable bad run only after approval.
```

Definition of done:

```text
Archive readable.
Bad run identified.
No source/canonical/structural data destroyed.
Repo clean.
```

## Phase 2 - Native AWSM to AWSC Merge

Status: required next AnchorWorks build item

Purpose:

```text
Use existing AWSM maps directly as input.
Correct canonical symbols to live genome authority in memory.
Write only AWSC binary cells.
```

Required command shape:

```text
anchorworks-symbol-counts merge-awsm-dir
  --input D:\AnchorMaps\symbolic_maps
  --canonical D:\AnchorWorks_Clean_Runtime\Canonical
  --structural D:\AnchorWorks_Clean_Runtime\Structural
  --output D:\AnchorWorks_Clean_Runtime\State\symbol_counts_binary
  --generation 20260516
```

Requirements:

```text
1. C++ reads AWSM files directly.
2. C++ reads live lexicon authority or a generated compact authority table.
3. Canonical AWSM symbols are remapped to current genome symbols during merge.
4. Source-local symbols remain source-local unless promoted by authority.
5. NULL never enters AWSC relation memory.
6. No AWSS file written.
7. No source-local symbol-count JSON written.
8. No observed-map JSON loaded in runtime.
9. AWSC verify passes.
10. Output metadata records input map count, relation count, remap count, skipped/null count, generation.
```

Tests:

```text
1. Fixture AWSM with old canonical symbol remaps to genome symbol.
2. Fixture AWSM with genome symbol remains unchanged.
3. Source-local relation stays source-local.
4. Invalid lane rejects.
5. Corrupt AWSM rejects.
6. Merge output verifies.
7. No intermediate AWSS/source-local JSON is created.
```

Definition of done:

```text
Native command exists.
Tests pass.
Small fixture merge verifies.
Full map merge runs detached.
Active AWSC root is genome-native.
ClearSpeak counts mode uses the active root.
```

## Phase 3 - TrueVision First Correction

Status: required before fresh ingest

Problem:

```text
Current PDF preparation extracts text before document-film/visual preservation.
Policy says: NEVER NORMALIZE PRIOR TO VISION.
```

Required path:

```text
source bytes
-> TrueVision visual/document-film preservation
-> visual refs and geometry metadata
-> derived text extraction
-> anchorization
-> mapping
```

Tasks:

```text
1. Move PDF visual preservation before PDF text extraction.
2. Preserve document-film packet where possible.
3. Keep recognition_status=not_run until a recognition backend exists.
4. Ensure visual refs flow into AWSV.
5. Ensure visual preview writes_allowed remains maps=false counts=false lifetime=false lexicon=false.
6. Add tests for PDF with extractable page images.
7. Add tests for PDF with no extractable page images: warn, do not fake recognition.
```

Definition of done:

```text
Vision proof runs before text derivation.
PDF visual metadata survives into AWSV.
No OCR/recognition is implied.
Tests pass.
```

## Phase 4 - Runtime Chat/Counts Sanity

Status: required after active AWSC rebuild

Tasks:

```text
1. Ask counts-only test questions:
   - what is inertia?
   - who is Isaac Newton?
   - why worry about laws of physics?
   - A 2 kg object accelerates at 3 m/s^2. What net force acts on it?
2. Confirm no off-frame junk leaks into speech.
3. Confirm glue words remain available for placement but do not dominate content.
4. Confirm inference admission blocks raw top-K fallback.
5. Confirm trace shows accepted/rejected candidates.
```

Definition of done:

```text
Counts mode is honest, traceable, and not word salad.
Formula lane may reject cleanly if formula solving is not built.
No raw candidate pile becomes assistant speech.
```

## Phase 5 - SecureCore Immediate Sweep

Status: next major work lane

Purpose:

```text
Stop security confusion and establish a real local security control surface.
```

Hard scope:

```text
Plan and inspect first.
Do not randomly block infrastructure.
Do not trust geolocation labels without RDAP/WHOIS verification.
Do not conflate outbound block with inbound attack.
Do not let UI/auth cosplay return.
```

Tasks:

```text
1. Identify SecureCore repo/root and active files.
2. Inventory current firewall/security scripts.
3. Identify what is actually connected to AnchorWorks, if anything.
4. Define SecureCore event schema:
   - timestamp
   - local process
   - pid
   - local address/port
   - remote address/port
   - direction
   - protocol
   - rule/action
   - attribution source
   - confidence
   - evidence command
5. Add verification commands for firewall rules.
6. Add local process attribution command:
   Get-NetTCPConnection -> OwningProcess -> Get-Process
7. Add RDAP/WHOIS verification lane for IP ownership.
8. Add allow/block decision record.
9. Add rollback/removal command for firewall rules.
10. Add log location and Event ID references.
```

Definition of done:

```text
Every block has evidence.
Every attribution has source/confidence.
Every firewall change has rollback.
Outbound vs inbound is explicit.
SecureCore does not invent threat claims.
```

## Phase 6 - SecureCore Integration Boundary

Status: after SecureCore sweep

Allowed AnchorWorks relationship:

```text
AnchorWorks may display SecureCore events.
AnchorWorks may cite SecureCore evidence.
AnchorWorks must not silently create firewall rules from chat.
```

Required boundary:

```text
SecureCore owns security actions.
AnchorWorks owns explanation and trace display.
User approval owns mutation.
```

Definition of done:

```text
No hidden security mutation from chat.
No fake auth page.
No mystery block rules.
Security events are inspectable and reversible.
```

## Final Finish-Line Order

```text
1. Commit current docs.
2. SecureCore inspection/planning.
3. Native AWSM->AWSC merge implementation.
4. TrueVision-first correction.
5. Full genome-corrected count rebuild.
6. Counts-mode sanity tests.
7. Only then fresh data expansion.
```

## Working Law

```text
Archive first.
Trace first.
Verify first.
Then mutate.
```

