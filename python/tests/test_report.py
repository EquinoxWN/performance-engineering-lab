"""The report judges every hypothesis, marks noisy cells, and refuses incomplete or unexpected results."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from performance_engineering_lab import report
from performance_engineering_lab.results import Results, Sample
from performance_engineering_lab.spec import RUNTIMES, Spec


def _full(spec: Spec, runtimes: tuple[str, ...] = RUNTIMES, forks: int = 3) -> Results:
    """Synthetic results: every cell 10 ns/element with 2% spread, boxed accumulator 24 B/element."""
    res = Results()
    for rt in runtimes:
        for exp, var, size in spec.cells(rt):
            for f in range(forks):
                alloc = (24.0 if var == "boxed-accumulator" else 0.0) if rt == "java" else None
                res.samples.append(Sample(rt, exp, var, size, f, 10.0 + 0.1 * f, alloc))
    return res


def test_complete_results_judge_every_hypothesis(spec: Spec) -> None:
    rep = report.build_report(spec, _full(spec), RUNTIMES)
    assert rep.problems == []
    assert len(rep.verdicts) == 19
    assert all(v is not None for v in rep.verdicts.values())
    h14 = rep.verdicts["H14"]
    assert h14 is not None
    assert h14.status == "confirmed"
    h01 = rep.verdicts["H01"]
    assert h01 is not None
    assert h01.status == "refuted"
    assert rep.result_line.startswith("RESULT hypotheses=19 ")
    assert "complete=yes" in rep.result_line
    assert "noisy_cells=0/33" in rep.result_line
    for h in spec.hypotheses:
        assert f"| {h.id} |" in rep.markdown


def test_missing_and_unexpected_cells_are_problems(spec: Spec) -> None:
    res = _full(spec)
    res.samples = [s for s in res.samples if not (s.runtime == "js" and s.variant == "smi-array")]
    res.samples.append(Sample("python", "boxing", "tuple", 1048576, 0, 1.0))
    rep = report.build_report(spec, res, RUNTIMES)
    assert "no results for js/boxing/smi-array/1048576" in rep.problems
    assert any("python/boxing/tuple" in p for p in rep.problems)
    assert rep.verdicts["H17"] is None
    assert "complete=no" in rep.result_line


def test_noisy_cells_are_marked_and_other_runtimes_ignored(spec: Spec) -> None:
    res = _full(spec, ("java",))
    res.samples[0] = Sample(*res.samples[0].key, 0, 20.0, 0.0)
    rep = report.build_report(spec, res, ("java",))
    assert rep.problems == []
    assert "**noisy**" in rep.markdown
    assert "noisy_cells=1/11" in rep.result_line
    assert len(rep.verdicts) == 7


def test_one_fork_is_reported_but_not_judged(spec: Spec) -> None:
    rep = report.build_report(spec, _full(spec, forks=1), RUNTIMES)
    assert "not_judged=19" in rep.result_line


def test_formatting_and_runtime_parsing() -> None:
    assert [report.fmt(x) for x in (1234.5, 12.34, 1.234, 0.1234)] == ["1,234", "12.3", "1.23", "0.123"]
    assert report.fmt(float("nan")) == "n/a"
    assert report.parse_runtimes("java, js,java") == ("java", "js")
    with pytest.raises(argparse.ArgumentTypeError, match="subset"):
        report.parse_runtimes("go")


def test_cli_exit_codes(fixtures: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "pyperf.json").write_text((fixtures / "pyperf.json").read_text(encoding="utf-8"), encoding="utf-8")
    assert report.main(["--results", str(tmp_path), "--runtimes", "python"]) == 3
    assert "no results for python/access-pattern" in capsys.readouterr().err
    assert (tmp_path / "report.md").is_file()
    (tmp_path / "mitata.jsonl").write_text("{broken\n", encoding="utf-8")
    assert report.main(["--results", str(tmp_path)]) == 2
