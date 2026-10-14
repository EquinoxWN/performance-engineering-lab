# Python package: performance_engineering_lab

Two roles: the CPython experiments (run by pyperf), and the runner and report for all three runtimes.

| Module | What it does |
|---|---|
| `datasets`, `kernels` | xorshift32 inputs and the measured loops, CPython version |
| `bench` | pyperf benchmarks for every Python cell of `spec/experiments.json` (`inner_loops` = size, so values are per element) |
| `spec` | strict loader for `spec/experiments.json`; refuses any cell without a hypothesis |
| `results` | readers for JMH JSON, pyperf JSON and the mitata JSON lines, into per-fork samples |
| `stats` | median, min-max, 95% t interval, and the conservative verdict rule |
| `report` | Markdown tables, hypothesis verdicts and the `RESULT` line; exit 3 when results are incomplete |
| `run` | `python -m performance_engineering_lab.run`: pins CPUs if asked, runs JMH, pyperf and mitata, writes the report |

Run from the repository root after `make setup` (see the main [README](../README.md)).
