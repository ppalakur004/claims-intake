"""Integration tests for the claims intake HTTP route."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

import pytest
from fastapi.testclient import TestClient

from claims.api.routes import app, get_policy_client, get_repository
from claims.policy_client import StubPolicyClient
from claims.repository import NotificationRepository

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture
def repository() -> NotificationRepository:
    return NotificationRepository(reference_year=2026)


@pytest.fixture
def client(repository: NotificationRepository) -> Iterator[TestClient]:
    app.dependency_overrides[get_policy_client] = StubPolicyClient
    app.dependency_overrides[get_repository] = lambda: repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def payload_from_data(file_name: str, payload_id: str) -> dict[str, Any]:
    records = json.loads((DATA_DIR / file_name).read_text())
    for record in records:
        if record["id"] == payload_id:
            return dict(record["payload"])
    raise AssertionError(f"Missing payload {payload_id}")


def assert_error(
    response_json: dict[str, Any],
    expected_code: str,
    expected_details: dict[str, Any],
) -> None:
    error = response_json["error"]
    assert error["code"] == expected_code
    for key, value in expected_details.items():
        assert error["detail"][key] == value


def test_accepts_valid_notification(client: TestClient) -> None:
    response = client.post(
        "/notifications",
        json=payload_from_data("fnol_valid.json", "VALID-01"),
    )

    assert response.status_code == 201
    assert response.json() == {
        "claim_reference": "CLM-2026-000001",
        "status": "recorded",
    }


def test_v1_policy_not_found(client: TestClient) -> None:
    response = client.post(
        "/notifications",
        json=payload_from_data("fnol_invalid.json", "INVALID-01"),
    )

    assert response.status_code == 422
    assert_error(response.json(), "POLICY_NOT_FOUND", {"policy_number": "MOT-9999"})


def test_v2_before_inception(client: TestClient) -> None:
    response = client.post(
        "/notifications",
        json=payload_from_data("fnol_invalid.json", "INVALID-02"),
    )

    assert response.status_code == 422
    assert_error(
        response.json(),
        "LOSS_BEFORE_INCEPTION",
        {"loss_date": "2026-02-20", "effective_date": "2026-03-15"},
    )


def test_v3_after_expiry(client: TestClient) -> None:
    response = client.post(
        "/notifications",
        json=payload_from_data("fnol_invalid.json", "INVALID-03"),
    )

    assert response.status_code == 422
    assert_error(
        response.json(),
        "LOSS_AFTER_EXPIRY",
        {"loss_date": "2026-03-20", "expiry_date": "2026-02-28"},
    )


def test_v4_amount_over_limit(client: TestClient) -> None:
    response = client.post(
        "/notifications",
        json=payload_from_data("fnol_invalid.json", "INVALID-04"),
    )

    assert response.status_code == 422
    assert_error(
        response.json(),
        "AMOUNT_EXCEEDS_LIMIT",
        {"estimated_amount": "14500.00", "limit": "10000.00"},
    )


def test_v5_type_not_covered(client: TestClient) -> None:
    response = client.post(
        "/notifications",
        json=payload_from_data("fnol_invalid.json", "INVALID-05"),
    )

    assert response.status_code == 422
    assert_error(
        response.json(),
        "TYPE_NOT_COVERED",
        {"claim_type": "collision", "permitted_claim_types": ["liability"]},
    )


def test_v6_duplicate_notification(client: TestClient) -> None:
    payload = payload_from_data("fnol_valid.json", "VALID-01")
    first_response = client.post("/notifications", json=payload)

    response = client.post("/notifications", json=payload)

    assert first_response.status_code == 201
    assert response.status_code == 409
    assert_error(
        response.json(),
        "DUPLICATE_NOTIFICATION",
        {
            "policy_number": "MOT-4471",
            "loss_date": "2026-04-02",
            "claim_type": "collision",
            "existing_claim_reference": "CLM-2026-000001",
        },
    )


def test_v7_policy_cancelled(client: TestClient) -> None:
    response = client.post(
        "/notifications",
        json=payload_from_data("fnol_invalid.json", "INVALID-07"),
    )

    assert response.status_code == 422
    assert_error(
        response.json(),
        "POLICY_CANCELLED",
        {"loss_date": "2026-03-05", "cancellation_date": "2026-02-01"},
    )


def test_missing_field_is_invalid_request(client: TestClient) -> None:
    response = client.post(
        "/notifications",
        json=payload_from_data("fnol_edge.json", "EDGE-08"),
    )

    assert response.status_code == 400
    assert_error(response.json(), "INVALID_REQUEST", {"field": "estimated_amount"})


def test_extra_field_is_invalid_request(client: TestClient) -> None:
    payload = payload_from_data("fnol_valid.json", "VALID-02")
    payload["unexpected"] = "value"

    response = client.post("/notifications", json=payload)

    assert response.status_code == 400
    assert_error(response.json(), "INVALID_REQUEST", {"field": "unexpected"})


@pytest.mark.parametrize(
    ("reason", "expected_status", "expected_code"),
    [
        pytest.param("unparsable", 502, "POLICY_MASTER_BAD_RESPONSE"),
        pytest.param("unreachable", 503, "POLICY_MASTER_UNAVAILABLE"),
        pytest.param("timeout", 504, "POLICY_MASTER_TIMEOUT"),
    ],
)
def test_policy_lookup_failures(
    repository: NotificationRepository,
    reason: Literal["unparsable", "unreachable", "timeout"],
    expected_status: int,
    expected_code: str,
) -> None:
    app.dependency_overrides[get_policy_client] = lambda: StubPolicyClient(fail_with=reason)
    app.dependency_overrides[get_repository] = lambda: repository
    with TestClient(app) as client:
        response = client.post(
            "/notifications",
            json=payload_from_data("fnol_valid.json", "VALID-03"),
        )
    app.dependency_overrides.clear()

    assert response.status_code == expected_status
    assert_error(
        response.json(),
        expected_code,
        {
            "policy_number": "MOT-4473",
            "dependency": "policy_master",
            "reason": reason,
        },
    )
