"""
Tests for cycle_calculator.py — pure Python, no LLM calls, fully deterministic.

All test cases use the ``reference_date`` parameter so they pass regardless
of when the test suite is run.
"""

import pytest

from anemia_diet_system.cycle_calculator import (
    calculate_cycle_info,
    has_phase_changed_since,
)

# ---------------------------------------------------------------------------
# Shared fixture values
# ---------------------------------------------------------------------------
START = "2026-08-01"
LEN28 = 28


# ---------------------------------------------------------------------------
# TC-CYC01  Day 1 of cycle → menstruation
# ---------------------------------------------------------------------------
def test_cyc01_day1_menstruation():
    result = calculate_cycle_info(
        cycle_start_date=START,
        average_cycle_length=LEN28,
        reference_date="2026-08-01",
    )
    assert result["cycle_day"] == 1
    assert result["cycle_phase"] == "menstruation"
    assert result["days_since_cycle_start"] == 0
    assert result["cycle_number"] == 0


# ---------------------------------------------------------------------------
# TC-CYC02  Day 3 → still menstruation
# ---------------------------------------------------------------------------
def test_cyc02_day3_menstruation():
    result = calculate_cycle_info(
        cycle_start_date=START,
        average_cycle_length=LEN28,
        reference_date="2026-08-03",
    )
    assert result["cycle_day"] == 3
    assert result["cycle_phase"] == "menstruation"


# ---------------------------------------------------------------------------
# TC-CYC03  Day 10 → follicular
# ---------------------------------------------------------------------------
def test_cyc03_day10_follicular():
    result = calculate_cycle_info(
        cycle_start_date=START,
        average_cycle_length=LEN28,
        reference_date="2026-08-10",
    )
    assert result["cycle_day"] == 10
    assert result["cycle_phase"] == "follicular"


# ---------------------------------------------------------------------------
# TC-CYC04  Day 15 → ovulation
# ---------------------------------------------------------------------------
def test_cyc04_day15_ovulation():
    result = calculate_cycle_info(
        cycle_start_date=START,
        average_cycle_length=LEN28,
        reference_date="2026-08-15",
    )
    assert result["cycle_day"] == 15
    assert result["cycle_phase"] == "ovulation"


# ---------------------------------------------------------------------------
# TC-CYC05  Day 25 → luteal
# ---------------------------------------------------------------------------
def test_cyc05_day25_luteal():
    result = calculate_cycle_info(
        cycle_start_date=START,
        average_cycle_length=LEN28,
        reference_date="2026-08-25",
    )
    assert result["cycle_day"] == 25
    assert result["cycle_phase"] == "luteal"


# ---------------------------------------------------------------------------
# TC-CYC06  Day 29 → rollover: cycle_day=1, menstruation, cycle_number=1
# ---------------------------------------------------------------------------
def test_cyc06_rollover_day29():
    result = calculate_cycle_info(
        cycle_start_date=START,
        average_cycle_length=LEN28,
        reference_date="2026-08-29",
    )
    assert result["cycle_day"] == 1, (
        f"Expected cycle_day=1 after rollover, got {result['cycle_day']}"
    )
    assert result["cycle_phase"] == "menstruation"
    assert result["cycle_number"] == 1, (
        f"Expected cycle_number=1, got {result['cycle_number']}"
    )


# ---------------------------------------------------------------------------
# TC-CYC07  24-day cycle — phase boundaries must scale proportionally
#
# 28-day reference:   menstruation ends at day 5  (boundary = 5/28 * 28 = 5)
#                     follicular   ends at day 13 (boundary = 13/28 * 28 = 13)
#                     ovulation    ends at day 16 (boundary = 16/28 * 28 = 16)
#
# 24-day proportional: menstruation ends at round(24 * 5/28)  = round(4.29) = 4
#                       follicular   ends at round(24 * 13/28) = round(11.14) = 11
#                       ovulation    ends at round(24 * 16/28) = round(13.71) = 14
#
# So day 13 in a 24-day cycle is OVULATION (not follicular as in 28-day logic),
# which proves we are scaling, not hardcoding.
# ---------------------------------------------------------------------------
def test_cyc07_24day_proportional_scaling():
    start_24 = "2026-08-01"
    # day 13 of 24-day cycle: 2026-08-13
    result = calculate_cycle_info(
        cycle_start_date=start_24,
        average_cycle_length=24,
        reference_date="2026-08-13",
    )
    assert result["cycle_day"] == 13

    # Day 13 in a 28-day cycle would be follicular.
    # In a 24-day cycle, ovulation boundary = round(24 * 16/28) = 14,
    # so day 13 falls in OVULATION — not follicular.
    assert result["cycle_phase"] == "ovulation", (
        f"Expected 'ovulation' (proportional 24-day boundary), "
        f"got '{result['cycle_phase']}'. Phase boundaries are NOT scaling correctly."
    )

    # Also verify menstruation ends at day 4 (not day 5) in 24-day cycle
    result_day4 = calculate_cycle_info(
        cycle_start_date=start_24,
        average_cycle_length=24,
        reference_date="2026-08-04",
    )
    assert result_day4["cycle_day"] == 4
    assert result_day4["cycle_phase"] == "menstruation"

    result_day5 = calculate_cycle_info(
        cycle_start_date=start_24,
        average_cycle_length=24,
        reference_date="2026-08-05",
    )
    assert result_day5["cycle_day"] == 5
    assert result_day5["cycle_phase"] == "follicular", (
        "In a 24-day cycle day 5 should be follicular (menstruation ends at day 4)."
    )


# ---------------------------------------------------------------------------
# TC-CYC08  cycle_start_date in the future → ValueError
# ---------------------------------------------------------------------------
def test_cyc08_future_start_raises():
    with pytest.raises(ValueError, match="future"):
        calculate_cycle_info(
            cycle_start_date="2030-01-01",
            average_cycle_length=LEN28,
            reference_date="2026-08-15",
        )


# ---------------------------------------------------------------------------
# TC-CYC09  average_cycle_length=10 (too short) → ValueError
# ---------------------------------------------------------------------------
def test_cyc09_invalid_cycle_length_raises():
    with pytest.raises(ValueError, match="average_cycle_length"):
        calculate_cycle_info(
            cycle_start_date=START,
            average_cycle_length=10,
            reference_date="2026-08-15",
        )


# bonus: verify upper bound too
def test_cyc09b_cycle_length_too_long_raises():
    with pytest.raises(ValueError, match="average_cycle_length"):
        calculate_cycle_info(
            cycle_start_date=START,
            average_cycle_length=50,
            reference_date="2026-08-15",
        )


# ---------------------------------------------------------------------------
# TC-CYC10  has_phase_changed_since — same phase → False
# ---------------------------------------------------------------------------
def test_cyc10_no_phase_change():
    # Day 3 → menstruation; last_known_phase also menstruation
    result = has_phase_changed_since(
        cycle_start_date=START,
        average_cycle_length=LEN28,
        last_known_phase="menstruation",
        reference_date="2026-08-03",
    )
    assert result is False


# ---------------------------------------------------------------------------
# TC-CYC11  has_phase_changed_since — phase changed → True
# ---------------------------------------------------------------------------
def test_cyc11_phase_changed():
    # Day 10 → follicular; last_known_phase is menstruation
    result = has_phase_changed_since(
        cycle_start_date=START,
        average_cycle_length=LEN28,
        last_known_phase="menstruation",
        reference_date="2026-08-10",
    )
    assert result is True


# ---------------------------------------------------------------------------
# Additional sanity checks
# ---------------------------------------------------------------------------

def test_next_period_date_first_cycle():
    """next_period_estimated_date should be cycle_start_date + cycle_length."""
    result = calculate_cycle_info(
        cycle_start_date=START,
        average_cycle_length=LEN28,
        reference_date="2026-08-10",
    )
    assert result["next_period_estimated_date"] == "2026-08-29"


def test_next_period_date_after_rollover():
    """After rollover into cycle 1, next_period should be start + 2*length."""
    result = calculate_cycle_info(
        cycle_start_date=START,
        average_cycle_length=LEN28,
        reference_date="2026-08-29",  # cycle_number=1
    )
    assert result["next_period_estimated_date"] == "2026-09-26"


def test_same_day_start_is_valid():
    """reference_date == cycle_start_date must not raise (edge: 0 days elapsed)."""
    result = calculate_cycle_info(
        cycle_start_date="2026-08-15",
        average_cycle_length=LEN28,
        reference_date="2026-08-15",
    )
    assert result["days_since_cycle_start"] == 0
    assert result["cycle_day"] == 1


def test_last_day_of_cycle_is_luteal():
    """Day 28 of a 28-day cycle must be luteal."""
    result = calculate_cycle_info(
        cycle_start_date=START,
        average_cycle_length=LEN28,
        reference_date="2026-08-28",
    )
    assert result["cycle_day"] == 28
    assert result["cycle_phase"] == "luteal"
