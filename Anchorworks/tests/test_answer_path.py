from __future__ import annotations

from AnchorWorks.answer_path import choose_answer_block_path


def test_choose_answer_block_path_selects_best_whole_candidate() -> None:
    result = choose_answer_block_path(
        ["elements", "water"],
        [
            {
                "raw_block_text": "The squid pushes water backward and the water pushes the squid forward.",
                "text": "The squid pushes water backward and the water pushes the squid forward.",
                "source_name": "motion_lesson.md",
                "block_id": 1,
                "score": 1000,
            },
            {
                "raw_block_text": "Water is a compound made of the elements hydrogen and oxygen.",
                "text": "Water is a compound made of the elements hydrogen and oxygen.",
                "source_name": "chemistry_lesson.md",
                "block_id": 2,
                "score": 1,
            },
        ],
    )

    assert result["ok"] is True
    assert result["strategy"] == "answer_block_path"
    assert result["selected"]["source_name"] == "chemistry_lesson.md"
    assert result["speech"] == "Water is a compound made of the elements hydrogen and oxygen."


def test_choose_answer_block_path_refuses_when_no_candidate_passes_frame() -> None:
    result = choose_answer_block_path(
        ["elements", "water"],
        [
            {
                "raw_block_text": "The squid pushes water backward and the water pushes the squid forward.",
                "text": "The squid pushes water backward and the water pushes the squid forward.",
                "source_name": "motion_lesson.md",
                "block_id": 1,
                "score": 1000,
            },
        ],
    )

    assert result["ok"] is False
    assert result["speech"] == ""
    assert result["selected"] == {}
