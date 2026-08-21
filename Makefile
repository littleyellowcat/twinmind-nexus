.PHONY: doctor harness-test py-compile diff-check api-test frontend-build github-report-smoke

PYTHON ?= python3
PYTHON312 ?= /Users/kitten/.local/bin/python3.12

doctor:
	$(PYTHON) scripts/dev_env_doctor.py --json

harness-test:
	$(PYTHON) -c "import datetime, sys; setattr(datetime, 'UTC', getattr(datetime, 'UTC', datetime.timezone.utc)); import pytest; sys.exit(pytest.main(['tests/unit/test_project_archive_harness.py', '-q']))"

api-test:
	$(PYTHON) -m pytest tests/unit/test_project_archive_api.py -q

py-compile:
	$(PYTHON312) -m py_compile \
		scripts/dev_env_doctor.py \
		scripts/github_report_runner.py \
		scripts/harness_artifacts.py \
		scripts/harness_command.py \
		scripts/harness_doctor.py \
		scripts/harness_events.py \
		scripts/harness_export.py \
		src/project_archive/agent_profiles.py \
		src/project_archive/harness_artifact_retention.py \
		src/project_archive/harness_artifacts.py \
		src/project_archive/harness_commands.py \
		src/project_archive/harness_events.py \
		src/project_archive/harness_export.py \
		src/project_archive/harness_governance.py \
		src/project_archive/harness_policy.py \
		src/project_archive/harness_summary.py \
		src/project_archive/provider_runtime.py

diff-check:
	git diff --check

frontend-build:
	cd frontend && npm run build

github-report-smoke:
	$(PYTHON) scripts/github_report_runner.py --input docs/examples/twinmind_report_payload.json
