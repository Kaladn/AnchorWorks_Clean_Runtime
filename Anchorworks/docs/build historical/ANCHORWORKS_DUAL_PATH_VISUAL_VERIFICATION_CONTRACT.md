# AnchorWorks Dual-Path Visual Verification Contract

Last updated: 2026-05-08

## Purpose

Dual-path visual verification compares two readings of the same source:

```text
Source path:
document parser -> text spans / layout regions / anchors

Vision path:
rendered page or visual frame -> region map -> recognition candidates
```

The goal is not to let vision replace source parsing. The goal is to let vision verify, rescue, and clean source intake.

Core law:

```text
Source reads first.
Vision verifies and rescues.
Comparison teaches the backend.
Approval promotes memory.
```

## Output Shape

```json
{
  "contract_version": "anchorworks_visual_dual_path_verification@1",
  "verification_report_id": "vverify_...",
  "source_id": "module_m54094",
  "visual_record_id": "visual_...",
  "region_map_id": "region_map_...",
  "recognition_layer_id": "recognition_...",
  "source_span_count": 3,
  "visual_text_candidate_count": 3,
  "exact_match_count": 2,
  "agreement_ratio": 0.6667,
  "reading_order_match": false,
  "issues": [],
  "approval_status": "preview_only",
  "writes_allowed": {
    "maps": false,
    "counts": false,
    "lifetime": false,
    "lexicon": false
  }
}
```

## Verification Targets

The first report checks:

- text agreement
- visual text missing from source path
- source text missing from visual path
- low-confidence visual text
- reading order agreement

Future checks may add:

- region agreement
- table cell agreement
- caption/figure agreement
- chart axis agreement
- garbage artifact detection
- raster-only recovery score

## Forbidden Side Effects

Dual-path verification must not:

- run OCR/CV by itself
- create regions
- write maps
- write counts
- write lifetime
- write Canonical lexicon
- promote OCR text
- decide document truth

## Tiny Law

```text
Parser gives source truth candidates.
Vision gives visual candidates.
Verifier compares.
Promotion decides.
```
