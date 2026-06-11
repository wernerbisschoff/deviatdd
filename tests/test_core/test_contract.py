from __future__ import annotations

from pathlib import Path

from deviate.core.contract import emit_contract, load_contract


class TestContractRoundTrip:
    def test_contract_round_trip_preserves_keys(self, tmp_path: Path):
        data = {
            "issue_id": "ISS-001-001",
            "branch_name": "feat/test-branch",
            "spec_target": "specs/001/test/spec.md",
            "prd_requirements": ["FR-001", "FR-002"],
        }
        path = emit_contract(data, output_dir=tmp_path)
        loaded = load_contract(path)
        assert loaded == data

    def test_contract_round_trip_nested_dict(self, tmp_path: Path):
        data = {
            "issue_id": "ISS-001-002",
            "metadata": {
                "priority": "high",
                "labels": ["core", "cli"],
            },
        }
        path = emit_contract(data, output_dir=tmp_path)
        loaded = load_contract(path)
        assert loaded == data

    def test_contract_round_trip_empty_dict(self, tmp_path: Path):
        data: dict = {}
        path = emit_contract(data, output_dir=tmp_path)
        loaded = load_contract(path)
        assert loaded == {}
