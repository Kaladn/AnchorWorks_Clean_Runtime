"""Create/update the external ready-dataset index for AnchorWorks.

This keeps acquisition state outside the repository while leaving a repeatable
tool in the repo. It does not download data.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


READY_ROOT = Path(r"D:\AnchorWorks_Data_Curation\READY_DATASETS")
SOURCE_ROOTS = [
    Path(r"D:\AnchorWorks_Data_Curation\college_grad_core\hf_qa_first_pull"),
    Path(r"D:\AnchorWorks_Data_Curation\arc_solver_proven_qa"),
    Path(r"D:\AnchorWorks_Data_Curation\openai_pack"),
    Path(r"D:\AnchorWorks_Data_Curation\openai_pack_extra"),
    Path(r"D:\AnchorWorks_Data_Curation\openai_graphwalks_pack"),
    Path(r"D:\AnchorWorks_Data_Curation\openai_gsm8k_clean_pack"),
    Path(r"D:\AnchorWorks_Data_Curation\reasoning_frame_pack"),
]


NEEDED = [
    {
        "lane": "science_qa",
        "target_gb": 2,
        "have_status": "seeded",
        "source": "SciQ, OpenBookQA, cleaned science Q/A",
        "next_action": "Expand row caps after approval; keep ARC Challenge removed.",
    },
    {
        "lane": "evidence_qa",
        "target_gb": 4,
        "have_status": "seeded",
        "source": "SQuAD-style context/question/answer rows",
        "next_action": "Pull more context-grounded reading comprehension rows.",
    },
    {
        "lane": "college_core_textbooks",
        "target_gb": 18,
        "have_status": "partial_elsewhere",
        "source": "OpenStax and approved college texts",
        "next_action": "Approve exact books/modules and normalize text/PDF lessons.",
    },
    {
        "lane": "college_cs_major",
        "target_gb": 8,
        "have_status": "seeded",
        "source": "HumanEval tiny probe, CS50/MIT OCW approved notes later",
        "next_action": "Select CS major spine: intro, algorithms, systems, security.",
    },
    {
        "lane": "math_reasoning",
        "target_gb": 3,
        "have_status": "seeded",
        "source": "GSM8K plus curated math lessons",
        "next_action": "Clean answer formatting and add lessons/source explanations.",
    },
    {
        "lane": "standards_measurement_engineering",
        "target_gb": 6,
        "have_status": "partial_elsewhere",
        "source": "NIST/NASA technical PDFs already probed",
        "next_action": "Normalize approved PDFs and avoid noisy front matter.",
    },
    {
        "lane": "lee_proven_system_docs",
        "target_gb": 1,
        "have_status": "seeded",
        "source": "ARC solver proven Q/A and docs",
        "next_action": "Add ClearBoxAI/Cascadian docs only after review.",
    },
    {
        "lane": "history_civics_writing",
        "target_gb": 8,
        "have_status": "missing",
        "source": "Approved public-domain or open education sources",
        "next_action": "Pick trusted open sources and avoid random web scrape.",
    },
]


def folder_size(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    count = 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            count += 1
            total += item.stat().st_size
    return count, total


def copy_index_only() -> list[dict[str, object]]:
    READY_ROOT.mkdir(parents=True, exist_ok=True)
    datasets = []
    for source in SOURCE_ROOTS:
        count, total = folder_size(source)
        datasets.append(
            {
                "name": source.name,
                "source_path": str(source),
                "status": "ready_seed" if source.exists() else "missing",
                "file_count": count,
                "bytes": total,
                "target_ready_path": str(READY_ROOT / source.name),
                "copy_mode": "index_reference_only",
            }
        )
    return datasets


def render_checklist(payload: dict[str, object]) -> str:
    lines = [
        "# AnchorWorks Ready Dataset Checklist",
        "",
        "This folder tracks datasets ready to churn later. It is external to the repo.",
        "",
        f"Created: {payload['created_at']}",
        f"Target: {payload['target_total_gb']} GB before large churn",
        f"Current indexed size: {payload['current_indexed_gb']} GB",
        "",
        "## Ready Seeds",
        "",
    ]
    for dataset in payload["ready_datasets"]:
        lines.extend(
            [
                f"### {dataset['name']}",
                f"- Status: {dataset['status']}",
                f"- Source: `{dataset['source_path']}`",
                f"- Files: {dataset['file_count']}",
                f"- Size: {round(dataset['bytes'] / (1024**2), 3)} MB",
                f"- Ready path: `{dataset['target_ready_path']}`",
                "",
            ]
        )
    lines.extend(["## 50 GB Acquisition Board", ""])
    for item in payload["needed"]:
        lines.extend(
            [
                f"### [ ] {item['lane']} - target {item['target_gb']} GB",
                f"- Have: {item['have_status']}",
                f"- Source shape: {item['source']}",
                f"- Next action: {item['next_action']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Churn Gate",
            "",
            "Do not start large ingest until:",
            "",
            "- [ ] Total approved dataset size is at least 50 GB.",
            "- [ ] Each source has a license/permission note.",
            "- [ ] Each PDF lane has a text-normalization policy.",
            "- [ ] Q/A rows are converted to plain question -> answer text.",
            "- [ ] No ARC Challenge rows remain in the ready set.",
            "- [ ] Background count job command is detached and resumable.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    datasets = copy_index_only()
    current_bytes = sum(int(item["bytes"]) for item in datasets)
    payload = {
        "schema_version": "anchorworks.ready_dataset_index.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ready_root": str(READY_ROOT),
        "target_total_gb": 50,
        "current_indexed_bytes": current_bytes,
        "current_indexed_gb": round(current_bytes / (1024**3), 4),
        "ready_datasets": datasets,
        "needed": NEEDED,
    }
    (READY_ROOT / "reports").mkdir(parents=True, exist_ok=True)
    (READY_ROOT / "ready_dataset_index.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (READY_ROOT / "READY_DATASET_CHECKLIST.md").write_text(render_checklist(payload), encoding="utf-8")
    print(json.dumps({"ready_root": str(READY_ROOT), "current_indexed_gb": payload["current_indexed_gb"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
