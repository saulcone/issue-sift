from pathlib import Path
from typing import Any

import httpx
import pytest

from issue_sift.ingest.github_issues import (
    RateLimitError,
    build_client,
    download_issues,
    iter_issues,
    load_issues,
)

REPO = "acme/widgets"


def issue(number: int, labels: tuple[str, ...] = (), **extra: Any) -> dict[str, Any]:
    return {
        "number": number,
        "title": f"Issue {number}",
        "body": "Something is broken",
        "state": "closed",
        "state_reason": "completed",
        "labels": [{"name": name, "color": "fff"} for name in labels],
        "comments": 2,
        "created_at": "2025-01-01T10:00:00Z",
        "closed_at": "2025-01-02T10:00:00Z",
        "html_url": f"https://github.com/{REPO}/issues/{number}",
        "user": {"login": "someone"},
        **extra,
    }


def paginated_transport(pages: list[list[dict[str, Any]]]) -> httpx.MockTransport:
    """Serves pages through ?page=N, with a Link header like GitHub's."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/repos/{REPO}/issues"
        page = int(request.url.params.get("page", "1"))
        headers = {}
        if page < len(pages):
            next_url = f"https://api.github.com/repos/{REPO}/issues?state=all&page={page + 1}"
            headers["Link"] = f'<{next_url}>; rel="next"'
        return httpx.Response(200, json=pages[page - 1], headers=headers)

    return httpx.MockTransport(handler)


async def collect(transport: httpx.MockTransport, limit: int | None = None) -> list[int]:
    async with build_client(None, transport=transport) as client:
        return [i.number async for i in iter_issues(client, REPO, limit=limit)]


async def test_follows_pagination_across_pages() -> None:
    transport = paginated_transport([[issue(1), issue(2)], [issue(3)]])
    assert await collect(transport) == [1, 2, 3]


async def test_skips_pull_requests() -> None:
    pr = issue(2, pull_request={"url": "https://api.github.com/..."})
    transport = paginated_transport([[issue(1), pr, issue(3)]])
    assert await collect(transport) == [1, 3]


async def test_limit_stops_early() -> None:
    transport = paginated_transport([[issue(1), issue(2)], [issue(3)]])
    assert await collect(transport, limit=2) == [1, 2]


async def test_keeps_only_triage_fields() -> None:
    transport = paginated_transport([[issue(7, labels=("bug", "needs-repro"))]])
    async with build_client(None, transport=transport) as client:
        [raw] = [i async for i in iter_issues(client, REPO)]
    assert raw.labels == ["bug", "needs-repro"]
    assert raw.state_reason == "completed"
    assert "user" not in raw.model_dump()


async def test_rate_limit_raises_clear_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        headers = {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1767225600"}
        return httpx.Response(403, json={"message": "rate limit"}, headers=headers)

    with pytest.raises(RateLimitError, match="rate limit exhausted"):
        await collect(httpx.MockTransport(handler))


async def test_failed_download_leaves_no_partial_file(tmp_path: Path) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(404, json={}))
    output = tmp_path / "issues.jsonl"
    async with build_client(None, transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await download_issues(client, REPO, output)
    assert not output.exists()
    assert not output.with_suffix(".jsonl.part").exists()


async def test_download_writes_jsonl_that_loads_back(tmp_path: Path) -> None:
    transport = paginated_transport([[issue(1, labels=("question",)), issue(2)]])
    output = tmp_path / "raw" / "issues.jsonl"
    async with build_client(None, transport=transport) as client:
        count = await download_issues(client, REPO, output)

    assert count == 2
    assert not output.with_suffix(".jsonl.part").exists()
    loaded = load_issues(output)
    assert [i.number for i in loaded] == [1, 2]
    assert loaded[0].labels == ["question"]
