"""
Menstrual cycle phase calculator — pure Python, no LLM calls.

This module is deterministic date math only.  It is the foundation for
the real-time dashboard auto-update engine: call it cheaply and often
without any API cost or latency.

IMPORTANT: These functions must NEVER be called for a patient whose
``pregnancy_status`` is ``"pregnant"`` or ``"lactating"``.  The caller
is responsible for filtering to non-pregnant, menstruating patients
before invoking anything here.
"""

from __future__ import annotations

from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Phase boundary proportions (based on a standard 28-day reference cycle)
# ---------------------------------------------------------------------------
#   Menstruation : days 1-5   → 5/28 ≈ 17.86 %
#   Follicular   : days 6-13  → 8/28 ≈ 28.57 %
#   Ovulation    : days 14-16 → 3/28 ≈ 10.71 %
#   Luteal       : days 17-28 → 12/28 ≈ 42.86 %
#
# Stored as cumulative *upper-bound* fractions so we can do a single
# ordered walk for any cycle length.
# ---------------------------------------------------------------------------
_PHASE_FRACTIONS: list[tuple[str, float]] = [
    ("menstruation", 5 / 28),   # days 1 .. floor(cycle_length * 5/28)
    ("follicular",   13 / 28),  # .. floor(cycle_length * 13/28)
    ("ovulation",    16 / 28),  # .. floor(cycle_length * 16/28)
    ("luteal",       1.0),      # remainder through end of cycle
]

_MIN_CYCLE_LENGTH = 15
_MAX_CYCLE_LENGTH = 45


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_date(value: str, param_name: str) -> date:
    """Parse an ISO-format date string; raise ValueError with a clear message."""
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"'{param_name}' must be an ISO date string (YYYY-MM-DD), "
            f"got: {value!r}"
        ) from exc


def _phase_for_cycle_day(cycle_day: int, cycle_length: int) -> str:
    """
    Return the phase name for a 1-indexed *cycle_day* within a cycle of
    *cycle_length* days.

    Phase boundaries are scaled proportionally from the 28-day reference.
    """
    for phase, upper_fraction in _PHASE_FRACTIONS:
        boundary = round(cycle_length * upper_fraction)
        # Ensure the last phase always covers through the final day exactly.
        if phase == "luteal" or cycle_day <= boundary:
            return phase
    return "luteal"  # fallback (should never be reached)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculate_cycle_info(
    cycle_start_date: str,
    average_cycle_length: int = 28,
    reference_date: str | None = None,
) -> dict:
    """
    Calculate the current menstrual cycle phase and related metadata.

    Parameters
    ----------
    cycle_start_date : str
        ISO date string for the first day of the patient's most recent period
        (e.g. ``"2026-08-01"``).
    average_cycle_length : int, optional
        Patient's average cycle length in days.  Must be between
        ``_MIN_CYCLE_LENGTH`` and ``_MAX_CYCLE_LENGTH`` (inclusive).
        Defaults to 28.
    reference_date : str | None, optional
        ISO date string for "today".  Defaults to the actual current date.
        **Provide this parameter in tests** so results are deterministic
        without waiting for real time to pass.

    Returns
    -------
    dict
        ``{
            "cycle_day": int,                      # 1-indexed day within current cycle
            "cycle_phase": str,                    # "menstruation" | "follicular" |
                                                    #   "ovulation" | "luteal"
            "days_since_cycle_start": int,         # calendar days since cycle_start_date
            "next_period_estimated_date": str,     # ISO date of next expected period
            "cycle_number": int                    # 0 for 1st cycle, 1 for 2nd, …
        }``

    Raises
    ------
    ValueError
        * If *cycle_start_date* is in the future relative to *reference_date*.
        * If *average_cycle_length* is outside ``[_MIN_CYCLE_LENGTH, _MAX_CYCLE_LENGTH]``.

    Notes
    -----
    Do **not** call this function for patients with
    ``pregnancy_status == "pregnant"`` or ``"lactating"``.  The caller owns
    that responsibility; this function does not perform the check.
    """
    # --- validate cycle length ---
    if not (_MIN_CYCLE_LENGTH <= average_cycle_length <= _MAX_CYCLE_LENGTH):
        raise ValueError(
            f"average_cycle_length must be between {_MIN_CYCLE_LENGTH} and "
            f"{_MAX_CYCLE_LENGTH} days, got {average_cycle_length}."
        )

    # --- parse dates ---
    start = _parse_date(cycle_start_date, "cycle_start_date")
    today = (
        _parse_date(reference_date, "reference_date")
        if reference_date is not None
        else date.today()
    )

    if start > today:
        raise ValueError(
            f"cycle_start_date ({cycle_start_date}) is in the future "
            f"relative to reference_date ({today.isoformat()}). "
            "Provide a past or present cycle start date."
        )

    # --- core math ---
    days_since_start: int = (today - start).days          # 0-indexed total days elapsed
    cycle_number: int = days_since_start // average_cycle_length
    cycle_day: int = (days_since_start % average_cycle_length) + 1  # 1-indexed

    cycle_phase: str = _phase_for_cycle_day(cycle_day, average_cycle_length)

    # Next period = start of the *next* cycle after the *current* cycle
    next_period: date = start + timedelta(
        days=(cycle_number + 1) * average_cycle_length
    )

    return {
        "cycle_day": cycle_day,
        "cycle_phase": cycle_phase,
        "days_since_cycle_start": days_since_start,
        "next_period_estimated_date": next_period.isoformat(),
        "cycle_number": cycle_number,
    }


def has_phase_changed_since(
    cycle_start_date: str,
    average_cycle_length: int,
    last_known_phase: str,
    reference_date: str | None = None,
) -> bool:
    """
    Return ``True`` if the current cycle phase differs from *last_known_phase*.

    This is the hook the daily auto-update engine uses to decide whether
    to regenerate the diet plan: call cheaply, act only on ``True``.

    Parameters
    ----------
    cycle_start_date : str
        ISO date string for the first day of the patient's most recent period.
    average_cycle_length : int
        Patient's average cycle length in days.
    last_known_phase : str
        The phase that was recorded the last time a diet plan was generated.
    reference_date : str | None, optional
        ISO date string for "today".  Defaults to the actual current date.
        Provide in tests for determinism.

    Returns
    -------
    bool
        ``True``  → phase has changed; regenerate the diet plan.
        ``False`` → still in the same phase; no action needed.
    """
    info = calculate_cycle_info(
        cycle_start_date=cycle_start_date,
        average_cycle_length=average_cycle_length,
        reference_date=reference_date,
    )
    return info["cycle_phase"] != last_known_phase
