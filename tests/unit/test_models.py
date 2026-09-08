"""Unit tests for claims boundary models."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from claims.models import ClaimRecord, NotificationRequest, Policy, RuleFailure
from claims.policy_client import StubPolicyClient

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def payload_from_data(file_name: str, payload_id: str) -> dict[str, object]:
    rows = cast(list[dict[str, Any]], json.loads((DATA_DIR / file_name).read_text()))
    matches = [row for row in rows if row["id"] == payload_id]
    if not matches:
        raise ValueError(f"Unknown payload id: {payload_id}")
    return cast(dict[str, object], matches[0]["payload"])


def request_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "policy_number": "MOT-4471",
        "loss_date": date(2026, 4, 6),
        "claim_type": "collision",
        "estimated_amount": Decimal("3300.00"),
        "description": "Rear-end collision",
    }
    payload.update(overrides)
    return payload


def policy_payload(**overrides: object) -> dict[str, object]:
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
    return payload


def claim_payload(**overrides: object) -> dict[str, object]:
    payload = request_payload()
    payload["claim_reference"] = "CLM-2026-000001"
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("file_name", "payload_id", "field", "expected"),
    [
        pytest.param("fnol_invalid.json", "INVALID-01", "policy_number", "MOT-9999", id="invalid-01-policy-not-found"),
        pytest.param("fnol_invalid.json", "INVALID-02", "loss_date", date(2026, 2, 20), id="invalid-02-before-inception"),
        pytest.param("fnol_invalid.json", "INVALID-03", "claim_type", "theft", id="invalid-03-after-expiry"),
        pytest.param("fnol_invalid.json", "INVALID-04", "estimated_amount", Decimal("14500.00"), id="invalid-04-over-limit"),
        pytest.param("fnol_invalid.json", "INVALID-05", "claim_type", "collision", id="invalid-05-type-not-covered"),
        pytest.param("fnol_invalid.json", "INVALID-06", "description", "Resubmission after a portal timeout.", id="invalid-06-duplicate"),
        pytest.param("fnol_invalid.json", "INVALID-07", "claim_type", "glass", id="invalid-07-cancelled"),
        pytest.param("fnol_edge.json", "EDGE-01", "loss_date", date(2026, 3, 15), id="edge-01-inception-boundary"),
        pytest.param("fnol_edge.json", "EDGE-02", "estimated_amount", Decimal("50000.00"), id="edge-02-limit-boundary"),
        pytest.param("fnol_edge.json", "EDGE-03", "loss_date", date(2026, 2, 28), id="edge-03-expiry-boundary"),
        pytest.param("fnol_edge.json", "EDGE-04", "loss_date", date(2026, 1, 15), id="edge-04-cancellation-boundary"),
        pytest.param("fnol_edge.json", "EDGE-05", "estimated_amount", Decimal("72000.00"), id="edge-05-multiple-rule-failures"),
        pytest.param("fnol_edge.json", "EDGE-06", "estimated_amount", Decimal("26000.00"), id="edge-06-over-limit"),
        pytest.param("fnol_edge.json", "EDGE-07", "policy_number", "mot-4471", id="edge-07-case-sensitive-policy"),
        pytest.param("fnol_edge.json", "EDGE-09", "claim_type", "collision", id="edge-09-type-not-covered"),
        pytest.param("fnol_edge.json", "EDGE-10", "loss_date", date(2026, 1, 8), id="edge-10-cancelled-and-expired"),
    ],
)
def test_rule_payloads_parse(
    file_name: str,
    payload_id: str,
    field: str,
    expected: object,
) -> None:
    notification = NotificationRequest.model_validate(payload_from_data(file_name, payload_id))

    assert getattr(notification, field) == expected


@pytest.mark.parametrize(
    ("payload_id", "field"),
    [
        pytest.param("EDGE-08", "estimated_amount", id="edge-08-missing-amount"),
        pytest.param("EDGE-11", "claim_type", id="edge-11-unknown-type"),
        pytest.param("EDGE-12", "estimated_amount", id="edge-12-three-decimals"),
    ],
)
def test_shape_payloads_fail(payload_id: str, field: str) -> None:
    with pytest.raises(ValidationError) as error:
        NotificationRequest.model_validate(payload_from_data("fnol_edge.json", payload_id))

    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(request_payload(extra="value"), id="extra-field"),
        pytest.param(
            {key: value for key, value in request_payload().items() if key != "policy_number"},
            id="missing-policy-number",
        ),
        pytest.param(
            {key: value for key, value in request_payload().items() if key != "loss_date"},
            id="missing-loss-date",
        ),
        pytest.param(
            {key: value for key, value in request_payload().items() if key != "claim_type"},
            id="missing-claim-type",
        ),
        pytest.param(
            {key: value for key, value in request_payload().items() if key != "estimated_amount"},
            id="missing-estimated-amount",
        ),
        pytest.param(request_payload(policy_number=""), id="empty-policy-number"),
        pytest.param(request_payload(loss_date="not-a-date"), id="bad-loss-date"),
        pytest.param(request_payload(claim_type="flood"), id="unknown-claim-type"),
        pytest.param(request_payload(estimated_amount=1.25), id="float-money"),
        pytest.param(request_payload(estimated_amount=Decimal("0.00")), id="zero-money"),
        pytest.param(request_payload(estimated_amount=Decimal("3499.999")), id="three-decimal-money"),
        pytest.param(request_payload(description=123), id="bad-description"),
    ],
)
def test_request_constraints_fail(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        NotificationRequest.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            {key: value for key, value in request_payload().items() if key != "description"},
            id="missing-description",
        ),
        pytest.param(request_payload(description=None), id="null-description"),
    ],
)
def test_description_optional(payload: dict[str, object]) -> None:
    notification = NotificationRequest.model_validate(payload)

    assert notification.description is None


def test_policy_record_parses(policy_client: StubPolicyClient) -> None:
    policy = Policy.model_validate(policy_client.get_policy("MOT-4497"))

    assert policy.cancellation_date == date(2026, 1, 15)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(policy_payload(extra="value"), id="extra-field"),
        pytest.param(policy_payload(policy_number=""), id="empty-policy-number"),
        pytest.param(policy_payload(product=""), id="empty-product"),
        pytest.param(policy_payload(effective_date="not-a-date"), id="bad-effective-date"),
        pytest.param(policy_payload(expiry_date="not-a-date"), id="bad-expiry-date"),
        pytest.param(policy_payload(cancellation_date="not-a-date"), id="bad-cancellation-date"),
        pytest.param(
            {key: value for key, value in policy_payload().items() if key != "cancellation_date"},
            id="missing-cancellation-date",
        ),
        pytest.param(policy_payload(limit=1.25), id="float-limit"),
        pytest.param(policy_payload(limit=Decimal("0.00")), id="zero-limit"),
        pytest.param(policy_payload(limit=Decimal("100.0")), id="one-decimal-limit"),
        pytest.param(
            policy_payload(permitted_claim_types=("collision", "flood")),
            id="unknown-permitted-type",
        ),
    ],
)
def test_policy_constraints_fail(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Policy.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(claim_payload(extra="value"), id="extra-field"),
        pytest.param(claim_payload(claim_reference="bad-reference"), id="bad-reference"),
        pytest.param(claim_payload(status="pending"), id="bad-status"),
        pytest.param(claim_payload(policy_number=""), id="empty-policy-number"),
        pytest.param(claim_payload(loss_date="not-a-date"), id="bad-loss-date"),
        pytest.param(claim_payload(claim_type="flood"), id="unknown-claim-type"),
        pytest.param(claim_payload(estimated_amount=Decimal("12.345")), id="bad-money"),
        pytest.param(claim_payload(description=123), id="bad-description"),
    ],
)
def test_claim_constraints_fail(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ClaimRecord.model_validate(payload)


def test_required_fields_have_no_defaults() -> None:
    required = {
        name
        for name, field in NotificationRequest.model_fields.items()
        if field.is_required()
    }

    assert required == {"policy_number", "loss_date", "claim_type", "estimated_amount"}


def test_rule_failure_is_frozen() -> None:
    failure = RuleFailure(rule="V-2", code="LOSS_BEFORE_INCEPTION")
    field_name = "code"

    with pytest.raises(FrozenInstanceError):
        setattr(failure, field_name, "POLICY_NOT_FOUND")
