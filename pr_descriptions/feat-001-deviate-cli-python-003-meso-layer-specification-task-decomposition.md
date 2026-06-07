This PR implements "ISS-003".  consolidate error handlers and enforce model consistency; mark task complete — integration tests verified  add integration tests for meso specify->tasks cycle; mark task complete in tasks.md  phase-parameterize error handlers to match macro.py pattern.

**Changes:**
- `specs/001-deviate-cli-python/003-meso-layer-specification-task-decomposition/spec.md`
- `specs/001-deviate-cli-python/003-meso-layer-specification-task-decomposition/tasks.md`
- `specs/issues.jsonl`
- `src/deviate/cli/__init__.py`
- `src/deviate/cli/_common.py`
- `src/deviate/cli/macro.py`
- `src/deviate/cli/meso.py`
- `src/deviate/state/config.py`
- `src/deviate/state/ledger.py`
- `tests/test_integration/conftest.py`
- `tests/test_integration/test_meso_task_ledger.py`
- `tests/test_meso/__init__.py`
- `tests/test_meso/test_specify.py`
- `tests/test_meso/test_tasks.py`
- `tests/test_state/test_config.py`
- `tests/test_state/test_ledger.py`

 16 files changed, 1148 insertions(+), 46 deletions(-)