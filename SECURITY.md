# Security policy

## Reporting a vulnerability

Please report security problems privately through GitHub:
**Security > Report a vulnerability** on this repository
(`https://github.com/EquinoxWN/performance-engineering-lab/security/advisories/new`). Do not open a public issue.

Include what you found, how to reproduce it, and the impact you expect. You will get an answer
within 7 days. Fixes are released as soon as they are ready, and you are credited unless you ask
not to be.

## Supported versions

This project is pre-1.0. Only the latest commit on `main` receives fixes.

## Scope

- **In scope:** the runner executing anything other than its fixed `java`, `python` and `node`
  commands; a crafted spec or result file making the report read outside the given folder, exhaust
  memory or accept malformed data; harnesses writing files outside the repository's `.tmp/`.
- **Out of scope:** performance differences between machines or runtime versions; those are
  measurements, not vulnerabilities.

## How this repository protects itself

- The runner starts processes with fixed argument lists (no shell) and caps every JVM
  (`-Xmx256m` host, `-Xmx512m` forks) and Node.js process (`--max-old-space-size=512`); crash files,
  heap dumps and temp files go to `.tmp/`, and a unit test checks every JMH command for this.
- The spec loader and the result readers accept exact field sets only, check types and ranges,
  and refuse files over 1 MiB (spec), 64 MiB (results) and JSON lines over 64 KiB.
- Benchmark inputs are generated from fixed seeds; nothing is downloaded at run time.
- Runtime dependencies: JMH 1.37 (Java), pyperf and psutil (Python), mitata (JavaScript), all pinned
  or bounded and audited in CI (pip-audit, npm audit, OSV.dev for Maven).
- Every GitHub Action is pinned to a full commit SHA; workflows run with read-only permissions and
  without persisted credentials. Dependabot update pull requests are paused (`open-pull-requests-limit: 0`) so the repository keeps a single `main` branch; dependencies are updated by hand and checked by the CI audit.
