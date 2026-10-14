// The measured loops. Variants of one experiment do the same arithmetic on the same values.
// Each benchmark process calls a kernel with one input type only, so V8's type feedback stays
// monomorphic; the expected results are computed by separate reference functions (cells.js).

/** Sum of data[idx[i]] in idx order. @param {Int32Array} data @param {Int32Array} idx */
export function gather(data, idx) {
  let s = 0;
  for (let i = 0; i < idx.length; i++) s += /** @type {number} */ (data[/** @type {number} */ (idx[i])]);
  return s;
}

/** Sum of the values >= 128, with an if. @param {Int32Array} bytes */
export function branchy(bytes) {
  let s = 0;
  for (let i = 0; i < bytes.length; i++) {
    const v = /** @type {number} */ (bytes[i]);
    if (v >= 128) s += v;
  }
  return s;
}

/** Sum of the byte values >= 128, with a mask from bit 7 instead of an if. @param {Int32Array} bytes */
export function branchless(bytes) {
  let s = 0;
  for (let i = 0; i < bytes.length; i++) {
    const v = /** @type {number} */ (bytes[i]);
    s += v & -(v >>> 7);
  }
  return s;
}

/** Sum of a typed array or a plain array of small integers. @param {Int32Array | number[]} values */
export function sum(values) {
  let s = 0;
  for (let i = 0; i < values.length; i++) s += /** @type {number} */ (values[i]);
  return s;
}

/** Sum of the v field of every object. @param {{ v: number }[]} items */
export function sumField(items) {
  let s = 0;
  for (let i = 0; i < items.length; i++) s += /** @type {{ v: number }} */ (items[i]).v;
  return s;
}
