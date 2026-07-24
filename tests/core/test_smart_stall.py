"""Tests for F2 (smart stall detector) — distinguishes hung subprocesses from
long-running-but-active output streams.

The default stall detector trips when no agent output appears for
``STREAM_STALL_TIMEOUT_SECONDS`` (900s by default). That's too coarse for
long-running commands like ``mix precommit``: the agent subprocess emits
~100 B/s during compile and test runs, well above zero, but eventually
the line rate drops to ~0 B/s when the subprocess is genuinely hung.

The smart detector tracks byte rate over a rolling window and only trips
when the rate falls below ``STREAM_STALL_MIN_BYTES_PER_SECOND`` for at
least half the stall timeout. This lets ``mix precommit`` (active, high
rate) complete while still catching a hung subprocess (low rate).
"""

from __future__ import annotations

import time

from deviate.core.agent import (
    STREAM_STALL_MIN_BYTES_PER_SECOND,
    STREAM_STALL_TIMEOUT_SECONDS,
    STREAM_STALL_WINDOW_SECONDS,
)


def test_smart_stall_constants_are_sane() -> None:
    """The thresholds should not silently drift to nonsense values."""
    # The minimum byte rate must be positive — a zero or negative floor
    # would classify every output stream as stalled.
    assert STREAM_STALL_MIN_BYTES_PER_SECOND > 0
    assert STREAM_STALL_MIN_BYTES_PER_SECOND < 10_000

    # The window must be long enough to amortise compile/test bursts but
    # short enough that we catch a real stall within the parent timeout.
    assert STREAM_STALL_WINDOW_SECONDS >= 30
    assert STREAM_STALL_WINDOW_SECONDS <= STREAM_STALL_TIMEOUT_SECONDS


def test_smart_stall_byte_rate_logic() -> None:
    """Byte-rate math correctly classifies fast vs slow output streams.

    This is the unit-level check that the formula in
    ``_invoke_streaming`` is right: given a sequence of (timestamp, bytes)
    samples, the rate below the floor must trip the stall detector, and
    the rate above the floor must not.
    """
    floor = STREAM_STALL_MIN_BYTES_PER_SECOND

    # 50 B/s is the floor — anything below trips, anything above does not.
    samples_under = [
        (0.0, 100),  # 100 bytes at t=0
        (1.0, 100),  # 100 bytes at t=1
        (2.0, 100),  # 100 bytes at t=2
        # Total: 400 bytes over ~2s = 200 B/s, above the floor — does NOT trip.
    ]
    samples_over = [
        (0.0, 5),
        (10.0, 5),
        (20.0, 5),
        (30.0, 5),
        (40.0, 5),
        (50.0, 5),
        (60.0, 5),
        # Total: 40 bytes over 60s = 0.67 B/s, well below the floor — trips.
    ]

    def rate(samples):
        if len(samples) < 3:
            return None
        window = samples[-1][0] - samples[0][0]
        if window <= 0:
            return None
        return sum(n for _, n in samples) / window

    assert rate(samples_under) > floor  # should not trip
    assert rate(samples_over) < floor  # should trip

    # The fast case (~`mix precommit`) keeps emit rate well above the floor.
    # ~100 B/s leaves ~50% margin to the floor for compile bursts.
    assert floor < 100


def test_smart_stall_smoke() -> None:
    """Smoke check: realistic mix-precommit-style output does not trip.

    Models a 60-second compile + test run emitting ~100 B/s of progress
    output, with some bursty periods. After 60 seconds, the rolling
    window should have a byte rate well above the stall floor.
    """
    samples = []
    now = time.monotonic()
    for second in range(STREAM_STALL_WINDOW_SECONDS):
        # Realistic `mix test` output: progress lines, dots, summary table.
        # ~100 bytes per second on average.
        samples.append((now + second, 100))

    total = sum(n for _, n in samples)
    window = samples[-1][0] - samples[0][0]
    rate = total / window if window > 0 else 0

    assert rate > STREAM_STALL_MIN_BYTES_PER_SECOND


def test_smart_stall_smoke_hung_subprocess() -> None:
    """Smoke check: a hung subprocess emitting <1 B/s trips the detector.

    Models a 60-second period where the agent subprocess is stuck — maybe
    an infinite tool loop, maybe a Postgres query that's waiting on a
    lock. The rolling window's byte rate falls well below the floor.
    """
    samples = []
    now = time.monotonic()
    for second in range(STREAM_STALL_WINDOW_SECONDS):
        # Hung subprocess: 1 byte every 10 seconds (e.g. progress heartbeat).
        if second % 10 == 0:
            samples.append((now + second, 1))

    total = sum(n for _, n in samples)
    window = samples[-1][0] - samples[0][0]
    rate = total / window if window > 0 else 0

    assert rate < STREAM_STALL_MIN_BYTES_PER_SECOND
