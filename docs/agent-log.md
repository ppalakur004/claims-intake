# Agent Decision Log

## Accepted: V-7 cancellation rule

**Change.** Added `evaluate_policy_not_cancelled` in `src/claims/service.py`.

The rule rejects a notification when the policy has a `cancellation_date` and
the `loss_date` is on or after that date.

The rule was placed before expiry validation in `POLICY_RULES`.

**Decision.** Accepted.

**Reason.** `docs/api-contract.md` section 4.1 requires `V-7` before `V-3`.

WI-0158 AC-4 says cancellation must win when a policy is both cancelled and
expired.

The test case `v7-before-v3` protects that behavior.

## Corrected: V-6 placement

**Change.** The duplicate check needed repository access.

An early design could have placed duplicate checking beside the policy-only
rules.

**Decision.** Kept `V-6` outside `POLICY_RULES`.

It is evaluated at the end of `evaluate_notification`.

**Reason.** Day 3 instructions say V-6 needs the repository while the other
rules are pure notification/policy checks.

Putting repository access inside `POLICY_RULES` would make that list mix two
different kinds of rules.

The final placement still preserves `docs/api-contract.md` section 4.1 order:
`V-1, V-2, V-7, V-3, V-4, V-5, V-6`.

The test `test_v6_duplicate_recorded_notification` protects the duplicate path.

## Checked: Policy lookup failure boundary

**Change.** `submit_notification` calls `evaluate_notification`, which asks the
policy client for the policy.

**Decision.** Let `PolicyLookupFailed` propagate instead of converting it into
`POLICY_NOT_FOUND`.

**Reason.** `docs/api-contract.md` section 6 distinguishes missing policy from
policy-master dependency failures.

`PolicyNotFound` means the policy master answered and no policy exists.

`PolicyLookupFailed` means the service does not know because the dependency
timed out, was unreachable, or returned an unparsable response.

Collapsing those conditions would send the caller the wrong error.

The test `test_policy_lookup_failure_propagates` covers all three reasons.

## Pipeline Observation

PR #1 ran `checks / checks` on `pull_request`.

The workflow passed in 11 seconds.

The workflow runs `uv sync --frozen`, `ruff`, `mypy src tests`, and `pytest`.

I did not verify a deliberately failing check against branch protection before submission.
