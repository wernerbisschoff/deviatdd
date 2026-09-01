"""Minimal PRD that satisfies ``validate_macro_contract(..., "prd")``.

Shard ``pre`` fail-closes on stub ``# PRD`` files. Tests that invoke
shard pre with a seeded ``prd.md`` must write this body so the
required ``##`` sections and an ``AO-NNN`` token are present. Do not
weaken the validator to make stubs pass.
"""

MINIMAL_VALID_PRD = """# PRD

## Document Control and Metadata
Stub.

## System Objectives and Scope Boundary
Stub.

## Architectural Constraints and Prerequisites
Stub.

## Functional Flow and Sequence Architecture
Stub.

## Functional Requirements and Epics
Stub.

## Issue Sharding Strategy
Stub.

## Acceptance Outline
- **AO-001**: Valid input succeeds.

## Ambiguity Resolution and Stakeholder Decisions
Stub.

## Session State
Stub.
"""
