"""Download the issues of a repository through the GitHub REST API.

The issues endpoint also returns pull requests; those are skipped.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx

from issue_sift.ingest.models import RawIssue

GITHUB_API = "https://api.github.com"
PER_PAGE = 100
MAX_ATTEMPTS = 3

State = Literal["open", "closed", "all"]


class RateLimitError(RuntimeError):
    """The GitHub API rate limit was exhausted."""


def build_client(
    token: str | None, transport: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "issue-sift",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.AsyncClient(
        base_url=GITHUB_API, headers=headers, timeout=30.0, transport=transport
    )


async def _get(
    client: httpx.AsyncClient, url: str, params: dict[str, Any] | None
) -> httpx.Response:
    """GET with retries on transient server errors and a clear rate-limit error."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = await client.get(url, params=params)
        if (
            response.status_code in (403, 429)
            and response.headers.get("x-ratelimit-remaining") == "0"
        ):
            reset = response.headers.get("x-ratelimit-reset")
            when = datetime.fromtimestamp(int(reset), tz=UTC).isoformat() if reset else "unknown"
            raise RateLimitError(f"GitHub rate limit exhausted, resets at {when}. Set a token.")
        if response.status_code >= 500 and attempt < MAX_ATTEMPTS:
            await asyncio.sleep(2**attempt)
            continue
        response.raise_for_status()
        return response
    raise AssertionError("unreachable")


async def iter_issues(
    client: httpx.AsyncClient, repo: str, state: State = "all", limit: int | None = None
) -> AsyncIterator[RawIssue]:
    """Yield the repository's issues, oldest first, following pagination."""
    url: str | None = f"/repos/{repo}/issues"
    params: dict[str, Any] | None = {
        "state": state,
        "per_page": PER_PAGE,
        "sort": "created",
        "direction": "asc",
    }
    yielded = 0
    while url:
        response = await _get(client, url, params)
        for item in response.json():
            if "pull_request" in item:
                continue
            yield RawIssue.from_github(item)
            yielded += 1
            if limit is not None and yielded >= limit:
                return
        # The "next" link already carries every query parameter.
        url = response.links.get("next", {}).get("url")
        params = None


async def download_issues(
    client: httpx.AsyncClient,
    repo: str,
    output: Path,
    state: State = "all",
    limit: int | None = None,
) -> int:
    """Write the issues to a JSON Lines file (one issue per line). Returns how many."""
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    tmp = output.with_suffix(output.suffix + ".part")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            async for issue in iter_issues(client, repo, state=state, limit=limit):
                fh.write(json.dumps(issue.model_dump(mode="json"), ensure_ascii=False) + "\n")
                count += 1
    except BaseException:
        tmp.unlink(missing_ok=True)  # never leave a half-written file behind
        raise
    tmp.replace(output)  # only a complete download replaces the previous file
    return count


def load_issues(path: Path) -> list[RawIssue]:
    with path.open(encoding="utf-8") as fh:
        return [RawIssue.model_validate_json(line) for line in fh if line.strip()]
