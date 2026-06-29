from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TypeVar


T = TypeVar("T")


def frozen_slots_dataclass(cls: T) -> T:
    kwargs = {"frozen": True}
    if sys.version_info >= (3, 10):
        kwargs["slots"] = True
    return dataclass(**kwargs)(cls)
