"""Spread, confidence intervals and the conservative verdict rule."""

from __future__ import annotations

import math

import pytest

from performance_engineering_lab.stats import judge_absolute, judge_ratio, summarize, t95


def test_summary_of_known_values() -> None:
    s = summarize([1.0, 2.0, 3.0])
    assert (s.n, s.median, s.minimum, s.maximum, s.mean) == (3, 2.0, 1.0, 3.0, 2.0)
    half = 4.303 * 1.0 / math.sqrt(3)
    assert s.ci_low == pytest.approx(2.0 - half)
    assert s.ci_high == pytest.approx(2.0 + half)
    assert s.spread == pytest.approx(1.0)


def test_single_value_has_no_interval_and_bad_values_are_refused() -> None:
    assert math.isnan(summarize([5.0]).ci_low)
    with pytest.raises(ValueError, match="no values"):
        summarize([])
    with pytest.raises(ValueError, match="finite"):
        summarize([1.0, math.inf])
    with pytest.raises(ValueError, match="degree"):
        t95(0)
    assert t95(100) == 1.96


def test_ratio_verdicts_use_the_worst_case_range_across_forks() -> None:
    slow, fast = summarize([40.0, 42.0, 44.0]), summarize([9.0, 10.0, 11.0])
    v = judge_ratio(">=", 3.0, slow, fast, 3)
    assert v.status == "confirmed"
    assert v.measured == pytest.approx(4.2)
    assert v.low == pytest.approx(40 / 11)
    assert v.high == pytest.approx(44 / 9)
    assert judge_ratio(">=", 4.0, slow, fast, 3).status == "inconclusive"
    assert judge_ratio(">=", 5.0, slow, fast, 3).status == "refuted"
    assert judge_ratio("<=", 5.0, slow, fast, 3).status == "confirmed"
    assert judge_ratio("<=", 3.0, slow, fast, 3).status == "refuted"
    assert judge_ratio("<=", 4.5, slow, fast, 3).status == "inconclusive"


def test_too_few_forks_are_not_judged() -> None:
    a, b = summarize([4.0, 4.1]), summarize([1.0, 1.1, 1.2])
    assert judge_ratio(">=", 2.0, a, b, 3).status == "not judged"
    assert judge_absolute(">=", 16.0, summarize([24.0]), 3).status == "not judged"


def test_absolute_verdicts() -> None:
    cell = summarize([24.0, 24.0, 24.1])
    assert judge_absolute(">=", 16.0, cell, 3).status == "confirmed"
    assert judge_absolute("<=", 16.0, cell, 3).status == "refuted"
    assert judge_absolute(">=", 24.05, cell, 3).status == "inconclusive"
    with pytest.raises(ValueError, match="operator"):
        judge_absolute("==", 1.0, cell, 3)


def test_a_range_touching_the_threshold_is_inconclusive_not_refuted() -> None:
    num, den = summarize([2.5, 2.75, 3.0]), summarize([1.0, 1.0, 1.0])
    assert judge_ratio(">=", 3.0, num, den, 3).status == "inconclusive"
    assert judge_ratio("<=", 2.5, num, den, 3).status == "inconclusive"
