"""HTTP surface for the claims intake service.

This layer does three things and no more: it parses the request, it calls the
service, and it maps the outcome to a status code. It holds no rule logic. A rule
that appears here is a rule the service layer cannot be tested for.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from claims.models import NotificationRequest, RecordedNotification
from claims.policy_client import PolicyClient, PolicyLookupFailed, StubPolicyClient
from claims.repository import NotificationRepository
from claims.service import ValidationOutcome, submit_notification

app = FastAPI(title="Claims Intake Service")

_policy_client = StubPolicyClient()
_repository = NotificationRepository()

RULE_STATUS: dict[str, int] = {
    "DUPLICATE_NOTIFICATION": status.HTTP_409_CONFLICT,
    "POLICY_NOT_FOUND": 422,
    "LOSS_BEFORE_INCEPTION": 422,
    "POLICY_CANCELLED": 422,
    "LOSS_AFTER_EXPIRY": 422,
    "AMOUNT_EXCEEDS_LIMIT": 422,
    "TYPE_NOT_COVERED": 422,
}

ERROR_MESSAGES: dict[str, str] = {
    "INVALID_REQUEST": "The request body could not be interpreted.",
    "DUPLICATE_NOTIFICATION": "A notification has already been recorded for this loss event.",
    "POLICY_NOT_FOUND": "The policy number was not found.",
    "LOSS_BEFORE_INCEPTION": "The loss date is before policy inception.",
    "POLICY_CANCELLED": "The policy was cancelled before the loss date.",
    "LOSS_AFTER_EXPIRY": "The loss date is after policy expiry.",
    "AMOUNT_EXCEEDS_LIMIT": "The estimated amount exceeds the policy limit.",
    "TYPE_NOT_COVERED": "The claim type is not covered by the policy.",
    "POLICY_MASTER_BAD_RESPONSE": "The policy master returned an unusable response.",
    "POLICY_MASTER_UNAVAILABLE": "The policy master was unreachable.",
    "POLICY_MASTER_TIMEOUT": "The policy master did not answer in time.",
}

LOOKUP_FAILURES: dict[str, tuple[str, int]] = {
    "unparsable": ("POLICY_MASTER_BAD_RESPONSE", status.HTTP_502_BAD_GATEWAY),
    "unreachable": ("POLICY_MASTER_UNAVAILABLE", status.HTTP_503_SERVICE_UNAVAILABLE),
    "timeout": ("POLICY_MASTER_TIMEOUT", status.HTTP_504_GATEWAY_TIMEOUT),
}


def get_policy_client() -> PolicyClient:
    return _policy_client


def get_repository() -> NotificationRepository:
    return _repository


def error_response(code: str, http_status: int, detail: dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content=jsonable_encoder(
            {
                "error": {
                    "code": code,
                    "message": ERROR_MESSAGES[code],
                    "detail": detail,
                }
            },
            custom_encoder={Decimal: str},
        ),
    )


def validation_detail(error: RequestValidationError) -> dict[str, str]:
    errors = error.errors()
    if len(errors) != 1:
        return {"reason": "multiple_invalid_fields"}

    first_error = errors[0]
    location = first_error.get("loc", ())
    field = next((part for part in reversed(location) if isinstance(part, str)), "body")
    reason = str(first_error.get("type", "invalid"))
    return {"field": field, "reason": reason}


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(
    _request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    return error_response(
        "INVALID_REQUEST",
        status.HTTP_400_BAD_REQUEST,
        validation_detail(error),
    )


@app.post("/notifications", status_code=status.HTTP_201_CREATED, response_model=None)
def create_notification(
    notification: NotificationRequest,
    policy_client: Annotated[PolicyClient, Depends(get_policy_client)],
    repository: Annotated[NotificationRepository, Depends(get_repository)],
) -> dict[str, str] | JSONResponse:
    try:
        result = submit_notification(notification, policy_client, repository)
    except PolicyLookupFailed as error:
        code, http_status = LOOKUP_FAILURES[error.reason]
        return error_response(
            code,
            http_status,
            {
                "policy_number": error.policy_number,
                "dependency": "policy_master",
                "reason": error.reason,
            },
        )

    if isinstance(result, ValidationOutcome):
        if result.passed or result.code is None:
            raise RuntimeError("validation outcome did not include a rule failure")
        return error_response(result.code, RULE_STATUS[result.code], result.detail)

    return success_response(result)


def success_response(record: RecordedNotification) -> dict[str, str]:
    return {
        "claim_reference": record.claim_reference,
        "status": record.status,
    }
