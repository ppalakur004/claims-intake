"""Unit tests for recorded notification persistence."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from claims.models import NotificationRequest
from claims.repository import NotificationRepository


@pytest.fixture
def repository() -> NotificationRepository:
    return NotificationRepository(reference_year=2026)


@pytest.fixture
def notification() -> NotificationRequest:
    return NotificationRequest(
        policy_number="MOT-4471",
        loss_date=date(2026, 4, 6),
        claim_type="collision",
        estimated_amount=Decimal("3300.00"),
    )


def test_record_reference(
    repository: NotificationRepository,
    notification: NotificationRequest,
) -> None:
    record = repository.record(notification)

    assert record.claim_reference == "CLM-2026-000001"


def test_record_policy(
    repository: NotificationRepository,
    notification: NotificationRequest,
) -> None:
    record = repository.record(notification)

    assert record.policy_number == "MOT-4471"


def test_record_status(
    repository: NotificationRepository,
    notification: NotificationRequest,
) -> None:
    record = repository.record(notification)

    assert record.status == "recorded"


def test_unique_references(repository: NotificationRepository) -> None:
    first = repository.record(
        NotificationRequest(
            policy_number="MOT-4471",
            loss_date=date(2026, 4, 6),
            claim_type="collision",
            estimated_amount=Decimal("3300.00"),
        )
    )
    second = repository.record(
        NotificationRequest(
            policy_number="MOT-4472",
            loss_date=date(2026, 4, 7),
            claim_type="theft",
            estimated_amount=Decimal("1200.00"),
        )
    )

    assert first.claim_reference != second.claim_reference


def test_duplicate_found(
    repository: NotificationRepository,
    notification: NotificationRequest,
) -> None:
    record = repository.record(notification)

    assert repository.find_matching("MOT-4471", date(2026, 4, 6), "collision") == record


@pytest.mark.parametrize(
    ("policy_number", "loss_date", "claim_type"),
    [
        pytest.param("MOT-4472", date(2026, 4, 6), "collision", id="different-policy-number"),
        pytest.param("MOT-4471", date(2026, 4, 7), "collision", id="different-loss-date"),
        pytest.param("MOT-4471", date(2026, 4, 6), "theft", id="different-claim-type"),
    ],
)
def test_partial_not_duplicate(
    repository: NotificationRepository,
    notification: NotificationRequest,
    policy_number: str,
    loss_date: date,
    claim_type: str,
) -> None:
    repository.record(notification)

    assert repository.find_matching(policy_number, loss_date, claim_type) is None


def test_unrecorded_not_duplicate(
    repository: NotificationRepository,
    notification: NotificationRequest,
) -> None:
    assert repository.find_matching(
        notification.policy_number,
        notification.loss_date,
        notification.claim_type,
    ) is None
