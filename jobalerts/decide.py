"""The routing result for one job, plus the decision settings from criteria.yaml."""
from typing import Literal

from pydantic import BaseModel

from jobalerts.filters import CRITERIA

RULES = CRITERIA["decision"]


class Decision(BaseModel):
    channel: Literal["apply_now", "maybe", "digest", "drop"]
    reason: str
    tags: list[str] = []
