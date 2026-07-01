from pathlib import Path

from src.project_archive.scanner import ProjectScanner, scanner_for_profile

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


def test_scanner_assigns_multilanguage_code_extensions(tmp_path):
    files = {
        "src/Main.java": "class Main {}",
        "src/native/index.cpp": "int main() { return 0; }",
        "frontend/src/App.ts": "export function App() {}",
        "frontend/src/app.js": "export function app() {}",
        "cmd/server/main.go": "package main",
        "src/main.rs": "fn main() {}",
        "go.mod": "module demo",
    }
    for relative_path, text in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    scanned = {file.path: file for file in ProjectScanner(root=tmp_path).scan()}

    assert scanned["src/Main.java"].language == "java"
    assert scanned["src/native/index.cpp"].language == "cpp"
    assert scanned["frontend/src/App.ts"].language == "typescript"
    assert scanned["frontend/src/app.js"].language == "javascript"
    assert scanned["cmd/server/main.go"].language == "go"
    assert scanned["src/main.rs"].language == "rust"
    assert scanned["go.mod"].language == "go_mod"


def test_scanner_skips_binary_files_that_decode_as_utf8(tmp_path):
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    (tmp_path / "payload.txt").write_bytes(b"text before\0text after")

    scanner = ProjectScanner(root=tmp_path)

    paths = {file.path for file in scanner.scan()}

    assert "README.md" in paths
    assert "payload.txt" not in paths


def test_scanner_ignores_dependency_and_cache_directories(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.js").write_text(
        "console.log('ignored')",
        encoding="utf-8",
    )
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "site.py").write_text("ignored", encoding="utf-8")

    scanner = ProjectScanner(root=tmp_path)

    paths = {file.path for file in scanner.scan()}

    assert "src/app.py" in paths
    assert "node_modules/pkg/index.js" not in paths
    assert ".venv/lib/site.py" not in paths


def test_architecture_profile_skips_tests_and_assistant_workflows(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "dubbo-common" / "src" / "main" / "java").mkdir(parents=True)
    (tmp_path / "dubbo-common" / "src" / "main" / "java" / "Demo.java").write_text(
        "class Demo {}",
        encoding="utf-8",
    )
    (tmp_path / "crates" / "core" / "src").mkdir(parents=True)
    (tmp_path / "crates" / "core" / "src" / "lib.rs").write_text(
        "pub fn run() {}",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("def test_ok(): pass", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "SKILL.md").write_text("# Skill", encoding="utf-8")

    paths = {file.path for file in scanner_for_profile(tmp_path, "architecture").scan()}

    assert "src/app.py" in paths
    assert "dubbo-common/src/main/java/Demo.java" in paths
    assert "crates/core/src/lib.rs" in paths
    assert "tests/test_app.py" not in paths
    assert ".claude/skills/SKILL.md" not in paths


def test_full_profile_keeps_supported_tests(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("def test_ok(): pass", encoding="utf-8")

    paths = {file.path for file in scanner_for_profile(tmp_path, "full").scan()}

    assert "src/app.py" in paths
    assert "tests/test_app.py" in paths
