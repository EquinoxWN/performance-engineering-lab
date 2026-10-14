package portfolio.performanceengineeringlab.data;

import java.util.Arrays;

/** Deterministic inputs shared with the Python and JavaScript experiments (spec/experiments.md). */
public final class Datasets {
    /** Seed of every value sequence (spec data.value_seed). */
    public static final long VALUE_SEED = 2_463_534_242L;
    /** Seed of the Fisher-Yates permutation (spec data.permutation_seed). */
    public static final long PERMUTATION_SEED = 88_675_123L;
    /** Bits per value in the access-pattern and boxing experiments (spec data.value_bits). */
    public static final int VALUE_BITS = 20;
    /** Bits per value in the branch experiment (spec data.byte_bits). */
    public static final int BYTE_BITS = 8;
    /** Largest input any experiment may ask for. */
    public static final int MAX_SIZE = 1 << 26;

    private Datasets() {}

    /** Rejects sizes outside 0..MAX_SIZE. */
    private static void checkSize(int n) {
        if (n < 0 || n > MAX_SIZE) {
            throw new IllegalArgumentException("size must be in 0.." + MAX_SIZE + ", got " + n);
        }
    }

    /** The top {@code bits} bits of n consecutive xorshift32 outputs. */
    public static int[] values(int n, long seed, int bits) {
        checkSize(n);
        if (bits < 1 || bits > 31) {
            throw new IllegalArgumentException("bits must be in 1..31, got " + bits);
        }
        XorShift32 rng = new XorShift32(seed);
        int shift = 32 - bits;
        int[] out = new int[n];
        for (int i = 0; i < n; i++) {
            out[i] = (int) (rng.next() >>> shift);
        }
        return out;
    }

    /** 0..n-1 in order. */
    public static int[] identity(int n) {
        checkSize(n);
        int[] out = new int[n];
        for (int i = 0; i < n; i++) {
            out[i] = i;
        }
        return out;
    }

    /** Fisher-Yates shuffle of 0..n-1 driven by xorshift32 (j = next() mod (i + 1)). */
    public static int[] permutation(int n, long seed) {
        int[] idx = identity(n);
        XorShift32 rng = new XorShift32(seed);
        for (int i = n - 1; i > 0; i--) {
            int j = (int) (rng.next() % (i + 1));
            int t = idx[i];
            idx[i] = idx[j];
            idx[j] = t;
        }
        return idx;
    }

    /** A sorted copy. */
    public static int[] sortedCopy(int[] values) {
        int[] out = values.clone();
        Arrays.sort(out);
        return out;
    }

    /** Sum of (i + 1) * perm[i], used to compare permutations across runtimes. */
    public static long weightedChecksum(int[] perm) {
        long s = 0;
        for (int i = 0; i < perm.length; i++) {
            s += (long) (i + 1) * perm[i];
        }
        return s;
    }
}
