"""Project directory scanner for TwinMind Archive."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, List

from src.project_archive.types import ProjectFile

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".superpowers",
    "__pycache__",
    "data",
    "dist",
    "build",
    "venv",
    ".venv",
}

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
}

MAX_GENERIC_FILE_BYTES = 200_000


class ProjectScanner:
    """Scan a project root into readable project files."""

    def __init__(
        self,
        root: Path | str,
        ignore_dirs: Iterable[str] = DEFAULT_IGNORE_DIRS,
    ) -> None:
        self.root = Path(root)
        self.ignore_dirs = set(ignore_dirs)

    def scan(self) -> List[ProjectFile]:
        files: List[ProjectFile] = []

        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or self._is_ignored(path):
                continue

            relative_path = path.relative_to(self.root).as_posix()
            language = LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "generic")

            try:
                size = path.stat().st_size
            except OSError:
                continue

            if language == "generic" and size > MAX_GENERIC_FILE_BYTES:
                continue

            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            files.append(
                ProjectFile(
                    id=_stable_file_id(relative_path),
                    path=relative_path,
                    language=language,
                    text=text,
                    metadata={"size": size},
                )
            )

        return sorted(files, key=lambda project_file: project_file.path)

    def _is_ignored(self, path: Path) -> bool:
        try:
            relative_parts = path.relative_to(self.root).parts
        except ValueError:
            relative_parts = path.parts
        return any(part in self.ignore_dirs for part in relative_parts)


def _stable_file_id(relative_path: str) -> str:
    digest = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:12]
    return f"file_{digest}"
