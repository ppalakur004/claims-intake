# Payload Triage

Every payload in `data/fnol_edge.json` classified against `docs/api-contract.md` as you have completed it. The classification records what the contract says the service does, which is not always what the payload obviously violates.

Fill one row per payload. Where a payload is accepted, leave the rule, code, and status columns as `-`.

## Classification

| Payload | Outcome | Rule | Code | Status |
| --- | --- | --- | --- | --- |
| EDGE-01 | Accepted | - | - | - |
| EDGE-02 | Accepted | - | - | - |
| EDGE-03 | Accepted | - | - | - |
| EDGE-04 | Rejected | V-7 | POLICY_CANCELLED | 422 |
| EDGE-05 | Rejected | V-2 | LOSS_BEFORE_INCEPTION | 422 |
| EDGE-06 | Rejected | V-4 | AMOUNT_EXCEEDS_LIMIT | 422 |
| EDGE-07 | Rejected | V-1 | POLICY_NOT_FOUND | 422 |
| EDGE-08 | Rejected | - | INVALID_REQUEST | 400 |
| EDGE-09 | Rejected | V-5 | TYPE_NOT_COVERED | 422 |
| EDGE-10 | Rejected | V-7 | POLICY_CANCELLED | 422 |
| EDGE-11 | Rejected | - | INVALID_REQUEST | 400 |
| EDGE-12 | Rejected | - | INVALID_REQUEST | 400 |

## Decision log

Three payloads cannot be classified against the contract as it shipped, because the contract left a decision unmade. For each one, record the ambiguity, the decision, its authority, and the alternative you rejected.

A decision recorded here and nowhere else has not been made. Amend `docs/api-contract.md` so that a reader of the contract alone could not arrive at the other reading.

### Decision 1

**Payload.** EDGE-07

**The ambiguity.** Contract did not state if `policy_number` matching is case-sensitive. EDGE-07 has "mot-4471" vs "MOT-4471" in master.

**Decision.** Case-sensitive matching. "mot-4471" does not match. Rejected with POLICY_NOT_FOUND.

**Authority.** Section 2.2: "as held in the policy master" means exact match.

**Rejected alternative.** Case-insensitive would contradict "as held" and mismatch submitted vs recorded data.

**Contract amended.** Section 2.2, `policy_number`: added "Case-sensitive".

### Decision 2

**Payload.** EDGE-11

**The ambiguity.** Unknown `claim_type` "flood" - is it 400 (malformed) or 422 (validation)?

**Decision.** 400 INVALID_REQUEST. Vocabulary is part of API contract.

**Authority.** Section 2.4: "cannot be interpreted" is 400. Service cannot interpret undefined types.

**Rejected alternative.** 422 implies service understood but policy doesn't cover it. Wrong - service can't evaluate undefined types.

**Contract amended.** Section 2.2, `claim_type`: added "Case-sensitive". Section 6: added vocabulary violation row.

### Decision 3

**Payload.** EDGE-12

**The ambiguity.** "3499.999" has three decimals. Reject or round to two?

**Decision.** Reject with 400 INVALID_REQUEST. No rounding.

**Authority.** Section 2.2 amended to "exactly two decimal places". Wrong type is 400.

**Rejected alternative.** Rounding would record $3500.00 when caller sent $3499.999 - data mismatch.

**Contract amended.** Section 2.2, `estimated_amount`: "exactly two". Section 6: added precision row.

## Day 2 reconciliation note
The Day 2 models were checked against `docs/api-contract.md` section 6 after implementing the request boundary. `NotificationRequest` can reject invalid JSON-equivalent shape problems: missing required fields, unknown fields, wrong types or formats, claim types outside the section 2.3 vocabulary, non-positive amounts, and amounts without exactly two decimal places. Those all map to the existing `INVALID_REQUEST` code with status `400`, so no new contract code was added. `Policy`, `RuleFailure`, and recorded claim model failures are internal construction errors and do not add caller-facing response codes.
