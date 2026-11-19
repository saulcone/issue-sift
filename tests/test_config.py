from pathlib import Path

import pytest

from issue_sift.config import Settings


def test_defaults_without_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GITHUB_TOKEN", "SOURCE_REPO", "DATA_DIR", "DATABASE_URL"):
        monkeypatch.delenv(f"ISSUE_SIFT_{name}", raising=False)

    settings = Settings(_env_file=None)

    assert settings.github_token is None
    assert settings.source_repo is None
    assert settings.data_dir == Path("data")


def test_reads_prefixed_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ISSUE_SIFT_GITHUB_TOKEN", "secret")
    monkeypatch.setenv("ISSUE_SIFT_SOURCE_REPO", "acme/widgets")
    monkeypatch.setenv("ISSUE_SIFT_DATA_DIR", "elsewhere")

    settings = Settings(_env_file=None)

    assert settings.github_token is not None
    assert settings.github_token.get_secret_value() == "secret"
    assert settings.source_repo == "acme/widgets"
    assert settings.data_dir == Path("elsewhere")
