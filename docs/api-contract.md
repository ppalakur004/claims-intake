# Claims Intake Service: API Contract

Version 0.4. Owned by the claims intake team. Consumed by the claims portal team.

This document is the authority on what the service accepts, what it returns, and under what conditions it refuses. Where the code and this document disagree, the document is correct and the code is a defect.

Sections 1 through 3 are fixed. Do not edit them.

## 1. Purpose and scope

The claims intake service accepts a first notice of loss from the claims portal, validates it against the policy master and a table of business rules, and either records a notification and issues a claim reference or refuses the submission with a specific reason.

**In scope.** Accepting a notification, validating it, and recording it. Issuing a claim reference. Reporting the reason a notification was refused.

**Out of scope.** Adjusting, reserving, payment, and any decision about coverage beyond the rules in section 4. The service decides whether a notification is well formed and admissible. It does not decide whether the claim will be paid.

**The policy master is a dependency, not part of this service.** The service reads policy records from it and does not write to it. A policy that cannot be read is a condition this contract specifies, and it is specified separately from a policy that does not exist, because the two require different action from the caller.

**Compatibility.** Adding a field to a response is a compatible change and callers must ignore fields they do not recognize. Adding a new error code is a compatible change and callers must fall through to default handling for a code they do not recognize. Changing the meaning of an existing code, removing a field, or changing a status code for an existing condition is not compatible and does not happen without a version increment agreed with the portal team.

## 2. Request

### 2.1 Endpoint

```
POST /notifications
Content-Type: application/json
```

### 2.2 Body

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `policy_number` | string | yes | Identifier as held in the policy master. Case-sensitive. Not empty. |
| `loss_date` | string | yes | Calendar date, `YYYY-MM-DD`. |
| `claim_type` | string | yes | One of the values in 2.3. Case-sensitive. Not empty. |
| `estimated_amount` | decimal | yes | United States dollars, exactly two decimal places. Greater than zero. |
| `description` | string | no | Free text. Absent and `null` are equivalent. |

The service rejects a body carrying a field not listed above. A misspelled field name is a defect in the caller's code, and accepting the payload with the field ignored would record a notification built from data the caller did not send.

### 2.3 Claim type vocabulary

`collision`, `theft`, `glass`, `liability`, `weather`.

Which of these are admissible on a given notification depends on the product the policy is written on. The vocabulary is fixed by this contract. The permitted subset is a property of the policy record and is evaluated by rule `V-5`.

### 2.4 Well formed against acceptable

A request that cannot be interpreted is refused with status `400`. This means the body was not valid JSON, a required field was absent, a field carried a value of the wrong type, or a field was present that this contract does not define. The caller's code is wrong.

A request that was interpreted and whose content is not admissible is refused with status `422`. The caller's data is wrong, and a person needs to see the reason.

This split is stated here once and holds without exception everywhere else in this document.

## 3. Success response

A notification that passes every rule in section 4 is recorded and the service responds:

```
201 Created
Content-Type: application/json

{
  "claim_reference": "CLM-2026-000317",
  "status": "recorded"
}
```

**`claim_reference`** matches the pattern `CLM-YYYY-NNNNNN`, where `YYYY` is the calendar year in which the notification was recorded and `NNNNNN` is a zero padded sequence. A claim reference is unique across all recorded notifications and is never reissued. It is the value the claims handler quotes and the value every downstream system keys on.

**`status`** is `recorded` on every success response this contract defines. It exists because the portal displays it and because a future state that is not `recorded` is foreseeable. Callers must not treat it as constant.

A refused notification is never recorded and no claim reference is issued. There is no partial outcome: either a notification exists with a reference, or nothing was written.

## 4. Validation

### 4.1 Evaluation order

Evaluation order: **V-1, V-2, V-7, V-3, V-4, V-5, V-6**. Stops at first failure.

V-1 short-circuits if policy not found. V-7 runs before V-3 so cancelled policies return POLICY_CANCELLED even if also expired (WI-0158 AC-4).

### 4.2 Rule table

| ID  | Condition                                      | Code                    | Status |
| --- | ---------------------------------------------- | ----------------------- | ------ |
| V-1 | `policy_number` exists in the policy master    | `POLICY_NOT_FOUND`      | 422    |
| V-2 | `loss_date` >= policy `effective_date`         | `LOSS_BEFORE_INCEPTION` | 422    |
| V-7 | If policy `cancellation_date` is not null, `loss_date` < `cancellation_date` | `POLICY_CANCELLED` | 422 |
| V-3 | `loss_date` <= policy `expiry_date`            | `LOSS_AFTER_EXPIRY`     | 422    |
| V-4 | `estimated_amount` <= policy `limit`           | `AMOUNT_EXCEEDS_LIMIT`  | 422    |
| V-5 | `claim_type` in policy `permitted_claim_types` | `TYPE_NOT_COVERED`      | 422    |
| V-6 | No existing recorded notification with same `policy_number`, `loss_date`, and `claim_type` | `DUPLICATE_NOTIFICATION` | 409 |

Boundaries are inclusive unless the operator is strict inequality. A loss on inception is covered. A loss on cancellation is not covered. A loss on expiry is covered. An amount equal to the limit is within cover.

## 5. Error envelope

All error responses use this JSON structure:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "detail": {}
  }
}
```

The envelope field names, `error.code`, and the status mapped in section 6 are stable contract promises. Callers may branch on `code`. `message` is not stable; it is display text and may change without a contract version change. `detail` is always an object, but its contents depend on `code`. Callers may rely on the documented keys for a code and must ignore extra keys.

Minimum stable `detail` keys:

| Code | Stable detail keys |
| --- | --- |
| `INVALID_REQUEST` | `field`, `reason` when a single field caused the failure; otherwise `reason` |
| `POLICY_NOT_FOUND` | `policy_number` |
| `LOSS_BEFORE_INCEPTION` | `policy_number`, `loss_date`, `effective_date` |
| `POLICY_CANCELLED` | `policy_number`, `loss_date`, `cancellation_date` |
| `LOSS_AFTER_EXPIRY` | `policy_number`, `loss_date`, `expiry_date` |
| `AMOUNT_EXCEEDS_LIMIT` | `policy_number`, `estimated_amount`, `limit` |
| `TYPE_NOT_COVERED` | `policy_number`, `claim_type`, `permitted_claim_types` |
| `DUPLICATE_NOTIFICATION` | `policy_number`, `loss_date`, `claim_type`, `existing_claim_reference` |
| `POLICY_MASTER_BAD_RESPONSE` | `policy_number`, `dependency`, `reason` |
| `POLICY_MASTER_UNAVAILABLE` | `policy_number`, `dependency`, `reason` |
| `POLICY_MASTER_TIMEOUT` | `policy_number`, `dependency`, `reason` |

For policy master dependency failures, `dependency` is `policy_master`. `reason` is `unparsable`, `unreachable`, or `timeout`.

Rule failure example:

```json
{
  "error": {
    "code": "DUPLICATE_NOTIFICATION",
    "message": "A notification has already been recorded for this loss event.",
    "detail": {
      "policy_number": "MOT-4471",
      "loss_date": "2026-04-06",
      "claim_type": "collision",
      "existing_claim_reference": "CLM-2026-000317"
    }
  }
}
```

Uninterpretable request example:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The request body could not be interpreted.",
    "detail": {
      "field": "estimated_amount",
      "reason": "required"
    }
  }
}
```

Policy master failure example:

```json
{
  "error": {
    "code": "POLICY_MASTER_TIMEOUT",
    "message": "The policy master did not answer in time.",
    "detail": {
      "policy_number": "MOT-4471",
      "dependency": "policy_master",
      "reason": "timeout"
    }
  }
}
```

## 6. Status code mapping

| Code | Status | Condition |
| --- | --- | --- |
| `INVALID_REQUEST` | 400 | The request cannot be interpreted: invalid JSON, missing required field, undefined field, wrong type or format, `claim_type` outside the vocabulary, or `estimated_amount` not greater than zero with exactly two decimal places. |
| `DUPLICATE_NOTIFICATION` | 409 | V-6 failed because a matching recorded notification already exists. |
| `POLICY_NOT_FOUND` | 422 | The policy master answered with no matching policy. |
| `LOSS_BEFORE_INCEPTION` | 422 | V-2 failed. |
| `POLICY_CANCELLED` | 422 | V-7 failed. |
| `LOSS_AFTER_EXPIRY` | 422 | V-3 failed. |
| `AMOUNT_EXCEEDS_LIMIT` | 422 | V-4 failed. |
| `TYPE_NOT_COVERED` | 422 | V-5 failed. |
| `POLICY_MASTER_BAD_RESPONSE` | 502 | The policy master answered, but the service could not parse the response. |
| `POLICY_MASTER_UNAVAILABLE` | 503 | The policy master was unreachable. |
| `POLICY_MASTER_TIMEOUT` | 504 | The policy master did not answer before the service timeout. |
