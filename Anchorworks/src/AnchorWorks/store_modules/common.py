from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class StoreFacade(Protocol):
    paths: Any


@dataclass
class StorePower:
    facade: StoreFacade

