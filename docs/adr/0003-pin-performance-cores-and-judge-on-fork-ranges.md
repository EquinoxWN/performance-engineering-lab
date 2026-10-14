# ADR 0003: Pin to performance cores and judge hypotheses on the range across forks

- **Status:** Accepted

## Context

The measurements run on a shared laptop (Intel Core i7-13700H: 6 performance cores with two
threads each, logical CPUs 0-11, and 8 efficiency cores, logical CPUs 12-19) while other jobs run.
A check before the first full run, with the JavaScript branch kernel on sorted bytes pinned to one
logical CPU at a time, gave about 0.87 to 1.07 ns per element on CPUs 0-10 and 1.95 to 2.09 ns on
CPUs 12-18. An unpinned process lands on either kind of core, so unpinned spreads mix two machines.
A verdict computed from means alone would also turn a noisy run into a confident claim.

## Decision

- `run --cpus 2-7` pins the runner with psutil before it starts any harness. Child processes inherit
  the affinity from their parent (checked on Windows: a Python child and grandchild and a Node.js
  process all reported CPUs 2-7, and pyperf records `cpu_affinity: 2-7` in its result metadata; JMH
  forks are started the same way but were not checked separately). Logical CPUs 0-1 are left to the
  operating system and other work. Pinning is opt-in (`CPUS=` in the Makefile) because CPU numbers
  are machine-specific; CI does not pin.
- Each cell is reduced to one estimate per fork (JMH fork, pyperf worker, Node.js process). A ratio
  hypothesis is judged on the worst-case range `min(A)/max(B) .. max(A)/min(B)`:
  **confirmed** if the whole range satisfies the prediction, **refuted** if none of it does,
  **inconclusive** otherwise. Absolute hypotheses use the min-max range of the cell.
  Fewer than 3 forks per cell gives **not judged**.
- A cell whose spread `(max - min) / median` exceeds 15% is labelled **noisy** in the report.

## Consequences

- Noise can turn a verdict into "inconclusive" but cannot produce a wrong "confirmed" or
  "refuted" unless every fork is biased the same way; the cost is more inconclusive verdicts than a
  test on means would give.
- Results describe the performance cores of this CPU; efficiency-core numbers are not measured.
- Three forks are few for a t interval (wide 95% intervals); the range rule does not depend on it,
  and the interval is reported for reference.
- CI's smoke profile (1 fork) can never judge a hypothesis, by construction.
