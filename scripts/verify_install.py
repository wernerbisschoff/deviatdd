from __future__ import annotations

from deviate.core.agent import (
    MAX_PROMPT_CHARS,
    STREAM_STALL_TIMEOUT_SECONDS,
    AgentBackend,
)


def main() -> None:
    assert MAX_PROMPT_CHARS == 80_000
    assert 0 < STREAM_STALL_TIMEOUT_SECONDS <= 120

    recovered = AgentBackend.parse_output("task_id: TSK-INSTALL-CHECK\n", "pi")
    assert recovered.phase == "UNKNOWN"
    assert recovered.status == "UNKNOWN"
    assert recovered.parse_errors
    assert not recovered.is_success

    escaped_quote_hint = AgentBackend._yaml_error_hint(
        '```yaml\nphase: "JUDGE"\nstatus: "PASS"\ndetail: "x == \\"y\\""\n```'
    )
    assert "Avoid backslash-escaped quotes" in escaped_quote_hint

    print("INSTALL_VERIFIED")


if __name__ == "__main__":
    main()
