# Sibling Flow Inventory (fixture)

Nearest existing user flow for a parallel crypto-withdrawal path.
Facts only. Quoted paths. No recommendations.

| Dimension | Observed fact | Path |
| :--- | :--- | :--- |
| Sibling flow | `payout_request` claim + Lightning in-request pay | `src/wallet/services/payout_request.py` |
| Amount vs fee | FLOW-01 charges **amount + fee** as separate fields | `src/wallet/models/payout.py` |
| Lock vs reserve | reserve → consume / release (not a row lock) | `src/wallet/services/ledger.py` |
| Vendor call | vendor create runs in a **job**, not the HTTP request | `src/wallet/jobs/payout_dispatch.py` |
| Idempotency | one vendor create / no auto-resubmit | `src/wallet/jobs/payout_dispatch.py` |
| Destination shape | typed destination snapshot (not generic JSONB) | `src/wallet/models/destination.py` |
| Claim | `skip_locked` claim on `payout_request` | `src/wallet/jobs/payout_claim.py` |
