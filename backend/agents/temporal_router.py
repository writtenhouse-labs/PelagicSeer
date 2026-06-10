"""Decides how to gather data for a requested date range.

Given a ``[start, end]`` window relative to *today*, this classifies the
request into a collection *mode* so every collector knows whether to pull live
observations, reach into historical archives, or fall back to seasonal context.
It keeps the "be as real-time as possible when the window includes today" rule
in one place rather than scattered across the agents.

Modes
-----
- ``live``       — the window includes today; prefer the freshest observations.
- ``historical`` — the window is entirely in the past; query archives for the
                   most relevant day in the window.
- ``forecast``   — the window is entirely in the future; we have no forecast
                   connector yet (phase 5), so collectors use the latest live
                   observation as a nowcast proxy and confidence is lowered.

``target_date`` is the single day a point-conditions *snapshot* should
represent. Conditions are a snapshot, not an average, so the router picks the
most decision-relevant day: today for live/forecast, the window end for
historical (the closest day to now within a past window).
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class TemporalPlan:
    start_date: date
    end_date: date
    today: date
    mode: str  # "live" | "historical" | "forecast"
    includes_today: bool
    days_span: int
    target_date: date
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "includes_today": self.includes_today,
            "days_span": self.days_span,
            "target_date": self.target_date.isoformat(),
            "notes": self.notes,
        }


def resolve_temporal_plan(
    start_date: date,
    end_date: date,
    today: date | None = None,
) -> TemporalPlan:
    """Classify a requested date range into a collection plan.

    Raises ValueError if ``start_date`` is after ``end_date``.
    """
    today = today or date.today()
    if start_date > end_date:
        raise ValueError("start_date cannot be after end_date")

    includes_today = start_date <= today <= end_date
    days_span = (end_date - start_date).days + 1
    notes: list[str] = []

    if includes_today:
        mode = "live"
        target_date = today
        notes.append("Window includes today; using the freshest available observations.")
    elif end_date < today:
        mode = "historical"
        target_date = end_date
        notes.append(
            "Window is in the past; conditions reflect archived observations near the window end."
        )
    else:  # start_date > today
        mode = "forecast"
        target_date = today
        notes.append(
            "Window is in the future; no forecast source is wired yet, so conditions use the "
            "latest observation as a nowcast proxy and confidence is reduced."
        )

    return TemporalPlan(
        start_date=start_date,
        end_date=end_date,
        today=today,
        mode=mode,
        includes_today=includes_today,
        days_span=days_span,
        target_date=target_date,
        notes=notes,
    )
