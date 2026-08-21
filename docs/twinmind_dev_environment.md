# TwinMind Dev Environment

This project keeps a small, stdlib-only diagnostic path so agents and CI can inspect readiness before importing the full application stack.

## Quick Checks

```bash
make doctor
make harness-test
make py-compile
make diff-check
```

`make doctor` never installs dependencies. Missing Python modules, Node tools, or `frontend/node_modules` are reported as warnings with explicit next steps.

## Dependency Policy

- Python project runtime targets Python 3.10+.
- The stdlib doctor can run on Python 3.9+ so older macOS shells can still report blockers.
- Dependency installation requires explicit user confirmation.
- API tests may fail when optional project modules such as `jieba` are missing.
- Frontend builds require `frontend/node_modules`; do not auto-install it from an agent run.

## Harness Verification

`make harness-test` runs the local harness behavior tests with a compatibility shim for `datetime.UTC` on older Python interpreters.

`make py-compile` uses `/Users/kitten/.local/bin/python3.12` by default because the project code uses modern typing syntax.
