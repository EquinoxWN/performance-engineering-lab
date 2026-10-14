"""Turn validated samples into Markdown tables, hypothesis verdicts and one RESULT line.

usage: python -m performance_engineering_lab.report [--results DIR] [--runtimes java,js,python] [--out FILE]
Exit codes: 0 complete, 2 bad arguments or unreadable files, 3 a spec cell has no results or a result
has no spec cell (a hypothesis cannot be judged).
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .results import CellKey, ResultError, Results, Sample, load_results
from .spec import RUNTIMES, Hypothesis, Spec, SpecError, load_spec
from .stats import Summary, Verdict, judge_absolute, judge_ratio, summarize

RUNTIME_NAMES = {"java": "Java (JMH)", "js": "Node.js (mitata)", "python": "CPython (pyperf)"}


@dataclass
class Report:
    """The rendered report and anything that makes it incomplete."""

    markdown: str
    result_line: str
    problems: list[str] = field(default_factory=list)
    verdicts: dict[str, Verdict | None] = field(default_factory=dict)


def fmt(x: float) -> str:
    """A number with precision suited to its size."""
    if x != x:  # NaN
        return "n/a"
    if abs(x) >= 100:
        return f"{x:,.0f}"
    if abs(x) >= 10:
        return f"{x:.1f}"
    if abs(x) >= 1:
        return f"{x:.2f}"
    return f"{x:.3f}"


def prediction(h: Hypothesis) -> str:
    """The hypothesis as a formula."""
    if h.kind == "ratio":
        return f"{h.numerator} / {h.denominator} {h.op} {h.value:g}"
    unit = "B/element" if h.metric == "alloc_bytes_per_element" else "ns/element"
    return f"{h.variant} {unit} {h.op} {h.value:g}"


def _alloc_summary(samples: list[Sample]) -> Summary | None:
    """Allocated bytes per element across forks, when the harness measured them."""
    allocs = [s.alloc_bytes_per_element for s in samples]
    if not allocs or any(a is None for a in allocs):
        return None
    return summarize([a for a in allocs if a is not None])


def judge(spec: Spec, h: Hypothesis, cells: dict[CellKey, list[Sample]]) -> Verdict | None:
    """The verdict of one hypothesis, or None when a variant has no results."""
    keys = [(h.runtime, h.experiment, v, h.size) for v in h.variants()]
    if any(k not in cells for k in keys):
        return None
    if h.kind == "ratio":
        num = summarize([s.ns_per_element for s in cells[keys[0]]])
        den = summarize([s.ns_per_element for s in cells[keys[1]]])
        return judge_ratio(h.op, h.value, num, den, spec.min_forks_for_verdict)
    samples = cells[keys[0]]
    if h.metric == "alloc_bytes_per_element":
        alloc = _alloc_summary(samples)
        if alloc is None:
            return None
        return judge_absolute(h.op, h.value, alloc, spec.min_forks_for_verdict)
    return judge_absolute(h.op, h.value, summarize([s.ns_per_element for s in samples]), spec.min_forks_for_verdict)


def build_report(spec: Spec, results: Results, runtimes: tuple[str, ...]) -> Report:
    """Check completeness, summarize every cell and judge every hypothesis of the given runtimes."""
    cells: dict[CellKey, list[Sample]] = defaultdict(list)
    for s in results.samples:
        if s.runtime in runtimes:
            cells[s.key].append(s)
    expected = {(rt, *c) for rt in runtimes for c in spec.cells(rt)}
    problems = [f"no results for {'/'.join(map(str, k))}" for k in sorted(expected - cells.keys())]
    problems += [
        f"results for {'/'.join(map(str, k))}, which the spec does not list" for k in sorted(cells.keys() - expected)
    ]

    lines = ["# Benchmark report", ""]
    lines += ["## Harnesses and runtimes", "", "| Runtime | Harness | Runtime version | Flags |", "|---|---|---|---|"]
    for info in results.infos:
        if info.runtime in runtimes:
            flags = " ".join(f"`{f}`" for f in info.flags if f) or "-"
            lines.append(
                f"| {info.runtime} | {info.harness} {info.harness_version} | {info.runtime_version} | {flags} |"
            )

    hyps = [h for h in spec.hypotheses if h.runtime in runtimes]
    verdicts: dict[str, Verdict | None] = {}
    lines += ["", "## Hypotheses (written before the runs)", ""]
    lines += ["| ID | Runtime | Size | Prediction | Measured (median) | Range across forks | Verdict |"]
    lines += ["|---|---|---|---|---|---|---|"]
    for h in hyps:
        v = judge(spec, h, cells)
        verdicts[h.id] = v
        if v is None:
            lines.append(f"| {h.id} | {h.runtime} | {h.size:,} | `{prediction(h)}` | - | - | **missing results** |")
        else:
            lines.append(
                f"| {h.id} | {h.runtime} | {h.size:,} | `{prediction(h)}` | {fmt(v.measured)} | "
                f"{fmt(v.low)} - {fmt(v.high)} | **{v.status}** |"
            )

    noisy = 0
    for rt in runtimes:
        lines += ["", f"## {RUNTIME_NAMES[rt]}: time per element", ""]
        header = "| Experiment | Variant | Size | ns/element, median [min-max] | 95% CI of the mean | Spread | Forks |"
        header += " Harness's own estimate (ns/element) |"
        sep = "|---|---|---|---|---|---|---|---|"
        if rt == "java":
            header += " Allocated B/element |"
            sep += "---|"
        lines += [header, sep]
        for experiment, variant, size in spec.cells(rt):
            key = (rt, experiment, variant, size)
            samples = cells.get(key)
            if not samples:
                lines.append(f"| {experiment} | {variant} | {size:,} | missing | | | | |")
                continue
            sm = summarize([x.ns_per_element for x in samples])
            is_noisy = sm.spread > spec.noise_threshold
            noisy += is_noisy
            spread = f"{sm.spread:.0%}" + (" **noisy**" if is_noisy else "")
            ci = f"{fmt(sm.ci_low)} - {fmt(sm.ci_high)}" if sm.n > 1 else "n/a"
            row = (
                f"| {experiment} | {variant} | {size:,} | {fmt(sm.median)} [{fmt(sm.minimum)}-{fmt(sm.maximum)}] | "
                f"{ci} | {spread} | {sm.n} | {results.native.get(key, '-')} |"
            )
            if rt == "java":
                a = _alloc_summary(samples)
                row += f" {fmt(a.median) if a else 'n/a'} |"
            lines.append(row)

    total = sum(len(spec.cells(rt)) for rt in runtimes)
    counts = dict.fromkeys(("confirmed", "refuted", "inconclusive", "not judged"), 0)
    for v in verdicts.values():
        if v is not None:
            counts[v.status] += 1
    result_line = (
        f"RESULT hypotheses={len(hyps)} confirmed={counts['confirmed']} refuted={counts['refuted']} "
        f"inconclusive={counts['inconclusive']} not_judged={counts['not judged']} "
        f"noisy_cells={noisy}/{total} complete={'no' if problems else 'yes'}"
    )
    lines += [
        "",
        f"Noise threshold: spread above {spec.noise_threshold:.0%} marks a cell as noisy.",
        "",
        f"`{result_line}`",
    ]
    if problems:
        lines += ["", "## Problems", ""] + [f"- {p}" for p in problems]
    return Report("\n".join(lines) + "\n", result_line, problems, verdicts)


def parse_runtimes(text: str) -> tuple[str, ...]:
    """Comma-separated runtime names, validated."""
    names = tuple(dict.fromkeys(t.strip() for t in text.split(",") if t.strip()))
    if not names or any(n not in RUNTIMES for n in names):
        raise argparse.ArgumentTypeError(f"runtimes must be a comma-separated subset of {','.join(RUNTIMES)}")
    return names


def main(argv: list[str] | None = None) -> int:
    """Build the report from a results folder and print the RESULT line."""
    repo = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(prog="python -m performance_engineering_lab.report")
    parser.add_argument("--results", type=Path, default=repo / ".tmp" / "results")
    parser.add_argument("--runtimes", type=parse_runtimes, default=RUNTIMES)
    parser.add_argument("--out", type=Path, default=None, help="Markdown file (default: <results>/report.md)")
    args = parser.parse_args(argv)
    try:
        report = build_report(load_spec(), load_results(args.results, repo), args.runtimes)
    except (SpecError, ResultError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    out = args.out or args.results / "report.md"
    out.write_text(report.markdown, encoding="utf-8")
    print(report.markdown)
    for p in report.problems:
        print(f"problem: {p}", file=sys.stderr)
    return 3 if report.problems else 0


if __name__ == "__main__":
    sys.exit(main())
