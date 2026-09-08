"""Unit tests for the claims service rule engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

import pytest

from claims import service
from claims.models import NotificationRequest, Policy, RecordedNotification
from claims.policy_client import (
    PolicyLookupFailed,
    PolicyNotFound,
    PolicyRecord,
    StubPolicyClient,
)
from claims.repository import NotificationRepository
from claims.service import ValidationOutcome


def notification(**overrides: object) -> NotificationRequest:
    payload: dict[str, object] = {
        "policy_number": "MOT-4471",
        "loss_date": date(2026, 4, 6),
        "claim_type": "collision",
        "estimated_amount": Decimal("3300.00"),
    }
    payload.update(overrides)
    return NotificationRequest.model_validate(payload)


def policy(**overrides: object) -> Policy:
    payload: dict[str, object] = {
        "policy_number": "MOT-4471",
        "product": "personal_auto_standard",
        "effective_date": date(2026, 3, 1),
        "expiry_date": date(2027, 2, 28),
        "cancellation_date": None,
        "limit": Decimal("50000.00"),
        "permitted_claim_types": ("collision", "theft", "glass", "liability", "weather"),
    }
    payload.update(overrides)
    return Policy.model_validate(payload)


def as_policy_record(record: Policy) -> PolicyRecord:
    return PolicyRecord(
        policy_number=record.policy_number,
        product=record.product,
        effective_date=record.effective_date,
        expiry_date=record.expiry_date,
        cancellation_date=record.cancellation_date,
        limit=record.limit,
        permitted_claim_types=record.permitted_claim_types,
    )


class StaticPolicyClient:
    def __init__(self, record: Policy | None = None) -> None:
        self._record = record or policy()

    def get_policy(self, policy_number: str) -> PolicyRecord:
        if policy_number != self._record.policy_number:
            raise PolicyNotFound(policy_number)
        return as_policy_record(self._record)


class OneMissThenPolicyClient:
    def __init__(self, record: Policy) -> None:
        self._record = record
        self._calls = 0

    def get_policy(self, policy_number: str) -> PolicyRecord:
        self._calls += 1
        if self._calls == 1:
            raise PolicyNotFound(policy_number)
        return as_policy_record(self._record)


def assert_outcome(
    outcome: ValidationOutcome,
    expected_rule: str | None,
    expected_code: str | None,
) -> None:
    assert (outcome.rule, outcome.code) == (expected_rule, expected_code)


def evaluate_v7(request: NotificationRequest, record: Policy) -> ValidationOutcome:
    evaluator = getattr(service, "evaluate_policy_not_cancelled", None)
    assert evaluator is not None
    outcome = evaluator(request, record)
    assert isinstance(outcome, ValidationOutcome)
    return outcome


@pytest.mark.parametrize(
    ("policy_number", "expected_rule", "expected_code"),
    [
        pytest.param("MOT-4471", None, None, id="policy-exists"),
        pytest.param("MOT-9999", "V-1", "POLICY_NOT_FOUND", id="policy-missing"),
    ],
)
def test_v1_policy_exists(
    policy_client: StubPolicyClient,
    policy_number: str,
    expected_rule: str | None,
    expected_code: str | None,
) -> None:
    outcome = service.evaluate_policy_exists(
        notification(policy_number=policy_number),
        policy_client,
    )

    assert_outcome(outcome, expected_rule, expected_code)


@pytest.mark.parametrize(
    ("loss_date", "expected_rule", "expected_code"),
    [
        pytest.param(date(2026, 2, 28), "V-2", "LOSS_BEFORE_INCEPTION", id="before"),
        pytest.param(date(2026, 3, 1), None, None, id="on-boundary"),
        pytest.param(date(2026, 3, 2), None, None, id="after"),
    ],
)
def test_v2_loss_after_inception(
    loss_date: date,
    expected_rule: str | None,
    expected_code: str | None,
) -> None:
    outcome = service.evaluate_loss_after_inception(notification(loss_date=loss_date), policy())

    assert_outcome(outcome, expected_rule, expected_code)


@pytest.mark.parametrize(
    ("loss_date", "expected_rule", "expected_code"),
    [
        pytest.param(date(2027, 2, 27), None, None, id="before"),
        pytest.param(date(2027, 2, 28), None, None, id="on-boundary"),
        pytest.param(date(2027, 3, 1), "V-3", "LOSS_AFTER_EXPIRY", id="after"),
    ],
)
def test_v3_loss_before_expiry(
    loss_date: date,
    expected_rule: str | None,
    expected_code: str | None,
) -> None:
    outcome = service.evaluate_loss_before_expiry(notification(loss_date=loss_date), policy())

    assert_outcome(outcome, expected_rule, expected_code)


@pytest.mark.parametrize(
    ("amount", "expected_rule", "expected_code"),
    [
        pytest.param(Decimal("49999.99"), None, None, id="under"),
        pytest.param(Decimal("50000.00"), None, None, id="on-boundary"),
        pytest.param(Decimal("50000.01"), "V-4", "AMOUNT_EXCEEDS_LIMIT", id="over"),
    ],
)
def test_v4_amount_within_limit(
    amount: Decimal,
    expected_rule: str | None,
    expected_code: str | None,
) -> None:
    outcome = service.evaluate_amount_within_limit(
        notification(estimated_amount=amount),
        policy(),
    )

    assert_outcome(outcome, expected_rule, expected_code)


@pytest.mark.parametrize(
    ("claim_type", "expected_rule", "expected_code"),
    [
        pytest.param("theft", None, None, id="permitted"),
        pytest.param("collision", "V-5", "TYPE_NOT_COVERED", id="not-permitted"),
    ],
)
def test_v5_claim_type_covered(
    claim_type: Literal["collision", "theft"],
    expected_rule: str | None,
    expected_code: str | None,
) -> None:
    named_perils = policy(permitted_claim_types=("theft", "glass", "liability", "weather"))
    outcome = service.evaluate_claim_type_covered(
        notification(claim_type=claim_type),
        named_perils,
    )

    assert_outcome(outcome, expected_rule, expected_code)


@pytest.mark.parametrize(
    ("cancellation_date", "loss_date", "expected_rule", "expected_code"),
    [
        pytest.param(date(2026, 6, 1), date(2026, 5, 31), None, None, id="before"),
        pytest.param(
            date(2026, 6, 1),
            date(2026, 6, 1),
            "V-7",
            "POLICY_CANCELLED",
            id="on-boundary",
        ),
        pytest.param(
            date(2026, 6, 1),
            date(2026, 6, 2),
            "V-7",
            "POLICY_CANCELLED",
            id="after",
        ),
        pytest.param(None, date(2026, 6, 1), None, None, id="absent"),
    ],
)
def test_v7_policy_not_cancelled(
    cancellation_date: date | None,
    loss_date: date,
    expected_rule: str | None,
    expected_code: str | None,
) -> None:
    outcome = evaluate_v7(
        notification(loss_date=loss_date),
        policy(cancellation_date=cancellation_date),
    )

    assert_outcome(outcome, expected_rule, expected_code)


@pytest.mark.parametrize(
    ("already_recorded", "expected_rule", "expected_code"),
    [
        pytest.param(False, None, None, id="new-notification"),
        pytest.param(True, "V-6", "DUPLICATE_NOTIFICATION", id="recorded-duplicate"),
    ],
)
def test_v6_duplicate_recorded_notification(
    already_recorded: bool,
    expected_rule: str | None,
    expected_code: str | None,
) -> None:
    request = notification()
    repository = NotificationRepository(reference_year=2026)
    if already_recorded:
        repository.record(request)

    outcome = service.evaluate_notification(request, StaticPolicyClient(), repository)

    assert_outcome(outcome, expected_rule, expected_code)


@pytest.mark.parametrize(
    ("claim_request", "record", "existing_duplicate", "expected_rule", "expected_code"),
    [
        pytest.param(
            notification(loss_date=date(2026, 2, 28), estimated_amount=Decimal("90000.00")),
            policy(),
            False,
            "V-2",
            "LOSS_BEFORE_INCEPTION",
            id="v2-before-v4",
        ),
        pytest.param(
            notification(loss_date=date(2026, 6, 1)),
            policy(cancellation_date=date(2026, 6, 1), expiry_date=date(2026, 5, 31)),
            False,
            "V-7",
            "POLICY_CANCELLED",
            id="v7-before-v3",
        ),
        pytest.param(
            notification(estimated_amount=Decimal("50000.01"), claim_type="collision"),
            policy(
                limit=Decimal("50000.00"),
                permitted_claim_types=("theft", "glass", "liability", "weather"),
            ),
            False,
            "V-4",
            "AMOUNT_EXCEEDS_LIMIT",
            id="v4-before-v5",
        ),
        pytest.param(
            notification(estimated_amount=Decimal("50000.01")),
            policy(),
            True,
            "V-4",
            "AMOUNT_EXCEEDS_LIMIT",
            id="v4-before-v6",
        ),
    ],
)
def test_evaluation_order_first_failure_wins(
    claim_request: NotificationRequest,
    record: Policy,
    existing_duplicate: bool,
    expected_rule: str,
    expected_code: str,
) -> None:
    repository = NotificationRepository(reference_year=2026)
    if existing_duplicate:
        repository.record(notification())

    outcome = service.evaluate_notification(claim_request, StaticPolicyClient(record), repository)

    assert_outcome(outcome, expected_rule, expected_code)


@pytest.mark.parametrize(
    "reason",
    [
        pytest.param("timeout", id="timeout"),
        pytest.param("unreachable", id="unreachable"),
        pytest.param("unparsable", id="unparsable"),
    ],
)
def test_policy_lookup_failure_propagates(
    reason: Literal["timeout", "unreachable", "unparsable"],
) -> None:
    client = StubPolicyClient(fail_with=reason)

    with pytest.raises(PolicyLookupFailed) as error:
        service.submit_notification(
            notification(),
            client,
            NotificationRepository(reference_year=2026),
        )

    assert error.value.reason == reason


def test_submit_records_accepted_notification(policy_client: StubPolicyClient) -> None:
    repository = NotificationRepository(reference_year=2026)

    result = service.submit_notification(notification(), policy_client, repository)

    assert isinstance(result, RecordedNotification)


def test_submit_does_not_record_rejected_notification(policy_client: StubPolicyClient) -> None:
    repository = NotificationRepository(reference_year=2026)
    request = notification(policy_number="MOT-9999")

    result = service.submit_notification(request, policy_client, repository)

    assert isinstance(result, ValidationOutcome) and repository.find_matching(
        request.policy_number,
        request.loss_date,
        request.claim_type,
    ) is None


def test_rejected_submission_is_not_duplicate() -> None:
    request = notification()
    repository = NotificationRepository(reference_year=2026)
    client = OneMissThenPolicyClient(policy())

    first_result = service.submit_notification(request, client, repository)
    second_result = service.submit_notification(request, client, repository)

    assert (
        isinstance(first_result, ValidationOutcome),
        isinstance(second_result, RecordedNotification),
    ) == (True, True)

def test_temporary_ci_gate_failure() -> None:
    assert False
