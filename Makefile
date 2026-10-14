.PHONY: setup lint test build bench bench-smoke report audit ci

# PY is the Python to use (the repo's .venv locally, setup-python's in CI); MVNLOCAL (set by the
# author's repoenv helper) keeps the Maven repository inside the repo and is empty in CI.
# CPUS pins every harness process to those logical CPUs (e.g. CPUS=2-7 for performance cores on a
# hybrid Intel CPU); empty means no pinning.
PY ?= python
CPUS ?=
MVN = mvn -B -q $(MVNLOCAL)
PIN = $(if $(CPUS),--cpus $(CPUS),)

setup:
	cd python && $(PY) -m pip install -e ".[dev]"
	cd js && npm ci

# Spotless check and javac -Xlint:all -Werror; ruff, ruff format and mypy --strict; tsc --checkJs --strict.
lint:
	cd java && $(MVN) -DskipTests compile
	cd python && $(PY) -m ruff check . && $(PY) -m ruff format --check . && $(PY) -m mypy
	cd js && npm run -s lint

test:
	cd java && $(MVN) verify
	cd python && $(PY) -m pytest -q
	cd js && npm test

# java/target/benchmarks.jar, the self-contained JMH launcher.
build:
	cd java && $(MVN) -DskipTests package

# Every experiment with JMH (3 forks), pyperf (5 processes) and mitata (5 processes); about 15 minutes.
# Writes .tmp/results/report.md; exits 3 if any hypothesis lacks results.
bench: build
	$(PY) -m performance_engineering_lab.run --profile full $(PIN)

# One fork/process per cell: proves the pipeline end to end (CI); too few forks to judge hypotheses.
bench-smoke: build
	$(PY) -m performance_engineering_lab.run --profile smoke $(PIN)

# Rebuild the report from the files already in .tmp/results.
report:
	$(PY) -m performance_engineering_lab.report

# Known vulnerabilities in Python, npm and Maven dependencies (Maven via OSV.dev, test scope included).
audit:
	cd python && $(PY) -m pip_audit --skip-editable --cache-dir ../.tmp/pip-audit
	cd js && npm audit --audit-level=low
	cd java && $(MVN) dependency:list -DincludeScope=test -DoutputFile=target/dependencies.txt
	$(PY) scripts/osv_audit.py Maven java/target/dependencies.txt

ci: setup lint test bench-smoke audit
