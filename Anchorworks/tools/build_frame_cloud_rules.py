"""Build compact frame-cloud rules from staged reasoning-frame rows.

The generated artifact is the runtime-facing shape. The 10k source corpus stays
external and should not be scanned during chat/render.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


INPUT_JSONL = Path(r"D:\AnchorWorks_Data_Curation\reasoning_frame_pack\jsonl\general_education_reasoning_frames.jsonl")
OUTPUT_ROOT = Path(r"D:\AnchorWorks_Data_Curation\frame_cloud_rules")


FRAME_TEMPLATES = {
    "what": {
        "pattern_id": "what_definition_cloud",
        "frame_type": "definition",
        "activity": "educational_question",
        "rule": "What-questions usually ask for identity, category, value, or defining property.",
        "template": "Identify what <subject> is and give the category or defining property.",
    },
    "which": {
        "pattern_id": "which_selection_cloud",
        "frame_type": "selection_check",
        "activity": "educational_question",
        "rule": "Which-questions usually ask for the candidate or statement that best fits a condition.",
        "template": "Select which statement or candidate fits <subject> and explain the basis.",
    },
    "who": {
        "pattern_id": "who_identity_cloud",
        "frame_type": "identity",
        "activity": "educational_question",
        "rule": "Who-questions usually ask for a person or named identity.",
        "template": "Identify who <subject> refers to and why that identity fits.",
    },
    "how": {
        "pattern_id": "how_process_cloud",
        "frame_type": "process_explanation",
        "activity": "educational_question",
        "rule": "How-questions usually ask for mechanism, method, amount, or process.",
        "template": "Explain how <subject> works, including the main steps or mechanism.",
    },
    "why": {
        "pattern_id": "why_causal_cloud",
        "frame_type": "causal_explanation",
        "activity": "educational_question",
        "rule": "Why-questions usually ask for cause, reason, purpose, or consequence.",
        "template": "Explain why <subject> happens and what evidence supports it.",
    },
    "when": {
        "pattern_id": "when_time_cloud",
        "frame_type": "time_lookup",
        "activity": "educational_question",
        "rule": "When-questions ask for time, date, order, or historical placement.",
        "template": "Identify when <subject> occurred or what time/date relation is requested.",
    },
    "where": {
        "pattern_id": "where_place_cloud",
        "frame_type": "place_lookup",
        "activity": "educational_question",
        "rule": "Where-questions ask for location, origin, or spatial placement.",
        "template": "Identify where <subject> is located or where the event belongs.",
    },
    "compare": {
        "pattern_id": "compare_relation_cloud",
        "frame_type": "comparison",
        "activity": "educational_question",
        "rule": "Compare/contrast requests ask for shared properties and differences.",
        "template": "Compare <left> and <right> by shared and differing properties.",
    },
    "does": {
        "pattern_id": "does_implication_cloud",
        "frame_type": "implication_check",
        "activity": "educational_question",
        "rule": "Does-questions often ask whether a relation, implication, or condition holds.",
        "template": "Check whether <subject> implies <relation> and explain the evidence.",
    },
    "open": {
        "pattern_id": "open_question_cloud",
        "frame_type": "open_educational_frame",
        "activity": "educational_question",
        "rule": "Open forms need routing before answer assembly.",
        "template": "Determine what kind of answer <subject> requests before gathering facts.",
    },
}


STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "did", "do", "does", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "what", "when",
    "where", "which", "who", "why", "with", "would",
}


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.casefold()) if w not in STOP and len(w) > 1]


def pattern_key(question: str) -> str:
    q = question.casefold().strip()
    for key in ("why", "how", "what", "which", "who", "when", "where", "does"):
        if q.startswith(key + " "):
            return key
    if q.startswith(("compare ", "contrast ")):
        return "compare"
    return "open"


def load_rows() -> list[dict[str, str]]:
    rows = []
    with INPUT_JSONL.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            rows.append(
                {
                    "question": str(row.get("question_text") or ""),
                    "frame": str(row.get("reasoning_frame_text") or ""),
                    "expected": str(row.get("expected_frame_text") or ""),
                }
            )
    return rows


def build_rules() -> dict[str, object]:
    rows = load_rows()
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    q_terms: dict[str, Counter[str]] = defaultdict(Counter)
    f_terms: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = pattern_key(row["question"])
        grouped[key].append(row)
        q_terms[key].update(words(row["question"]))
        f_terms[key].update(words(row["frame"]))

    rules = []
    for key, template in FRAME_TEMPLATES.items():
        examples = grouped.get(key, [])[:5]
        rules.append(
            {
                **template,
                "cloud_key": key,
                "source_examples": len(grouped.get(key, [])),
                "question_cloud_terms": q_terms[key].most_common(40),
                "frame_cloud_terms": f_terms[key].most_common(40),
                "example_pairs": [
                    {
                        "question": item["question"],
                        "frame": item["frame"],
                    }
                    for item in examples
                ],
                "fact_answer_authority": False,
            }
        )
    return {
        "schema_version": "anchorworks_frame_cloud_rules@1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(INPUT_JSONL),
        "source_rows": len(rows),
        "law": "Frame clouds teach answer shape, not answer truth.",
        "rules": rules,
        "runtime_contract": {
            "scan_source_corpus_live": False,
            "fact_answer_authority": False,
            "writes_allowed": {"maps": False, "counts": False, "lifetime": False, "lexicon": False},
        },
    }


def render_doc(payload: dict[str, object]) -> str:
    lines = [
        "# AnchorWorks Frame Cloud Rules",
        "",
        "This document is distilled from the reasoning-frame corpus. It teaches question-to-frame cloud shape only.",
        "",
        "```text",
        "Frame clouds teach aiming.",
        "They do not teach factual answers.",
        "Counts/source docs still prove truth.",
        "```",
        "",
    ]
    for rule in payload["rules"]:
        lines.extend(
            [
                f"## {rule['pattern_id']}",
                "",
                f"- Frame type: `{rule['frame_type']}`",
                f"- Activity: `{rule['activity']}`",
                f"- Source examples: `{rule['source_examples']}`",
                f"- Rule: {rule['rule']}",
                f"- Template: `{rule['template']}`",
                f"- Fact answer authority: `{str(rule['fact_answer_authority']).lower()}`",
                "",
                "Question cloud terms:",
                "",
                "```text",
                ", ".join(term for term, _count in rule["question_cloud_terms"][:20]) or "none",
                "```",
                "",
                "Frame cloud terms:",
                "",
                "```text",
                ", ".join(term for term, _count in rule["frame_cloud_terms"][:20]) or "none",
                "```",
                "",
            ]
        )
        if rule["example_pairs"]:
            lines.append("Examples:")
            lines.append("")
            for item in rule["example_pairs"][:3]:
                lines.append(f"- Q: {item['question']}")
                lines.append(f"  Frame: {item['frame']}")
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    payload = build_rules()
    (OUTPUT_ROOT / "frame_cloud_rules.json").write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    (OUTPUT_ROOT / "FRAME_CLOUD_RULES.md").write_text(render_doc(payload), encoding="utf-8")
    print(json.dumps({"output_root": str(OUTPUT_ROOT), "source_rows": payload["source_rows"], "rules": len(payload["rules"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
