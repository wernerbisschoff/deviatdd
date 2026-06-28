# Security Policy

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Use one of these private channels:

1. **GitHub Security Advisories (preferred)** — open a
   [private security advisory](../../security/advisories/new). This goes
   directly to the maintainers and lets you collaborate on a fix
   before public disclosure.
2. **Direct contact** — reach the maintainer through the GitHub
   handle on the top commit of [`main`](../../commits/main). Use this
   only if the Advisories path is unavailable.

Include as much of the following as you can:

- A clear description of the vulnerability and its impact
- Reproduction steps (commands, input fixtures, environment)
- Affected version(s) (`deviate --version`) and commit SHA
- Your environment: Python version, OS, agent backend
- Whether the issue is exploitable without local code execution
- (Optional) A suggested fix or mitigation

You will receive an acknowledgement within **3 business days**, and a
status update at least every **7 days** until resolution.

---

## Supported versions

Only the **latest released version** receives security fixes.

| Version | Supported |
|---|---|
| `2.x` (latest) | ✅ |
| `< 2.0.0` | ❌ |

We do not backport security fixes to older minor versions. If you are
on an older release, please upgrade.

The current version is published under
[GitHub releases](../../releases) and on
[PyPI](https://pypi.org/project/deviate/).

---

## Disclosure timeline

We follow a **coordinated disclosure** model:

| Day | Action |
|---|---|
| 0 | Report received; acknowledgement sent |
| +3 | Triage: scope, severity, reproducer confirmed |
| +14 | Patch developed in a private fork (or advisory branch) |
| +30 | Patch released; CVE requested if applicable |
| +90 | Public disclosure (advisory published; release notes published) |

The 90-day window can be shortened if a fix is ready sooner, or
extended if a reporter needs more time to coordinate with downstream
users. We will negotiate the timeline in the advisory thread.

---

## What we commit to

- **Acknowledgement** of every report within 3 business days
- **Status updates** at least every 7 days while a fix is in progress
- **Credit** in the release notes and the GitHub Security Advisory
  (unless you request anonymity)
- **No legal action** against researchers acting in good faith and
  following this policy
- **Post-mortem** for any vulnerability that reached a tagged release,
  including root cause and remediation

---

## Scope

The following are **in scope**:

- Remote code execution or arbitrary file write via the `deviate` CLI
- Command injection in `git`, `pytest`, `bats`, or `uv` invocations
  spawned by the framework
- Sandbox or Tamper-Guard bypasses that allow a Micro-layer agent to
  write outside `src/**/*.py`
- JSONL ledger parser bugs that permit code execution or privilege
  escalation
- Path traversal or symlink attacks in worktree / branch creation
  (`src/deviate/cli/feature.py`)
- Insecure handling of credentials or tokens passed through agent
  backends (opencode, claude, droid, pi)
- Supply-chain compromise of dependencies listed in `pyproject.toml`

The following are **out of scope**:

- Vulnerabilities in third-party agent backends (opencode, Claude
  Code, Pi, Droid) — report those to the respective vendors
- Prompt-injection against user-supplied content (the framework
  deliberately passes user content to the agent; this is by design)
- Denial-of-service via oversized input (we rate-limit at the CLI
  level; sustained resource exhaustion is an operational concern)
- Issues only reproducible on unsupported Python versions
  (`< 3.13`)

---

## Security assumptions

DeviaTDD is a **single-user, local-first CLI**. The threat model
assumes:

- The user controls the working directory and the `git` repository
  the CLI operates on
- The user's shell environment is not hostile
- Agent backends are invoked with credentials the user has chosen to
  provide

Anything that crosses those boundaries (multi-tenant deployments,
untrusted code execution, network-exposed surfaces) is **not** part of
the supported threat model. If you need that, run the CLI inside a
sandbox you control.

---

## Past advisories

None to date. As advisories are published they will be linked here.

---

## Acknowledgements

We are grateful to the security community for responsible disclosure.
Reporters (with their permission) will be listed in release notes and
the project README's acknowledgements section once a fix ships.
