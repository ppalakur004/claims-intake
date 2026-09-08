"""Boundary models for the claims intake service.

Everything that enters the service is parsed into one of these before any rule
runs. A payload that reaches the rule layer has already been proven well formed,
which is what keeps a shape problem and a content problem from arriving at the
caller as the same status code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field

type ClaimType = Literal["collision", "theft", "glass", "liability", "weather"]
type RuleIdentifier = Literal["V-1", "V-2", "V-3", "V-4", "V-5", "V-6", "V-7"]
type ErrorCode = Literal[
    "POLICY_NOT_FOUND",
    "LOSS_BEFORE_INCEPTION",
    "LOSS_AFTER_EXPIRY",
    "AMOUNT_EXCEEDS_LIMIT",
    "TYPE_NOT_COVERED",
    "DUPLICATE_NOTIFICATION",
    "POLICY_CANCELLED",
]


def _reject_float(value: object) -> object:
    if type(value) is float:
        raise ValueError("money values must not be floats")
    return value


def _require_two_decimal_places(value: Decimal) -> Decimal:
    if value.as_tuple().exponent != -2:
        raise ValueError("money values must have exactly two decimal places")
    return value


type Money = Annotated[
    Decimal,
    BeforeValidator(_reject_float),
    Field(gt=Decimal("0.00")),
    AfterValidator(_require_two_decimal_places),
]


class NotificationRequest(BaseModel):
    """A first notice of loss as submitted by the claims portal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_number: str = Field(min_length=1)
    loss_date: date
    claim_type: ClaimType
    estimated_amount: Money
    description: str | None = None


class Policy(BaseModel):
    """A policy as this service works with it."""

    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)

    policy_number: str = Field(min_length=1)
    product: str = Field(min_length=1)
    effective_date: date
    expiry_date: date
    cancellation_date: date | None
    limit: Money
    permitted_claim_types: tuple[ClaimType, ...]


@dataclass(frozen=True, slots=True)
class RuleFailure:
    """The stable rule/code pair returned when one validation rule fails."""

    rule: RuleIdentifier
    code: ErrorCode


class ClaimRecord(BaseModel):
    """A notification that passed every rule and was written."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_reference: str = Field(pattern=r"^CLM-\d{4}-\d{6}$")
    policy_number: str = Field(min_length=1)
    loss_date: date
    claim_type: ClaimType
    estimated_amount: Money
    description: str | None = None
    status: Literal["recorded"] = "recorded"


class RecordedNotification(ClaimRecord):
    """Compatibility name used by the starter service and repository stubs."""
