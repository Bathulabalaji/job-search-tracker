from datetime import date

import pytest

from app.models.enums import Source, Stage
from app.services.analytics_math import (
    OpportunityProgress,
    applied_and_responded,
    build_funnel,
    compute_streaks,
    furthest_step,
    percent_of_target,
    ratio,
    week_start,
)


def _opp(
    *stages: Stage, responded: bool = False, source: Source = Source.other
) -> OpportunityProgress:
    return OpportunityProgress(source=source, visited=frozenset(stages), responded=responded)


class TestFurthestStep:
    def test_defaults_to_found_when_only_exit_stages_seen(self) -> None:
        assert furthest_step([Stage.parked]) == 0

    def test_rejected_after_screening_keeps_screening_credit(self) -> None:
        assert furthest_step([Stage.found, Stage.applied, Stage.screening, Stage.rejected]) == 2

    def test_both_interview_stages_are_one_step(self) -> None:
        assert (
            furthest_step([Stage.interview_scheduled]) == furthest_step([Stage.interviewing]) == 3
        )


class TestFunnel:
    def test_counts_reached_not_current(self) -> None:
        progress = [
            _opp(Stage.found),
            _opp(Stage.found, Stage.applied),
            _opp(Stage.found, Stage.applied, Stage.screening, Stage.rejected),
            _opp(Stage.found, Stage.applied, Stage.screening, Stage.interviewing),
        ]
        funnel = {step.key: step for step in build_funnel(progress)}
        assert [
            funnel[k].count for k in ("found", "applied", "screening", "interview", "offer")
        ] == [
            4,
            3,
            2,
            1,
            0,
        ]

    def test_conversion_rates(self) -> None:
        progress = [_opp(Stage.found)] * 2 + [_opp(Stage.found, Stage.applied)] * 2
        funnel = {step.key: step for step in build_funnel(progress)}
        assert funnel["found"].conversion_from_previous is None
        assert funnel["applied"].conversion_from_previous == 0.5
        assert funnel["applied"].conversion_from_start == 0.5
        # Nobody reached screening: the rate from "applied" is 0, from "screening" onward undefined.
        assert funnel["screening"].conversion_from_previous == 0.0
        assert funnel["offer"].conversion_from_previous is None

    def test_empty_funnel_has_no_rates(self) -> None:
        funnel = build_funnel([])
        assert all(step.count == 0 for step in funnel)
        assert all(step.conversion_from_start is None for step in funnel)


class TestResponseRate:
    def test_only_counts_opportunities_that_were_applied_to(self) -> None:
        progress = [
            _opp(Stage.found, responded=True),  # replied but never applied: excluded
            _opp(Stage.applied, responded=True),
            _opp(Stage.applied),
            _opp(Stage.found, Stage.applied, Stage.rejected, responded=True),
        ]
        assert applied_and_responded(progress) == (3, 2)

    def test_ratio_handles_zero(self) -> None:
        assert ratio(1, 0) is None
        assert ratio(1, 4) == 0.25


class TestWeekAndTargets:
    @pytest.mark.parametrize(
        ("day", "monday"),
        [
            (date(2026, 11, 9), date(2026, 11, 9)),
            (date(2026, 11, 11), date(2026, 11, 9)),
            (date(2026, 11, 15), date(2026, 11, 9)),  # Sunday belongs to the previous Monday
            (date(2026, 11, 16), date(2026, 11, 16)),
        ],
    )
    def test_week_start(self, day: date, monday: date) -> None:
        assert week_start(day) == monday

    def test_percent_of_target(self) -> None:
        assert percent_of_target(5, 10) == 50.0
        assert percent_of_target(15, 10) == 150.0  # over target is allowed
        assert percent_of_target(3, 0) is None
        assert percent_of_target(3, None) is None


class TestStreaks:
    today = date(2026, 11, 11)

    def _days(self, *offsets: int) -> set[date]:
        return {date(2026, 11, 11).replace(day=11 + o) for o in offsets}

    def test_empty(self) -> None:
        assert compute_streaks(set(), self.today) == (0, 0)

    def test_run_ending_today(self) -> None:
        assert compute_streaks(self._days(0, -1, -2), self.today) == (3, 3)

    def test_today_not_logged_yet_does_not_break_streak(self) -> None:
        assert compute_streaks(self._days(-1, -2), self.today) == (2, 2)

    def test_gap_resets_current_but_keeps_longest(self) -> None:
        assert compute_streaks(self._days(0, -1, -5, -6, -7, -8), self.today) == (2, 4)

    def test_two_days_ago_is_a_broken_streak(self) -> None:
        assert compute_streaks(self._days(-2, -3), self.today) == (0, 2)
