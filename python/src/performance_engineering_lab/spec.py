"""Strict loader for spec/experiments.json: experiments, hypotheses, harness profiles and checks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

RUNTIMES = ("java", "js", "python")
OPS = (">=", "<=")
METRICS = ("ns_per_element", "alloc_bytes_per_element")
MAX_SPEC_BYTES = 1 << 20
MAX_BENCH_SIZE = 1 << 26
# V8 flags a profile may pass to node: plain switches only, no paths or values that name files.
NODE_FLAG = re.compile(r"--[a-z][a-z0-9-]{1,60}")

Runtime = Literal["java", "js", "python"]


class SpecError(ValueError):
    """The spec file is missing, malformed or inconsistent."""


@dataclass(frozen=True)
class RuntimePlan:
    """Sizes and variant names one runtime runs for one experiment."""

    sizes: tuple[int, ...]
    variants: tuple[str, ...]


@dataclass(frozen=True)
class Experiment:
    """One effect, measured as several variants of the same work."""

    id: str
    effect: str
    kernel: str
    runtimes: dict[str, RuntimePlan]


@dataclass(frozen=True)
class Hypothesis:
    """A prediction written before the measurement, judged from the results."""

    id: str
    runtime: str
    experiment: str
    size: int
    statement: str
    why: str
    kind: Literal["ratio", "absolute"]
    op: Literal[">=", "<="]
    value: float
    metric: str
    numerator: str | None = None
    denominator: str | None = None
    variant: str | None = None

    def variants(self) -> tuple[str, ...]:
        """Variant names the verdict needs."""
        if self.kind == "ratio" and self.numerator is not None and self.denominator is not None:
            return (self.numerator, self.denominator)
        if self.kind == "absolute" and self.variant is not None:
            return (self.variant,)
        raise SpecError(f"{self.id}: incomplete hypothesis")


@dataclass(frozen=True)
class JavaProfile:
    """JMH forks and iteration counts."""

    forks: int
    warmup_iterations: int
    iterations: int
    iteration_ms: int


@dataclass(frozen=True)
class PythonProfile:
    """pyperf worker processes and values per process."""

    processes: int
    values: int
    warmups: int
    min_time: float


@dataclass(frozen=True)
class JsProfile:
    """Fresh Node.js processes per mitata benchmark, mitata's minimum sampling time, extra V8 flags."""

    processes: int
    min_cpu_ms: int
    node_flags: tuple[str, ...]


@dataclass(frozen=True)
class Profile:
    """Harness settings for every runtime."""

    java: JavaProfile
    python: PythonProfile
    js: JsProfile


@dataclass(frozen=True)
class DataSpec:
    """Seeds and bit widths of the shared inputs."""

    value_seed: int
    permutation_seed: int
    value_bits: int
    byte_bits: int


@dataclass(frozen=True)
class Spec:
    """The whole experiment plan."""

    data: DataSpec
    checks: dict[str, Any]
    noise_threshold: float
    min_forks_for_verdict: int
    profiles: dict[str, Profile]
    experiments: tuple[Experiment, ...]
    hypotheses: tuple[Hypothesis, ...]

    def experiment(self, experiment_id: str) -> Experiment:
        """The experiment with this id."""
        for e in self.experiments:
            if e.id == experiment_id:
                return e
        raise SpecError(f"unknown experiment {experiment_id!r}")

    def cells(self, runtime: str) -> list[tuple[str, str, int]]:
        """Every (experiment, variant, size) one runtime must measure, in spec order."""
        out: list[tuple[str, str, int]] = []
        for e in self.experiments:
            plan = e.runtimes.get(runtime)
            if plan is None:
                continue
            out.extend((e.id, v, s) for s in plan.sizes for v in plan.variants)
        return out


def default_spec_path() -> Path:
    """spec/experiments.json at the repository root."""
    return Path(__file__).resolve().parents[3] / "spec" / "experiments.json"


def _obj(value: Any, where: str, keys: set[str], optional: set[str] | None = None) -> dict[str, Any]:
    """A JSON object with exactly the given keys (plus optional ones)."""
    if not isinstance(value, dict):
        raise SpecError(f"{where}: expected an object")
    allowed = keys | (optional or set())
    missing = keys - value.keys()
    extra = value.keys() - allowed
    if missing:
        raise SpecError(f"{where}: missing {sorted(missing)}")
    if extra:
        raise SpecError(f"{where}: unexpected {sorted(extra)}")
    return value


def _int(value: Any, where: str, lo: int, hi: int) -> int:
    """An integer (not a bool) within lo..hi."""
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise SpecError(f"{where}: expected an integer in {lo}..{hi}, got {value!r}")
    return value


def _num(value: Any, where: str, lo: float, hi: float) -> float:
    """A number (not a bool) within lo..hi."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not lo <= value <= hi:
        raise SpecError(f"{where}: expected a number in {lo}..{hi}, got {value!r}")
    return float(value)


def _str(value: Any, where: str, choices: tuple[str, ...] | None = None) -> str:
    """A non-empty string, optionally from a fixed set."""
    if not isinstance(value, str) or not value.strip():
        raise SpecError(f"{where}: expected a non-empty string")
    if choices is not None and value not in choices:
        raise SpecError(f"{where}: expected one of {list(choices)}, got {value!r}")
    return value


def _unique_strs(value: Any, where: str) -> tuple[str, ...]:
    """A non-empty list of distinct names."""
    if not isinstance(value, list) or not value:
        raise SpecError(f"{where}: expected a non-empty list")
    names = tuple(_str(v, f"{where}[{i}]") for i, v in enumerate(value))
    if len(set(names)) != len(names):
        raise SpecError(f"{where}: duplicate names")
    return names


def _profile(raw: Any, where: str) -> Profile:
    """One harness profile."""
    p = _obj(raw, where, {"java", "python", "js"})
    j = _obj(p["java"], f"{where}.java", {"forks", "warmup_iterations", "iterations", "iteration_ms"})
    py = _obj(p["python"], f"{where}.python", {"processes", "values", "warmups", "min_time"})
    js = _obj(p["js"], f"{where}.js", {"processes", "min_cpu_ms", "node_flags"})
    flags = js["node_flags"]
    if not isinstance(flags, list) or not all(isinstance(f, str) and NODE_FLAG.fullmatch(f) for f in flags):
        raise SpecError(f"{where}.js.node_flags: expected a list of flags like --no-maglev")
    return Profile(
        java=JavaProfile(
            forks=_int(j["forks"], f"{where}.java.forks", 1, 20),
            warmup_iterations=_int(j["warmup_iterations"], f"{where}.java.warmup_iterations", 0, 50),
            iterations=_int(j["iterations"], f"{where}.java.iterations", 1, 50),
            iteration_ms=_int(j["iteration_ms"], f"{where}.java.iteration_ms", 10, 10_000),
        ),
        python=PythonProfile(
            processes=_int(py["processes"], f"{where}.python.processes", 1, 50),
            values=_int(py["values"], f"{where}.python.values", 1, 50),
            warmups=_int(py["warmups"], f"{where}.python.warmups", 0, 20),
            min_time=_num(py["min_time"], f"{where}.python.min_time", 0.001, 10.0),
        ),
        js=JsProfile(
            processes=_int(js["processes"], f"{where}.js.processes", 1, 50),
            min_cpu_ms=_int(js["min_cpu_ms"], f"{where}.js.min_cpu_ms", 1, 60_000),
            node_flags=tuple(flags),
        ),
    )


def _experiment(raw: Any, where: str) -> Experiment:
    """One experiment with its per-runtime plan."""
    e = _obj(raw, where, {"id", "effect", "kernel", "runtimes"})
    rts = e["runtimes"]
    if not isinstance(rts, dict) or not rts:
        raise SpecError(f"{where}.runtimes: expected a non-empty object")
    plans: dict[str, RuntimePlan] = {}
    for rt, plan_raw in rts.items():
        _str(rt, f"{where}.runtimes key", RUNTIMES)
        p = _obj(plan_raw, f"{where}.runtimes.{rt}", {"sizes", "variants"})
        sizes_raw = p["sizes"]
        if not isinstance(sizes_raw, list) or not sizes_raw:
            raise SpecError(f"{where}.runtimes.{rt}.sizes: expected a non-empty list")
        sizes = tuple(_int(s, f"{where}.runtimes.{rt}.sizes", 1, MAX_BENCH_SIZE) for s in sizes_raw)
        if len(set(sizes)) != len(sizes):
            raise SpecError(f"{where}.runtimes.{rt}.sizes: duplicate sizes")
        plans[rt] = RuntimePlan(sizes=sizes, variants=_unique_strs(p["variants"], f"{where}.runtimes.{rt}.variants"))
    return Experiment(
        id=_str(e["id"], f"{where}.id"),
        effect=_str(e["effect"], f"{where}.effect"),
        kernel=_str(e["kernel"], f"{where}.kernel"),
        runtimes=plans,
    )


def _hypothesis(raw: Any, where: str, experiments: dict[str, Experiment]) -> Hypothesis:
    """One hypothesis, checked against the experiment it predicts."""
    base = {"id", "runtime", "experiment", "size", "statement", "why", "kind", "op", "value"}
    kind = raw.get("kind") if isinstance(raw, dict) else None
    if kind == "ratio":
        h = _obj(raw, where, base | {"numerator", "denominator"})
    elif kind == "absolute":
        h = _obj(raw, where, base | {"variant", "metric"})
    else:
        raise SpecError(f"{where}.kind: expected 'ratio' or 'absolute'")
    hid = _str(h["id"], f"{where}.id")
    rt = _str(h["runtime"], f"{hid}.runtime", RUNTIMES)
    exp = experiments.get(_str(h["experiment"], f"{hid}.experiment"))
    if exp is None:
        raise SpecError(f"{hid}.experiment: unknown experiment {h['experiment']!r}")
    plan = exp.runtimes.get(rt)
    if plan is None:
        raise SpecError(f"{hid}: experiment {exp.id} does not run on {rt}")
    size = _int(h["size"], f"{hid}.size", 1, MAX_BENCH_SIZE)
    if size not in plan.sizes:
        raise SpecError(f"{hid}.size: {size} is not a {rt} size of {exp.id}")
    op = _str(h["op"], f"{hid}.op", OPS)
    if kind == "ratio":
        num = _str(h["numerator"], f"{hid}.numerator", plan.variants)
        den = _str(h["denominator"], f"{hid}.denominator", plan.variants)
        if num == den:
            raise SpecError(f"{hid}: numerator and denominator are the same variant")
        value = _num(h["value"], f"{hid}.value", 0.01, 1000.0)
        return Hypothesis(
            hid, rt, exp.id, size, _str(h["statement"], f"{hid}.statement"), _str(h["why"], f"{hid}.why"),
            "ratio", ">=" if op == ">=" else "<=", value, "ns_per_element", numerator=num, denominator=den,
        )  # fmt: skip
    metric = _str(h["metric"], f"{hid}.metric", METRICS)
    if metric == "alloc_bytes_per_element" and rt != "java":
        raise SpecError(f"{hid}.metric: allocated bytes are only measured on java (JMH -prof gc)")
    variant = _str(h["variant"], f"{hid}.variant", plan.variants)
    value = _num(h["value"], f"{hid}.value", 0.0, 1e9)
    return Hypothesis(
        hid, rt, exp.id, size, _str(h["statement"], f"{hid}.statement"), _str(h["why"], f"{hid}.why"),
        "absolute", ">=" if op == ">=" else "<=", value, metric, variant=variant,
    )  # fmt: skip


def parse_spec(raw: Any) -> Spec:
    """Validate a decoded spec document."""
    top = _obj(raw, "spec", {"name", "version", "data", "checks", "settings", "profiles", "experiments", "hypotheses"})
    _int(top["version"], "version", 1, 1)
    d = _obj(top["data"], "data", {"generator", "value_seed", "permutation_seed", "value_bits", "byte_bits"})
    _str(d["generator"], "data.generator", ("xorshift32",))
    data = DataSpec(
        value_seed=_int(d["value_seed"], "data.value_seed", 1, 0xFFFFFFFF),
        permutation_seed=_int(d["permutation_seed"], "data.permutation_seed", 1, 0xFFFFFFFF),
        value_bits=_int(d["value_bits"], "data.value_bits", 1, 26),
        byte_bits=_int(d["byte_bits"], "data.byte_bits", 8, 8),
    )
    checks = _obj(top["checks"], "checks", {"xorshift32_seed1_first", "values_4096", "permutation_4096", "bytes_65536"})
    settings = _obj(top["settings"], "settings", {"noise_threshold", "min_forks_for_verdict"})
    profiles_raw = top["profiles"]
    if not isinstance(profiles_raw, dict) or "full" not in profiles_raw:
        raise SpecError("profiles: expected an object with at least a 'full' profile")
    profiles = {name: _profile(p, f"profiles.{name}") for name, p in profiles_raw.items()}
    exps_raw = top["experiments"]
    if not isinstance(exps_raw, list) or not exps_raw:
        raise SpecError("experiments: expected a non-empty list")
    experiments = tuple(_experiment(e, f"experiments[{i}]") for i, e in enumerate(exps_raw))
    by_id = {e.id: e for e in experiments}
    if len(by_id) != len(experiments):
        raise SpecError("experiments: duplicate ids")
    hyps_raw = top["hypotheses"]
    if not isinstance(hyps_raw, list) or not hyps_raw:
        raise SpecError("hypotheses: expected a non-empty list")
    hypotheses = tuple(_hypothesis(h, f"hypotheses[{i}]", by_id) for i, h in enumerate(hyps_raw))
    if len({h.id for h in hypotheses}) != len(hypotheses):
        raise SpecError("hypotheses: duplicate ids")
    covered = {(h.runtime, h.experiment, h.size) for h in hypotheses}
    for e in experiments:
        for rt, plan in e.runtimes.items():
            for size in plan.sizes:
                if (rt, e.id, size) not in covered:
                    raise SpecError(f"{e.id} on {rt} at size {size} has no hypothesis: state one before measuring")
    return Spec(
        data=data,
        checks=checks,
        noise_threshold=_num(settings["noise_threshold"], "settings.noise_threshold", 0.01, 1.0),
        min_forks_for_verdict=_int(settings["min_forks_for_verdict"], "settings.min_forks_for_verdict", 2, 50),
        profiles=profiles,
        experiments=experiments,
        hypotheses=hypotheses,
    )


def load_spec(path: Path | None = None) -> Spec:
    """Read and validate the spec file (at most 1 MiB)."""
    p = path or default_spec_path()
    try:
        if p.stat().st_size > MAX_SPEC_BYTES:
            raise SpecError(f"{p}: larger than {MAX_SPEC_BYTES} bytes")
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpecError(f"{p}: {exc}") from exc
    return parse_spec(raw)
