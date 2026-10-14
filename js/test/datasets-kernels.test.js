import test from "node:test";
import assert from "node:assert/strict";
import { MAX_SIZE, XorShift32, identity, permutation, sortedCopy, values, weightedChecksum } from "../src/datasets.js";
import { branchless, branchy, gather, sum, sumField } from "../src/kernels.js";
import { loadSpec } from "../src/cells.js";

const spec = loadSpec();
const checks = spec.raw.checks;
const { value_seed: VS, permutation_seed: PS, value_bits: VB, byte_bits: BB } = spec.data;

/** Sum of an Int32Array. @param {Int32Array} v */
const total = (v) => v.reduce((a, b) => a + b, 0);

test("xorshift32 matches the reference sequence and rejects bad seeds", () => {
  const rng = new XorShift32(1);
  assert.deepEqual([rng.next(), rng.next(), rng.next()], checks.xorshift32_seed1_first);
  for (const bad of [0, -1, 2 ** 32, 1.5]) assert.throws(() => new XorShift32(bad), RangeError);
});

test("values, permutation and bytes match the spec checksums", () => {
  const v = values(4096, VS, VB);
  assert.equal(total(v), checks.values_4096.sum);
  assert.deepEqual(Array.from(v.subarray(0, 3)), checks.values_4096.first);
  const p = permutation(4096, PS);
  assert.equal(weightedChecksum(p), checks.permutation_4096.weighted);
  assert.deepEqual(Array.from(p.subarray(0, 3)), checks.permutation_4096.first);
  const b = Array.from(values(65536, VS, BB)).filter((x) => x >= 128);
  assert.equal(b.reduce((a, x) => a + x, 0), checks.bytes_65536.sum_at_least_128);
  assert.equal(b.length, checks.bytes_65536.count_at_least_128);
});

test("permutations are permutations for random sizes", () => {
  const rng = new XorShift32(77);
  for (let t = 0; t < 50; t++) {
    const n = rng.next() % 3000;
    assert.deepEqual(sortedCopy(permutation(n, 1 + (rng.next() % 1000))), identity(n));
  }
});

test("bad sizes and widths are rejected", () => {
  assert.throws(() => values(-1, 1, 20), RangeError);
  assert.throws(() => values(MAX_SIZE + 1, 1, 20), RangeError);
  assert.throws(() => values(10, 1, 0), RangeError);
  assert.throws(() => identity(1.5), RangeError);
});

test("every variant of an experiment computes the same result (200 random inputs)", () => {
  const rng = new XorShift32(9);
  for (let t = 0; t < 200; t++) {
    const n = rng.next() % 500;
    const seed = 1 + (rng.next() % 0xfffffff0);
    const data = values(n, seed, VB);
    const expected = total(data);
    assert.equal(gather(data, identity(n)), expected);
    assert.equal(gather(data, permutation(n, seed)), expected);
    assert.equal(sum(data), expected);
    assert.equal(sum(Array.from(data)), expected);
    assert.equal(sumField(Array.from(data, (v) => ({ v }))), expected);
    const bytes = values(n, seed, BB);
    assert.equal(branchless(bytes), branchy(bytes));
    assert.equal(branchy(sortedCopy(bytes)), branchy(bytes));
  }
  const edge = Int32Array.from([0, 127, 128, 255]);
  assert.equal(branchy(edge), 383);
  assert.equal(branchless(edge), 383);
});
