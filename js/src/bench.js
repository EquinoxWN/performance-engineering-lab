// One mitata measurement of one cell in a fresh process; prints one JSON line.
// usage: node --max-old-space-size=512 src/bench.js --experiment E --variant V --size N [--min-cpu-ms M]
// Exit codes: 0 ok, 2 bad arguments, 3 the kernel returned a wrong result.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";
import { do_not_optimize, measure } from "mitata";
import { loadSpec, prepare } from "./cells.js";

const MITATA_VERSION = JSON.parse(readFileSync(new URL("../node_modules/mitata/package.json", import.meta.url), "utf8")).version;

/** Strict options; throws on unknown, missing or out-of-range values. @param {string[]} argv */
export function parseOptions(argv) {
  const { values } = parseArgs({
    args: argv,
    strict: true,
    allowPositionals: false,
    options: {
      experiment: { type: "string" },
      variant: { type: "string" },
      size: { type: "string" },
      "min-cpu-ms": { type: "string", default: "642" },
    },
  });
  const { experiment, variant, size } = values;
  if (!experiment || !variant || !size) throw new RangeError("--experiment, --variant and --size are required");
  if (!/^[0-9]{1,9}$/.test(size)) throw new RangeError(`--size must be a positive integer, got ${size}`);
  const minCpu = values["min-cpu-ms"];
  if (!/^[0-9]{1,6}$/.test(minCpu) || Number(minCpu) < 1) throw new RangeError(`--min-cpu-ms must be 1..999999`);
  return { experiment, variant, size: Number(size), minCpuMs: Number(minCpu) };
}

/** Runs the call until it has run at least 5 times and for 250 ms, so V8 has tiered up. @param {() => number} call */
function warmUp(call) {
  const start = performance.now();
  for (let i = 0; i < 5 || performance.now() - start < 250; i++) do_not_optimize(call());
}

/** Builds, checks, warms up and measures one cell. @param {string[]} argv */
export async function main(argv) {
  let opts;
  try {
    opts = parseOptions(argv);
  } catch (err) {
    process.stderr.write(`error: ${err instanceof Error ? err.message : String(err)}\n`);
    return 2;
  }
  const spec = loadSpec();
  let prepared;
  try {
    prepared = prepare(spec, opts);
  } catch (err) {
    process.stderr.write(`error: ${err instanceof Error ? err.message : String(err)}\n`);
    return 2;
  }
  const { call, expected } = prepared;
  const got = call();
  if (got !== expected) {
    process.stderr.write(`error: ${opts.experiment}/${opts.variant}/${opts.size} returned ${got}, expected ${expected}\n`);
    return 3;
  }
  warmUp(call);
  const stats = await measure(() => do_not_optimize(call()), { min_cpu_time: opts.minCpuMs * 1e6 });
  const line = {
    harness: "mitata",
    harness_version: MITATA_VERSION,
    runtime_version: process.version,
    v8: process.versions.v8,
    exec_argv: process.execArgv,
    experiment: opts.experiment,
    variant: opts.variant,
    size: opts.size,
    checksum: got,
    samples: stats.samples.length,
    ns_per_call: { avg: stats.avg, p50: stats.p50, min: stats.min, max: stats.max },
  };
  process.stdout.write(`${JSON.stringify(line)}\n`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main(process.argv.slice(2));
}
