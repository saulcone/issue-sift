"""Copy a repository's documentation (Markdown / reStructuredText files) locally.

The repository is shallow-cloned into a temporary folder and only the
documentation files are kept, preserving their relative paths.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

DOC_SUFFIXES = {".md", ".mdx", ".rst"}
SKIPPED_DIRS = {".git", ".github", "node_modules", "tests", "test"}


def select_doc_files(root: Path) -> list[Path]:
    """Documentation files under root, as paths relative to root, sorted."""
    files = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part in SKIPPED_DIRS for part in rel.parts):
            continue
        if path.is_file() and path.suffix.lower() in DOC_SUFFIXES:
            files.append(rel)
    return sorted(files, key=lambda p: p.as_posix())


def download_docs(repo: str, output_dir: Path) -> int:
    """Shallow-clone https://github.com/<repo> and copy its docs to output_dir."""
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "repo"
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--quiet",
                f"https://github.com/{repo}.git",
                str(clone),
            ],
            check=True,
        )
        files = select_doc_files(clone)
        if output_dir.exists():
            shutil.rmtree(output_dir)
        for rel in files:
            target = output_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(clone / rel, target)
    return len(files)
