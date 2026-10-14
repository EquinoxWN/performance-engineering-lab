"""Deterministic inputs shared by the Java, JavaScript and Python experiments (spec/experiments.md)."""

from __future__ import annotations

MASK32 = 0xFFFFFFFF
MAX_SIZE = 1 << 26


class XorShift32:
    """Marsaglia's xorshift32 on an unsigned 32-bit state."""

    __slots__ = ("_state",)

    def __init__(self, seed: int) -> None:
        """Start from a non-zero 32-bit seed."""
        if not 1 <= seed <= MASK32:
            raise ValueError(f"seed must be in 1..{MASK32}, got {seed}")
        self._state = seed

    def next(self) -> int:
        """Advance and return the next 32-bit value."""
        x = self._state
        x ^= (x << 13) & MASK32
        x ^= x >> 17
        x ^= (x << 5) & MASK32
        self._state = x
        return x


def _check_size(n: int) -> None:
    """Reject sizes outside 0..MAX_SIZE."""
    if not 0 <= n <= MAX_SIZE:
        raise ValueError(f"size must be in 0..{MAX_SIZE}, got {n}")


def values(n: int, seed: int, bits: int = 20) -> list[int]:
    """The top `bits` bits of n consecutive xorshift32 outputs."""
    _check_size(n)
    if not 1 <= bits <= 32:
        raise ValueError(f"bits must be in 1..32, got {bits}")
    rng = XorShift32(seed)
    shift = 32 - bits
    return [rng.next() >> shift for _ in range(n)]


def permutation(n: int, seed: int) -> list[int]:
    """Fisher-Yates shuffle of 0..n-1 driven by xorshift32 (j = next() mod (i + 1))."""
    _check_size(n)
    rng = XorShift32(seed)
    idx = list(range(n))
    for i in range(n - 1, 0, -1):
        j = rng.next() % (i + 1)
        idx[i], idx[j] = idx[j], idx[i]
    return idx


def fresh_ints(items: list[int]) -> list[int]:
    """Copy of the list whose large ints are new objects allocated in list order."""
    # `v ^ 0` builds a new int object (ints above 256 are not cached), so the objects of a
    # shuffled index list sit in memory in the order they are read, like those of the identity.
    return [v ^ 0 for v in items]


def weighted_checksum(perm: list[int]) -> int:
    """Sum of (i + 1) * perm[i], used to compare permutations across runtimes."""
    return sum((i + 1) * p for i, p in enumerate(perm))
