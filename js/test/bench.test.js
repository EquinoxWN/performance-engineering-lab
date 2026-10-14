import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { loadSpec, prepare } from "../src/cells.js";
import { parseOptions } from "../src/bench.js";

const BENCH = fileURLToPath(new URL("../src/bench.js", import.meta.url));
const spec = loadSpec();

/** Runs bench.js in a fresh, heap-capped process. @param {string[]} args */
const run = (args) => spawnSync(process.execPath, ["--max-old-space-size=512", BENCH, ...args], { encoding: "utf8" });

test("the spec lists 11 JavaScript cells and each prepares a call returning its expected result", () => {
  assert.equal(spec.cells.length, 11);
  for (const cell of spec.cells) {
    const { call, expected } = prepare(spec, cell);
    assert.equal(call(), expected, `${cell.experiment}/${cell.variant}`);
  }
});

test("cells outside the spec are refused", () => {
  assert.throws(() => prepare(spec, { experiment: "branch", variant: "branchy-sorted", size: 1 }), RangeError);
  assert.throws(() => prepare(spec, { experiment: "nope", variant: "x", size: 4096 }), RangeError);
});

test("one process prints one valid mitata result line", () => {
  const r = run(["--experiment", "branch", "--variant", "branchless-sorted", "--size", "65536", "--min-cpu-ms", "50"]);
  assert.equal(r.status, 0, r.stderr);
  const lines = r.stdout.trim().split("\n");
  assert.equal(lines.length, 1);
  const rec = JSON.parse(/** @type {string} */ (lines[0]));
  assert.equal(rec.harness, "mitata");
  assert.equal(rec.checksum, spec.raw.checks.bytes_65536.sum_at_least_128);
  assert.deepEqual(rec.exec_argv, ["--max-old-space-size=512"]);
  assert.ok(rec.samples > 0 && rec.ns_per_call.min <= rec.ns_per_call.p50 && rec.ns_per_call.p50 <= rec.ns_per_call.max);
});

test("bad arguments exit with 2 and say why", () => {
  for (const args of [
    [],
    ["--experiment", "branch", "--variant", "branchy-sorted"],
    ["--experiment", "branch", "--variant", "branchy-sorted", "--size", "-3"],
    ["--experiment", "branch", "--variant", "nope", "--size", "65536"],
    ["--experiment", "branch", "--variant", "branchy-sorted", "--size", "65536", "--unknown", "1"],
  ]) {
    const r = run(args);
    assert.equal(r.status, 2, args.join(" "));
    assert.match(r.stderr, /error:/);
  }
  assert.throws(() => parseOptions(["--experiment", "a", "--variant", "b", "--size", "1", "--min-cpu-ms", "0"]), RangeError);
});
