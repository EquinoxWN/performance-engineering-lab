"""The spec loader accepts the real spec and refuses every kind of inconsistency."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from performance_engineering_lab.spec import RUNTIMES, Spec, SpecError, load_spec, parse_spec


def test_real_spec_has_a_hypothesis_for_every_cell(spec: Spec) -> None:
    assert len(spec.hypotheses) == 19
    covered = {(h.runtime, h.experiment, h.size) for h in spec.hypotheses}
    for rt in RUNTIMES:
        for experiment, _, size in spec.cells(rt):
            assert (rt, experiment, size) in covered
    assert {len(spec.cells(rt)) for rt in RUNTIMES} == {11}


def test_hypotheses_name_only_variants_their_runtime_measures(spec: Spec) -> None:
    for h in spec.hypotheses:
        plan = spec.experiment(h.experiment).runtimes[h.runtime]
        assert set(h.variants()) <= set(plan.variants)
        assert h.size in plan.sizes


def _set(path: list[Any], value: Any) -> Callable[[dict[str, Any]], None]:
    """A mutation that sets one nested value."""

    def apply(raw: dict[str, Any]) -> None:
        node: Any = raw
        for p in path[:-1]:
            node = node[p]
        node[path[-1]] = value

    return apply


def _drop_hypothesis(hid: str) -> Callable[[dict[str, Any]], None]:
    """A mutation that removes one hypothesis."""

    def apply(raw: dict[str, Any]) -> None:
        raw["hypotheses"] = [h for h in raw["hypotheses"] if h["id"] != hid]

    return apply


def _duplicate_first_hypothesis(raw: dict[str, Any]) -> None:
    raw["hypotheses"].append(dict(raw["hypotheses"][0]))


def _extra_top_key(raw: dict[str, Any]) -> None:
    raw["unexpected"] = 1


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (_drop_hypothesis("H02"), "has no hypothesis"),
        (_duplicate_first_hypothesis, "duplicate ids"),
        (_extra_top_key, "unexpected"),
        (_set(["hypotheses", 0, "numerator"], "random"), "numerator"),
        (_set(["hypotheses", 0, "denominator"], "shuffled"), "same variant"),
        (_set(["hypotheses", 0, "size"], 1234), "is not a java size"),
        (_set(["hypotheses", 0, "op"], ">"), "op"),
        (_set(["hypotheses", 0, "runtime"], "go"), "runtime"),
        (_set(["hypotheses", 0, "kind"], "difference"), "kind"),
        (_set(["hypotheses", 0, "value"], True), "value"),
        (_set(["hypotheses", 0, "experiment"], "nope"), "unknown experiment"),
        (_set(["experiments", 0, "runtimes", "java", "sizes"], [4096, 4096]), "duplicate sizes"),
        (_set(["experiments", 0, "runtimes", "java", "sizes"], [0]), "sizes"),
        (_set(["experiments", 0, "runtimes", "java", "variants"], []), "non-empty list"),
        (_set(["profiles", "full", "java", "forks"], 0), "forks"),
        (_set(["profiles", "full", "js", "min_cpu_ms"], "642"), "min_cpu_ms"),
        (_set(["data", "value_seed"], 0), "value_seed"),
        (_set(["profiles", "full", "js", "node_flags"], ["--prof=../x"]), "node_flags"),
        (_set(["settings", "noise_threshold"], 5), "noise_threshold"),
    ],
)
def test_inconsistent_specs_are_refused(
    raw_spec: dict[str, Any], mutate: Callable[[dict[str, Any]], None], message: str
) -> None:
    mutate(raw_spec)
    with pytest.raises(SpecError, match=message):
        parse_spec(raw_spec)


def test_allocation_metric_only_on_java(raw_spec: dict[str, Any]) -> None:
    h = next(h for h in raw_spec["hypotheses"] if h["kind"] == "absolute")
    h.update(runtime="js", variant="object-array", experiment="boxing")
    with pytest.raises(SpecError, match="only measured on java"):
        parse_spec(raw_spec)


def test_oversized_and_broken_files_are_refused(tmp_path: Path) -> None:
    big = tmp_path / "big.json"
    big.write_bytes(b" " * ((1 << 20) + 1))
    with pytest.raises(SpecError, match="larger than"):
        load_spec(big)
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(SpecError):
        load_spec(bad)
    with pytest.raises(SpecError):
        load_spec(tmp_path / "missing.json")
    good = tmp_path / "list.json"
    good.write_text(json.dumps([]), encoding="utf-8")
    with pytest.raises(SpecError, match="expected an object"):
        load_spec(good)
