# Agent Decision Log

## Accepted: V-7 cancellation rule

**Change.** Added `evaluate_policy_not_cancelled` in `src/claims/service.py`.

**Decision.** Accepted.

**Reason.** The contract says the rule order is `V-1, V-2, V-7, V-3, V-4, V-5, V-6`. V-7 must run before V-3 so a cancelled and expired policy returns `POLICY_CANCELLED`, not `LOSS_AFTER_EXPIRY`. This matches WI-0158 AC-4.

## Corrected: V-6 duplicate placement

**Change.** The duplicate rule needs to check stored recorded notifications.

**Decision.** Kept V-6 outside `POLICY_RULES` and handled it at the end of `evaluate_notification`.

**Reason.** The Day 3 instructions say V-6 needs the repository, while the other rules are pure notification-and-policy checks. This keeps repository access out of `POLICY_RULES` and still preserves the contract order.

## Checked: Policy lookup failures

**Change.** `submit_notification` uses the policy client before recording anything.

**Decision.** Let `PolicyLookupFailed` propagate instead of turning it into `POLICY_NOT_FOUND`.

**Reason.** Contract section 6 separates missing policies from policy-master failures. A missing policy is a caller data problem. A timeout, unreachable dependency, or unparsable policy response is a system/dependency problem.

## Pipeline Observation

PR #1 ran `checks / checks` on `pull_request` and passed in 11 seconds.

The workflow runs `uv sync --frozen`, `ruff`, `mypy src tests`, and `pytest`.

I pushed a temporary failing test in commit `b02ab29`. The PR workflow failed on `pytest` with 1 failed and 93 passed, proving the workflow can fail the job. I then removed the temporary failing test before submission.

