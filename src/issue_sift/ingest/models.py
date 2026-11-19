"""Shape of the data we keep from GitHub.

Only the fields needed for triage are stored (no author data): data minimisation.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RawIssue(BaseModel):
    number: int
    title: str
    body: str | None
    state: str  # "open" | "closed"
    state_reason: str | None  # e.g. "completed", "not_planned", "duplicate"; None when open
    labels: list[str]
    comments: int
    created_at: datetime
    closed_at: datetime | None
    html_url: str

    @classmethod
    def from_github(cls, item: dict[str, Any]) -> "RawIssue":
        return cls(
            number=item["number"],
            title=item["title"],
            body=item.get("body"),
            state=item["state"],
            state_reason=item.get("state_reason"),
            labels=[label["name"] for label in item.get("labels", [])],
            comments=item.get("comments", 0),
            created_at=item["created_at"],
            closed_at=item.get("closed_at"),
            html_url=item["html_url"],
        )
