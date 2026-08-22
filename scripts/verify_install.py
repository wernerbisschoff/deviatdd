from __future__ import annotations

from deviate.core.agent import (
    MAX_PROMPT_CHARS,
    STREAM_STALL_TIMEOUT_SECONDS,
    AgentBackend,
    MalformedHandoverManifestError,
)


def main() -> None:
    assert MAX_PROMPT_CHARS == 80_000
    assert STREAM_STALL_TIMEOUT_SECONDS == 900

    try:
        AgentBackend.parse_output("task_id: TSK-INSTALL-CHECK\n", "pi")
        raise AssertionError("bare task_id line should not parse as a manifest")
    except MalformedHandoverManifestError as exc:
        assert "No YAML handover manifest" in str(exc)

    escaped_quote_hint = AgentBackend._yaml_error_hint(
        '```yaml\nphase: "JUDGE"\nstatus: "PASS"\ndetail: "x == \\"y\\""\n```'
    )
    assert "Avoid backslash-escaped quotes" in escaped_quote_hint

    recovered = AgentBackend.parse_output(
        "```yaml\nphase: RED\nstatus: PASS\ntask_id: TSK-INSTALL-CHECK\n```\n",
        "pi",
    )
    assert recovered.phase == "RED"
    assert recovered.status == "PASS"
    assert recovered.is_success

    print("INSTALL_VERIFIED")


if __name__ == "__main__":
    main()
