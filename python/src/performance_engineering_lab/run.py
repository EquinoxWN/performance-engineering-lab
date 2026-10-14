"""Run every experiment with its own harness (JMH, pyperf, mitata), then build the report.

usage: python -m performance_engineering_lab.run [--profile full|smoke] [--runtimes java,js,python]
       [--cpus 2-7] [--results DIR]
Commands are fixed argument lists (no shell); every JVM is heap-capped and every harness writes
only under the repository's .tmp/. Exit codes: 0 complete, 1 a harness failed, 2 bad arguments,
3 the report is incomplete.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import psutil

from .report import build_report, parse_runtimes
from .results import JMH_CLASSES, load_results
from .spec import RUNTIMES, Profile, Spec, SpecError, load_spec

REPO = Path(__file__).resolve().parents[3]
JMH_JAR = Path("java") / "target" / "benchmarks.jar"
INHERITED_ENV = "PYTHONDONTWRITEBYTECODE,PYTHONPYCACHEPREFIX,TMP,TEMP,TMPDIR,APPDATA,LOCALAPPDATA"
JMH_TIMEOUT_S, PYPERF_TIMEOUT_S, NODE_TIMEOUT_S = 3600, 3600, 600


class RunError(RuntimeError):
    """A harness could not be started or failed."""


def _no_spaces(path: Path) -> str:
    """A path JMH can take inside its space-separated -jvmArgs string."""
    text = path.as_posix()
    if " " in text:
        raise RunError(f"JMH splits -jvmArgs on spaces; move the repository to a path without spaces: {text}")
    return text


def jvm_flags(tmp: Path, heap_mb: int) -> list[str]:
    """Heap cap, no hsperfdata, and crash files, heap dumps and temp files inside tmp."""
    t = _no_spaces(tmp)
    return [
        f"-Xmx{heap_mb}m",
        "-XX:-UsePerfData",
        f"-XX:ErrorFile={t}/hs_err_pid%p.log",
        f"-XX:HeapDumpPath={t}",
        f"-Djava.io.tmpdir={t}",
    ]


def jmh_commands(spec: Spec, profile: Profile, repo: Path, results: Path, java: str = "java") -> list[list[str]]:
    """One JMH invocation per experiment, with sizes and variants taken from the spec."""
    classes = {exp: cls for cls, exp in JMH_CLASSES.items()}
    tmp = repo / ".tmp" / "jmh"
    j = profile.java
    out = []
    for e in spec.experiments:
        plan = e.runtimes.get("java")
        if plan is None:
            continue
        cmd = [java, *jvm_flags(tmp, 256), "-jar", str(repo / JMH_JAR)]
        cmd += [rf"portfolio\.performanceengineeringlab\.bench\.{classes[e.id]}\.run$"]
        cmd += ["-p", "size=" + ",".join(map(str, plan.sizes)), "-p", "variant=" + ",".join(plan.variants)]
        cmd += ["-f", str(j.forks), "-wi", str(j.warmup_iterations), "-i", str(j.iterations)]
        cmd += ["-w", f"{j.iteration_ms}ms", "-r", f"{j.iteration_ms}ms", "-bm", "avgt", "-tu", "ns"]
        cmd += ["-prof", "gc", "-foe", "true", "-rf", "json", "-rff", str(results / f"jmh-{e.id}.json")]
        cmd += ["-jvmArgs", " ".join(jvm_flags(tmp, 512))]
        out.append(cmd)
    return out


def pyperf_command(profile: Profile, results: Path, python: str = sys.executable) -> list[str]:
    """One pyperf invocation for every Python cell; pyperf runs each in fresh worker processes."""
    p = profile.python
    return [
        python, "-m", "performance_engineering_lab.bench", "-o", str(results / "pyperf.json"),
        "--processes", str(p.processes), "--values", str(p.values), "--warmups", str(p.warmups),
        "--min-time", str(p.min_time), "--inherit-environ", INHERITED_ENV, "--quiet",
    ]  # fmt: skip


def node_commands(spec: Spec, profile: Profile, repo: Path, node: str = "node") -> list[list[str]]:
    """One fresh Node.js process per cell and repetition, interleaved across cells."""
    script = str(repo / "js" / "src" / "bench.js")
    cells = spec.cells("js")
    return [
        [node, "--max-old-space-size=512", *profile.js.node_flags, script,
         "--experiment", e, "--variant", v, "--size", str(n), "--min-cpu-ms", str(profile.js.min_cpu_ms)]
        for _ in range(profile.js.processes)
        for e, v, n in cells
    ]  # fmt: skip


def child_env(repo: Path) -> dict[str, str]:
    """The current environment with every temp folder pointing into .tmp/."""
    env = dict(os.environ)
    tmp = str(repo / ".tmp")
    env.update(TMP=tmp, TEMP=tmp, TMPDIR=tmp, PYTHONDONTWRITEBYTECODE="1")
    return env


def parse_cpus(text: str) -> list[int]:
    """CPU list like '2-7' or '2,3,6'."""
    cpus: set[int] = set()
    try:
        for part in text.split(","):
            lo, _, hi = part.strip().partition("-")
            first, last = int(lo), int(hi or lo)
            if first < 0 or last < first or last > 1023:
                raise ValueError(part)
            cpus.update(range(first, last + 1))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"bad CPU list {text!r}: use e.g. 2-7 or 2,3,6") from exc
    return sorted(cpus)


def _run(cmd: list[str], repo: Path, timeout: int, capture: bool = False) -> str:
    """Run one harness command; raise RunError if it fails."""
    print("$ " + " ".join(cmd[:3]) + " ...", flush=True)
    try:
        done = subprocess.run(  # noqa: S603 - fixed argument list, no shell
            cmd, cwd=repo, env=child_env(repo), timeout=timeout, check=False, text=True,
            stdout=subprocess.PIPE if capture else None,
        )  # fmt: skip
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RunError(f"{cmd[0]}: {exc}") from exc
    if done.returncode != 0:
        raise RunError(f"{' '.join(cmd[:4])} ... exited with {done.returncode}")
    return done.stdout or ""


def run_harnesses(spec: Spec, profile: Profile, runtimes: tuple[str, ...], repo: Path, results: Path) -> None:
    """Run the requested harnesses, replacing their previous result files."""
    results.mkdir(parents=True, exist_ok=True)
    (repo / ".tmp" / "jmh").mkdir(parents=True, exist_ok=True)
    if "java" in runtimes:
        if not (repo / JMH_JAR).is_file():
            raise RunError(f"{JMH_JAR} is missing: build it with `make build` (mvn package)")
        for old in results.glob("jmh-*.json"):
            old.unlink()
        for cmd in jmh_commands(spec, profile, repo, results):
            _run(cmd, repo, JMH_TIMEOUT_S)
    if "python" in runtimes:
        (results / "pyperf.json").unlink(missing_ok=True)  # pyperf refuses to overwrite
        _run(pyperf_command(profile, results), repo, PYPERF_TIMEOUT_S)
    if "js" in runtimes:
        lines = [_run(cmd, repo, NODE_TIMEOUT_S, capture=True).strip() for cmd in node_commands(spec, profile, repo)]
        (results / "mitata.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Pin the CPUs if asked, run the harnesses, write the report, print the RESULT line."""
    parser = argparse.ArgumentParser(prog="python -m performance_engineering_lab.run")
    parser.add_argument("--profile", default="full", help="harness settings from spec/experiments.json")
    parser.add_argument("--runtimes", type=parse_runtimes, default=RUNTIMES)
    parser.add_argument("--cpus", type=parse_cpus, default=None, help="pin every harness process, e.g. 2-7")
    parser.add_argument("--results", type=Path, default=REPO / ".tmp" / "results")
    args = parser.parse_args(argv)
    try:
        spec = load_spec()
        if args.profile not in spec.profiles:
            parser.error(f"unknown profile {args.profile!r}; the spec defines {sorted(spec.profiles)}")
        if args.cpus is not None:
            # Child processes inherit the affinity, so JMH forks, pyperf workers and node do too.
            psutil.Process().cpu_affinity(args.cpus)
        run_harnesses(spec, spec.profiles[args.profile], args.runtimes, REPO, args.results)
        report = build_report(spec, load_results(args.results, REPO), args.runtimes)
    except RunError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (SpecError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    (args.results / "report.md").write_text(report.markdown, encoding="utf-8")
    print(report.markdown)
    pinned = ",".join(map(str, args.cpus)) if args.cpus else "none"
    print(f"profile={args.profile} cpus={pinned} report={args.results / 'report.md'}")
    for p in report.problems:
        print(f"problem: {p}", file=sys.stderr)
    print(report.result_line)
    return 3 if report.problems else 0


if __name__ == "__main__":
    sys.exit(main())
