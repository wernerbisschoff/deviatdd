## ⚡ DeviaTDD Verification and Mise Tasks

Use `mise run <task>`:

| Task | Purpose |
|------|---------|
| `mise run test` | Unit tests by default |
{{targeted_test_row}}
| `mise run test:unit` | Unit tests only |
| `mise run test:integration` | Unit plus integration tests |
| `mise run test:e2e` | Unit plus integration plus E2E tests |
| `mise run doctor` | Readiness |
| `mise run doctor:unit` | Unit readiness |
| `mise run doctor:integration` | Unit+integration readiness |
| `mise run doctor:e2e` | Unit+integration+E2E readiness |

{{targeted_test_guidance}}
Before completion, run the matching `test:*` layer task.

Unit tests must not require external services.
Put service-dependent checks in integration tests.
