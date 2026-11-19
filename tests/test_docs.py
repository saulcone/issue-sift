from pathlib import Path

from issue_sift.ingest.docs import select_doc_files


def touch(root: Path, rel: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


def test_selects_documentation_files_only(tmp_path: Path) -> None:
    for rel in [
        "README.md",
        "docs/guide/intro.md",
        "docs/api.rst",
        "docs/page.mdx",
        "src/app.py",
        ".github/ISSUE_TEMPLATE/bug.md",
        "tests/fixtures/sample.md",
        "node_modules/pkg/README.md",
    ]:
        touch(tmp_path, rel)

    assert select_doc_files(tmp_path) == [
        Path("README.md"),
        Path("docs/api.rst"),
        Path("docs/guide/intro.md"),
        Path("docs/page.mdx"),
    ]
