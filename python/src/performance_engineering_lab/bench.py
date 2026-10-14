"""pyperf benchmarks for every Python cell of spec/experiments.json.

Run through the runner (`python -m performance_engineering_lab.run`) or directly:
`python -m performance_engineering_lab.bench -o .tmp/results/pyperf.json --processes 5`.
pyperf starts one fresh worker process per run (it re-runs this file as a script, hence the
absolute imports); each worker builds only its own input.
"""

from __future__ import annotations

import argparse
import time
from array import array
from collections.abc import Callable
from functools import cache
from typing import Any

import pyperf

from performance_engineering_lab import datasets, kernels
from performance_engineering_lab.spec import Spec, load_spec

Prepared = tuple[Callable[[], int], int]


def prepare(spec: Spec, experiment: str, variant: str, size: int) -> Prepared:
    """The measured call and the result it must return, for one cell."""
    vs, ps = spec.data.value_seed, spec.data.permutation_seed
    if experiment == "access-pattern":
        data = datasets.values(size, vs, spec.data.value_bits)
        if variant == "sequential":
            idx = datasets.fresh_ints(list(range(size)))
        elif variant == "shuffled":
            idx = datasets.fresh_ints(datasets.permutation(size, ps))
        else:
            raise ValueError(f"unknown access-pattern variant {variant!r}")
        return (lambda: kernels.gather(data, idx)), sum(data)
    if experiment == "branch":
        raw = datasets.values(size, vs, spec.data.byte_bits)
        expected = sum(v for v in raw if v >= 128)
        kernel_name, _, order = variant.partition("-")
        if order not in ("sorted", "shuffled") or kernel_name not in ("branchy", "branchless"):
            raise ValueError(f"unknown branch variant {variant!r}")
        values = sorted(raw) if order == "sorted" else raw
        kernel = kernels.branchy if kernel_name == "branchy" else kernels.branchless
        return (lambda: kernel(values)), expected
    if experiment == "boxing":
        ints = datasets.values(size, vs, spec.data.value_bits)
        expected = sum(ints)
        if variant == "list":
            return (lambda: kernels.total(ints)), expected
        if variant == "array":
            packed = array("q", ints)
            return (lambda: kernels.total(packed)), expected
        if variant == "objects":
            items = [kernels.Item(v) for v in ints]
            return (lambda: kernels.total_attr(items)), expected
        raise ValueError(f"unknown boxing variant {variant!r}")
    raise ValueError(f"unknown experiment {experiment!r}")


@cache
def _prepared(experiment: str, variant: str, size: int) -> Prepared:
    """Build a cell's input once per worker process and check its result."""
    call, expected = prepare(load_spec(), experiment, variant, size)
    got = call()
    if got != expected:
        raise RuntimeError(f"{experiment}/{variant}/{size}: result {got} != expected {expected}")
    return call, expected


def time_cell(loops: int, experiment: str, variant: str, size: int) -> float:
    """Seconds for `loops` calls of the cell's kernel (input built outside the timing)."""
    call, _ = _prepared(experiment, variant, size)
    t0 = time.perf_counter()
    for _ in range(loops):
        call()
    return time.perf_counter() - t0


def bench_name(experiment: str, variant: str, size: int) -> str:
    """pyperf benchmark name of a cell."""
    return f"{experiment}/{variant}/{size}"


def _forward_only(cmd: list[str], args: argparse.Namespace) -> None:
    """Pass --only on to pyperf's worker processes."""
    if args.only:
        cmd.extend(("--only", args.only))


def selected_cells(spec: Spec, only: str | None) -> list[tuple[str, str, int]]:
    """Python cells whose name starts with `only` (all when None)."""
    cells = spec.cells("python")
    if only:
        cells = [c for c in cells if bench_name(*c).startswith(only)]
        if not cells:
            raise SystemExit(f"--only {only!r} matches no benchmark")
    return cells


def main() -> None:
    """Register every selected cell with pyperf and let it run them."""
    runner: Any = pyperf.Runner(add_cmdline_args=_forward_only)
    runner.argparser.add_argument("--only", default=None, help="run only benchmarks whose name starts with this")
    args = runner.parse_args()
    spec = load_spec()
    runner.metadata["perflab_spec_version"] = "1"
    for experiment, variant, size in selected_cells(spec, args.only):
        # inner_loops=size makes every pyperf value a time per element.
        runner.bench_time_func(
            bench_name(experiment, variant, size), time_cell, experiment, variant, size, inner_loops=size
        )


if __name__ == "__main__":
    main()
