"""Spread, confidence intervals and hypothesis verdicts over per-fork (per-process) estimates."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Literal

# Two-sided 95% Student t quantiles for 1..30 degrees of freedom.
_T95 = (
    12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
    2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
    2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042,
)  # fmt: skip

Status = Literal["confirmed", "refuted", "inconclusive", "not judged"]


def t95(df: int) -> float:
    """Two-sided 95% t quantile (normal approximation above 30 degrees of freedom)."""
    if df < 1:
        raise ValueError("need at least 1 degree of freedom")
    return _T95[df - 1] if df <= len(_T95) else 1.96


@dataclass(frozen=True)
class Summary:
    """One cell's per-fork estimates reduced to centre and spread."""

    n: int
    median: float
    minimum: float
    maximum: float
    mean: float
    ci_low: float
    ci_high: float

    @property
    def spread(self) -> float:
        """(max - min) / median: the range across forks relative to the median."""
        return (self.maximum - self.minimum) / self.median if self.median else math.inf


def summarize(values: list[float]) -> Summary:
    """Median, min, max, mean and the 95% t interval of the mean."""
    if not values:
        raise ValueError("no values to summarize")
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("values must be finite and non-negative")
    mean = statistics.fmean(values)
    half = t95(len(values) - 1) * statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else math.nan
    return Summary(
        n=len(values),
        median=statistics.median(values),
        minimum=min(values),
        maximum=max(values),
        mean=mean,
        ci_low=mean - half,
        ci_high=mean + half,
    )


@dataclass(frozen=True)
class Verdict:
    """The measured value of a hypothesis, its conservative range and the outcome."""

    status: Status
    measured: float
    low: float
    high: float
    reason: str


def _decide(op: str, threshold: float, low: float, high: float) -> Status:
    """Confirmed if the whole range satisfies the prediction, refuted if none of it does."""
    if op == ">=":
        if low >= threshold:
            return "confirmed"
        return "refuted" if high < threshold else "inconclusive"
    if op == "<=":
        if high <= threshold:
            return "confirmed"
        return "refuted" if low > threshold else "inconclusive"
    raise ValueError(f"unknown operator {op!r}")


def judge_ratio(op: str, threshold: float, num: Summary, den: Summary, min_forks: int) -> Verdict:
    """Ratio of medians, with the range min(num)/max(den) .. max(num)/min(den) across forks."""
    measured = num.median / den.median
    low, high = num.minimum / den.maximum, num.maximum / den.minimum
    if min(num.n, den.n) < min_forks:
        return Verdict("not judged", measured, low, high, f"fewer than {min_forks} forks per variant")
    return Verdict(_decide(op, threshold, low, high), measured, low, high, "worst-case range across forks")


def judge_absolute(op: str, threshold: float, cell: Summary, min_forks: int) -> Verdict:
    """Median of one variant's metric, with its min..max range across forks."""
    if cell.n < min_forks:
        return Verdict("not judged", cell.median, cell.minimum, cell.maximum, f"fewer than {min_forks} forks")
    status = _decide(op, threshold, cell.minimum, cell.maximum)
    return Verdict(status, cell.median, cell.minimum, cell.maximum, "min..max across forks")
