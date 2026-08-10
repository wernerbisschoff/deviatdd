<lifecycle mode="product">

**Product-Layer Lifecycle (Release / Architecture / Flows)**:
Product-layer commands author a single artifact under `specs/_product/` and
commit it through the canonical helper. There is **no** `deviate <phase> pre`
and **no** `deviate <phase> post` script — those exist only for plan /
specify / tasks / pr / merge (meso and micro phases).

**Pre-work (read-only)**:
- Read `specs/constitution.md` (prepended as the first tier of this prompt)
  for the binding tech-stack, testing, and definition-of-done rules.
- Read `specs/_product/architecture.md` and `specs/_product/flows/index.md`
  when present. Both are optional inputs — release planning falls back to the
  operator's release-goal description when catalogs are absent.

**Artifact authoring**:
- Write the artifact with the `write` tool. Paths in the artifact body MUST
  be relative to `repo_root`; absolute paths are forbidden.
- The artifact's content schema is defined in this prompt's body (Goal /
  Constraints / Included Flows / Included Work / Deferred Epics / Acceptance
  Criteria for release; cross-epic contract for architecture; flow catalog
  entries for flows).

**Commit via the canonical helper**:
```python
from pathlib import Path
from deviate.core.commit import commit_artifact

commit_artifact(
    Path("<artifact-path>"),
    "docs(release): <one-line summary of the release goal>",
)
```
The exact commit subject prefix (`docs(release):`, `docs(architecture):`,
`docs(flows):`) follows the product-layer convention; see the body of this
prompt. The skill MUST NOT pass `no_verify=True`. If a pre-commit hook
fails, surface the hook stderr verbatim and stop — do not retry with
`--no-verify`. Conversational output alone is NOT sufficient: the artifact
must be on disk and committed before the phase terminates, because
downstream `/deviate-explore` reads the file from disk as the guiding
compass for the next layer.

**HITL Gate Handoff**:
After the commit succeeds, terminate. Do NOT auto-advance to the next
phase. The product-layer phase terminates at a HITL gate — the human
decides when to invoke `/deviate-explore` (or the next product-layer
command) against the just-authored artifact.

</lifecycle>