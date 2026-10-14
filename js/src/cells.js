// Reads the JavaScript cells from spec/experiments.json and builds each cell's input.

import { readFileSync, statSync } from "node:fs";
import { identity, permutation, sortedCopy, values } from "./datasets.js";
import { branchless, branchy, gather, sum, sumField } from "./kernels.js";

const SPEC_URL = new URL("../../spec/experiments.json", import.meta.url);
const MAX_SPEC_BYTES = 1 << 20;

/**
 * @typedef {{ value_seed: number, permutation_seed: number, value_bits: number, byte_bits: number }} DataSpec
 * @typedef {{ experiment: string, variant: string, size: number }} Cell
 * @typedef {{ data: DataSpec, cells: Cell[], raw: any }} JsSpec
 * @typedef {{ call: () => number, expected: number }} Prepared
 */

/** Loads the spec (at most 1 MiB) and lists every JavaScript cell. @returns {JsSpec} */
export function loadSpec(url = SPEC_URL) {
  if (statSync(url).size > MAX_SPEC_BYTES) throw new Error(`spec larger than ${MAX_SPEC_BYTES} bytes`);
  const raw = JSON.parse(readFileSync(url, "utf8"));
  const d = raw.data;
  for (const key of ["value_seed", "permutation_seed", "value_bits", "byte_bits"]) {
    if (!Number.isInteger(d?.[key])) throw new Error(`spec data.${key} must be an integer`);
  }
  /** @type {Cell[]} */
  const cells = [];
  for (const e of raw.experiments) {
    const plan = e.runtimes?.js;
    if (!plan) continue;
    for (const size of plan.sizes) for (const variant of plan.variants) cells.push({ experiment: e.id, variant, size });
  }
  return { data: d, cells, raw };
}

/** Reference sum (never used as a measured kernel). @param {Int32Array} v */
function refSum(v) {
  let s = 0;
  for (const x of v) s += x;
  return s;
}

/** Reference sum of the values >= 128 (never used as a measured kernel). @param {Int32Array} v */
function refHigh(v) {
  let s = 0;
  for (const x of v) if (x >= 128) s += x;
  return s;
}

/** The measured call and the result it must return, for one cell. @param {JsSpec} spec @param {Cell} cell @returns {Prepared} */
export function prepare(spec, { experiment, variant, size }) {
  if (!spec.cells.some((c) => c.experiment === experiment && c.variant === variant && c.size === size)) {
    throw new RangeError(`${experiment}/${variant}/${size} is not a JavaScript cell of the spec`);
  }
  const { value_seed: vs, permutation_seed: ps, value_bits: vb, byte_bits: bb } = spec.data;
  if (experiment === "access-pattern") {
    const data = values(size, vs, vb);
    const idx = variant === "shuffled" ? permutation(size, ps) : identity(size);
    return { call: () => gather(data, idx), expected: refSum(data) };
  }
  if (experiment === "branch") {
    const raw = values(size, vs, bb);
    const bytes = variant.endsWith("-sorted") ? sortedCopy(raw) : raw;
    const kernel = variant.startsWith("branchless") ? branchless : branchy;
    return { call: () => kernel(bytes), expected: refHigh(raw) };
  }
  if (experiment === "boxing") {
    const ints = values(size, vs, vb);
    const expected = refSum(ints);
    if (variant === "int32array") return { call: () => sum(ints), expected };
    if (variant === "smi-array") {
      /** @type {number[]} */
      const smis = [];
      for (const x of ints) smis.push(x);
      return { call: () => sum(smis), expected };
    }
    const items = Array.from(ints, (v) => ({ v }));
    return { call: () => sumField(items), expected };
  }
  throw new RangeError(`unknown experiment ${experiment}`);
}
