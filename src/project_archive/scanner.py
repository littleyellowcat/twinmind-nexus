"""Project directory scanner for TwinMind Archive."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from src.project_archive.types import ProjectFile

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".superpowers",
    ".cache",
    ".next",
    ".parcel-cache",
    ".tox",
    ".turbo",
    "__pycache__",
    "coverage",
    "data",
    "dist",
    "build",
    "node_modules",
    "site-packages",
    "target",
    "venv",
    ".venv",
    ".twinmind",
}

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".java": "java",
    ".c": "cpp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "cpp",
    ".hh": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".xml": "xml",
    ".gradle": "gradle",
    ".properties": "properties",
    ".ini": "ini",
}

LANGUAGE_BY_FILENAME = {
    "Dockerfile": "dockerfile",
    "docker-compose.yml": "yaml",
    "docker-compose.yaml": "yaml",
    "go.mod": "go_mod",
    "go.sum": "go_mod",
    "Cargo.lock": "toml",
    "Gemfile": "ruby",
    "Makefile": "makefile",
}

MAX_GENERIC_FILE_BYTES = 200_000
BINARY_SAMPLE_BYTES = 4096
BINARY_CONTROL_RATIO = 0.30
SCAN_PROFILE_ARCHITECTURE = "architecture"
SCAN_PROFILE_FULL = "full"
SCAN_PROFILE_DOCS = "docs"
SCAN_PROFILE_TESTS = "tests"
SCAN_PROFILES = {
    SCAN_PROFILE_ARCHITECTURE,
    SCAN_PROFILE_FULL,
    SCAN_PROFILE_DOCS,
    SCAN_PROFILE_TESTS,
}
SCAN_PROFILE_INCLUDE_PREFIXES = {
    SCAN_PROFILE_DOCS: {
        "README.md",
        "DEV_SPEC.md",
        "docs/",
    },
    SCAN_PROFILE_TESTS: {
        "src/",
        "tests/",
        "test/",
        "pytest.ini",
        "pyproject.toml",
    },
}
SCAN_PROFILE_IGNORE_PREFIXES = {
    SCAN_PROFILE_ARCHITECTURE: {
        ".claude/",
        ".github/",
        "docs/superpowers/",
        "test/",
        "tests/",
    },
    SCAN_PROFILE_DOCS: {
        ".claude/",
        ".github/",
        "tests/",
    },
    SCAN_PROFILE_TESTS: {
        ".claude/",
        ".github/",
        "docs/",
    },
}


class ProjectScanner:
    """Scan a project root into readable project files."""

    def __init__(
        self,
        root: Path | str,
        ignore_dirs: Iterable[str] = DEFAULT_IGNORE_DIRS,
        include_path_prefixes: Iterable[str] | None = None,
        ignore_path_prefixes: Iterable[str] | None = None,
    ) -> None:
        self.root = Path(root)
        self.ignore_dirs = set(ignore_dirs)
        self.include_path_prefixes = set(include_path_prefixes or [])
        self.ignore_path_prefixes = set(ignore_path_prefixes or [])
        self._last_diagnostics: dict[str, Any] = {}

    def scan(self) -> list[ProjectFile]:
        files: list[ProjectFile] = []
        total_files = 0
        skipped_by_reason: Counter[str] = Counter()
        language_counts: Counter[str] = Counter()
        skipped_samples: list[dict[str, str]] = []

        def record_skip(path: Path, reason: str) -> None:
            skipped_by_reason[reason] += 1
            if len(skipped_samples) >= 20:
                return
            try:
                relative_path = path.relative_to(self.root).as_posix()
            except ValueError:
                relative_path = path.as_posix()
            skipped_samples.append({"path": relative_path, "reason": reason})

        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            total_files += 1
            if self._is_ignored(path):
                record_skip(path, "ignored_path")
                continue

            relative_path = path.relative_to(self.root).as_posix()
            if not self._is_included(relative_path):
                record_skip(path, "outside_scan_profile")
                continue
            language = LANGUAGE_BY_FILENAME.get(
                path.name,
                LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "generic"),
            )

            try:
                size = path.stat().st_size
            except OSError:
                record_skip(path, "stat_error")
                continue

            if language == "generic" and size > MAX_GENERIC_FILE_BYTES:
                record_skip(path, "generic_file_too_large")
                continue

            try:
                if _looks_binary(path):
                    record_skip(path, "binary_file")
                    continue
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                record_skip(path, "decode_error")
                continue
            except OSError:
                record_skip(path, "read_error")
                continue

            language_counts[language] += 1
            files.append(
                ProjectFile(
                    id=_stable_file_id(relative_path),
                    path=relative_path,
                    language=language,
                    text=text,
                    metadata={"size": size},
                )
            )

        kept_files = sorted(files, key=lambda project_file: project_file.path)
        self._last_diagnostics = {
            "total_files_discovered": total_files,
            "kept_files": len(kept_files),
            "skipped_files": sum(skipped_by_reason.values()),
            "skipped_by_reason": dict(sorted(skipped_by_reason.items())),
            "skipped_samples": skipped_samples,
            "language_counts": dict(sorted(language_counts.items())),
            "limits": {
                "max_generic_file_bytes": MAX_GENERIC_FILE_BYTES,
            },
            "include_path_prefixes": sorted(self.include_path_prefixes),
            "ignore_path_prefixes": sorted(self.ignore_path_prefixes),
            "ignored_dirs": sorted(self.ignore_dirs),
        }
        return kept_files

    def diagnostics(self) -> dict[str, Any]:
        return dict(self._last_diagnostics)

    def _is_ignored(self, path: Path) -> bool:
        try:
            relative_parts = path.relative_to(self.root).parts
        except ValueError:
            relative_parts = path.parts
        relative_path = "/".join(relative_parts)
        return any(part in self.ignore_dirs for part in relative_parts) or _matches_path_filter(
            relative_path,
            self.ignore_path_prefixes,
        )

    def _is_included(self, relative_path: str) -> bool:
        if not self.include_path_prefixes:
            return True
        return _matches_path_filter(relative_path, self.include_path_prefixes)


def scanner_for_profile(root: Path | str, profile: str) -> ProjectScanner:
    normalized = normalize_scan_profile(profile)
    return ProjectScanner(
        root=root,
        include_path_prefixes=SCAN_PROFILE_INCLUDE_PREFIXES.get(normalized),
        ignore_path_prefixes=SCAN_PROFILE_IGNORE_PREFIXES.get(normalized),
    )


def normalize_scan_profile(profile: str | None) -> str:
    if profile in SCAN_PROFILES:
        return profile
    return SCAN_PROFILE_ARCHITECTURE


def include_prefixes_for_profile(profile: str | None) -> set[str] | None:
    normalized = normalize_scan_profile(profile)
    return SCAN_PROFILE_INCLUDE_PREFIXES.get(normalized)


def ignore_prefixes_for_profile(profile: str | None) -> set[str]:
    normalized = normalize_scan_profile(profile)
    return set(SCAN_PROFILE_IGNORE_PREFIXES.get(normalized, set()))


def _matches_path_filter(relative_path: str, filters: Iterable[str]) -> bool:
    normalized_path = relative_path.strip("/")
    for raw_filter in filters:
        normalized_filter = raw_filter.strip("/")
        if not normalized_filter:
            continue
        if raw_filter.endswith("/"):
            if normalized_path == normalized_filter or normalized_path.startswith(
                f"{normalized_filter}/"
            ):
                return True
        elif normalized_path == normalized_filter:
            return True
    return False


def _stable_file_id(relative_path: str) -> str:
    digest = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:12]
    return f"file_{digest}"


def _looks_binary(path: Path) -> bool:
    with path.open("rb") as handle:
        sample = handle.read(BINARY_SAMPLE_BYTES)
    if not sample:
        return False
    if b"\0" in sample:
        return True

    control_bytes = sum(
        1
        for byte in sample
        if byte < 32 and byte not in (9, 10, 12, 13)
    )
    return control_bytes / len(sample) > BINARY_CONTROL_RATIO
