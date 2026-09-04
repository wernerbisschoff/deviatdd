## ⚡ DeviaTDD Verification and Mise Tasks

Use `mise run <task>` for project checks. `/deviate-init` creates or merges these tasks:

| Task | Purpose |
|------|---------|
| `mise run test` | Unit tests by default |
{{targeted_test_row}}
| `mise run test:unit` | Unit tests only |
| `mise run test:integration` | Unit plus integration tests |
| `mise run test:e2e` | Unit plus integration plus E2E tests, when configured |
| `mise run doctor` | Readiness checks for all configured layers |
| `mise run doctor:unit` | Unit toolchain readiness; no external services |
| `mise run doctor:integration` | Unit and integration dependency readiness |
| `mise run doctor:e2e` | Unit, integration, and E2E dependency readiness, when configured |

{{targeted_test_guidance}}
Before completion, run the matching `test:*` layer task.
Verify before you say a task is done.

Unit tests must not require a database, Redis, network service, container, or other external service.
Put service-dependent checks in integration tests.
