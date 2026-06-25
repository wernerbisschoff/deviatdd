# Release: Product Layer

## Goal
- Solves the problem of having too large epics
- Solves the problem of initial high level context getting lost the farther downstream you go

## Constraints
- Minimal cli implementation. Keep it agent-centric

## Included Flows
| Flow ID | Name | Notes |
|---|---|---|
| FLOW-01 | Flows | Cornerstone of the product layer |
| FLOW-02 | Architecture | Defines integration patterns and main components |
| FLOW-03 | Release | Serves as guiding star for epics | 

## Included Work
| Title | Type | Flow Refs | Status |
|---|---|---|
| Product Layer | ADHOC |  [FLOW-01, FLOW-02, FLOW-03] | planned |

## Deferred Epics
N/A

## Acceptance Criteria
- `deviate setup` will create new /deviate-flows, /deviate-architecture, and /deviate-release skills
