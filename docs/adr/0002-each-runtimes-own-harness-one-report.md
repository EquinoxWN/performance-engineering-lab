# ADR 0002: Each runtime's own benchmark harness, one validated report

- **Status:** Accepted

## Context

The experiments compare loops whose cost per element ranges from about 0.1 ns (a vectorized Java
sum) to several hundred ns (CPython chasing pointers through 160 MB). Micro-benchmarks at that scale
fall into well-known traps: dead-code elimination, constant folding, measuring the interpreter
before the JIT has compiled the loop, JIT profiles polluted by other variants in the same process,
timer resolution, and one lucky or unlucky process. Each ecosystem has a harness built to avoid
them: JMH for the JVM, pyperf for CPython, mitata for JavaScript engines. They report different
statistics in different formats.

## Decision

- **Java:** JMH 1.37, average-time mode, the result returned from `@Benchmark` (consumed by JMH's
  blackhole), inputs built in `@Setup(Level.Trial)`, 3 forks x (3 warm-up + 5 measured 500 ms
  iterations) per cell, `-prof gc` for allocated bytes per operation. Each (size, variant) runs in its
  own forks, so the JIT profile sees one variant only.
- **CPython:** pyperf with `bench_time_func`, `inner_loops` = number of elements, 5 worker processes
  x 3 values after a calibration run; the input is built in each worker outside the timed region.
- **Node.js:** mitata's `measure` with `do_not_optimize`, after an explicit warm-up (at least 5 calls
  and 250 ms) so TurboFan has compiled the kernel; one fresh process per cell and repetition, 5
  repetitions interleaved across cells. Expected results come from separate reference functions so
  the measured kernel only ever sees one input type (monomorphic feedback).
- Every harness checks its kernel's result against the expected sum before timing and fails
  otherwise. The native outputs (JMH JSON, pyperf JSON, mitata JSON lines) are kept, and one Python
  report reads all three with strict validation, reduces each cell to per-fork estimates and judges
  the hypotheses the same way for every runtime (ADR 0003).

## Consequences

- Each runtime is measured with the tool its community trusts, and the harness's own estimate (JMH's
  99.9% interval, pyperf's mean and standard deviation) is printed next to the common statistics.
- One normalization layer means one place to get wrong; it is covered by tests on trimmed real
  outputs of all three harnesses.
- mitata has no forking of its own, so the runner provides it (fresh processes); this costs about
  55 Node.js start-ups per full run.
- Allocated bytes are only measured on the JVM (JMH's GC profiler). V8 and CPython allocation is not
  measured in M1, and the spec refuses an allocation hypothesis for those runtimes.
