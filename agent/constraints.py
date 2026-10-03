from __future__ import annotations

from typing import Any


def check_constraints(
    *,
    days: int,
    budget: float,
    total_cost: float,
    itinerary: list[dict[str, Any]] | None = None,
) -> dict[str, bool]:
    """
    Deterministic constraint checker.

    The user's requested number of days and budget are authoritative.
    Replanning is triggered only when a real constraint fails.
    """

    days_ok = int(days) > 0

    budget_ok = float(total_cost) <= float(budget)

    itinerary = itinerary or []

    # If structured places are available, make sure they do not claim
    # more day numbers than the requested trip duration.
    itinerary_days_ok = True

    for item in itinerary:
        day = item.get("day")
        if day is not None:
            try:
                if int(day) < 1 or int(day) > int(days):
                    itinerary_days_ok = False
                    break
            except (TypeError, ValueError):
                itinerary_days_ok = False
                break

    overall_ok = days_ok and budget_ok and itinerary_days_ok

    return {
        "budget": budget_ok,
        "days": days_ok and itinerary_days_ok,
        "overall": overall_ok,
    }
