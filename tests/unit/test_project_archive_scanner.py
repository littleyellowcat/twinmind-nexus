from pathlib import Path

from src.project_archive.scanner import ProjectScanner


FIXTURE = Path("tests/fixtures/project_archive_sample")


def test_scanner_discovers_supported_project_files():
    scanner = ProjectScanner(root=FIXTURE)

    files = scanner.scan()
    paths = {file.path for file in files}

    assert "README.md" in paths
    assert "pyproject.toml" in paths
    assert "src/sample_app/main.py" in paths
    assert "config/settings.yaml" in paths


def test_scanner_assigns_languages_from_extensions():
    scanner = ProjectScanner(root=FIXTURE)

    files = {file.path: file for file in scanner.scan()}

    assert files["src/sample_app/main.py"].language == "python"
    assert files["README.md"].language == "markdown"
    assert files["pyproject.toml"].language == "toml"
    assert files["config/settings.yaml"].language == "yaml"


def test_scanner_skips_binary_files_that_decode_as_utf8(tmp_path):
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    (tmp_path / "payload.txt").write_bytes(b"text before\0text after")

    scanner = ProjectScanner(root=tmp_path)

    paths = {file.path for file in scanner.scan()}

    assert "README.md" in paths
    assert "payload.txt" not in paths
