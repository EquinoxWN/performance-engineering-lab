"""Harness commands: spec-driven, heap-capped, contained in .tmp/, no shell; plus a real pyperf run."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pytest

from performance_engineering_lab import run
from performance_engineering_lab.bench import bench_name, selected_cells
from performance_engineering_lab.spec import Spec

REPO = Path("C:/repo") if sys.platform == "win32" else Path("/repo")


def test_jmh_commands_take_params_from_the_spec_and_stay_contained(spec: Spec, tmp_path: Path) -> None:
    cmds = run.jmh_commands(spec, spec.profiles["full"], REPO, tmp_path)
    assert len(cmds) == 3
    tmp = (REPO / ".tmp" / "jmh").as_posix()
    for cmd, exp in zip(cmds, spec.experiments, strict=True):
        plan = exp.runtimes["java"]
        assert cmd[cmd.index("-p") + 1] == "size=" + ",".join(map(str, plan.sizes))
        assert "variant=" + ",".join(plan.variants) in cmd
        assert cmd[cmd.index("-f") + 1] == "3"
        assert "gc" in cmd
        assert cmd[cmd.index("-rf") + 1] == "json"
        assert cmd[cmd.index("-rff") + 1] == str(tmp_path / f"jmh-{exp.id}.json")
        host = cmd[1 : cmd.index("-jar")]
        forks = cmd[cmd.index("-jvmArgs") + 1].split(" ")
        for flags, heap in ((host, "-Xmx256m"), (forks, "-Xmx512m")):
            assert heap in flags
            assert "-XX:-UsePerfData" in flags
            assert f"-Djava.io.tmpdir={tmp}" in flags
            assert f"-XX:ErrorFile={tmp}/hs_err_pid%p.log" in flags


def test_paths_with_spaces_are_refused_for_jmh(spec: Spec, tmp_path: Path) -> None:
    with pytest.raises(run.RunError, match="spaces"):
        run.jmh_commands(spec, spec.profiles["full"], Path("C:/my repo"), tmp_path)


def test_node_commands_are_interleaved_and_heap_capped(spec: Spec) -> None:
    cmds = run.node_commands(spec, spec.profiles["full"], REPO)
    cells = spec.cells("js")
    assert len(cmds) == 5 * len(cells)
    assert [c[c.index("--variant") + 1] for c in cmds[: len(cells)]] == [v for _, v, _ in cells]
    assert all(c[1] == "--max-old-space-size=512" and c[c.index("--min-cpu-ms") + 1] == "642" for c in cmds)


def test_profile_node_flags_come_before_the_script(spec: Spec) -> None:
    cmd = run.node_commands(spec, spec.profiles["js-no-maglev"], REPO)[0]
    assert cmd[1:3] == ["--max-old-space-size=512", "--no-maglev"]
    assert cmd[3].endswith("bench.js")


def test_pyperf_command_and_child_environment(spec: Spec, tmp_path: Path) -> None:
    cmd = run.pyperf_command(spec.profiles["smoke"], tmp_path, python="py")
    assert cmd[:3] == ["py", "-m", "performance_engineering_lab.bench"]
    assert cmd[cmd.index("-o") + 1] == str(tmp_path / "pyperf.json")
    assert cmd[cmd.index("--processes") + 1] == "1"
    assert "TMP" in cmd[cmd.index("--inherit-environ") + 1]
    env = run.child_env(REPO)
    assert env["TMP"] == env["TEMP"] == env["TMPDIR"] == str(REPO / ".tmp")


def test_cpu_lists() -> None:
    assert run.parse_cpus("2-4,7") == [2, 3, 4, 7]
    for bad in ("x", "5-2", "-1", "2-2000"):
        with pytest.raises(argparse.ArgumentTypeError, match="CPU list"):
            run.parse_cpus(bad)


def test_missing_benchmark_jar_is_reported(spec: Spec, tmp_path: Path) -> None:
    with pytest.raises(run.RunError, match="make build"):
        run.run_harnesses(spec, spec.profiles["smoke"], ("java",), tmp_path, tmp_path / "results")


def test_bench_selection(spec: Spec) -> None:
    assert len(selected_cells(spec, None)) == 11
    only = selected_cells(spec, "boxing/")
    assert [bench_name(*c) for c in only] == ["boxing/list/1048576", "boxing/array/1048576", "boxing/objects/1048576"]
    with pytest.raises(SystemExit, match="matches no benchmark"):
        selected_cells(spec, "nothing")


def test_pyperf_runs_one_real_cell_end_to_end(tmp_path: Path) -> None:
    out = tmp_path / "one.json"
    cmd = [sys.executable, "-m", "performance_engineering_lab.bench", "--only", "branch/branchless-sorted"]
    cmd += ["--debug-single-value", "-o", str(out), "--inherit-environ", run.INHERITED_ENV, "--quiet"]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=240, check=False)
    assert done.returncode == 0, done.stderr
    from performance_engineering_lab.results import parse_pyperf

    samples = parse_pyperf(out.read_text(encoding="utf-8")).samples
    assert len(samples) == 1
    assert samples[0].variant == "branchless-sorted"
    assert samples[0].ns_per_element > 0
