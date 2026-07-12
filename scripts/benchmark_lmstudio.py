#!/usr/bin/env python3
"""Benchmark every chat model exposed by LM Studio across the DeviaTDD micro cycle.

For each chat model discovered on ``/v1/models`` (embeddings/clip/whisper are
skipped), the script renders the real auto-templates from
``src/deviate/prompts/auto/{red,green,judge,refactor}.md`` via
``deviate.prompts.assembly.assemble_prompt`` — so the measured payloads are
defensibly tied to what ``deviate micro red|green|judge|refactor`` actually
sends — and fires one ``POST /v1/chat/completions`` per (phase, mode,
reasoning, n_ctx, round). Timing comes from the streaming SSE timeline:

    ttft_ms     = perf_counter(open) → first chunk arrival
    decode_ms   = first chunk arrival → last chunk arrival
    total_ms    = perf_counter(open) → close

The final SSE chunk carries ``usage`` with ``prompt_tokens``,
``completion_tokens`` (includes any reasoning tokens), and
``reasoning_tokens``. We do **not** rely on LM Studio's older ``timings``
block — chat-completions requests don't populate it consistently on every
build, and conflating ``decode_ms = total_ms`` was a real bug in the prior
version. The streaming split is the source of truth.

Cache behaviour is controlled explicitly:

- ``--cache-mode cold`` (matches the real micro layer): every call rebuilds
  the prompt text so the prompt-cache key differs per call.
- ``--cache-mode warm``: round 0 rebuilds; rounds 1..N reuse the *exact
  same* rendered prompt for the system message. The user message carries a
  per-round suffix so user-turn work varies (mirrors "user keeps asking
  follow-ups in the same session") while the system prefix — the part the
  cache amortises — stays byte-identical for clean cache hits.
- ``--cache-mode both`` (default) runs both and reports side by side.

Reasoning levels (``off | low | medium | high | on``): unsupported levels
per model are read from ``/api/v1/models`` ``capabilities.reasoning``
rather than a runtime probe.

Context lengths: the default sweep is ``[16384, 65536]`` (set by
``DEFAULT_CONTEXT_LENGTHS``). Pass ``--context-lengths 16384 32768 65536``
to widen to three windows. The model is reloaded between windows so the
KV cache is reset and host memory never holds more than one model at
one n_ctx. ``--context-length N`` (default 16384) is the single-value
override that loses to ``--context-lengths`` when both are passed.

Stdlib-only on purpose.

Usage:

    mise run bench-lmstudio                                       # all defaults
    mise run bench-lmstudio -- --list                             # preview
    mise run bench-lmstudio -- --cache-mode cold                  # skip warm
    mise run bench-lmstudio -- --reasoning off high               # subset
    mise run bench-lmstudio -- --context-lengths 16384 32768      # custom sweep
    mise run bench-lmstudio -- --endpoint http://host:1234/v1
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import math
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parent.parent
PHASE_KEYS: tuple[str, ...] = ("red", "green", "judge", "refactor")
CACHE_MODES: tuple[str, ...] = ("cold", "warm")
REASONING_LEVELS: tuple[str, ...] = ("off", "low", "medium", "high", "on")
# Default context-length sweep when neither ``--context-length`` nor
# ``--context-lengths`` is set. The two endpoints bracket the
# practical range: 16K clears the JUDGE auto-template cliff (~7.3K
# tokens) with comfortable headroom for warm-cache prefix growth;
# 64K is the upper bound on every chat model in the box (verified
# live). Pass ``--context-lengths 16384 32768 65536`` to widen.
DEFAULT_CONTEXT_LENGTHS: tuple[int, ...] = (16384, 65536)

CHAT_MODEL_NAME_RE = re.compile(r"^(?!text-embedding-|clip|whisper)", re.IGNORECASE)
SIZE_TAG_RE = re.compile(r"(\d+(?:\.\d+)?)b", re.IGNORECASE)
QUANT_TAG_RE = re.compile(r"[-_](q\d+(_mldl)?(?:-[a-z0-9]+)?)(?=\W|$)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Phase payloads (synthetic fixtures so the auto-templates get realistic input)
# ---------------------------------------------------------------------------

SYNTHETIC_TASK = {
    "id": "TSK-BENCH-01",
    "issue_id": "ISS-BENCH-01",
    "description": (
        "Implement `normalize_slug(text: str) -> str` that lowercases, strips "
        "punctuation, and collapses whitespace to single hyphens."
    ),
    "execution_mode": "TDD",
    "verification": "pytest tests/test_slug.py -q",
    "verification_command": "pytest tests/test_slug.py -q",
    "verification_binary": "pytest tests/test_slug.py -q",
    "lint_command": "ruff check .",
    "test_command": "pytest tests/test_slug.py -q",
    "feature_slug": "bench-fixture",
    "issue_slug": "ISS-BENCH-01",
}

SYNTHETIC_SPEC = """\
# FR-1: Slug normalization

A slug is the canonical, filesystem-safe form of a free-text label.

## AC-1.1 — Lowercasing
Given any input, the output SHALL be lowercase: ASCII A-Z map to a-z.

## AC-1.2 — Punctuation stripping
All non-alphanumeric characters are removed except for internal whitespace.

## AC-1.3 — Whitespace collapse
Runs of whitespace collapse to a single ASCII hyphen (``-``).

## AC-1.4 — Empty input
An all-whitespace or all-punctuation input returns an empty string.
"""

SYNTHETIC_DATA_MODEL = "n/a (pure function)"
SYNTHETIC_PRD = "Reference benchmark fixture; no PRD."

PHASE_CONTEXT: dict[str, dict[str, str]] = {
    phase: {
        "task_content": json.dumps(SYNTHETIC_TASK, indent=2),
        "spec_content": SYNTHETIC_SPEC,
        "data_model_content": SYNTHETIC_DATA_MODEL,
        "prd_content": SYNTHETIC_PRD,
        "task_id": SYNTHETIC_TASK["id"],
        "issue_id": SYNTHETIC_TASK["issue_id"],
        "feature_slug": SYNTHETIC_TASK["feature_slug"],
        "test_command": SYNTHETIC_TASK["test_command"],
        "lint_command": SYNTHETIC_TASK["lint_command"],
        "verification_command": SYNTHETIC_TASK["verification_command"],
        "verification_binary": SYNTHETIC_TASK["verification_binary"],
        "next_phase": "",
    }
    for phase in PHASE_KEYS
}


# Module-level stash for warm-mode prompt-cache. Keyed on
# (phase, context_length) so a 16K-sweep warm round can't share prefix with
# a 32K-sweep warm round inside the same phase (KV cache is per-context).
_WARM_RENDER_CACHE: dict[tuple[str, int | None], tuple[str, str]] = {}


def _build_phase_messages(
    phase: str,
    constitution_path: Path,
    cache_mode: Literal["cold", "warm"],
    round_idx: int,
    context_length: int | None,
) -> list[dict[str, str]]:
    """Render the micro-layer prompt for *phase*.

    Cold mode: every round rebuilds from scratch (matches the real micro
    layer — each call is a fresh session).

    Warm mode: round 0 rebuilds; rounds 1..N reuse the exact same rendered
    system message. The user message carries a per-round suffix so user-turn
    work varies (mirrors "user keeps asking follow-ups in the same session")
    while the system prefix — the part the prompt-cache amortises — stays
    byte-identical for clean cache hits.
    """
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from deviate.prompts.assembly import assemble_prompt

    warm_key = (phase, context_length)

    if cache_mode == "warm" and round_idx > 0:
        stashed = _WARM_RENDER_CACHE.get(warm_key)
        if stashed is not None:
            reused_system, _ = stashed
            return [
                {"role": "system", "content": reused_system},
                {"role": "user", "content": f"Follow-up #{round_idx}: confirm."},
            ]

    rendered_system = assemble_prompt(
        template_name=phase,
        context=PHASE_CONTEXT[phase],
        constitution_path=constitution_path,
    )
    user_text = f"Execute the {phase.upper()} phase now."

    if cache_mode == "warm":
        _WARM_RENDER_CACHE[warm_key] = (rendered_system, user_text)

    return [
        {"role": "system", "content": rendered_system},
        {"role": "user", "content": user_text},
    ]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _scrub_nans(obj: Any) -> Any:
    """Recursively replace ``float('nan')`` and ``float('inf')`` with
    ``None`` so the JSONL stream stays strictly valid JSON.

    ``json.dumps(..., allow_nan=False)`` raises ``ValueError`` (not
    ``TypeError``) on NaN, so a ``default=`` handler is never invoked
    for it. The only way to get a JSON-spec output is to scrub the
    data first. ``None``-for-missing means consumers don't have to
    handle two flavors of "absent" (``null`` vs literal ``NaN``).
    """
    if isinstance(obj, float):
        return (
            None if (obj != obj or obj == float("inf") or obj == float("-inf")) else obj
        )
    if isinstance(obj, dict):
        return {k: _scrub_nans(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_scrub_nans(v) for v in obj]
    return obj


def _http_get_json(url: str, timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(
    url: str, body: dict[str, Any], timeout: float
) -> tuple[int, dict[str, Any] | str | None]:
    """POST JSON. ``(status, payload_dict_or_raw_text_or_none)``."""
    request_payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=request_payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
            try:
                return (
                    getattr(resp, "status", 200),
                    json.loads(raw) if raw.strip() else {},
                )
            except json.JSONDecodeError:
                return getattr(resp, "status", 200), raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, f"transport: {exc}"


def _http_post_stream_chat(
    url: str, body: dict[str, Any], timeout: float
) -> tuple[
    int,  # HTTP status (0 on transport error)
    dict[str, Any] | None,  # usage block, or None if never observed
    str | None,  # finish_reason (None if no non-usage chunk had one)
    float,  # total_ms across the open + read
    float,  # ttft_ms (open → first SSE chunk), NaN if 0 chunks
    float,  # decode_ms (first chunk → last chunk), NaN if 0 chunks
]:
    """Open a streaming OpenAI-compat chat-completion and time the SSE timeline.

    Each ``data:`` event is one LM Studio stream chunk. Multiple events can
    arrive bundled in one socket read on fast localhost — we drain the
    line buffer each iteration so the usage-only final chunk is never
    silently dropped.

    Timestamps are stamped on socket-chunk arrival (the libssl flush
    boundary), so a single ``data:`` line straddling two reads is parsed
    in full and yet retains ms-level prefill-vs-decode timing.
    """
    request_payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=request_payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)  # noqa: S310
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            err_payload: dict[str, Any] | None = json.loads(raw)
        except json.JSONDecodeError:
            err_payload = None
        elapsed = (time.perf_counter() - started) * 1000.0
        return exc.code, err_payload, None, elapsed, float("nan"), float("nan")
    except (urllib.error.URLError, TimeoutError, OSError):
        return (
            0,
            None,
            None,
            (time.perf_counter() - started) * 1000.0,
            float("nan"),
            float("nan"),
        )

    ttft_ms = float("nan")
    last_chunk_ms = float("nan")
    last_content_chunk_ms: float | None = None
    usage: dict[str, Any] | None = None
    finish_reason: str | None = None
    done = False
    saw_chunk = False
    status = getattr(resp, "status", 200)
    try:
        buf = b""
        while not done:
            try:
                raw = resp.read(65536)
            except (urllib.error.URLError, TimeoutError, OSError):
                break
            if not raw:
                break  # server closed the stream
            buf += raw
            # Drain every complete line in the buffer — critical for the
            # usage-only final chunk which is the LAST event and the most
            # likely to be bundled with prior events on localhost.
            while b"\n" in buf:
                line_bytes, buf = buf.split(b"\n", 1)
                line = line_bytes.decode("utf-8", "replace").rstrip("\r")
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    done = True
                    buf = b""
                    break
                # Per-event timestamp — captured AFTER the [DONE] guard so
                # we only stamp actual content events. When the server
                # bundles all SSE events into one TCP write, these still
                # land within microseconds of each other; ``decode_ms``
                # collapses to ~0 in that case, which we surface as ``—``
                # rather than a fabricated number. The server-truth
                # ``stats.tokens_per_second`` (via /api/v1/chat probe)
                # fills in the actual decode rate.
                event_arrival = (time.perf_counter() - started) * 1000.0
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if not saw_chunk:
                    ttft_ms = event_arrival
                    saw_chunk = True
                is_usage_only = isinstance(event.get("usage"), dict)
                if not is_usage_only:
                    choices = event.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        # Real content carries a non-empty ``content`` or
                        # a tool-call in the delta. Empty deltas (role-only
                        # openers, finish_reason-only chunks) shouldn't
                        # extend the decode span — those arrive after the
                        # model has stopped streaming.
                        if delta.get("content"):
                            last_content_chunk_ms = event_arrival
                        elif choices[0].get("finish_reason"):
                            pass  # finish_reason chunk; don't extend decode span
                        elif not last_content_chunk_ms:
                            # First non-usage event before any content
                            # delta (e.g. role-only opener) — count it as
                            # content so we don't understate decode span.
                            last_content_chunk_ms = event_arrival
                        fr = choices[0].get("finish_reason")
                        if fr:
                            finish_reason = fr
                if is_usage_only:
                    usage = event["usage"]
                # ``last_chunk_ms`` stays as the literal "any event
                # arrival" — useful for debugging; ``decode_ms`` below
                # uses ``last_content_chunk_ms`` only.
                last_chunk_ms = event_arrival
        if saw_chunk:
            decode_ms = max(
                0.0,
                (last_content_chunk_ms or last_chunk_ms) - ttft_ms,
            )
        else:
            decode_ms = float("nan")
    finally:
        with contextlib.suppress(OSError):
            resp.close()

    total_ms = (time.perf_counter() - started) * 1000.0
    return (
        status,
        usage,
        finish_reason,
        total_ms,
        ttft_ms if saw_chunk else float("nan"),
        decode_ms,
    )


def _resolve_api_base(endpoint: str) -> str:
    """Return the API root (``http://host:port``) — strips trailing ``/v1``."""
    base = endpoint.rstrip("/")
    if base.endswith("/v1"):
        return base[:-3]
    return base


# ---------------------------------------------------------------------------
# LM Studio models + capabilities
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, kw_only=True)
class ModelInfo:
    id: str
    owned_by: str = ""
    size_label: str | None = None
    quant_label: str | None = None
    supported_reasoning: tuple[str, ...] = ()
    # Authoritative cap from ``/api/v1/models`` ``max_context_length``.
    # ``None`` when the v1 endpoint didn't report it (older LM Studio
    # builds) or when the model was loaded from the OpenAI-compat
    # endpoint only. The load loop clamps the user-requested
    # ``context_length`` against this so we never ask the host to
    # allocate a window it can't serve.
    max_context_length: int | None = None

    @classmethod
    def from_lmstudio(cls, raw: dict[str, Any]) -> "ModelInfo":
        mid = str(raw.get("id", ""))
        size_match = SIZE_TAG_RE.search(mid)
        quant_match = QUANT_TAG_RE.search(mid)
        return cls(
            id=mid,
            owned_by=str(raw.get("owned_by", "")),
            size_label=f"{size_match.group(1)}B" if size_match else None,
            quant_label=(
                quant_match.group(1).upper().replace("_", "-") if quant_match else None
            ),
        )

    def __str__(self) -> str:
        extras: list[str] = []
        if self.size_label:
            extras.append(self.size_label)
        if self.quant_label:
            extras.append(self.quant_label)
        return f"{self.id} ({' / '.join(extras)})" if extras else self.id


def list_chat_models(endpoint: str, timeout: float) -> list[ModelInfo]:
    payload = _http_get_json(
        _resolve_api_base(endpoint) + "/v1/models", timeout=timeout
    )
    out: list[ModelInfo] = []
    for entry in payload.get("data", []):
        model = ModelInfo.from_lmstudio(entry)
        if not CHAT_MODEL_NAME_RE.match(model.id):
            continue
        if not entry.get("id"):
            continue
        out.append(model)
    out.sort(key=lambda m: m.id)
    return out


def _load_v1_models(endpoint: str, timeout: float) -> list[dict[str, Any]]:
    """Return raw ``models[]`` from the v1 REST API.

    The v1 payload includes each model's authoritative ``capabilities`` —
    including ``capabilities.reasoning.allowed_options`` so we can know
    which reasoning levels each model supports without paying for runtime
    probes — plus ``loaded_instances[]`` for orchestration.
    """
    payload = _http_get_json(
        _resolve_api_base(endpoint) + "/api/v1/models", timeout=timeout
    )
    return list(payload.get("models") or [])


def _reasoning_levels_for(
    v1_entry: dict[str, Any], requested: Iterable[str]
) -> tuple[str, ...]:
    """Return the subset of ``requested`` this model advertises support for.

    Models without a ``capabilities.reasoning`` block fall back to the
    sentinel ``"_none_"`` (caller omits the field entirely, falling back to
    LM Studio's model default).
    """
    caps = v1_entry.get("capabilities") or {}
    r = caps.get("reasoning") or {}
    allowed = tuple(r.get("allowed_options") or ())
    if not allowed:
        return ("_none_",)
    allowed_set = {a.lower() for a in allowed}
    out = tuple(lvl for lvl in requested if lvl.lower() in allowed_set)
    return out or ("_none_",)


def _list_loaded_llm_instances(
    v1_models: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    """Return ``[(model_key, instance_id)]`` for every currently-loaded LLM."""
    out: list[tuple[str, str]] = []
    for m in v1_models:
        if m.get("type") != "llm":
            continue
        for inst in m.get("loaded_instances") or []:
            iid = inst.get("id")
            if iid:
                out.append((str(m.get("key") or m.get("id") or ""), iid))
    return out


def _is_model_loaded(v1_models: list[dict[str, Any]], model_id: str) -> bool:
    return any(
        (m.get("key") == model_id or m.get("id") == model_id)
        and (m.get("loaded_instances") or [])
        for m in v1_models
    )


# ---------------------------------------------------------------------------
# LM Studio load/unload orchestration
# ---------------------------------------------------------------------------


def _unload_instance(endpoint: str, instance_id: str, timeout: float) -> bool:
    """Unload one LLM instance by its ``instance_id`` (no-op if not loaded)."""
    status, payload = _http_post_json(
        _resolve_api_base(endpoint) + "/api/v1/models/unload",
        {"instance_id": instance_id},
        timeout=timeout,
    )
    if status == 200:
        return True
    # ``model_not_found`` just means it wasn't loaded — treat as success.
    if (
        isinstance(payload, dict)
        and payload.get("error", {}).get("type") == "model_not_found"
    ):
        return True
    return False


def _unload_all_llms(endpoint: str, timeout: float) -> int:
    """Evict every currently-loaded LLM instance. Returns count unloaded."""
    v1 = _load_v1_models(endpoint, timeout=timeout)
    unloaded = 0
    for _key, instance_id in _list_loaded_llm_instances(v1):
        if _unload_instance(endpoint, instance_id, timeout=timeout):
            unloaded += 1
    return unloaded


def _coerce_max_context_length(v1_entry: dict[str, Any]) -> int | None:
    """Pull ``max_context_length`` from a ``/api/v1/models`` entry.

    Returns ``None`` if absent or non-numeric — caller treats that as
    "unknown cap" and skips clamping rather than fabricating a number.
    """
    raw = v1_entry.get("max_context_length")
    if isinstance(raw, bool):  # bool is an int subclass in Python
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if isinstance(raw, str) and raw.isdigit():
        v = int(raw)
        return v if v > 0 else None
    return None


def _load_model(
    endpoint: str,
    model_id: str,
    timeout: float,
    context_length: int | None = None,
) -> tuple[bool, float, dict[str, Any] | None]:
    """Force-load a model and wait for ``status: "loaded"``.

    Returns ``(ok, seconds, load_config_or_none)``. ``load_config`` is
    LM Studio's effective configuration (only populated when
    ``echo_load_config=True`` is sent AND the load succeeds).
    """
    started = time.perf_counter()
    body: dict[str, Any] = {"model": model_id, "echo_load_config": True}
    if context_length is not None:
        body["context_length"] = context_length
    status, payload = _http_post_json(
        _resolve_api_base(endpoint) + "/api/v1/models/load",
        body,
        timeout=timeout,
    )
    load_config = payload.get("load_config") if isinstance(payload, dict) else None
    ok = (
        status == 200
        and isinstance(payload, dict)
        and payload.get("status") == "loaded"
    )
    return ok, time.perf_counter() - started, load_config if ok else None


def _probe_v1_chat_stats(
    endpoint: str,
    model_id: str,
    system: str,
    user: str,
    max_tokens: int,
    timeout: float,
) -> dict[str, Any] | None:
    """Fire one non-streaming ``/api/v1/chat`` request and capture the
    server-truth ``stats`` block: ``time_to_first_token_seconds``,
    ``tokens_per_second`` (decode rate), ``input_tokens``, and
    ``total_output_tokens``.

    Returns ``None`` if the request fails for any reason — caller
    surfaces the absence as ``stats_*`` fields being ``None`` rather
    than crashing the bench.

    The probe uses LM Studio's Responses-shaped ``/api/v1/chat``
    endpoint, which is *not* the same as the OpenAI Chat Completions
    endpoint used for the streaming call. Input items take
    ``{"type":"text","content":...}`` (no ``role`` field); ``role``
    is implicit on the streaming-output side. Sending the OpenAI
    Chat-Completions shape (``role`` + ``content``) returns
    ``invalid_request`` from the host.
    """
    url = _resolve_api_base(endpoint) + "/api/v1/chat"
    body = {
        "model": model_id,
        "input": [
            {"type": "text", "content": system},
            {"type": "text", "content": user},
        ],
        "max_output_tokens": max_tokens,
        "temperature": 0,
    }
    request_payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=request_payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
            data = json.loads(raw) if raw.strip() else {}
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
    ):
        return None
    return data.get("stats") if isinstance(data, dict) else None


# Phase results
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, kw_only=True)
class PhaseResult:
    """One (model, phase, mode, reasoning, n_ctx, round) measurement."""

    phase: str
    mode: Literal["cold", "warm"]
    reasoning: str | None
    context_length: int | None  # None = model-default (field omitted)
    round_idx: int
    is_warmup: bool
    total_ms: float
    prefill_ms: float  # NaN if SSE produced zero chunks
    decode_ms: float  # NaN if SSE produced zero or one chunk
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    total_tokens: int
    error: str | None = None
    finish_reason: str | None = None
    http_status: int | None = None
    # Server-truth fields from a parallel /api/v1/chat probe. None if
    # the probe wasn't fired, returned no stats block, or had a non-OK
    # status. These give a real decode rate even when the SSE split
    # collapses to 0 on bundled localhost writes.
    stats_ttft_s: float | None = None
    stats_decode_tok_per_s: float | None = None
    stats_prompt_tokens: int | None = None
    stats_completion_tokens: int | None = None

    @property
    def tokens_per_s_total(self) -> float:
        return (
            self.total_tokens / (self.total_ms / 1000.0)
            if self.total_ms > 0
            else float("nan")
        )

    @property
    def tokens_per_s_decode(self) -> float:
        return (
            self.completion_tokens / (self.decode_ms / 1000.0)
            if self.decode_ms > 0
            else float("nan")
        )

    def to_row_dict(self) -> dict[str, Any]:
        """Flat dict for one JSONL line.

        Includes derived ``tokens_per_s_*`` properties (which
        ``dataclasses.asdict`` skips) so downstream consumers don't
        have to recompute them. NaN/Inf handling is the caller's job
        (``_scrub_nans`` before ``json.dumps``) so direct field
        floats are also covered.
        """
        d = dataclasses.asdict(self)
        for derived in ("tokens_per_s_total", "tokens_per_s_decode"):
            d[derived] = getattr(self, derived)
        return d


@dataclasses.dataclass(kw_only=True)
class PhaseStats:
    samples: list[PhaseResult] = dataclasses.field(default_factory=list)

    def add(self, result: PhaseResult) -> None:
        self.samples.append(result)

    @property
    def counted(self) -> list[PhaseResult]:
        return [s for s in self.samples if not s.is_warmup and s.error is None]

    def median(self, attr: str) -> float:
        vals = [getattr(s, attr) for s in self.counted]
        return statistics.median(vals) if vals else float("nan")


@dataclasses.dataclass(frozen=True, kw_only=True)
class ModelSummary:
    model_id: str
    size_label: str | None
    quant_label: str | None
    supported_reasoning: tuple[str, ...]
    # Authoritative context cap surfaced in the JSON output so the
    # caller can confirm exactly what window each round ran against.
    # ``None`` when ``/api/v1/models`` didn't report it.
    max_context_length: int | None = None


def run_phase_round(
    *,
    endpoint: str,
    model_id: str,
    phase: str,
    mode: Literal["cold", "warm"],
    reasoning: str | None,
    context_length: int | None,
    round_idx: int,
    is_warmup: bool,
    temperature: float,
    max_tokens: int,
    timeout: float,
    constitution_path: Path,
) -> PhaseResult:
    """Time one (phase, mode, reasoning, n_ctx, round) chat completion."""
    messages = _build_phase_messages(
        phase, constitution_path, mode, round_idx, context_length
    )
    # Capture system/user for the parallel /api/v1/chat probe. The probe
    # gets the *same* prompt the streaming call sent so its stats block
    # is comparable — that's the whole point of the two-endpoint split.
    probe_system = messages[0]["content"] if messages else ""
    probe_user = messages[1]["content"] if len(messages) > 1 else ""
    body: dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        # Streaming SSE so we can split prefill (TTFT) from decode span.
        # The final chunk carries the ``usage`` block — completion_tokens
        # includes any reasoning_tokens per LM Studio's contract.
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if reasoning is not None:
        body["reasoning"] = reasoning

    url = endpoint.rstrip("/") + "/chat/completions"
    status, usage, finish_reason, total_ms, prefill_ms, decode_ms = (
        _http_post_stream_chat(url, body, timeout=timeout)
    )

    if usage is None:
        # Either transport / parse error or server didn't emit a usage
        # chunk. Surface as a failed cell so it's visible in the table
        # rather than silently zero.
        err_label = (
            "transport or no usage chunk"
            if status == 200
            else f"HTTP {status}: no usage"
        )
    # Server-truth probe. Fires regardless of streaming outcome: if the
    # streaming call failed we still want the probe's verdict so the
    # stats_* fields tell us whether the model itself is healthy.
    stats = _probe_v1_chat_stats(
        endpoint=endpoint,
        model_id=model_id,
        system=probe_system,
        user=probe_user,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    stats_ttft_s: float | None = None
    stats_decode_tok_per_s: float | None = None
    stats_prompt_tokens: int | None = None
    stats_completion_tokens: int | None = None
    if isinstance(stats, dict):
        v = stats.get("time_to_first_token_seconds")
        if isinstance(v, (int, float)) and v >= 0:
            stats_ttft_s = float(v)
        v = stats.get("tokens_per_second")
        if isinstance(v, (int, float)) and v >= 0:
            stats_decode_tok_per_s = float(v)
        v = stats.get("input_tokens")
        if isinstance(v, (int, float)) and v >= 0:
            stats_prompt_tokens = int(v)
        v = stats.get("total_output_tokens")
        if isinstance(v, (int, float)) and v >= 0:
            stats_completion_tokens = int(v)

    if usage is None:
        # Either transport / parse error or server didn't emit a usage
        # chunk. Surface as a failed cell so it's visible in the table
        # rather than silently zero.
        err_label = (
            "transport or no usage chunk"
            if status == 200
            else f"HTTP {status}: no usage"
        )
        return PhaseResult(
            phase=phase,
            mode=mode,
            reasoning=reasoning,
            context_length=context_length,
            round_idx=round_idx,
            is_warmup=is_warmup,
            total_ms=total_ms,
            prefill_ms=prefill_ms,
            decode_ms=decode_ms,
            prompt_tokens=0,
            completion_tokens=0,
            reasoning_tokens=0,
            total_tokens=0,
            error=err_label,
            http_status=status,
            stats_ttft_s=stats_ttft_s,
            stats_decode_tok_per_s=stats_decode_tok_per_s,
            stats_prompt_tokens=stats_prompt_tokens,
            stats_completion_tokens=stats_completion_tokens,
        )

    pt = int(usage.get("prompt_tokens") or 0)
    ct = int(usage.get("completion_tokens") or 0)
    cd = usage.get("completion_tokens_details") or {}
    rt = int(cd.get("reasoning_tokens") or 0) if isinstance(cd, dict) else 0

    # Sanity: decode_ms + prefill_ms + (network slack) should fit inside
    # total_ms. Differences within ~500ms are normal — libssl flush,
    # Python stream buffer, OS scheduling. Anything larger means the SSE
    # clock is off; demote to NaN so the table shows blanks rather than
    # meaningless numbers.
    if (
        not math.isnan(prefill_ms)
        and not math.isnan(decode_ms)
        and (prefill_ms + decode_ms) > total_ms + 500
    ):
        decode_ms = float("nan")
        prefill_ms = float("nan")

    return PhaseResult(
        phase=phase,
        mode=mode,
        reasoning=reasoning,
        context_length=context_length,
        round_idx=round_idx,
        is_warmup=is_warmup,
        total_ms=total_ms,
        prefill_ms=prefill_ms,
        decode_ms=decode_ms,
        prompt_tokens=pt,
        completion_tokens=ct,
        reasoning_tokens=rt,
        total_tokens=int(usage.get("total_tokens") or (pt + ct)),
        finish_reason=finish_reason,
        http_status=status,
        stats_ttft_s=stats_ttft_s,
        stats_decode_tok_per_s=stats_decode_tok_per_s,
        stats_prompt_tokens=stats_prompt_tokens,
        stats_completion_tokens=stats_completion_tokens,
    )


# ---------------------------------------------------------------------------
# CLI / table rendering
# ---------------------------------------------------------------------------


def _extract_constitution_text() -> str:
    path = REPO_ROOT / "specs" / "constitution.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return (
        "# DeviaTDD Constitution (benchmark stub)\n\n"
        "Prefer boring, deterministic code.\n"
    )


def _write_synthetic_constitution(text: str) -> Path:
    target = REPO_ROOT / ".deviate" / "artifacts" / "benchmark_constitution.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Benchmark LM Studio chat models across the DeviaTDD micro cycle. "
            "Reports total time, prefill time, and tokens-per-second for each "
            "(model, phase, cache mode, reasoning level, context length)."
        ),
    )
    p.add_argument(
        "--endpoint",
        default="http://localhost:1234/v1",
        help="LM Studio OpenAI-compatible base URL (default: %(default)s)",
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="List chat models + supported reasoning levels, then exit",
    )
    p.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="Restrict to these model IDs (default: all chat models)",
    )
    p.add_argument(
        "--phases",
        nargs="*",
        default=list(PHASE_KEYS),
        choices=list(PHASE_KEYS),
        help="Phases to run (default: red green judge refactor)",
    )
    p.add_argument(
        "--cache-mode",
        choices=["cold", "warm", "both"],
        default="both",
        help=(
            "cold: fresh prefix per call (real micro layer). "
            "warm: identical prefix across rounds. "
            "both runs both (default)."
        ),
    )
    p.add_argument(
        "--reasoning",
        nargs="*",
        default=list(REASONING_LEVELS),
        choices=list(REASONING_LEVELS),
        help=(
            "Reasoning levels to benchmark (default: "
            f"{' '.join(REASONING_LEVELS)}). Levels unsupported by a "
            "given model are skipped per-model."
        ),
    )
    p.add_argument(
        "--rounds",
        type=int,
        default=3,
        help=(
            "Rounds per (model, phase, mode, reasoning, n_ctx). The first "
            "round is warmup and excluded from medians (default: %(default)s)"
        ),
    )
    p.add_argument(
        "--no-warmup",
        dest="warmup",
        action="store_false",
        help="Disable warmup round (default: warmup on)",
    )
    p.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature (default: %(default)s)",
    )
    p.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="Per-completion token cap (default: %(default)s)",
    )
    p.add_argument(
        "--load-strategy",
        choices=["single", "manual"],
        default="single",
        help=(
            "single: load only the model under test, unloading any other "
            "LLMs first (one model in memory at a time — safe for "
            "workstations). manual: leave LM Studio's loaded set "
            "untouched (faster but risks OOM on multi-model hosts). "
            "(default: %(default)s)"
        ),
    )
    p.add_argument(
        "--context-length",
        type=int,
        default=None,
        help=(
            "Single pinned context length forwarded to /api/v1/models/load. "
            "Defaults to None, which lets the bench run its "
            "DEFAULT_CONTEXT_LENGTHS sweep ([16384, 65536]). Pass an "
            "explicit value to pin a single window. 0 means 'omit the "
            "field and let LM Studio use each model's native window'. "
            "Ignored when --context-lengths is set."
        ),
    )
    p.add_argument(
        "--load-timeout",
        type=float,
        default=180.0,
        help="HTTP timeout for /api/v1/models/load (default: %(default)s)",
    )
    p.add_argument(
        "--context-lengths",
        type=int,
        nargs="*",
        default=None,
        help=(
            "Sweep over a list of pinned context lengths (e.g. "
            "--context-lengths 16384 32768 65536). The model is reloaded "
            "for each value so the KV-cache / prompt-cache is reset, "
            "preventing host OOM on large contexts. A value of 0 means "
            "'use LM Studio's model default' (no field sent). Mutually "
            "exclusive with --context-length; if both are passed, "
            "--context-lengths wins. Default (when neither is set): the "
            "DEFAULT_CONTEXT_LENGTHS sweep, currently "
            f"{list(DEFAULT_CONTEXT_LENGTHS)}."
        ),
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="HTTP timeout per call, seconds (default: %(default)s)",
    )
    p.add_argument(
        "--inter-call-delay",
        type=float,
        default=0.25,
        help="Sleep between calls, seconds (default: %(default)s)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "Write per-round JSONL output to this path. One line per "
            "completed round, appended incrementally so Ctrl-C / OOM "
            "never loses results. Default: "
            ".deviate/artifacts/benchmark_lmstudio_<ts>.jsonl"
        ),
    )
    p.set_defaults(warmup=True)
    return p.parse_args(argv)


def render_table(
    by_key: dict[tuple[str, str, str, str, int | None], PhaseStats],
    summary_index: dict[str, ModelSummary],
    modes: Iterable[str],
    levels: Iterable[str],
    context_lengths: Iterable[int | None],
) -> str:
    """Plain-text table. Rows keyed by (model, phase, mode, reasoning, n_ctx)."""
    header = [
        "model",
        "size",
        "quant",
        "phase",
        "mode",
        "reasoning",
        "n_ctx",
        "total_ms",
        "prefill_ms",
        "decode_ms",
        "tok/s_total",
        "tok/s_decode",
        "prompt",
        "completion",
        "reasoning_tokens",
        "samples (warmup)",
    ]

    def fmt(v: float) -> str:
        return "—" if (isinstance(v, float) and math.isnan(v)) else f"{v:.1f}"

    def ctx_label(c: int | None) -> str:
        return str(c) if c is not None else "default"

    rows: list[list[str]] = [header]
    for model_id in sorted(summary_index):
        ms = summary_index[model_id]
        for phase in PHASE_KEYS:
            for mode in modes:
                for level in levels:
                    for context_length in context_lengths:
                        key: tuple[str, str, str, str, int | None] = (
                            model_id,
                            phase,
                            mode,
                            level if level != "_none_" else "_",
                            context_length,
                        )
                        stats = by_key.get(key)
                        ctx_str = ctx_label(context_length)
                        base = [
                            model_id,
                            ms.size_label or "",
                            ms.quant_label or "",
                            phase,
                            mode,
                            level,
                            ctx_str,
                        ]
                        if stats is None:
                            rows.append([*base, *["—"] * 8, "0 (0)"])
                            continue
                        counted = stats.counted
                        warmup_total = sum(1 for s in stats.samples if s.is_warmup)
                        if not counted:
                            rows.append([*base, *["—"] * 8, f"0 ({warmup_total})"])
                            continue
                        rows.append(
                            [
                                *base,
                                fmt(stats.median("total_ms")),
                                fmt(stats.median("prefill_ms")),
                                fmt(stats.median("decode_ms")),
                                fmt(stats.median("tokens_per_s_total")),
                                fmt(stats.median("tokens_per_s_decode")),
                                f"{int(statistics.median([s.prompt_tokens for s in counted]))}",
                                f"{int(statistics.median([s.completion_tokens for s in counted]))}",
                                f"{int(statistics.median([s.reasoning_tokens for s in counted]))}",
                                f"{len(counted)} ({warmup_total})",
                            ]
                        )

    widths = [max(len(r[i]) for r in rows) for i in range(len(header))]
    return "\n".join(
        "  ".join(c.ljust(widths[i]) for i, c in enumerate(r)) for r in rows
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run() -> int:
    args = parse_args(None)
    endpoint = args.endpoint
    if not endpoint.rstrip("/").endswith("/v1"):
        endpoint = endpoint.rstrip("/") + "/v1"

    constitution_path = _write_synthetic_constitution(_extract_constitution_text())

    try:
        models_all = list_chat_models(endpoint, timeout=10.0)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(
            f"error: could not reach LM Studio at {endpoint}: {exc}",
            file=sys.stderr,
        )
        return 2

    if args.models:
        wanted = set(args.models)
        models = [m for m in models_all if m.id in wanted]
        missing = wanted - {m.id for m in models}
        if missing:
            print(
                f"error: requested models not present: {sorted(missing)}",
                file=sys.stderr,
            )
            print("use --list to see available chat models", file=sys.stderr)
            return 2
    else:
        models = models_all

    if not models:
        print(
            "error: no chat models available on LM Studio; warm up at least "
            "one and retry",
            file=sys.stderr,
        )
        return 2

    # Pull v1 metadata once: capabilities.reasoning.allowed_options for
    # authoritative per-model reasoning support, and loaded_instances[]
    # for orchestration.
    try:
        v1_models = _load_v1_models(endpoint, timeout=10.0)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"error: could not read /api/v1/models: {exc}", file=sys.stderr)
        return 2

    v1_by_id: dict[str, dict[str, Any]] = {
        (m.get("key") or m.get("id")): m for m in v1_models if m.get("type") == "llm"
    }
    requested_levels: tuple[str, ...] = tuple(args.reasoning) or REASONING_LEVELS
    supported_by_id: dict[str, tuple[str, ...]] = {
        mid: _reasoning_levels_for(entry, requested_levels)
        for mid, entry in v1_by_id.items()
    }

    if args.list:
        print("\nChat models exposed by LM Studio:")
        for m in models:
            v1_entry = v1_by_id.get(m.id, {})
            caps = v1_entry.get("capabilities") or {}
            r = caps.get("reasoning") or {}
            allowed = r.get("allowed_options") or ()
            print(
                f"  - {m}    reasoning: "
                f"{', '.join(allowed) if allowed else '(unspecified — field omitted)'}"
            )
        if args.load_strategy == "single":
            loaded_now = _list_loaded_llm_instances(v1_models)
            print(
                f"\nLoaded LLMs right now: {[iid for _, iid in loaded_now] or '(none)'}"
            )
        print(f"\nEndpoint: {endpoint}")
        return 0

    modes: tuple[str, ...] = (
        CACHE_MODES if args.cache_mode == "both" else (args.cache_mode,)
    )

    # Resolve context-length axis.
    # ``--context-lengths`` is the explicit-sweep flag (may be ``None``
    # when the user didn't pass it). When unset, fall back to the
    # module-level ``DEFAULT_CONTEXT_LENGTHS`` sweep so the bench
    # actually exercises both ends of the practical range instead of
    # a single pinned window. ``--context-length`` is a single-value
    # override used when the user wants a one-off window outside
    if args.context_lengths:
        context_lengths: tuple[int | None, ...] = tuple(
            c or None for c in args.context_lengths
        )
    elif args.context_length is not None:
        # 0 is a meaningful value (means "omit the field") — only None
        # means "user didn't pin a window, fall back to the default sweep".
        context_lengths = (args.context_length or None,)
    else:
        context_lengths = tuple(DEFAULT_CONTEXT_LENGTHS)
    summary_index: dict[str, ModelSummary] = {
        m.id: ModelSummary(
            model_id=m.id,
            size_label=m.size_label,
            quant_label=m.quant_label,
            supported_reasoning=supported_by_id.get(m.id, ()),
            # Join against the v1 REST payload, which is the *only*
            # endpoint that reports ``max_context_length``. The OpenAI
            # compat ``/v1/models`` payload typically omits it. Without
            # this join the auto-cap below would silently no-op.
            max_context_length=_coerce_max_context_length(v1_by_id.get(m.id, {})),
        )
        for m in models
    }
    by_key: dict[tuple[str, str, str, str, int | None], PhaseStats] = {}
    # Per-(model_id, n_ctx) authoritative ``load_config`` returned by
    # ``/api/v1/models/load``. Populated by the helper that owns the
    # load call and surfaced in the JSON output so the caller can
    # verify what window each round actually ran against (especially
    # after the auto-cap clamps a request down).
    load_config_by_key: dict[tuple[str, int | None], dict[str, Any]] = {}

    def key_for(
        model_id: str,
        phase: str,
        mode: str,
        level: str,
        context_length: int | None,
    ) -> tuple[str, str, str, str, int | None]:
        # ``_`` slot means "reasoning field omitted" (model that doesn't
        # support reasoning, or caller asked for no reasoning).
        return (
            model_id,
            phase,
            mode,
            level if level != "_none_" else "_",
            context_length,
        )

    def _ensure_only_this_model_loaded(
        model_id: str, context_length: int | None
    ) -> tuple[bool, str | None]:
        """Evict other LLMs, load *model_id* with the requested n_ctx.

        Returns ``(ok, instance_id)``. If the model is already loaded with
        the right n_ctx, returns ``(True, cached_instance_id)`` without
        reloading. If loaded with the wrong n_ctx, evicts and reloads.
        """
        nonlocal own_loaded_instance_id
        fresh = _load_v1_models(endpoint, timeout=10.0)
        # Unload any LLMs currently loaded that aren't the target.
        for key, iid in _list_loaded_llm_instances(fresh):
            if key != model_id and key != (v1_by_id.get(model_id, {}).get("key")):
                if not _unload_instance(endpoint, iid, timeout=10.0):
                    print(
                        f"  [warn] failed to unload {iid}",
                        file=sys.stderr,
                    )
        # Decide whether the target model needs a (re)load.
        target_key = (model_id, context_length)
        fresh = _load_v1_models(endpoint, timeout=10.0)
        cached = load_config_by_key.get(target_key)
        cached_ctx = cached.get("context_length") if cached else None

        for key, iid in _list_loaded_llm_instances(fresh):
            if key == model_id:
                own_loaded_instance_id = iid
                if cached_ctx == context_length:
                    return True, iid
                # Wrong n_ctx — evict and reload.
                _unload_instance(endpoint, iid, timeout=10.0)
                break

        ctx_label = (
            f"{context_length}" if context_length is not None else "(model default)"
        )
        print(f"  loading {model_id} @ n_ctx={ctx_label}…", flush=True)
        ok, seconds, load_config = _load_model(
            endpoint,
            model_id,
            timeout=args.load_timeout,
            context_length=context_length,
        )
        own_loaded_instance_id = model_id if ok and load_config else None
        if ok:
            load_config_by_key[target_key] = load_config or {
                "context_length": context_length,
                "note": "load OK but no load_config returned",
            }
            # Locate the freshly-loaded instance id.
            fresh = _load_v1_models(endpoint, timeout=10.0)
            for key, iid in _list_loaded_llm_instances(fresh):
                if key == model_id:
                    own_loaded_instance_id = iid
                    return True, iid
            return True, None
        print(
            f"  [warn] load failed after {seconds:.1f}s",
            file=sys.stderr,
        )
        return False, None

    def _evict_self_from_memory() -> None:
        if args.load_strategy != "single" or own_loaded_instance_id is None:
            return
        try:
            fresh = _load_v1_models(endpoint, timeout=10.0)
        except (urllib.error.URLError, TimeoutError, OSError):
            return
        for key, iid in _list_loaded_llm_instances(fresh):
            if iid == own_loaded_instance_id:
                _unload_instance(endpoint, iid, timeout=10.0)
                break

    own_loaded_instance_id: str | None = None

    total_calls = (
        sum(len(supported_by_id.get(m.id, ())) or 1 for m in models)
        * len(args.phases)
        * len(modes)
        * len(context_lengths)
        * max(1, args.rounds)
    )
    print(
        f"Models: {len(models)} · phases: {len(args.phases)} · modes: {modes} "
        f"· rounds: {args.rounds} · context_lengths: "
        f"{[c if c is not None else 'model-default' for c in context_lengths]}"
        f" · reasoning: "
        f"{ {m.id: supported_by_id.get(m.id, ()) for m in models} }"
        f" · total calls: {total_calls}"
    )
    print()

    # JSONL artifact — one line per completed round, appended as we go.
    # Survives Ctrl-C / OOM / SIGTERM mid-run: every completed round
    # is on disk before the next one starts. End-of-run summary is
    # not regenerated separately; consumers read the JSONL stream.
    if args.out is not None:
        jsonl_path = args.out
    else:
        jsonl_path = (
            REPO_ROOT
            / ".deviate"
            / "artifacts"
            / f"benchmark_lmstudio_{int(time.time())}.jsonl"
        )
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_file = open(jsonl_path, "a", encoding="utf-8")
    print(f"Streaming JSONL: {jsonl_path}")
    try:
        for model in models:
            supported = supported_by_id.get(model.id, ())
            levels_for_model: tuple[str, ...] = supported if supported else ("_none_",)

            for context_length in context_lengths:
                # Auto-cap on the model's reported max_context_length.
                # ``None`` means "unknown cap" — pass the request through
                # and let LM Studio reject it if it really can't serve.
                effective_ctx = context_length
                model_cap = summary_index[model.id].max_context_length
                if (
                    effective_ctx is not None
                    and model_cap is not None
                    and effective_ctx > model_cap
                ):
                    print(
                        f"  [warn] {model.id}: requested n_ctx="
                        f"{effective_ctx}, model max={model_cap}, "
                        f"clamping to {model_cap}"
                    )
                    effective_ctx = model_cap

                if args.load_strategy == "single":
                    ok, _iid = _ensure_only_this_model_loaded(model.id, effective_ctx)
                    if not ok:
                        ctx_str = (
                            str(effective_ctx)
                            if effective_ctx is not None
                            else "default"
                        )
                        print(f"== {model} @ n_ctx={ctx_str} == (skipped: load failed)")
                        continue
                else:
                    # Manual mode: trust the user's loaded set; ensure
                    # the target is loaded with a single opportunistic
                    # load (skip if already in memory).
                    fresh = _load_v1_models(endpoint, timeout=10.0)
                    if not _is_model_loaded(fresh, model.id):
                        print(f"  loading {model.id}…", flush=True)
                        _load_model(
                            endpoint,
                            model.id,
                            timeout=args.load_timeout,
                            context_length=effective_ctx,
                        )
                ctx_label = (
                    f"{effective_ctx}"
                    if effective_ctx is not None
                    else "(model default)"
                )
                print(f"== {model} @ n_ctx={ctx_label} ==")

                for phase in args.phases:
                    for mode in modes:
                        # Clear warm-cache between cells so each
                        # (phase, mode, ctx) sees cold→warm on its own
                        # rendered prompt.
                        _WARM_RENDER_CACHE.clear()
                        for level in levels_for_model:
                            body_reasoning = level if level != "_none_" else None
                            label = (
                                f"{phase.upper()} ({mode}, {level}, n_ctx={ctx_label})"
                            )
                            print(f" -- {label} --")
                            for round_idx in range(args.rounds):
                                is_warmup = args.warmup and round_idx == 0
                                result = run_phase_round(
                                    endpoint=endpoint,
                                    model_id=model.id,
                                    phase=phase,
                                    mode=mode,
                                    reasoning=body_reasoning,
                                    context_length=effective_ctx,
                                    round_idx=round_idx,
                                    is_warmup=is_warmup,
                                    temperature=args.temperature,
                                    max_tokens=args.max_tokens,
                                    timeout=args.timeout,
                                    constitution_path=constitution_path,
                                )
                                stats = by_key.setdefault(
                                    key_for(
                                        model.id,
                                        phase,
                                        mode,
                                        level,
                                        context_length,
                                    ),
                                    PhaseStats(),
                                )
                                stats.add(result)
                                # Persist immediately so this round survives
                                # any subsequent failure (Ctrl-C, OOM, network
                                # drop, etc.). ``_scrub_nans`` keeps the line
                                # strictly valid JSON (``NaN`` → ``null``);
                                # ``allow_nan=False`` is the belt-and-suspenders
                                # guard so a future addition can't reintroduce
                                # raw ``NaN`` literals.
                                row = {
                                    "model_id": model.id,
                                    "phase": phase,
                                    "mode": mode,
                                    "level": level,
                                    "context_length_requested": context_length,
                                    "context_length_effective": effective_ctx,
                                    **result.to_row_dict(),
                                }
                                jsonl_file.write(
                                    json.dumps(_scrub_nans(row), allow_nan=False) + "\n"
                                )
                                jsonl_file.flush()
                                if result.error:
                                    extras = f" error={result.error}"
                                else:
                                    decode_str = (
                                        f"{result.decode_ms:.0f}ms"
                                        if not math.isnan(result.decode_ms)
                                        else "—"
                                    )
                                    # Server-truth probe rate — present
                                    # even when SSE split collapsed to 0
                                    # because the host bundled all chunks
                                    # into one TCP write at TTFT.
                                    stats_decode_str = (
                                        f"{result.stats_decode_tok_per_s:.2f}tok/s"
                                        if result.stats_decode_tok_per_s is not None
                                        else "—"
                                    )
                                    stats_ttft_str = (
                                        f"{result.stats_ttft_s:.3f}s"
                                        if result.stats_ttft_s is not None
                                        else "—"
                                    )
                                    extras = (
                                        f" t={result.total_ms:.0f}ms "
                                        f"prefill={result.prefill_ms:.0f}ms "
                                        f"decode={decode_str} "
                                        f"completion={result.completion_tokens}tok "
                                        f"tok/s_total={result.tokens_per_s_total:.2f} "
                                        f"stats_decode={stats_decode_str} "
                                        f"stats_ttft={stats_ttft_str}"
                                    )
                                print(
                                    f"  [{model.id:>34}] "
                                    f"{phase.upper():>7} {mode:>4} "
                                    f"{level:>7} "
                                    f"r{round_idx + 1}/{args.rounds}"
                                    f"{extras}"
                                )
                                if (
                                    round_idx + 1 < args.rounds
                                    and args.inter_call_delay > 0
                                ):
                                    time.sleep(args.inter_call_delay)

                # After each context window in single mode, evict so the
                # next context (or model) starts cold.
                if args.load_strategy == "single":
                    _evict_self_from_memory()
                    own_loaded_instance_id = None
    finally:
        # Always clean up even on Ctrl-C.
        if args.load_strategy == "single":
            _evict_self_from_memory()
        with contextlib.suppress(OSError):
            jsonl_file.close()

    # ---- Render ----
    levels_union: list[str] = []
    seen: set[str] = set()
    for m in models:
        for lv in supported_by_id.get(m.id, ()) or ("_none_",):
            if lv not in seen:
                seen.add(lv)
                levels_union.append(lv)
    if not levels_union:
        levels_union = list(REASONING_LEVELS)

    print()
    print(
        render_table(
            by_key,
            summary_index,
            modes,
            levels_union,
            context_lengths,
        )
    )

    if "cold" in modes and "warm" in modes:
        print()
        print("Cache-help signal (warm / cold tok/s_total, >1 ⇒ cache helped):")
        for model_id, ms in sorted(summary_index.items()):
            supported_levels = ms.supported_reasoning or ("_none_",)
            for context_length in context_lengths:
                ctx_str = (
                    str(context_length) if context_length is not None else "default"
                )
                for phase in args.phases:
                    for level in supported_levels:
                        cold = by_key.get(
                            key_for(
                                model_id,
                                phase,
                                "cold",
                                level,
                                context_length,
                            )
                        )
                        warm = by_key.get(
                            key_for(
                                model_id,
                                phase,
                                "warm",
                                level,
                                context_length,
                            )
                        )
                        if not cold or not warm or not cold.counted or not warm.counted:
                            continue
                        ratio = warm.median("tokens_per_s_total") / cold.median(
                            "tokens_per_s_total"
                        )
                        print(
                            f"  {model_id:>34} {phase.upper():>7}  "
                            f"reasoning={level:>7}  n_ctx={ctx_str:>7}  "
                            f"ratio={ratio:.2f}"
                        )

    # ---- Done ----
    # JSONL was streamed per-round inside the try/finally above; the
    # full summary renders to stdout via ``render_table`` and the
    # cache-help signal. No second pass — downstream tooling reads
    # the JSONL artifact directly.
    print(f"\nJSONL: {jsonl_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
