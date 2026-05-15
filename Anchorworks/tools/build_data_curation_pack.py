"""Build AnchorWorks data curation planning artifacts.

This tool does not download datasets by default. It writes a source manifest,
Q/A conversion notes, and a clickable human action checklist for assembling a
clean college-grad corpus outside the repository.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUTPUT_ROOT = Path(r"D:\AnchorWorks_Data_Curation\college_grad_core")


HF_QA_DATASETS = [
    {
        "id": "allenai/sciq",
        "url": "https://huggingface.co/datasets/allenai/sciq",
        "config": "default",
        "split": "train",
        "domain": "science",
        "rows_hint": 13679,
        "shape": "question, correct_answer, support, distractors",
        "conversion": "question -> correct_answer; support becomes optional source context.",
        "recommendation": "first",
        "notes": "Clean science exam style. Strong for well-formed science clouds.",
    },
    {
        "id": "allenai/openbookqa",
        "url": "https://huggingface.co/datasets/allenai/openbookqa",
        "config": "main",
        "split": "train",
        "domain": "science",
        "rows_hint": None,
        "shape": "question_stem, choices, answerKey",
        "conversion": "question_stem -> selected choice text; open-book facts are useful if present in export.",
        "recommendation": "early",
        "notes": "Small, science-heavy, and useful for fact-cloud formation.",
    },
    {
        "id": "rajpurkar/squad",
        "url": "https://huggingface.co/datasets/rajpurkar/squad",
        "config": "plain_text",
        "split": "train",
        "domain": "reading_comprehension",
        "rows_hint": 98200,
        "shape": "context, question, answers.text",
        "conversion": "context becomes source doc; question -> first answer text.",
        "recommendation": "middle",
        "notes": "Good for evidence-grounded short answers; context must stay attached.",
    },
    {
        "id": "cais/mmlu",
        "url": "https://huggingface.co/datasets/cais/mmlu",
        "config": "college_computer_science",
        "split": "test",
        "domain": "college_cs",
        "rows_hint": None,
        "shape": "subject, question, choices, answer index",
        "conversion": "question -> selected choice text; subject tags domain cloud.",
        "recommendation": "middle",
        "notes": "Broad college-level coverage; use reviewed subsets before bulk ingestion.",
    },
    {
        "id": "openai/gsm8k",
        "url": "https://huggingface.co/datasets/openai/gsm8k",
        "config": "main",
        "split": "train",
        "domain": "math_word_problems",
        "rows_hint": 8792,
        "shape": "question, answer with reasoning and final marker",
        "conversion": "question -> cleaned final answer plus optional reasoning source text.",
        "recommendation": "middle",
        "notes": "Useful for arithmetic language patterns; strip markup carefully.",
    },
    {
        "id": "openai/openai_humaneval",
        "url": "https://huggingface.co/datasets/openai/openai_humaneval",
        "config": "openai_humaneval",
        "split": "test",
        "domain": "programming",
        "rows_hint": 164,
        "shape": "prompt, canonical_solution, tests",
        "conversion": "docstring task -> canonical solution summary/code; keep as CS lane only.",
        "recommendation": "small_cs_probe",
        "notes": "Tiny but clean. Good first programming cloud probe, not a broad CS corpus.",
    },
]


CLICK_SOURCES = [
    {
        "name": "OpenStax Subjects",
        "url": "https://openstax.org/subjects",
        "purpose": "General education spine: physics, biology, chemistry, math, history, economics.",
        "user_action": "Pick books/modules to approve for ingestion; verify license and edition.",
    },
    {
        "name": "MIT OpenCourseWare Search",
        "url": "https://ocw.mit.edu/search/",
        "purpose": "College-level math, physics, engineering, and CS notes.",
        "user_action": "Approve courses and file types; prefer text/PDF lecture notes over video transcripts first.",
    },
    {
        "name": "Harvard CS50",
        "url": "https://cs50.harvard.edu/x/",
        "purpose": "Intro CS major lane: programming concepts, algorithms, data structures.",
        "user_action": "Approve public pages/notes only; avoid pulling account-gated or video-only content.",
    },
    {
        "name": "NIST Publications",
        "url": "https://www.nist.gov/publications",
        "purpose": "Measurements, standards, engineering, physical sciences.",
        "user_action": "Pick standards/education documents by topic; PDFs need text normalization pass.",
    },
    {
        "name": "NASA STEM",
        "url": "https://www.nasa.gov/stem/",
        "purpose": "Space, physics, engineering, mission language.",
        "user_action": "Approve educator PDFs/pages; keep lessons with answers, skip unanswered worksheets unless answered.",
    },
    {
        "name": "Hugging Face Datasets",
        "url": "https://huggingface.co/datasets",
        "purpose": "Q/A rows that can form simple question -> answer clouds.",
        "user_action": "Approve dataset IDs, splits, row caps, and licenses before any download.",
    },
]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_manifest(output_root: Path) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": "anchorworks.data_curation.v1",
        "created_at": now,
        "output_root": str(output_root),
        "intent": "Build a clean college-grad corpus for symbol/count cloud formation.",
        "hard_laws": [
            "No bulk download before human approval.",
            "No account-gated or terms-restricted scraping.",
            "Question/answer rows must convert to plain text before intake.",
            "Source docs remain source truth; counts learn language shape.",
            "Licenses must be reviewed before ingestion.",
        ],
        "target_domains": [
            "general science",
            "physics",
            "math",
            "writing/reading comprehension",
            "history/civics",
            "college computer science",
            "standards/measurement",
        ],
        "huggingface_qa_candidates": HF_QA_DATASETS,
        "manual_click_sources": CLICK_SOURCES,
    }


def render_action_links(manifest: dict) -> str:
    lines = [
        "# AnchorWorks Data Curation Action Links",
        "",
        "Generated for a clean college-grad corpus. These are approval links, not auto-download commands.",
        "",
        "## What Lee Must Decide",
        "",
        "- Approve which sources are allowed.",
        "- Approve dataset licenses and row caps.",
        "- Choose whether each Q/A dataset is `core`, `probe`, or `skip`.",
        "- Choose whether PDFs should be normalized to text before intake.",
        "- Choose the first CS-major lane: intro programming, algorithms, systems, or security.",
        "",
        "## Source Links",
        "",
    ]
    for source in manifest["manual_click_sources"]:
        lines.extend(
            [
                f"### [{source['name']}]({source['url']})",
                f"- Purpose: {source['purpose']}",
                f"- Your action: {source['user_action']}",
                "",
            ]
        )
    lines.extend(["## Hugging Face Q/A Candidates", ""])
    for dataset in manifest["huggingface_qa_candidates"]:
        lines.extend(
            [
                f"### [{dataset['id']}]({dataset['url']})",
                f"- Domain: {dataset['domain']}",
                f"- Recommended use: {dataset['recommendation']}",
                f"- Shape: `{dataset['shape']}`",
                f"- Conversion: {dataset['conversion']}",
                f"- Notes: {dataset['notes']}",
                "",
            ]
        )
    return "\n".join(lines)


def render_hf_report(manifest: dict) -> str:
    lines = [
        "# Hugging Face Q/A Dataset Shortlist",
        "",
        "Goal: choose datasets that become plain `question -> answer` rows with clean clouds.",
        "",
        "| Dataset | Domain | Shape | Conversion | Use |",
        "|---|---|---|---|---|",
    ]
    for dataset in manifest["huggingface_qa_candidates"]:
        lines.append(
            "| "
            f"[{dataset['id']}]({dataset['url']}) | "
            f"{dataset['domain']} | "
            f"`{dataset['shape']}` | "
            f"{dataset['conversion']} | "
            f"{dataset['recommendation']} |"
        )
    lines.extend(
        [
            "",
            "## First Pull Recommendation",
            "",
            "1. `allenai/sciq`: first science Q/A probe.",
            "2. `allenai/openbookqa`: compact open-book science field.",
            "3. `rajpurkar/squad`: evidence/context pairing.",
            "4. `cais/mmlu` selected configs only: college CS plus selected STEM.",
            "5. `openai/gsm8k`: arithmetic language and answer-shape probe.",
            "",
            "Do not ingest giant web-scale corpora until these smaller fields produce sane top-K clouds.",
        ]
    )
    return "\n".join(lines)


def render_conversion_contract(manifest: dict) -> dict:
    return {
        "schema_version": "anchorworks.qa_conversion.v1",
        "row_shape": {
            "dataset_id": "string",
            "dataset_config": "string",
            "dataset_split": "string",
            "row_id": "string",
            "domain": "string",
            "question_text": "string",
            "answer_text": "string",
            "source_context_text": "optional string",
            "choices": "optional array",
            "blocked_alternatives": "optional array",
            "license_reviewed": "boolean",
            "approved_for_intake": "boolean",
        },
        "rules": [
            "question_text and answer_text must be plain text before AnchorWorks intake",
            "multiple-choice answerKey must be resolved to answer text before intake",
            "unsupported or unresolved answers are excluded from count-building",
            "context stays attached for evidence datasets such as SQuAD",
            "dataset/domain tags become source metadata, not language facts",
        ],
        "candidate_datasets": [dataset["id"] for dataset in manifest["huggingface_qa_candidates"]],
    }


def build(output_root: Path) -> None:
    manifest = build_manifest(output_root)
    _write_json(output_root / "source_manifest.json", manifest)
    _write_json(output_root / "qa_conversion_contract.json", render_conversion_contract(manifest))
    _write_text(output_root / "ACTION_LINKS.md", render_action_links(manifest))
    _write_text(output_root / "HF_QA_DATASETS.md", render_hf_report(manifest))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build AnchorWorks data curation planning artifacts.")
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="External output folder for curation artifacts.",
    )
    args = parser.parse_args()
    output_root = Path(args.output_root)
    build(output_root)
    print(f"Wrote curation pack to {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
