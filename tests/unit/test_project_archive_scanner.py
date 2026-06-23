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
