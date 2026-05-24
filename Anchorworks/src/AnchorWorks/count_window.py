from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


COUNT_WINDOW_SCHEMA_VERSION = "anchorworks_count_window_config@1"


@dataclass(frozen=True)
class CountWindowConfig:
    left_context_units: int
    center_units: int
    right_context_units: int
    unit_size: int = 1
    lane: str = "symbolic"
    name: str = "custom"

    def __post_init__(self) -> None:
        if self.left_context_units < 1:
            raise ValueError("left_context_units must be >= 1")
        if self.center_units < 1:
            raise ValueError("center_units must be >= 1")
        if self.right_context_units < 1:
            raise ValueError("right_context_units must be >= 1")
        if self.unit_size < 1:
            raise ValueError("unit_size must be >= 1")
        if self.left_context_units != self.right_context_units:
            raise ValueError("left and right context units must match for current deterministic counts")

    @property
    def window_shape(self) -> str:
        if self.unit_size == 1:
            return f"{self.left_context_units}-{self.center_units}-{self.right_context_units}"
        return f"{self.left_context_units}x{self.unit_size}-{self.center_units}-{self.right_context_units}x{self.unit_size}"

    @property
    def context_span_each_side(self) -> int:
        return self.left_context_units * self.unit_size

    @property
    def total_window_symbols(self) -> int:
        return self.context_span_each_side + self.center_units + self.context_span_each_side

    @property
    def configurable(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row.update(
            {
                "schema_version": COUNT_WINDOW_SCHEMA_VERSION,
                "window_shape": self.window_shape,
                "context_span_each_side": self.context_span_each_side,
                "total_window_symbols": self.total_window_symbols,
                "configurable": True,
            }
        )
        return row


def count_window_preset(name: str) -> CountWindowConfig:
    key = str(name or "").strip().casefold()
    if key in {"text_6_1_6", "6-1-6", "language_base"}:
        return CountWindowConfig(
            left_context_units=6,
            center_units=1,
            right_context_units=6,
            unit_size=1,
            lane="text",
            name="text_6_1_6",
        )
    if key in {"occular_6x4_4_6x4", "6x4-4-6x4", "visual_base"}:
        return CountWindowConfig(
            left_context_units=6,
            center_units=4,
            right_context_units=6,
            unit_size=4,
            lane="occular",
            name="occular_6x4_4_6x4",
        )
    raise ValueError(f"unknown count window preset: {name}")
