"""Fetch small Hugging Face Q/A datasets into AnchorWorks curation rows.

This pulls bounded public dataset rows through the Hugging Face Dataset Viewer
API and converts them into plain question -> answer records. It writes only to
the external curation root by default.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


DEFAULT_OUTPUT_ROOT = Path(r"D:\AnchorWorks_Data_Curation\college_grad_core\hf_qa_first_pull")
API_ROOT = "https://datasets-server.huggingface.co"


DATASETS = [
    {
        "id": "allenai/sciq",
        "config": "default",
        "split": "train",
        "domain": "science",
        "row_cap": 500,
        "converter": "sciq",
    },
    {
        "id": "allenai/openbookqa",
        "config": "main",
        "split": "train",
        "domain": "science",
        "row_cap": 500,
        "converter": "openbookqa",
    },
    {
        "id": "rajpurkar/squad",
        "config": "plain_text",
        "split": "train",
        "domain": "reading_comprehension",
        "row_cap": 500,
        "converter": "squad",
    },
    {
        "id": "cais/mmlu",
        "config": "college_computer_science",
        "split": "test",
        "domain": "college_computer_science",
        "row_cap": 200,
        "converter": "mmlu",
    },
    {
        "id": "cais/mmlu",
        "config": "college_physics",
        "split": "test",
        "domain": "college_physics",
        "row_cap": 200,
        "converter": "mmlu",
    },
    {
        "id": "openai/gsm8k",
        "config": "main",
        "split": "train",
        "domain": "math_word_problems",
        "row_cap": 10000,
        "converter": "gsm8k",
    },
    {
        "id": "openai/openai_humaneval",
        "config": "openai_humaneval",
        "split": "test",
        "domain": "programming",
        "row_cap": 164,
        "converter": "humaneval",
    },
    {
        "id": "openai/graphwalks",
        "config": "default",
        "split": "train",
        "domain": "graph_reasoning",
        "row_cap": 1000,
        "converter": "graphwalks",
    },
    {
        "id": "openai/frontierscience",
        "config": "default",
        "split": "test",
        "domain": "frontier_science",
        "row_cap": 1000,
        "converter": "frontierscience",
    },
]


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def final_gsm8k_answer(answer: str) -> str:
    answer = clean_text(answer)
    marker = "####"
    if marker in answer:
        final = answer.split(marker, 1)[1].strip()
        if final:
            return final
    return answer


def choice_by_key(choices: dict[str, Any], key: Any) -> str:
    labels = choices.get("label") or []
    texts = choices.get("text") or []
    key_text = str(key).strip()
    for label, text in zip(labels, texts):
        if str(label).strip() == key_text:
            return clean_text(text)
    if key_text.isdigit():
        index = int(key_text)
        if 0 <= index < len(texts):
            return clean_text(texts[index])
    return ""


def convert_sciq(row: dict[str, Any], meta: dict[str, Any], index: int) -> dict[str, Any] | None:
    question = clean_text(row.get("question"))
    answer = clean_text(row.get("correct_answer"))
    if not question or not answer:
        return None
    return record(meta, index, question, answer, clean_text(row.get("support")), [])


def convert_openbookqa(row: dict[str, Any], meta: dict[str, Any], index: int) -> dict[str, Any] | None:
    question = clean_text(row.get("question_stem"))
    choices = row.get("choices") or {}
    answer = choice_by_key(choices, row.get("answerKey"))
    if not question or not answer:
        return None
    alternatives = [clean_text(x) for x in choices.get("text", []) if clean_text(x) != answer]
    return record(meta, index, question, answer, "", alternatives)


def convert_squad(row: dict[str, Any], meta: dict[str, Any], index: int) -> dict[str, Any] | None:
    question = clean_text(row.get("question"))
    answers = row.get("answers") or {}
    answer_texts = answers.get("text") or []
    answer = clean_text(answer_texts[0] if answer_texts else "")
    context = clean_text(row.get("context"))
    if not question or not answer:
        return None
    return record(meta, index, question, answer, context, [])


def convert_mmlu(row: dict[str, Any], meta: dict[str, Any], index: int) -> dict[str, Any] | None:
    question = clean_text(row.get("question"))
    choices = [clean_text(x) for x in row.get("choices", [])]
    answer_index = row.get("answer")
    answer = ""
    if isinstance(answer_index, int) and 0 <= answer_index < len(choices):
        answer = choices[answer_index]
    if not question or not answer:
        return None
    alternatives = [x for i, x in enumerate(choices) if i != answer_index]
    return record(meta, index, question, answer, "", alternatives)


def convert_gsm8k(row: dict[str, Any], meta: dict[str, Any], index: int) -> dict[str, Any] | None:
    question = clean_text(row.get("question"))
    raw_answer = clean_text(row.get("answer"))
    answer = final_gsm8k_answer(raw_answer)
    if not question or not answer:
        return None
    return record(meta, index, question, answer, raw_answer, [])


def convert_humaneval(row: dict[str, Any], meta: dict[str, Any], index: int) -> dict[str, Any] | None:
    prompt = clean_text(row.get("prompt"))
    solution = clean_text(row.get("canonical_solution"))
    entry = clean_text(row.get("entry_point"))
    if not prompt or not solution:
        return None
    question = f"Implement the programming task for {entry}."
    context = prompt
    answer = solution
    return record(meta, index, question, answer, context, [])


def convert_prompt_answer(row: dict[str, Any], meta: dict[str, Any], index: int) -> dict[str, Any] | None:
    prompt = clean_text(row.get("prompt"))
    answer = clean_text(row.get("answer"))
    if not prompt or not answer:
        return None
    return record(meta, index, prompt, answer, "", [])


def convert_graphwalks(row: dict[str, Any], meta: dict[str, Any], index: int) -> dict[str, Any] | None:
    prompt = clean_text(row.get("prompt"))
    nodes = row.get("answer_nodes")
    if isinstance(nodes, list):
        answer = "[" + ", ".join(clean_text(node) for node in nodes) + "]"
    else:
        answer = clean_text(nodes)
    if not prompt or not answer:
        return None
    item = record(meta, index, prompt, answer, "", [])
    item["problem_type"] = clean_text(row.get("problem_type"))
    return item


def convert_frontierscience(row: dict[str, Any], meta: dict[str, Any], index: int) -> dict[str, Any] | None:
    problem = clean_text(row.get("problem"))
    answer = clean_text(row.get("answer"))
    subject = clean_text(row.get("subject"))
    if not problem or not answer:
        return None
    item = record(meta, index, problem, answer, "", [])
    item["domain"] = f"{meta['domain']}:{subject}" if subject else meta["domain"]
    return item


CONVERTERS: dict[str, Callable[[dict[str, Any], dict[str, Any], int], dict[str, Any] | None]] = {
    "sciq": convert_sciq,
    "openbookqa": convert_openbookqa,
    "squad": convert_squad,
    "mmlu": convert_mmlu,
    "gsm8k": convert_gsm8k,
    "humaneval": convert_humaneval,
    "prompt_answer": convert_prompt_answer,
    "graphwalks": convert_graphwalks,
    "frontierscience": convert_frontierscience,
}


def record(
    meta: dict[str, Any],
    index: int,
    question: str,
    answer: str,
    source_context: str,
    blocked_alternatives: list[str],
) -> dict[str, Any]:
    source_key = f"{meta['id']}::{meta['config']}::{meta['split']}::{index}"
    return {
        "schema_version": "anchorworks.qa_plain.v1",
        "source_key": source_key,
        "dataset_id": meta["id"],
        "dataset_config": meta["config"],
        "dataset_split": meta["split"],
        "domain": meta["domain"],
        "row_index": index,
        "question_text": question,
        "answer_text": answer,
        "source_context_text": source_context,
        "blocked_alternatives": [x for x in blocked_alternatives if x],
        "approved_for_intake": False,
        "license_review_required": True,
    }


def fetch_rows(meta: dict[str, Any], offset: int, length: int, token: str | None, retries: int = 5) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "dataset": meta["id"],
            "config": meta["config"],
            "split": meta["split"],
            "offset": offset,
            "length": length,
        }
    )
    request = urllib.request.Request(f"{API_ROOT}/rows?{params}")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return [item["row"] for item in payload.get("rows", [])]
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == retries - 1:
                raise
            retry_after = exc.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else 5 * (attempt + 1)
            time.sleep(delay)
    return []


def safe_name(meta: dict[str, Any]) -> str:
    raw = f"{meta['id']}__{meta['config']}__{meta['split']}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def write_plaintext(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(f"Question: {row['question_text']}\n")
            handle.write(f"Answer: {row['answer_text']}\n")
            context = row.get("source_context_text") or ""
            if context:
                handle.write(f"Context: {context}\n")
            handle.write("\n---\n\n")


def pull_dataset(meta: dict[str, Any], output_root: Path, max_rows: int, token: str | None) -> dict[str, Any]:
    wanted = min(int(meta["row_cap"]), max_rows)
    converter = CONVERTERS[meta["converter"]]
    converted: list[dict[str, Any]] = []
    errors: list[str] = []
    offset = 0
    page_size = 100
    started = time.perf_counter()
    while len(converted) < wanted:
        length = min(page_size, wanted - len(converted))
        try:
            rows = fetch_rows(meta, offset, length, token)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            errors.append(f"offset {offset}: {exc}")
            break
        if not rows:
            break
        for row in rows:
            item = converter(row, meta, offset)
            if item:
                converted.append(item)
            offset += 1
            if len(converted) >= wanted:
                break
    name = safe_name(meta)
    jsonl_path = output_root / "jsonl" / f"{name}.jsonl"
    text_path = output_root / "plain_text" / f"{name}.txt"
    write_jsonl(jsonl_path, converted)
    write_plaintext(text_path, converted)
    return {
        "dataset_id": meta["id"],
        "config": meta["config"],
        "split": meta["split"],
        "domain": meta["domain"],
        "requested_rows": wanted,
        "converted_rows": len(converted),
        "jsonl_path": str(jsonl_path),
        "plain_text_path": str(text_path),
        "errors": errors,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch bounded HF Q/A rows for AnchorWorks curation.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--max-rows-per-dataset", type=int, default=500)
    parser.add_argument("--dataset", action="append", help="Optional dataset id filter; may repeat.")
    args = parser.parse_args()

    output_root = Path(args.output_root)
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    selected = DATASETS
    if args.dataset:
        requested = set(args.dataset)
        selected = [dataset for dataset in DATASETS if dataset["id"] in requested]
    output_root.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": "anchorworks.hf_qa_first_pull.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_root": str(output_root),
        "auth_header_used": bool(token),
        "max_rows_per_dataset": args.max_rows_per_dataset,
        "datasets": [],
    }
    for meta in selected:
        result = pull_dataset(meta, output_root, args.max_rows_per_dataset, token)
        report["datasets"].append(result)
        print(
            f"{result['dataset_id']} {result['config']} {result['split']}: "
            f"{result['converted_rows']} rows in {result['elapsed_seconds']}s"
        )
    total = sum(item["converted_rows"] for item in report["datasets"])
    report["total_converted_rows"] = total
    (output_root / "reports").mkdir(parents=True, exist_ok=True)
    (output_root / "reports" / "first_pull_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Total converted rows: {total}")
    print(f"Report: {output_root / 'reports' / 'first_pull_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
