"""Command line entry point: `uv run issue-sift <command>`."""

import argparse
import asyncio
from pathlib import Path
from typing import cast

import httpx

from issue_sift.config import Settings, get_settings
from issue_sift.ingest.docs import download_docs
from issue_sift.ingest.github_issues import RateLimitError, State, build_client, download_issues


def repo_dir(settings: Settings, repo: str) -> Path:
    return settings.data_dir / "raw" / repo.replace("/", "__")


def resolve_repo(arg: str | None, settings: Settings) -> str:
    repo = arg or settings.source_repo
    if not repo or repo.count("/") != 1:
        raise SystemExit("Give the repository as owner/name (--repo or ISSUE_SIFT_SOURCE_REPO).")
    return repo


async def _ingest_issues(repo: str, state: State, limit: int | None, settings: Settings) -> None:
    token = settings.github_token.get_secret_value() if settings.github_token else None
    output = repo_dir(settings, repo) / "issues.jsonl"
    async with build_client(token) as client:
        count = await download_issues(client, repo, output, state=state, limit=limit)
    print(f"Saved {count} issues to {output}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="issue-sift")
    sub = parser.add_subparsers(dest="command", required=True)

    p_issues = sub.add_parser("ingest-issues", help="Download issues to JSON Lines")
    p_issues.add_argument("--repo", help="owner/name (default: ISSUE_SIFT_SOURCE_REPO)")
    p_issues.add_argument("--state", choices=["open", "closed", "all"], default="all")
    p_issues.add_argument("--limit", type=int, default=None, help="Stop after N issues")

    p_docs = sub.add_parser("ingest-docs", help="Copy the repository documentation")
    p_docs.add_argument("--repo", help="owner/name (default: ISSUE_SIFT_SOURCE_REPO)")

    args = parser.parse_args(argv)
    settings = get_settings()
    repo = resolve_repo(args.repo, settings)

    if args.command == "ingest-issues":
        try:
            asyncio.run(_ingest_issues(repo, cast(State, args.state), args.limit, settings))
        except RateLimitError as e:
            raise SystemExit(str(e)) from None
        except httpx.HTTPStatusError as e:
            raise SystemExit(
                f"GitHub answered {e.response.status_code} for {e.request.url}. "
                "Check the repository name and your token."
            ) from None
    elif args.command == "ingest-docs":
        output = repo_dir(settings, repo) / "docs"
        count = download_docs(repo, output)
        print(f"Saved {count} documentation files to {output}")


if __name__ == "__main__":
    main()
