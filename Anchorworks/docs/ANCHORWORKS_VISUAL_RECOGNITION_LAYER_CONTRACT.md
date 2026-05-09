# AnchorWorks Visual Recognition Layer Contract

Last updated: 2026-05-08

## Purpose

Visual Region Map answers:

```text
where is something on the visual source?
```

Visual Recognition Layer answers:

```text
what candidate thing was seen there?
```

Recognition is candidate evidence. It is not source truth, not Canonical lexicon truth, not lifetime knowledge, and not a direct map/count write.

Core law:

```text
Recognition names candidates.
Relations connect candidates.
Approval promotes truth.
```

## Boundary

Recognition Layer may attach candidate labels, readings, classifications, and notes to visual regions.

Recognition Layer must not:

- create Canonical anchors
- write lifetime memory
- write global counts
- write source maps directly
- decide promotion
- hide uncertainty
- replace native geometry
- treat model output as truth

## Required Record Shape

```json
{
  "schema_version": "anchorworks_visual_recognition_layer@1",
  "recognition_layer_id": "vrec_...",
  "visual_record_id": "visual_596a28bab4021571",
  "region_map_id": "vrmap_...",
  "source_hash": "...",
  "source_name": "figure.png",
  "coordinate_space": "native_pixels",
  "backend": {
    "backend_id": "anchorworks_ocr_candidate_probe",
    "backend_type": "ocr",
    "backend_version": "contract_only",
    "provider": "local",
    "operation_id": "...",
    "created_at": "2026-05-08T00:00:00Z"
  },
  "candidates": [
    {
      "candidate_id": "vcand_0001",
      "candidate_type": "ocr_text",
      "region_id": "r1",
      "surface": "velocity",
      "normalized_surface": "velocity",
      "confidence": 0.91,
      "evidence_refs": ["r1"],
      "approval_status": "candidate",
      "authority": "source_local_visual_evidence",
      "speak_eligible": false,
      "map_eligible": false,
      "count_eligible": false,
      "lifetime_eligible": false,
      "payload": {},
      "warnings": []
    }
  ],
  "approval_status": "preview_only",
  "writes_allowed": {
    "maps": false,
    "counts": false,
    "lifetime": false,
    "lexicon": false
  },
  "trace": {
    "source": "visual_recognition_preview",
    "write_intent": "l3_recognition_candidate_only",
    "promotion_required": true
  }
}
```

## Candidate Types

Allowed first candidate types:

- `ocr_text`
- `object`
- `diagram_element`
- `chart_element`
- `table_structure`
- `ui_element`
- `frame_state_change`
- `symbolic_note`

Each type may use a specialized payload, but the common candidate fields remain mandatory.

## Common Candidate Fields

Every recognition candidate must include:

- `candidate_id`
- `candidate_type`
- `region_id`
- `confidence`
- `evidence_refs`
- `approval_status`
- `authority`
- `speak_eligible`
- `map_eligible`
- `count_eligible`
- `lifetime_eligible`
- `payload`

Rules:

- Candidate IDs are source-local handles.
- Candidate surfaces are display/review values, not Canonical anchors.
- Confidence is support weight, not proof.
- Eligibility defaults to false until an approval gate changes it.

## OCR Text Candidate

Shape:

```json
{
  "candidate_id": "vcand_text_0001",
  "candidate_type": "ocr_text",
  "region_id": "r_text_01",
  "surface": "velocity",
  "normalized_surface": "velocity",
  "confidence": 0.91,
  "payload": {
    "language": "en",
    "line_index": 0,
    "char_span": [0, 8],
    "reading_order": 3
  },
  "approval_status": "candidate"
}
```

Rules:

- OCR text must not enter text intake automatically.
- OCR text may become an intake candidate only after visual/text review.
- OCR text must keep region provenance.

## Object Candidate

Shape:

```json
{
  "candidate_id": "vcand_object_0001",
  "candidate_type": "object",
  "region_id": "r_object_01",
  "surface": "car",
  "confidence": 0.78,
  "payload": {
    "label_source": "backend_label",
    "class_id": "car",
    "attributes": []
  },
  "approval_status": "candidate"
}
```

Rules:

- Object labels are recognition candidates, not document claims.
- Object labels cannot speak as answer terms without promotion.
- Object labels must not create Canonical lexicon entries by default.

## Diagram Element Candidate

Shape:

```json
{
  "candidate_id": "vcand_diag_0001",
  "candidate_type": "diagram_element",
  "region_id": "r_arrow_01",
  "surface": "arrow",
  "confidence": 0.84,
  "payload": {
    "element_kind": "arrow",
    "orientation": "right",
    "connects_candidate_regions": ["r_label_01", "r_part_02"]
  },
  "approval_status": "candidate"
}
```

Rules:

- Diagram candidates may support later relation graph candidates.
- Diagram candidates are not final interpretation.

## Chart Element Candidate

Shape:

```json
{
  "candidate_id": "vcand_chart_0001",
  "candidate_type": "chart_element",
  "region_id": "r_axis_x",
  "surface": "time",
  "confidence": 0.75,
  "payload": {
    "element_kind": "axis_label",
    "axis": "x",
    "units": "seconds"
  },
  "approval_status": "candidate"
}
```

Allowed `element_kind` examples:

- `axis`
- `axis_label`
- `tick_label`
- `legend_item`
- `data_mark`
- `line_series`
- `bar_series`
- `curve`

## Table Structure Candidate

Shape:

```json
{
  "candidate_id": "vcand_table_0001",
  "candidate_type": "table_structure",
  "region_id": "r_table_01",
  "surface": "table",
  "confidence": 0.82,
  "payload": {
    "row_count": 5,
    "column_count": 4,
    "header_regions": ["r_header_01"],
    "cell_regions": ["r_cell_01", "r_cell_02"]
  },
  "approval_status": "candidate"
}
```

Rules:

- Table recognition may define structure candidates.
- Cell content still requires OCR/text candidate review.

## UI Element Candidate

Shape:

```json
{
  "candidate_id": "vcand_ui_0001",
  "candidate_type": "ui_element",
  "region_id": "r_button_01",
  "surface": "submit button",
  "confidence": 0.88,
  "payload": {
    "element_kind": "button",
    "state": "enabled"
  },
  "approval_status": "candidate"
}
```

UI recognition is useful for screenshots, app traces, and future system-help examples. It does not run commands or decide intent.

## Frame State Change Candidate

Shape:

```json
{
  "candidate_id": "vcand_state_0001",
  "candidate_type": "frame_state_change",
  "region_id": "r_object_01",
  "surface": "object moved",
  "confidence": 0.69,
  "payload": {
    "previous_frame_id": "frame_0009",
    "current_frame_id": "frame_0010",
    "change_kind": "moved",
    "from_region_id": "r_prev",
    "to_region_id": "r_current"
  },
  "approval_status": "candidate"
}
```

Frame state changes are for video, screen capture, and replay/film sequences.

## Symbolic Note Candidate

Shape:

```json
{
  "candidate_id": "vcand_note_0001",
  "candidate_type": "symbolic_note",
  "region_id": "r_full_canvas",
  "surface": "likely graph about velocity over time",
  "confidence": 0.6,
  "payload": {
    "note_kind": "scene_summary",
    "derived_from_candidates": ["vcand_chart_0001", "vcand_text_0001"]
  },
  "approval_status": "candidate"
}
```

Rules:

- Symbolic notes are derived notes only.
- Symbolic notes cannot become answer truth without approval.
- Symbolic notes must cite candidate/evidence refs.

## Relation Graph Fit

Recognition candidates do not connect themselves into truth.

The relation graph may later connect candidates:

```text
candidate A labels candidate B
candidate C is axis of chart D
candidate E is cell in row F
candidate G moved to region H
```

But the recognition layer only names candidates. Relation graph records must preserve their own confidence and provenance.

## TrueVision / Forge Window Fit

TrueVision operator outputs fit the recognition layer as source-local visual state candidates.

Example:

```json
{
  "candidate_id": "vcand_tvflag_0001",
  "candidate_type": "frame_state_change",
  "region_id": "r_grid_full_canvas",
  "surface": "AIM_RESISTANCE",
  "confidence": 0.72,
  "payload": {
    "operator_flag": "AIM_RESISTANCE",
    "operator_score": 0.72,
    "eomm_score": 0.82,
    "window_id": "000123"
  },
  "approval_status": "candidate",
  "speak_eligible": false,
  "map_eligible": false,
  "count_eligible": false,
  "lifetime_eligible": false
}
```

Law:

```text
TrueVision flags are observed detector outputs.
They are not proof.
They are not Canonical language.
They are not lifetime truth.
```

## U-Symbol Fit

If a recognition candidate needs a temporary symbol, use source-local U-symbols.

Rule:

```text
U + hash(source_id + "::" + candidate_type + "::" + normalized_surface)
```

U-symbols may support source-local preview maps later. They must not enter lifetime counts unless promoted.

## Forbidden Side Effects

Recognition layer creation must not:

- write maps
- write counts
- write lifetime
- write Canonical lexicon
- silently promote OCR text
- silently promote object labels
- generate final answer claims
- call command/tools
- run model inference unless explicitly routed through an approved backend

## Approval Path

Approval may later change candidate eligibility:

```text
candidate-only
-> reviewed visual evidence
-> source-local map eligible
-> text intake candidate
-> count eligible
-> lifetime eligible
```

Each step must be explicit and traceable.

## Tiny Law

```text
Region maps locate.
Recognition names.
Relations connect.
Approval promotes.
```
