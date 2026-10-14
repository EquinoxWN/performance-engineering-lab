"""The measured loops. Variants of one experiment do the same arithmetic on the same values."""

from __future__ import annotations

from collections.abc import Iterable, Sequence


class Item:
    """An object with one integer field, for the boxing experiment."""

    __slots__ = ("v",)

    def __init__(self, v: int) -> None:
        """Hold one value."""
        self.v = v


def gather(data: Sequence[int], idx: Iterable[int]) -> int:
    """Sum data[i] for every i in idx, in idx order."""
    s = 0
    for i in idx:
        s += data[i]
    return s


def branchy(values: Iterable[int]) -> int:
    """Sum of the values >= 128, with an if."""
    s = 0
    for v in values:
        if v >= 128:
            s += v
    return s


def branchless(values: Iterable[int]) -> int:
    """Sum of the byte values >= 128, with a mask from bit 7 instead of an if."""
    s = 0
    for v in values:
        s += v & -(v >> 7)
    return s


def total(values: Iterable[int]) -> int:
    """Sum of the values with an explicit loop (the same loop for list and array)."""
    s = 0
    for v in values:
        s += v
    return s


def total_attr(items: Iterable[Item]) -> int:
    """Sum of the v field of every item."""
    s = 0
    for item in items:
        s += item.v
    return s
