# Agent Decision Log

## Accepted: V-7 cancellation rule

**Change.** Added `evaluate_policy_not_cancelled` and placed it before expiry validation.

**Decision.** Accepted.

**Reason.** `docs/api-contract.md` section 4.1 requires `V-7` before `V-3`. WI-0158 AC-4 says cancellation must win when a policy is both cancelled and expired.

## Corrected: V-6 placement

**Change.** The duplicate check needed repository access.

**Decision.** Kept `V-6` outside `POLICY_RULES` and evaluated it at the end of `evaluate_notification`.

**Reason.** Day 3 instructions say V-6 needs the repository while the other rules are pure notification/policy checks. This keeps the contract order without putting repository access inside `POLICY_RULES`.

## Pipeline Observation

PR #1 ran `checks / checks` on `pull_request` and passed in 11 seconds.

I did not verify a deliberately failing check against branch protection before submission.
