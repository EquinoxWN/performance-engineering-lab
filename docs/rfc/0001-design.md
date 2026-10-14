# RFC 0001: performance-engineering-lab design

- **Status:** Accepted (M1 implemented)
- **Author:** EquinoxWN
- **Created:** 2026

## Problem

Two functions with the same Big-O can differ by 10x or more in practice. Summing the same 16 million
integers in a different order, testing the same bytes sorted or shuffled, or keeping the same
numbers in an `int[]` instead of a list of boxed integers changes nothing in the complexity class
and a lot in the run time, because of cache lines and prefetching, branch prediction, and
allocation and pointer chasing. Engineers usually argue about these effects from rules of thumb,
and micro-benchmarks written by hand often measure the trap instead of the effect (dead code
removed by the JIT, an unwarmed interpreter, one lucky process, a thread that landed on an
efficiency core).

This project states a numeric hypothesis for each effect before measuring, measures it with each
language's proper harness (JMH, pyperf, mitata), reports the spread, and records when the
hypothesis was wrong.

**Users:** backend engineers deciding whether a data-layout or branch change is worth making;
engineers preparing for "this got 2x slower, find out why" interviews; and the author, as the base
for M2 (hardware counters and flame graphs) and M3 (fixes with significance tests).

## Critical-to-quality measures (Define)

| CTQ | Measure | Target (M1) |
|---|---|---|
| Hypothesis first | every (runtime, experiment, size) cell in `spec/experiments.json` has a hypothesis with a numeric prediction | 100%, enforced by the spec loader |
| Proper harness | JMH forks, pyperf worker processes, fresh Node.js processes | at least 3 independent forks/processes per cell in the full profile |
| Same work | each variant's result checked against the expected sum before timing; shared checksums in all three test suites | 0 mismatches |
| Reported spread | median, min-max across forks, 95% t interval, spread `(max - min) / median` | reported for 100% of cells; cells above 15% labelled noisy |
| Honest verdicts | confirmed / refuted / inconclusive from the worst-case range across forks | every hypothesis judged; refuted ones reported, never edited after the run |
| Containment | heaps capped (JVM 256/512 MB, Node.js 512 MB); temp, crash and result files | all inside the repo's `.tmp/` |
| Build quality | compiler warnings, lint and type errors, known-vulnerable dependencies | 0 |

## Goals

- **M1:** three experiments, each in Java, Python and JavaScript, each starting from written
  hypotheses: `access-pattern` (cache lines), `branch` (branch prediction), `boxing` (allocation and
  pointer chasing). A runner that drives JMH, pyperf and mitata and one report that validates their
  output and judges every hypothesis.
- **M2:** Linux `perf` hardware counters (cache and branch misses) to explain each result; flame
  graphs from async-profiler, py-spy and clinic.js on a realistic mini-service.
- **M3:** fixes applied one at a time with significance tests; separating what mattered from noise.

## Non-goals

- Ranking languages. Each runtime gets its own hypotheses; cross-runtime ns/element compares
  different machines (an interpreter and two JITs), not languages.
- Hardware counter explanations in M1 (Windows laptop, no `perf`); M1 explains with controlled
  variants and follow-up runs instead, and says where an explanation is still a hypothesis.
- Running as a hosted service.

## Proposed design

![architecture](../architecture.png)

```
spec/experiments.json  (seeds, sizes, variants, 19 hypotheses, harness profiles)
   │            │                    │
   ▼            ▼                    ▼
java/ JMH    python/ pyperf       js/ mitata (one process per cell and repetition)
   │ jmh-*.json │ pyperf.json        │ mitata.jsonl
   └────────────┴──────────┬─────────┘
                           ▼
   python -m performance_engineering_lab.run / .report
   validate → per-fork estimates → median [min-max], 95% CI, spread → verdicts → report.md + RESULT
```

### Experiments

| Experiment | Kernel (same arithmetic in every variant) | Variants |
|---|---|---|
| `access-pattern` | `s += data[idx[i]]` over all i | `idx` = identity (`sequential`) or a Fisher-Yates permutation (`shuffled`); 16 KB vs 64 MB of data (Java, JS), 4096 vs 2,097,152 list elements (CPython) |
| `branch` | sum of the bytes >= 128 among 65,536 | `branchy` (an `if`) or `branchless` (`v & -(v >>> 7)`), on the bytes `sorted` or in generation order (`shuffled`) |
| `boxing` | sum of 1,048,576 20-bit values | Java: `int[]`, `ArrayList<Integer>`, `Long` accumulator; JS: `Int32Array`, plain array of small integers, array of `{v}`; CPython: `list`, `array('q')`, objects with `__slots__` |

All inputs come from xorshift32 with fixed seeds, identical in the three languages (checked by
shared checksums). In CPython the index lists are rebuilt so their int objects lie in memory in the
order they are read, so only the access to `data` differs between the two orders.

### Harnesses

See ADR 0002. JMH runs every (size, variant) in its own forks with `-prof gc`; pyperf runs each
cell in fresh workers with values per element; mitata runs in a fresh Node.js process per cell
and repetition after an explicit warm-up.

### Verdicts and noise

See ADR 0003: verdicts use the worst-case range across forks; spread above 15% marks a cell noisy;
the runner can pin all harness processes to performance cores (`--cpus 2-7`).

## Alternatives considered

| Option | Why not (yet) |
|---|---|
| One hand-written timing loop per language with the same statistics everywhere | Uniform output, but it re-creates the traps the harnesses exist to avoid (dead-code elimination, warm-up detection, process isolation). M1's backlog item is exactly to use the proper harness. |
| A significance test on means (Welch's t-test or Mann-Whitney) for each hypothesis | Needs more forks than a short run on a shared laptop allows to be meaningful, and a significant difference is not the question: the hypotheses predict a size of effect. The range rule is conservative and simple; significance testing is the M3 item. |
| Linux `perf stat` counters in M1 | The explanation the project wants, but the M1 machine runs Windows; counters are the M2 item, run on Linux. |
| JMH only, with Python and JavaScript calling into the JVM | One harness, but it measures something else. Each runtime's own behaviour (interpreter, V8 elements kinds) is the point. |
| Docker or a dedicated benchmark machine | Better isolation, but not available for M1; the pinned, interleaved, multi-fork design plus reported spread is the substitute, and every result says the machine was shared. |

## Measurement plan (Measure, Analyze, Control)

- **Method:** `make bench CPUS=2-7`: JMH 3 forks x (3 x 500 ms warm-up + 5 x 500 ms) per cell; pyperf
  5 processes x 3 values (min time 100 ms each) after calibration; mitata 5 fresh processes per
  cell, interleaved, at least 642 ms of samples each.
- **Reported:** ns per element median [min-max] across forks, 95% t interval of the mean, spread,
  the harness's own estimate, allocated bytes per element (Java), versions and flags, the verdict of
  each hypothesis with its range.
- **Control:** the spec loader refuses cells without hypotheses; each harness refuses to time a
  kernel that returns the wrong sum; unit tests in all three languages check the shared checksums
  and that variants agree; the report exits 3 if any hypothesis lacks results; CI runs every cell
  through every harness (smoke profile) and prints the `RESULT` line as an annotation.

## Milestones

- **M1:** the three experiments in three runtimes with hypotheses, proper harnesses and verdicts. Done.
- **M2:** hardware counters with Linux `perf`; flame graphs on a mini-service.
- **M3:** fixes one at a time with significance levels; what mattered vs noise.

## Risks and open questions

- **Shared machine.** Other jobs (a GPU training job, other builds) ran during the M1 runs. Pinning,
  interleaving and the range rule limit the damage; noisy cells are labelled.
- **JIT and CPU specific.** Results hold for Temurin 21.0.12.1, Node.js 24.19.0 (V8 13.6), CPython
  3.14.5 and the performance cores of an i7-13700H. A different JIT may vectorize or use conditional
  moves where these did not.
- **Explanations without counters.** Where M1 explains a refuted hypothesis, the explanation is
  backed by a controlled variant or follow-up run, not by hardware counters; M2 checks them.
