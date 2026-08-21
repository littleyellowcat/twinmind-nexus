from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.project_archive.harness_artifacts import HarnessArtifactStore
from src.project_archive.harness_events import HarnessEventStore
from src.project_archive.harness_governance import (
    FORBIDDEN_CODING_AGENT_TOOLS,
    build_harness_policy_check,
    evaluate_harness_operation,
    harness_capability_matrix,
)
from src.project_archive.harness_summary import build_harness_summary
from src.project_archive.scanner import ProjectScanner


def test_harness_event_store_appends_project_events_in_sequence(tmp_path: Path) -> None:
    store = HarnessEventStore(tmp_path)

    first = store.append(
        project_id="sample",
        run_id="run-1",
        event_type="run.started",
        data={"phase": "agent_eval"},
    )
    second = store.append(
        project_id="sample",
        run_id="run-1",
        event_type="run.completed",
        data={"status": "pass"},
    )

    assert first.sequence == 1
    assert second.sequence == 2
    assert first.id != second.id
    events = store.list_events("sample")
    assert [event.type for event in events] == ["run.started", "run.completed"]
    assert [event.sequence for event in events] == [1, 2]
    assert store.list_events("sample", event_type="run.completed")[0].data["status"] == "pass"
    raw_lines = (tmp_path / "sample" / "harness_events.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["sequence"] for line in raw_lines] == [1, 2]


def test_harness_event_store_limit_returns_latest_events(tmp_path: Path) -> None:
    store = HarnessEventStore(tmp_path)
    for index in range(4):
        store.append(
            project_id="sample",
            run_id=f"run-{index}",
            event_type="run.completed",
            data={"index": index},
        )

    events = store.list_events("sample", limit=2)

    assert [event.sequence for event in events] == [3, 4]
    assert [event.data["index"] for event in events] == [2, 3]


def test_harness_artifact_store_retains_full_content_with_bounded_preview(tmp_path: Path) -> None:
    content = "HEAD-" + ("x" * 240) + "-TAIL"
    store = HarnessArtifactStore(tmp_path, max_preview_bytes=80)

    artifact = store.persist_text(
        project_id="sample",
        run_id="run-1",
        kind="agent_eval_report",
        content=content,
    )

    assert artifact.kind == "agent_eval_report"
    assert artifact.bytes == len(content.encode("utf-8"))
    assert artifact.sha256 == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert artifact.truncated is True
    assert artifact.omitted_bytes > 0
    assert "output truncated" in artifact.preview
    assert "HEAD-" in artifact.preview
    assert "-TAIL" in artifact.preview
    assert Path(artifact.path).read_text(encoding="utf-8") == content


def test_harness_governance_evaluates_default_operation_risks() -> None:
    assert evaluate_harness_operation("read_only", "archive:sample").effect == "allow"
    assert evaluate_harness_operation("local_artifact_write", "artifact:sample").effect == "allow"
    assert evaluate_harness_operation("live_model_call", "provider:deepseek").effect == "ask"
    assert evaluate_harness_operation("external_api_call", "github:zip").effect == "ask"
    assert evaluate_harness_operation("paid_operation", "image-generation").effect == "ask"
    assert evaluate_harness_operation("production_operation", "deploy").effect == "deny"


def test_harness_capability_matrix_excludes_coding_agent_tools() -> None:
    matrix = harness_capability_matrix()
    roles = {role["role"] for role in matrix["roles"]}

    assert {"archivist", "cartographer", "detective", "skeptic", "curator"} <= roles
    all_tools = {
        tool
        for role in matrix["roles"]
        for tool in role["allowed_tools"]
    }
    assert all_tools.isdisjoint(FORBIDDEN_CODING_AGENT_TOOLS)
    detective = next(role for role in matrix["roles"] if role["role"] == "detective")
    assert "hybrid_search" in detective["allowed_tools"]
    assert detective["risk_level"] == "medium"


def test_harness_summary_reports_last_failure_and_resume_guidance(tmp_path: Path) -> None:
    event_store = HarnessEventStore(tmp_path)
    event_store.append(
        project_id="sample",
        run_id="agent-eval:1",
        event_type="run.started",
        data={"kind": "agent_eval_harness"},
    )
    event_store.append(
        project_id="sample",
        run_id="agent-eval:1",
        event_type="artifact.persisted",
        data={
            "kind": "agent_eval_report",
            "artifact_id": "artifact_1",
            "sha256": "abc",
            "bytes": 42,
            "path": "/tmp/report.json",
        },
    )
    event_store.append(
        project_id="sample",
        run_id="agent-eval:1",
        event_type="run.failed",
        data={"kind": "agent_eval_harness", "error": "evaluation failed"},
    )

    summary = build_harness_summary(
        project_id="sample",
        events=[event.to_dict() for event in event_store.list_events("sample")],
        agent_eval_report={
            "id": "agent-eval:1",
            "status": "failed",
            "recommendations": ["Refresh golden questions."],
            "artifacts": {
                "agent_eval_report": {
                    "kind": "agent_eval_report",
                    "artifact_id": "artifact_1",
                    "sha256": "abc",
                    "bytes": 42,
                    "preview": "{}",
                }
            },
            "metadata": {
                "agent_error": "",
                "evaluation_error": "evaluation failed",
            },
        },
        version_events=[
            {
                "kind": "agent_eval_harness",
                "status": "failed",
                "artifact_path": "/tmp/report.json",
            }
        ],
        mission_records=[
            {
                "id": "mission-1",
                "status": "stopped",
                "created_at": "2026-08-21T00:00:00+00:00",
            }
        ],
    )

    assert summary["project_id"] == "sample"
    assert summary["status"] == "failed"
    assert summary["phase"] == "agent_eval_harness"
    assert summary["latest_sequence"] == 3
    assert summary["last_run"]["run_id"] == "agent-eval:1"
    assert summary["last_failure"]["error"] == "evaluation failed"
    assert summary["resume_available"] is True
    assert summary["resume_action"] == "rerun_agent_eval_harness"
    assert summary["next_best_action"] == "Inspect the last failure, then rerun AgentEval with deterministic settings."
    assert summary["artifacts"][0]["artifact_id"] == "artifact_1"
    assert "evaluation failed" in summary["errors"]
    assert "Refresh golden questions." in summary["warnings"]
    assert summary["metrics"]["mission_records"] == 1


def test_harness_policy_check_returns_dry_run_cost_guard_without_secrets() -> None:
    policy = build_harness_policy_check(
        action="live_model_call",
        resource="provider:deepseek",
        provider_status={
            "llm_enabled": False,
            "provider": "rules",
            "model": None,
            "api_key": "sk-secret",
        },
    )

    assert policy["dry_run"] is True
    assert policy["decision"]["effect"] == "ask"
    assert policy["requires_confirmation"] is True
    assert policy["allowed_without_confirmation"] is False
    assert policy["denied"] is False
    assert policy["provider"]["configured"] is False
    assert policy["provider"]["provider"] == "rules"
    assert policy["next_required_action"] == "Request explicit confirmation before calling live providers or paid/external services."
    assert "sk-secret" not in json.dumps(policy)


def test_harness_cli_helpers_list_events_and_diagnose_storage(tmp_path: Path) -> None:
    project_dir = tmp_path / "sample"
    project_dir.mkdir()
    (project_dir / "draft_archive.json").write_text(
        json.dumps({"project_id": "sample"}),
        encoding="utf-8",
    )
    event_store = HarnessEventStore(tmp_path)
    event_store.append(
        project_id="sample",
        run_id="run-1",
        event_type="run.started",
        data={"kind": "agent_eval_harness"},
    )
    event_store.append(
        project_id="sample",
        run_id="run-1",
        event_type="run.completed",
        data={"status": "pass"},
    )

    from scripts.harness_doctor import inspect_harness_storage
    from scripts.harness_events import load_project_events

    listed = load_project_events(tmp_path, "sample", event_type="run.completed", limit=10)
    report = inspect_harness_storage(tmp_path, project_id="sample")

    assert listed["metrics"]["events"] == 1
    assert listed["events"][0]["type"] == "run.completed"
    assert report["storage_dir"] == str(tmp_path)
    assert report["metrics"]["projects"] == 1
    assert report["projects"][0]["project_id"] == "sample"
    assert report["projects"][0]["harness"]["latest_sequence"] == 2


def test_dev_env_doctor_reports_missing_dependencies_without_installing(monkeypatch) -> None:
    from scripts.dev_env_doctor import inspect_dev_environment

    monkeypatch.setattr(
        "scripts.dev_env_doctor._module_available",
        lambda name: name in {"pytest", "fastapi"},
    )
    monkeypatch.setattr(
        "scripts.dev_env_doctor._command_available",
        lambda name: name == "python3",
    )

    report = inspect_dev_environment(project_root=Path("."), python_executable="python3")

    assert report["status"] == "warn"
    assert "jieba" in report["missing"]["python_modules"]
    assert "node" in report["missing"]["commands"]
    assert report["checks"]["python_version"]["ok"] is True
    assert report["policy"]["auto_install"] is False


def test_project_scanner_marks_agent_rule_files(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("Use deterministic tests.", encoding="utf-8")
    (tmp_path / "llms.txt").write_text("TwinMind project map.", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Sample", encoding="utf-8")

    scanned = {file.path: file for file in ProjectScanner(tmp_path).scan()}

    assert scanned["AGENTS.md"].metadata["rule_file"] is True
    assert scanned["AGENTS.md"].metadata["rule_kind"] == "agents"
    assert scanned["llms.txt"].metadata["rule_file"] is True
    assert scanned["llms.txt"].metadata["rule_kind"] == "llms"
    assert scanned["README.md"].metadata.get("rule_file") is not True


def test_harness_policy_v2_evaluates_role_tool_resource_rules() -> None:
    from src.project_archive.harness_policy import (
        HarnessPolicyContext,
        evaluate_policy,
        load_default_policy_rules,
    )

    rules = load_default_policy_rules()
    allowed = evaluate_policy(
        HarnessPolicyContext(
            role="detective",
            action="read_only",
            tool="hybrid_search",
            resource="archive:sample",
        ),
        rules,
    )
    denied = evaluate_policy(
        HarnessPolicyContext(
            role="curator",
            action="coding_agent_tool",
            tool="bash",
            resource="shell:local",
        ),
        rules,
    )
    ask = evaluate_policy(
        HarnessPolicyContext(
            role="detective",
            action="live_model_call",
            tool="agent_report",
            resource="provider:deepseek",
        ),
        rules,
    )

    assert allowed.effect == "allow"
    assert denied.effect == "deny"
    assert "Forbidden coding-agent tool" in denied.reason
    assert ask.effect == "ask"


def test_agent_profiles_reject_forbidden_tools() -> None:
    from src.project_archive.agent_profiles import load_agent_profiles, profiles_to_capability_matrix

    profiles = load_agent_profiles(
        {
            "roles": {
                "archivist": {
                    "purpose": "Select evidence.",
                    "allowed_tools": ["list_halls", "get_evidence"],
                    "disallowed_actions": ["archive_mutation"],
                    "risk_level": "low",
                }
            }
        }
    )
    matrix = profiles_to_capability_matrix(profiles)

    assert matrix["roles"][0]["role"] == "archivist"
    assert matrix["roles"][0]["allowed_tools"] == ["list_halls", "get_evidence"]
    try:
        load_agent_profiles(
            {
                "roles": {
                    "bad": {
                        "purpose": "Bad profile.",
                        "allowed_tools": ["bash"],
                        "disallowed_actions": [],
                        "risk_level": "high",
                    }
                }
            }
        )
    except ValueError as exc:
        assert "Forbidden tool" in str(exc)
    else:
        raise AssertionError("Expected forbidden tool validation failure")


def test_harness_export_builds_redacted_timeline_and_manifest(tmp_path: Path) -> None:
    from src.project_archive.harness_export import build_harness_export

    project_dir = tmp_path / "sample"
    project_dir.mkdir()
    (project_dir / "draft_archive.json").write_text(json.dumps({"project_id": "sample"}), encoding="utf-8")
    event_store = HarnessEventStore(tmp_path)
    event_store.append(project_id="sample", run_id="run-1", event_type="run.started", data={"kind": "query"})
    artifact = HarnessArtifactStore(tmp_path).persist_text(
        project_id="sample",
        run_id="run-1",
        kind="query_trace",
        content="secret-free trace",
    )
    event_store.append(
        project_id="sample",
        run_id="run-1",
        event_type="artifact.persisted",
        data=artifact.to_dict(),
    )

    exported = build_harness_export(tmp_path, "sample")

    assert exported["project_id"] == "sample"
    assert exported["timeline"][0]["category"] == "run"
    assert exported["artifacts_manifest"]["artifacts"][0]["artifact_id"] == artifact.artifact_id
    assert str(tmp_path) not in json.dumps(exported)


def test_harness_commands_are_safe_and_dry_run_by_default() -> None:
    from src.project_archive.harness_commands import list_harness_commands, run_harness_command

    commands = list_harness_commands()
    command_ids = {command["id"] for command in commands}
    assert {"doctor", "events", "export-harness"} <= command_ids
    assert all("shell" not in json.dumps(command).lower() for command in commands)

    dry_run = run_harness_command("agent-eval-live", {"project_id": "sample"}, dry_run=True)
    assert dry_run["dry_run"] is True
    assert dry_run["policy"]["decision"]["effect"] == "ask"
    assert dry_run["executed"] is False


def test_artifact_retention_manifest_and_cleanup_dry_run(tmp_path: Path) -> None:
    from src.project_archive.harness_artifact_retention import (
        build_artifact_manifest,
        cleanup_artifacts,
        validate_artifacts,
    )

    artifact = HarnessArtifactStore(tmp_path).persist_text(
        project_id="sample",
        run_id="run-1",
        kind="agent_eval_report",
        content="report",
    )
    orphan_dir = tmp_path / "sample" / "harness_artifacts" / "orphan"
    orphan_dir.mkdir(parents=True)
    orphan = orphan_dir / "old.txt"
    orphan.write_text("old", encoding="utf-8")

    manifest = build_artifact_manifest(tmp_path, "sample")
    validation = validate_artifacts(tmp_path, "sample")
    cleanup = cleanup_artifacts(tmp_path, "sample", dry_run=True)

    assert manifest["artifacts"][0]["artifact_id"] == artifact.artifact_id
    assert any(item["path"].endswith("old.txt") for item in validation["orphans"])
    assert cleanup["dry_run"] is True
    assert any(item["path"].endswith("old.txt") for item in cleanup["candidates"])
    assert orphan.exists()


def test_provider_runtime_sanitizes_errors_and_records_fallback() -> None:
    from src.project_archive.provider_runtime import provider_failure_payload, sanitize_provider_error

    message = sanitize_provider_error("401 invalid api_key sk-secret-token")
    payload = provider_failure_payload(
        provider="deepseek",
        model="deepseek-chat",
        error="timeout with api_key sk-secret-token",
        fallback="rules",
    )

    assert "sk-secret-token" not in message
    assert payload["category"] == "provider_timeout"
    assert payload["fallback"] == "rules"
    assert "sk-secret-token" not in json.dumps(payload)


def test_github_report_runner_generates_report_only_markdown() -> None:
    from scripts.github_report_runner import render_report_markdown

    markdown = render_report_markdown(
        {
            "project_id": "sample",
            "status": "complete",
            "summary": {"entities": 3, "relations": 2, "evidence": 1},
            "harness": {"status": "complete", "latest_sequence": 4},
            "artifacts": [{"kind": "harness_export", "path": "export.json"}],
        }
    )

    assert "# TwinMind Report: sample" in markdown
    assert "Report-only runner" in markdown
    assert "No code changes were generated" in markdown
