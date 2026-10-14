"""Read JMH, pyperf and mitata output into one validated list of per-fork samples."""

from __future__ import annotations

import json
import math
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MAX_RESULT_BYTES = 64 << 20
MAX_LINE_BYTES = 1 << 16
JMH_CLASSES = {"AccessPatternBench": "access-pattern", "BranchBench": "branch", "BoxingBench": "boxing"}
MITATA_KEYS = {
    "harness", "harness_version", "runtime_version", "v8", "exec_argv", "experiment", "variant", "size",
    "checksum", "samples", "ns_per_call",
}  # fmt: skip
CellKey = tuple[str, str, str, int]


class ResultError(ValueError):
    """A result file is malformed or does not match the expected harness format."""


@dataclass(frozen=True)
class Sample:
    """One fork's (one process's) estimate for one cell."""

    runtime: str
    experiment: str
    variant: str
    size: int
    fork: int
    ns_per_element: float
    alloc_bytes_per_element: float | None = None

    @property
    def key(self) -> CellKey:
        """The cell this sample belongs to."""
        return (self.runtime, self.experiment, self.variant, self.size)


@dataclass(frozen=True)
class HarnessInfo:
    """Harness and runtime versions and flags, with local paths removed."""

    runtime: str
    harness: str
    harness_version: str
    runtime_version: str
    flags: tuple[str, ...]


@dataclass
class Results:
    """Everything read from one results folder."""

    samples: list[Sample] = field(default_factory=list)
    infos: list[HarnessInfo] = field(default_factory=list)
    native: dict[CellKey, str] = field(default_factory=dict)

    def extend(self, other: Results) -> None:
        """Add another file's results."""
        self.samples.extend(other.samples)
        self.infos.extend(i for i in other.infos if i not in self.infos)
        self.native.update(other.native)


def scrub(text: str, repo: Path | None) -> str:
    """Replace the repository path (either slash style) with <repo>."""
    if repo is None:
        return text
    for form in {str(repo), repo.as_posix()}:
        text = text.replace(form, "<repo>")
    return text


def _finite(value: Any, where: str) -> float:
    """A finite, non-negative number."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or value < 0:
        raise ResultError(f"{where}: expected a finite non-negative number, got {value!r}")
    return float(value)


def _size(value: Any, where: str) -> int:
    """A positive element count given as an int or a decimal string."""
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,8}", value):
        return int(value)
    if isinstance(value, int) and not isinstance(value, bool) and 0 < value < 10**9:
        return value
    raise ResultError(f"{where}: expected a positive size, got {value!r}")


def _fork_means(raw: Any, where: str) -> list[float]:
    """Mean of each fork's iteration scores from a JMH rawData array."""
    if not isinstance(raw, list) or not raw:
        raise ResultError(f"{where}: rawData must be a non-empty list of forks")
    out = []
    for i, fork in enumerate(raw):
        if not isinstance(fork, list) or not fork:
            raise ResultError(f"{where}: fork {i} has no iterations")
        out.append(statistics.fmean(_finite(v, f"{where}[{i}]") for v in fork))
    return out


def _num_or_nan(value: Any) -> float:
    """JMH writes "NaN" as a string when an error cannot be computed."""
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else math.nan


def parse_jmh(text: str, repo: Path | None = None) -> Results:
    """JMH -rf json output (avgt mode, ns/op, optional -prof gc)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ResultError(f"JMH: not JSON: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise ResultError("JMH: expected a non-empty list of benchmark entries")
    out = Results()
    for n, entry in enumerate(data):
        where = f"JMH entry {n}"
        if not isinstance(entry, dict):
            raise ResultError(f"{where}: expected an object")
        name = entry.get("benchmark")
        parts = name.split(".") if isinstance(name, str) else []
        if len(parts) < 2 or parts[-1] != "run" or parts[-2] not in JMH_CLASSES:
            raise ResultError(f"{where}: unknown benchmark {name!r}")
        if entry.get("mode") != "avgt":
            raise ResultError(f"{where}: expected mode avgt, got {entry.get('mode')!r}")
        params = entry.get("params")
        if not isinstance(params, dict) or set(params) != {"size", "variant"} or not isinstance(params["variant"], str):
            raise ResultError(f"{where}: params must be exactly size and variant")
        size = _size(params["size"], f"{where}.params.size")
        pm = entry.get("primaryMetric")
        if not isinstance(pm, dict) or pm.get("scoreUnit") != "ns/op":
            raise ResultError(f"{where}: primaryMetric must be in ns/op")
        times = _fork_means(pm.get("rawData"), f"{where}.primaryMetric")
        allocs: list[float | None] = [None] * len(times)
        norm = (entry.get("secondaryMetrics") or {}).get("gc.alloc.rate.norm")
        if norm is not None:
            if not isinstance(norm, dict) or norm.get("scoreUnit") != "B/op":
                raise ResultError(f"{where}: gc.alloc.rate.norm must be in B/op")
            fork_allocs = _fork_means(norm.get("rawData"), f"{where}.gc.alloc.rate.norm")
            if len(fork_allocs) != len(times):
                raise ResultError(f"{where}: allocation and time fork counts differ")
            allocs = [a / size for a in fork_allocs]
        experiment = JMH_CLASSES[parts[-2]]
        variant = params["variant"]
        for fork, (t, a) in enumerate(zip(times, allocs, strict=True)):
            out.samples.append(Sample("java", experiment, variant, size, fork, t / size, a))
        score, err = _num_or_nan(pm.get("score")), _num_or_nan(pm.get("scoreError"))
        if math.isfinite(err):
            out.native[("java", experiment, variant, size)] = f"{score / size:.4g} ± {err / size:.2g} (99.9%)"
        args = entry.get("jvmArgs")
        flags = tuple(scrub(a, repo) for a in args if isinstance(a, str)) if isinstance(args, list) else ()
        info = HarnessInfo(
            "java",
            "JMH",
            str(entry.get("jmhVersion", "?")),
            f"{entry.get('vmName', '?')} {entry.get('vmVersion', '?')}",
            flags,
        )
        if info not in out.infos:
            out.infos.append(info)
    return out


def parse_pyperf(text: str, repo: Path | None = None) -> Results:
    """pyperf JSON (benchmarks named experiment/variant/size, inner_loops = size)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ResultError(f"pyperf: not JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != "1.0" or not isinstance(data.get("benchmarks"), list):
        raise ResultError("pyperf: expected a version 1.0 suite with a benchmarks list")
    common = data.get("metadata") or {}
    if not isinstance(common, dict):
        raise ResultError("pyperf: metadata must be an object")
    out = Results()
    for n, bench in enumerate(data["benchmarks"]):
        if not isinstance(bench, dict) or not isinstance(bench.get("runs"), list):
            raise ResultError(f"pyperf benchmark {n}: expected an object with runs")
        md = {**common, **(bench.get("metadata") or {})}
        name = md.get("name")
        m = re.fullmatch(
            r"([a-z][a-z0-9-]*)/([a-z][a-z0-9-]*)/([1-9][0-9]{0,8})", name if isinstance(name, str) else ""
        )
        if m is None:
            raise ResultError(f"pyperf benchmark {n}: bad name {name!r}")
        experiment, variant, size = m[1], m[2], int(m[3])
        if md.get("inner_loops") != size:
            raise ResultError(f"pyperf {name}: inner_loops must equal the size so values are per element")
        everything: list[float] = []
        fork = 0
        for run in bench["runs"]:
            values = run.get("values") if isinstance(run, dict) else None
            if values is None:
                continue  # calibration run: warm-ups only
            if not isinstance(values, list) or not values:
                raise ResultError(f"pyperf {name}: run without values")
            ns = [_finite(v, f"pyperf {name}") * 1e9 for v in values]
            everything.extend(ns)
            out.samples.append(Sample("python", experiment, variant, size, fork, statistics.fmean(ns)))
            fork += 1
        if fork == 0:
            raise ResultError(f"pyperf {name}: no measured runs")
        if len(everything) > 1:
            mean, sd = statistics.fmean(everything), statistics.stdev(everything)
            out.native[("python", experiment, variant, size)] = f"{mean:.4g} ± {sd:.2g} (std dev)"
    out.infos.append(
        HarnessInfo(
            "python",
            "pyperf",
            str(common.get("perf_version", "?")),
            f"{common.get('python_implementation', '?')} {common.get('python_version', '?')}",
            (scrub(str(common.get("python_compiler", "")), repo),),
        )
    )
    return out


def parse_mitata(text: str, repo: Path | None = None) -> Results:
    """JSON lines printed by js/src/bench.js, one per Node.js process."""
    out = Results()
    forks: dict[CellKey, int] = {}
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if len(line) > MAX_LINE_BYTES:
            raise ResultError(f"mitata line {n}: longer than {MAX_LINE_BYTES} bytes")
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ResultError(f"mitata line {n}: not JSON: {exc}") from exc
        if not isinstance(rec, dict) or set(rec) != MITATA_KEYS or rec["harness"] != "mitata":
            raise ResultError(f"mitata line {n}: expected exactly the fields {sorted(MITATA_KEYS)}")
        size = _size(rec["size"], f"mitata line {n}.size")
        stats = rec["ns_per_call"]
        if not isinstance(stats, dict) or set(stats) != {"avg", "p50", "min", "max"}:
            raise ResultError(f"mitata line {n}: ns_per_call must hold avg, p50, min and max")
        avg = _finite(stats["avg"], f"mitata line {n}.avg")
        for field_name in ("experiment", "variant", "harness_version", "runtime_version", "v8"):
            if not isinstance(rec[field_name], str) or not rec[field_name]:
                raise ResultError(f"mitata line {n}: {field_name} must be a non-empty string")
        key: CellKey = ("js", rec["experiment"], rec["variant"], size)
        fork = forks.get(key, 0)
        forks[key] = fork + 1
        out.samples.append(Sample("js", rec["experiment"], rec["variant"], size, fork, avg / size))
        argv = rec["exec_argv"]
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
            raise ResultError(f"mitata line {n}: exec_argv must be a list of strings")
        info = HarnessInfo(
            "js",
            "mitata",
            rec["harness_version"],
            f"Node.js {rec['runtime_version']} (V8 {rec['v8']})",
            tuple(scrub(a, repo) for a in argv),
        )
        if info not in out.infos:
            out.infos.append(info)
    return out


def _read(path: Path) -> str:
    """Read a result file of at most 64 MiB."""
    if path.stat().st_size > MAX_RESULT_BYTES:
        raise ResultError(f"{path.name}: larger than {MAX_RESULT_BYTES} bytes")
    return path.read_text(encoding="utf-8")


def load_results(folder: Path, repo: Path | None = None) -> Results:
    """Every jmh-*.json, pyperf.json and mitata.jsonl in the folder."""
    out = Results()
    for path in sorted(folder.glob("jmh-*.json")):
        out.extend(parse_jmh(_read(path), repo))
    if (folder / "pyperf.json").is_file():
        out.extend(parse_pyperf(_read(folder / "pyperf.json"), repo))
    if (folder / "mitata.jsonl").is_file():
        out.extend(parse_mitata(_read(folder / "mitata.jsonl"), repo))
    return out
