// Deterministic inputs shared with the Java and Python experiments (spec/experiments.md).

export const MAX_SIZE = 1 << 26;

/** Marsaglia's xorshift32 on an unsigned 32-bit state. */
export class XorShift32 {
  /** @type {number} */
  #state;

  /** Starts from a non-zero 32-bit seed. @param {number} seed */
  constructor(seed) {
    if (!Number.isInteger(seed) || seed < 1 || seed > 0xffffffff) {
      throw new RangeError(`seed must be an integer in 1..4294967295, got ${seed}`);
    }
    this.#state = seed >>> 0;
  }

  /** Advances and returns the next unsigned 32-bit value. @returns {number} */
  next() {
    let x = this.#state;
    x ^= x << 13;
    x ^= x >>> 17;
    x ^= x << 5;
    this.#state = x >>> 0;
    return this.#state;
  }
}

/** Rejects sizes outside 0..MAX_SIZE. @param {number} n */
function checkSize(n) {
  if (!Number.isInteger(n) || n < 0 || n > MAX_SIZE) {
    throw new RangeError(`size must be an integer in 0..${MAX_SIZE}, got ${n}`);
  }
}

/** The top `bits` bits of n consecutive xorshift32 outputs. @param {number} n @param {number} seed @param {number} bits */
export function values(n, seed, bits) {
  checkSize(n);
  if (!Number.isInteger(bits) || bits < 1 || bits > 31) {
    throw new RangeError(`bits must be an integer in 1..31, got ${bits}`);
  }
  const rng = new XorShift32(seed);
  const shift = 32 - bits;
  const out = new Int32Array(n);
  for (let i = 0; i < n; i++) out[i] = rng.next() >>> shift;
  return out;
}

/** 0..n-1 in order. @param {number} n */
export function identity(n) {
  checkSize(n);
  const out = new Int32Array(n);
  for (let i = 0; i < n; i++) out[i] = i;
  return out;
}

/** Fisher-Yates shuffle of 0..n-1 driven by xorshift32 (j = next() mod (i + 1)). @param {number} n @param {number} seed */
export function permutation(n, seed) {
  const idx = identity(n);
  const rng = new XorShift32(seed);
  for (let i = n - 1; i > 0; i--) {
    const j = rng.next() % (i + 1);
    const t = /** @type {number} */ (idx[i]);
    idx[i] = /** @type {number} */ (idx[j]);
    idx[j] = t;
  }
  return idx;
}

/** A numerically sorted copy. @param {Int32Array} v */
export function sortedCopy(v) {
  return v.slice().sort();
}

/** Sum of (i + 1) * perm[i], used to compare permutations across runtimes. @param {Int32Array} perm */
export function weightedChecksum(perm) {
  let s = 0;
  for (let i = 0; i < perm.length; i++) s += (i + 1) * /** @type {number} */ (perm[i]);
  return s;
}
