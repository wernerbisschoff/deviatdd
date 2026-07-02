---
title: "Why Sha-Anchored Verification"
description: "Why every doc page carries a verified_sha and last_verified_at, how the anchor defends against doc rot, and the trade-offs we accept."
doc_type: explanation
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues: []
prev: explanation/data-and-governance/append-only-ledgers.md
next: false
---

A doc page is a snapshot of how some piece of the codebase is shaped. Code, however, is in motion: every commit moves interfaces, renames modules, and invalidates the claims a page made yesterday. Doc rot — the slow corruption of a still-formatted page whose underlying facts no longer hold — is the dominant failure mode of any docs site that lives alongside an active codebase. The question the frontmatter schema has to answer is how to give a reader a credible signal that the page they are looking at is anchored to a real, identifiable code state, not to an impressionistic memory of one. Without such an anchor, a docs site degrades into folklore: pages look authoritative, but no one can tell which version of the code they describe.

## Rationale

The decision is to make every page carry two provenance fields — `verified_sha` and `last_verified_at` — alongside Starlight's default `title` / `description`. `verified_sha` is the commit SHA the page's claims have been validated against; `last_verified_at` is the date a human (or a verifier under human supervision) last walked the page and confirmed the claims still hold. Both are declared as required in the `extend` block of `apps/docs/src/content.config.ts`, which means a page that omits them fails the Starlight build with an `InvalidContentEntryDataError`. That hard fail is deliberate: a doc without provenance is a doc with no anchor, and a docs site that lets un-anchored pages ship is the site that publishes folklore. The verifier (C6) walks the diff between each page's `verified_sha` and the current `HEAD` to surface which pages have drifted; the writer prompts (C2–C5) declare the schema they must emit; the scaffold (C7) creates the `extend` schema idempotently. The contract is enforced at every link in the chain, which is the only way a contract survives.

## Mental Model

Picture the docs site as a layer cake. Each page is a horizontal slice whose top surface is the prose the reader sees, whose side surfaces are the cross-links, and whose bottom surface — pressed firmly into the codebase — is the commit SHA the prose is true against. The SHA is the binding: it is what makes the page *reprovable*. When a reviewer re-reads a page after a commit, they are not asking "does this prose read well?"; they are asking "does this prose still hold under the commit SHA currently stamped on it?" If yes, the anchor stays; if no, the anchor moves, and the verifier routes the page back to its writer for re-verification.

```
    ┌─────────────────────────────────────────────────┐
    │  prose body — the readable claims               │
    ├─────────────────────────────────────────────────┤
    │  cross-links (related how-to, tutorial, ref)    │
    ├═════════════════════════════════════════════════┤ <- binding surface
    │  verified_sha: 36b6a8b   last_verified_at: …   │ <- the anchor
    └─────────────────────────────────────────────────┘
        │                                  │
        v                                  v
   reader-facing                       codebase-grounded
    presentation                        truth claim
```

## Trade-Offs

Three alternatives were considered and rejected before adopting sha-anchored verification.

A **no-provenance contract** — every page ships with just Starlight's defaults — was rejected because it removes the cost of fabrication. A writer can produce a confidently-worded page whose claims are unverified and uncheckable, and the reader has no recourse except to read the code themselves. Sha-anchored verification does not make doc rot impossible, but it makes fabrication visible at review time, which is the property the rest of the contract depends on.

A **release-version anchor** — pages claim to describe `v2.3.1` of the codebase — was rejected because it presupposes a release cadence that fits the doc, not the code. A docs site for a tool that ships daily would either accumulate stale pages or force a `verified_sha` rewrite with every release. A commit SHA is finer-grained than any release tag and survives trunk-based development without ceremony.

A **content-hash anchor** — the page's prose is hashed and the hash is stamped back into the frontmatter — was rejected because prose can be reworded without losing truth. The hash would drift on every editorial pass (synonyms, punctuation, formatting) and never on the change that actually matters (the code moved). Git already gives us a content-addressable identity for the code, and binding the doc to the code is the cheaper, more durable contract. The cost we accept is that the binding site moves over time — every doc edit is a chance to re-anchor — but that movement is exactly what doc-rot defence requires.

## Implications

The contract changes what *reviewing a page* means. A reviewer is no longer the last reader; they are the most recent anchorer. The transition from `status: draft` to `status: reviewed` is gated on a sha-anchored pass: if the reviewer cannot point at a commit that vouches for the page's claims, the page stays draft. The verifier (C6) becomes a dependency of publishing, not a polite suggestion: a writer may emit a page, but until a reviewer has walked it against its `verified_sha`, the page's claims are provisional. The cost we accept is friction — every doc edit requires either re-anchoring or explicit acknowledgement that the anchor still holds. We accept that friction because doc rot is the failure mode we are buying safety against, and the only known defence against doc rot is to make staleness loud.

## See Also

- [Tutorial → Run Your First DeviaTDD Cycle](/tutorials/starter-first-run) — see the provenance fields updated across one full development cycle
- [How-To → Getting Started → Run /deviate-init](/how-to/getting-started/init) — the operator recipe that materialises the governance skeleton this contract defends
- [Reference → Config → Config Field Reference](/reference/config/starter-config) — every Tome frontmatter field with allowed values and the `extend`-block source
