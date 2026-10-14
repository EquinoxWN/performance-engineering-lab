package portfolio.performanceengineeringlab.kernels;

import java.util.List;

/** The measured loops. Variants of one experiment do the same arithmetic on the same values. */
public final class Kernels {
    private Kernels() {}

    /** Sum of data[idx[i]] in idx order. */
    public static long gather(int[] data, int[] idx) {
        long s = 0;
        for (int i = 0; i < idx.length; i++) {
            s += data[idx[i]];
        }
        return s;
    }

    /** Sum of the values >= 128, with an if. */
    public static long branchy(int[] bytes) {
        long s = 0;
        for (int v : bytes) {
            if (v >= 128) {
                s += v;
            }
        }
        return s;
    }

    /** Sum of the byte values >= 128, with a mask from bit 7 instead of an if. */
    public static long branchless(int[] bytes) {
        long s = 0;
        for (int v : bytes) {
            s += v & -(v >>> 7);
        }
        return s;
    }

    /** Sum of a primitive array into a primitive accumulator. */
    public static long sumInts(int[] values) {
        long s = 0;
        for (int v : values) {
            s += v;
        }
        return s;
    }

    /** Sum of a list of boxed integers, written the everyday way. */
    public static long sumList(List<Integer> values) {
        long s = 0;
        for (int v : values) {
            s += v;
        }
        return s;
    }

    /** Sum of a primitive array into a boxed accumulator (each += boxes a new Long). */
    public static long sumBoxedAccumulator(int[] values) {
        Long s = 0L;
        for (int v : values) {
            s += v;
        }
        return s;
    }
}
