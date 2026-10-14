"""The shared inputs match the spec checksums, and every variant of an experiment computes the same result."""

from __future__ import annotations

import random
from array import array

import pytest

from performance_engineering_lab import datasets, kernels
from performance_engineering_lab.bench import prepare
from performance_engineering_lab.spec import Spec


def test_xorshift32_matches_the_reference_sequence(spec: Spec) -> None:
    rng = datasets.XorShift32(1)
    assert [rng.next() for _ in range(3)] == spec.checks["xorshift32_seed1_first"]


@pytest.mark.parametrize("seed", [0, -1, 1 << 32])
def test_xorshift32_rejects_seeds_outside_32_bits(seed: int) -> None:
    with pytest.raises(ValueError, match="seed"):
        datasets.XorShift32(seed)


def test_values_permutation_and_bytes_match_the_spec_checksums(spec: Spec) -> None:
    d, c = spec.data, spec.checks
    v = datasets.values(4096, d.value_seed, d.value_bits)
    assert sum(v) == c["values_4096"]["sum"]
    assert v[:3] == c["values_4096"]["first"]
    p = datasets.permutation(4096, d.permutation_seed)
    assert datasets.weighted_checksum(p) == c["permutation_4096"]["weighted"]
    assert p[:3] == c["permutation_4096"]["first"]
    b = datasets.values(65536, d.value_seed, d.byte_bits)
    assert sum(x for x in b if x >= 128) == c["bytes_65536"]["sum_at_least_128"]
    assert sum(1 for x in b if x >= 128) == c["bytes_65536"]["count_at_least_128"]


def test_permutation_is_a_permutation_for_random_sizes() -> None:
    rnd = random.Random(7)
    for _ in range(50):
        n = rnd.randint(0, 3000)
        assert sorted(datasets.permutation(n, rnd.randint(1, 2**32 - 1))) == list(range(n))


def test_values_stay_within_their_bit_width() -> None:
    assert all(0 <= x < 1 << 20 for x in datasets.values(5000, 99, 20))
    assert all(0 <= x < 256 for x in datasets.values(5000, 99, 8))


@pytest.mark.parametrize(("n", "bits"), [(-1, 20), (datasets.MAX_SIZE + 1, 20), (10, 0), (10, 33)])
def test_values_reject_bad_sizes_and_widths(n: int, bits: int) -> None:
    with pytest.raises(ValueError, match="must be in"):
        datasets.values(n, 1, bits)


def test_fresh_ints_copies_values_into_new_objects() -> None:
    src = [10**6 + i for i in range(100)]
    out = datasets.fresh_ints(src)
    assert out == src
    assert all(a is not b for a, b in zip(out, src, strict=True))


def test_variants_agree_for_random_inputs() -> None:
    rnd = random.Random(11)
    for _ in range(200):
        n = rnd.randint(0, 400)
        seed = rnd.randint(1, 2**32 - 1)
        data = datasets.values(n, seed, 20)
        perm = datasets.permutation(n, seed ^ 0x5A5A5A5A or 1)
        assert kernels.gather(data, perm) == kernels.gather(data, range(n)) == sum(data)
        b = datasets.values(n, seed, 8)
        assert kernels.branchy(b) == kernels.branchless(b) == kernels.branchy(sorted(b))
        assert kernels.total(data) == kernels.total(array("q", data)) == kernels.total_attr(map(kernels.Item, data))


def test_branch_kernels_on_the_edge_values() -> None:
    edge = [0, 127, 128, 255]
    assert kernels.branchy(edge) == kernels.branchless(edge) == 383
    assert kernels.branchy([]) == kernels.branchless([]) == kernels.total([]) == 0


def test_every_python_cell_prepares_and_returns_its_expected_result(spec: Spec) -> None:
    for experiment, variant, _ in spec.cells("python"):
        call, expected = prepare(spec, experiment, variant, 3000)
        assert call() == expected, (experiment, variant)


@pytest.mark.parametrize(("experiment", "variant"), [("branch", "branchy-random"), ("boxing", "tuple"), ("x", "y")])
def test_prepare_rejects_unknown_cells(spec: Spec, experiment: str, variant: str) -> None:
    with pytest.raises(ValueError, match="unknown"):
        prepare(spec, experiment, variant, 10)
