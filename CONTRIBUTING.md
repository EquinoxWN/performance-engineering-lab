# Contributing

Thanks for helping. This is a Java, Python and JavaScript project; issues and pull requests are welcome.

## Set up and check your change

Needs JDK 21+ with Maven 3.9+, Python 3.11+, Node.js 24+. Caches, virtual environments and
benchmark output stay in git-ignored folders inside the repo (`.venv/`, `node_modules/`, `.tmp/`).

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
make setup         # Python package and dev tools, npm packages
make lint          # Spotless + javac -Werror, ruff + mypy --strict, tsc --checkJs --strict
make test          # JUnit, pytest and node --test suites
make bench-smoke   # every experiment once through JMH, pyperf and mitata (a few minutes)
make bench CPUS=2-7  # the full measurement (about 15 minutes); pin to performance cores if your CPU is hybrid
make audit         # known-vulnerability check (as in CI)
```

`cd java && mvn spotless:apply` formats the Java sources.

## Adding or changing an experiment

1. Write the hypothesis first: add it to `hypotheses` in `spec/experiments.json` with a predicted
   ratio or value. The loader refuses any (runtime, experiment, size) without a hypothesis.
2. Implement the variant in every runtime it lists, keep all variants returning the same result,
   and extend the checksum tests if inputs change.
3. Run `make bench` and record the numbers, the machine, versions, flags and the spread in
   `docs/results/`. Do not edit a hypothesis after seeing its result; add a new one instead.

Keep function comments to one short phrase. Significant design changes need an ADR in `docs/adr/`.
Report security problems privately, as described in [SECURITY.md](SECURITY.md).

By contributing you agree that your work is released under the [MIT License](LICENSE).
