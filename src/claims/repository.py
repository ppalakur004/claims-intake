"""Persistence for recorded notifications.

An in-memory store is sufficient for Week 1 and is deliberate rather than a
shortcut. The rules do not know where a notification is stored, so replacing this
with a database in a later week is a change to one module.

The duplicate check that `WI-0151` describes is a query against what has been
recorded, which is why it belongs here rather than in the rule table.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from claims.models import NotificationRequest, RecordedNotification


class NotificationRepository:
    """Stores recorded notifications and issues claim references."""

    def __init__(self, reference_year: int | None = None) -> None:
        self._reference_year = reference_year or datetime.now(UTC).year
        self._next_sequence = 1
        self._records: list[RecordedNotification] = []

    def record(self, notification: NotificationRequest) -> RecordedNotification:
        """Write a notification and return it with its issued claim reference.

        The reference format is fixed by contract section 3. References are unique
        and are never reissued.
        """
        record = RecordedNotification(
            claim_reference=self._next_claim_reference(),
            policy_number=notification.policy_number,
            loss_date=notification.loss_date,
            claim_type=notification.claim_type,
            estimated_amount=notification.estimated_amount,
            description=notification.description,
        )
        self._records.append(record)
        return record

    def find_matching(
        self,
        policy_number: str,
        loss_date: date,
        claim_type: str,
    ) -> RecordedNotification | None:
        """Return an existing recorded notification matching all three values.

        `WI-0151` AC-1 fixes which fields constitute a match. AC-3 is the reason
        this searches recorded notifications only: a submission that was refused
        was never written, so there is nothing for a later one to duplicate.
        """
        for record in self._records:
            if (
                record.policy_number == policy_number
                and record.loss_date == loss_date
                and record.claim_type == claim_type
            ):
                return record
        return None

    def _next_claim_reference(self) -> str:
        reference = f"CLM-{self._reference_year}-{self._next_sequence:06d}"
        self._next_sequence += 1
        return reference
