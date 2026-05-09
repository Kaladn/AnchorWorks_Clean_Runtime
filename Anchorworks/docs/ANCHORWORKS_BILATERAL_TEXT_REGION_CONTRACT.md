# AnchorWorks Bilateral Text Region Contract

Last updated: 2026-05-08

## Purpose

Bilateral text regions are the production unit for typed-page visual ingestion.

They record both sides of a text-bearing region:

```text
source_text = what the document/layout claims
visual_text = what the rendered/captured page appears to show
agreement = how those sides compare
permissions = what each side may do
approval_status = whether anything may join memory
```

Core law:

```text
Source tells.
Vision witnesses.
The bilateral record remembers both.
Agreement adjusts trust.
Permissions block drift.
Promotion decides memory.
```

Agreement strengthens trust. Disagreement creates evidence, not truth.

## Boundary

A bilateral text region is source-local evidence. It may be used by verification, rescue, audit, cleanup, and later promotion workflows.

It must not directly:

- create Canonical anchors
- write maps
- write counts
- write lifetime memory
- write lexicon entries
- allow visual text to speak as truth
- treat OCR or visual recognition as authoritative by default

## Required Record Shape

```json
{
  "schema_version": "anchorworks_bilateral_text_region@1",
  "bilateral_text_region_id": "btext_...",
  "page_id": "page_1",
  "visual_record_id": "visual_...",
  "region_id": "r42",
  "source_text": {
    "text": "photosynthesis converts light energy...",
    "authority": "source_layout_evidence",
    "span_id": "s42",
    "reading_order": 17,
    "permissions": {
      "may_feed_text_intake": true,
      "may_feed_maps": true,
      "may_feed_counts": "if_source_authority_approved",
      "may_feed_lifetime": "promotion_required",
      "may_speak": true
    }
  },
  "visual_text": {
    "text": "photosynthesis converts light energy...",
    "authority": "derived_visual_recognition",
    "candidate_id": "vc42",
    "confidence": 0.98,
    "permissions": {
      "may_feed_text_intake": false,
      "may_feed_maps": "source_local_candidate",
      "may_feed_counts": "source_local_preview",
      "may_feed_lifetime": false,
      "may_speak": false,
      "may_rescue": true,
      "may_audit": true,
      "promotion_required": true
    }
  },
  "agreement": {
    "status": "exact",
    "score": 1.0,
    "normalized_source": "photosynthesis converts light energy",
    "normalized_visual": "photosynthesis converts light energy"
  },
  "approval_status": "candidate",
  "writes_allowed": {
    "maps": false,
    "counts": false,
    "lifetime": false,
    "lexicon": false
  },
  "notes": []
}
```

## Agreement Statuses

```text
exact
near
missing_visual
missing_source
conflict
unreadable_visual
source_layout_only
visual_rescue_candidate
```

### exact

Source text and visual text normalize to the same value.

Default handling:

```text
source_text remains authority
visual_text confirms/witnesses
trust may increase
normal promotion gate still applies
```

### near

Source text and visual text are similar but not identical.

Default handling:

```text
source_text remains authority
visual_text becomes cleanup/audit evidence
review may be required
```

### source_layout_only / missing_visual

Source text exists, but visual text is absent or unreadable.

Default handling:

```text
source_text remains authority
visual path failed or did not observe the region
no visual penalty unless visual evidence was expected
```

### visual_rescue_candidate / missing_source

Visual text exists, but source text is absent.

Default handling:

```text
visual_text may rescue
visual_text may audit
visual_text may not speak
visual_text may not feed lifetime
review and promotion are required
```

### conflict

Source text and visual text disagree.

Default handling:

```text
block promotion
preserve both sides
mark for review
do not count
do not map as truth
```

## Default Permissions

Source-side text may feed normal text intake only under the usual route and authority gates.

```text
source_text:
  may_feed_text_intake: true
  may_feed_maps: true
  may_feed_counts: if source authority approved
  may_feed_lifetime: promotion_required
  may_speak: true
```

Visual-side text is rescue/audit evidence by default.

```text
visual_text:
  may_feed_text_intake: false
  may_feed_maps: source_local_candidate
  may_feed_counts: source_local_preview
  may_feed_lifetime: false
  may_speak: false
  may_rescue: true
  may_audit: true
  promotion_required: true
```

## Count Lane Mapping

Bilateral text allows counts to retain provenance instead of flattening every token into the same trust bucket.

Suggested future count lanes:

```text
verified_source_counts
source_only_counts
visual_rescue_preview_counts
conflict_hold_no_counts
```

### verified_source_counts

Use when source text and visual text agree and source authority is approved.

### source_only_counts

Use when source text is valid but visual witness is absent or not required.

### visual_rescue_preview_counts

Use only for source-local preview and review workflows. These counts must not join global/lifetime memory without explicit promotion.

### conflict_hold_no_counts

Use when source and visual disagree. Preserve evidence, block promotion, and require review.

## Promotion Rules

Bilateral text regions are always created as:

```text
approval_status: candidate
writes_allowed:
  maps: false
  counts: false
  lifetime: false
  lexicon: false
```

Promotion is a separate AnchorWorks decision. Promotion must inspect:

- source authority
- visual witness status
- agreement status
- confidence
- route permissions
- operator approval

## Fit With Existing Stack

```text
Visual Manifest
-> Visual Region Map
-> Visual Recognition Layer
-> Bilateral Text Region
-> Dual-Path Verification Report
-> PPS Trial / Backend Tuning
-> Approval Promotion
```

Bilateral text is the bridge between source layout evidence and visual recognition evidence. It does not replace either side.
