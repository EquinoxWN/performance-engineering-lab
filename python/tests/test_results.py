"""The three harness formats are read into per-fork samples, and malformed output is refused."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from performance_engineering_lab.results import (
    ResultError,
    load_results,
    parse_jmh,
    parse_mitata,
    parse_pyperf,
    scrub,
)


def test_jmh_output_gives_per_element_time_and_allocation(fixtures: Path) -> None:
    res = parse_jmh((fixtures / "jmh-boxing.json").read_text(encoding="utf-8"))
    assert {s.variant for s in res.samples} == {"int-array", "boxed-list", "boxed-accumulator"}
    acc = next(s for s in res.samples if s.variant == "boxed-accumulator")
    assert acc.runtime == "java"
    assert acc.experiment == "boxing"
    assert acc.size == 1048576
    assert acc.alloc_bytes_per_element is not None
    assert 23.9 < acc.alloc_bytes_per_element < 24.1
    assert 0 < acc.ns_per_element < 100
    assert res.infos[0].harness == "JMH"
    assert "-Xmx512m" in res.infos[0].flags


def test_jmh_fork_means_and_missing_allocation_profile() -> None:
    entry = {
        "benchmark": "x.BranchBench.run", "mode": "avgt", "jmhVersion": "1.37",
        "params": {"size": "100", "variant": "branchy-sorted"},
        "primaryMetric": {
            "score": 150.0, "scoreError": 30.0, "scoreUnit": "ns/op", "rawData": [[100.0, 200.0], [300.0]],
        },
    }  # fmt: skip
    res = parse_jmh(json.dumps([entry]))
    assert [s.ns_per_element for s in res.samples] == [1.5, 3.0]
    assert [s.fork for s in res.samples] == [0, 1]
    assert all(s.alloc_bytes_per_element is None for s in res.samples)
    assert res.native[("java", "branch", "branchy-sorted", 100)].startswith("1.5 ± 0.3")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"benchmark": "x.Other.run"}, "unknown benchmark"),
        ({"mode": "thrpt"}, "avgt"),
        ({"params": {"size": "100"}}, "params"),
        ({"params": {"size": "-5", "variant": "v"}}, "size"),
        ({"primaryMetric": {"scoreUnit": "us/op", "rawData": [[1.0]]}}, "ns/op"),
        ({"primaryMetric": {"scoreUnit": "ns/op", "rawData": []}}, "rawData"),
        ({"primaryMetric": {"scoreUnit": "ns/op", "rawData": [[float("nan")]]}}, "finite"),
    ],
)
def test_malformed_jmh_entries_are_refused(change: dict[str, object], message: str) -> None:
    entry: dict[str, object] = {
        "benchmark": "x.BranchBench.run", "mode": "avgt",
        "params": {"size": "100", "variant": "v"},
        "primaryMetric": {"scoreUnit": "ns/op", "rawData": [[1.0]]},
    }  # fmt: skip
    entry.update(change)
    with pytest.raises(ResultError, match=message):
        parse_jmh(json.dumps([entry]))
    with pytest.raises(ResultError):
        parse_jmh("not json")


def test_pyperf_output_skips_calibration_and_uses_values_per_element(fixtures: Path) -> None:
    res = parse_pyperf((fixtures / "pyperf.json").read_text(encoding="utf-8"))
    assert {s.variant for s in res.samples} == {"branchy-sorted", "branchy-shuffled"}
    assert all(s.runtime == "python" and s.size == 65536 and 1 < s.ns_per_element < 1000 for s in res.samples)
    assert res.infos[0].harness == "pyperf"
    assert res.infos[0].harness_version == "2.10.0"


def test_pyperf_requires_inner_loops_equal_to_size(fixtures: Path) -> None:
    data = json.loads((fixtures / "pyperf.json").read_text(encoding="utf-8"))
    data["benchmarks"][0]["metadata"]["inner_loops"] = 1
    with pytest.raises(ResultError, match="inner_loops"):
        parse_pyperf(json.dumps(data))
    data["benchmarks"][0]["metadata"].update(inner_loops=65536, name="bad name")
    with pytest.raises(ResultError, match="bad name"):
        parse_pyperf(json.dumps(data))
    with pytest.raises(ResultError, match=r"version 1.0"):
        parse_pyperf(json.dumps({"benchmarks": []}))


def test_mitata_lines_become_one_sample_per_process(fixtures: Path) -> None:
    text = (fixtures / "mitata.jsonl").read_text(encoding="utf-8")
    res = parse_mitata(text + text)
    assert len(res.samples) == 6
    assert sorted({s.fork for s in res.samples}) == [0, 1]
    assert res.infos[0].runtime_version.startswith("Node.js v24")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"extra": 1}, "exactly the fields"),
        ({"harness": "benchmark.js"}, "exactly the fields"),
        ({"ns_per_call": {"avg": 1.0}}, "avg, p50"),
        ({"ns_per_call": {"avg": -1.0, "p50": 1, "min": 1, "max": 1}}, "non-negative"),
        ({"exec_argv": "--x"}, "exec_argv"),
        ({"variant": ""}, "variant"),
    ],
)
def test_malformed_mitata_lines_are_refused(fixtures: Path, change: dict[str, object], message: str) -> None:
    rec = json.loads((fixtures / "mitata.jsonl").read_text(encoding="utf-8").splitlines()[0])
    rec.update(change)
    with pytest.raises(ResultError, match=message):
        parse_mitata(json.dumps(rec))


def test_oversized_mitata_line_is_refused() -> None:
    with pytest.raises(ResultError, match="longer than"):
        parse_mitata("x" * (1 << 17))


def test_load_results_reads_every_harness_file_and_scrubs_paths(fixtures: Path, tmp_path: Path) -> None:
    for name in ("jmh-boxing.json", "pyperf.json", "mitata.jsonl"):
        (tmp_path / name).write_text((fixtures / name).read_text(encoding="utf-8"), encoding="utf-8")
    res = load_results(tmp_path)
    assert {s.runtime for s in res.samples} == {"java", "python", "js"}
    assert scrub("-Djava.io.tmpdir=C:/r/x/.tmp", Path("C:/r/x")) == "-Djava.io.tmpdir=<repo>/.tmp"
