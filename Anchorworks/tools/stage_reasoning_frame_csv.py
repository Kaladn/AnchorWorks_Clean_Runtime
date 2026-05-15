"""Stage question-to-reasoning-frame CSV files for AnchorWorks curation.

These rows are not fact-answer authority. They are useful for activity chooser,
question rewriting, and reasoning-frame clouds.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_INPUT = Path(r"D:\general_education_qa_revised.csv")
DEFAULT_OUTPUT_ROOT = Path(r"D:\AnchorWorks_Data_Curation\reasoning_frame_pack")


def clean_text(value: str) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"Question", "Answer_Frame", "Expected_Answer"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
        return [
            {
                "question": clean_text(row["Question"]),
                "answer_frame": clean_text(row["Answer_Frame"]),
                "expected_answer": clean_text(row["Expected_Answer"]),
            }
            for row in reader
        ]


def convert(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    converted = []
    for index, row in enumerate(rows):
        if not row["question"] or not row["answer_frame"]:
            continue
        converted.append(
            {
                "schema_version": "anchorworks.reasoning_frame.v1",
                "source_key": f"general_education_reasoning_frame::{index:05d}",
                "dataset_id": "lee/general_education_reasoning_frames",
                "dataset_config": "revised",
                "dataset_split": "local",
                "domain": "general_education_reasoning",
                "row_index": index,
                "question_text": row["question"],
                "reasoning_frame_text": row["answer_frame"],
                "expected_frame_text": row["expected_answer"],
                "answer_text": "",
                "fact_answer_authority": False,
                "approved_for_intake": True,
                "intake_lane": "reasoning_frame_cloud",
            }
        )
    return converted


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def write_plain_text(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(f"Question: {row['question_text']}\n")
            handle.write(f"Reasoning Frame: {row['reasoning_frame_text']}\n")
            expected = row.get("expected_frame_text") or ""
            if expected:
                handle.write(f"Expected Frame: {expected}\n")
            handle.write("\n---\n\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage reasoning-frame CSV for AnchorWorks.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()
    input_path = Path(args.input)
    output_root = Path(args.output_root)
    rows = load_rows(input_path)
    converted = convert(rows)

    jsonl_path = output_root / "jsonl" / "general_education_reasoning_frames.jsonl"
    text_path = output_root / "plain_text" / "general_education_reasoning_frames.txt"
    write_jsonl(jsonl_path, converted)
    write_plain_text(text_path, converted)
    report = {
        "schema_version": "anchorworks.reasoning_frame_pack_report.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_path": str(input_path),
        "output_root": str(output_root),
        "source_rows": len(rows),
        "converted_rows": len(converted),
        "jsonl_path": str(jsonl_path),
        "plain_text_path": str(text_path),
        "fact_answer_authority": False,
        "recommended_use": "activity chooser, question frame selection, reasoning-cloud shape",
        "blocked_use": "grounded factual answer authority",
    }
    reports = output_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "reasoning_frame_pack_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
