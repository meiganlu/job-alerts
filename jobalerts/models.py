"""Defines what a job looks like, so every source produces the same shape."""
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class Job(BaseModel):
    source: str  # where it came from: "greenhouse", "lever", "ashby", ...
    company: str
    board: str = ""  # the company's slug on its job board, e.g. "affirm"
    job_id: str
    title: str
    location: str
    url: HttpUrl
    posted_at: datetime | None = None
    description: str = ""

    @property # lets you use a method like a field
    def key(self) -> str:
        """A unique ID across all sources, used later to skip jobs already seen."""
        return f"{self.source}:{self.company}:{self.job_id}"