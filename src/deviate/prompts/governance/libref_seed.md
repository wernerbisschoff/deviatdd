## Offline Documentation System

The `libref` CLI is a local-first documentation tool for AI agents. It provides offline-queryable API docs for all project dependencies. **Always prefer `libref query <library> <topic>` over web fetching** — results are local, instant, and token-cheap.

### Usage Rules
- **Discovery first**: Run `libref list` to see available documentation packages before querying a library.
- **Primary lookup**: Use `libref query <library@version> "<topic>"` as the first and primary documentation mechanism for all library/framework API questions.
- **Registration**: When a dependency is not yet indexed, use `libref add <source>` (git repo URL) to register its documentation.
- **Fallback hierarchy**: `libref query` → training data → web fetch (last resort). Web fetching is only acceptable when `libref` has no documentation for the required library.

### Quick-Start Workflow
1. Run `deviate explore` to scan the codebase
2. Run `deviate research` for architectural analysis
3. Run `deviate prd` to compile requirements
4. Run `deviate shard` to decompose into issues
5. Run `deviate specify` to write functional contracts
6. Run `deviate tasks` to decompose into TDD cycles
7. Execute each task via RED → GREEN → REFACTOR
8. Run `deviate e2e` for end-to-end verification
