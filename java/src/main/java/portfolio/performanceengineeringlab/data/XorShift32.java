package portfolio.performanceengineeringlab.data;

/** Marsaglia's xorshift32 on an unsigned 32-bit state, identical in all three runtimes. */
public final class XorShift32 {
    private static final long MAX_SEED = 0xFFFF_FFFFL;
    private int state;

    /** Starts from a non-zero 32-bit seed. */
    public XorShift32(long seed) {
        if (seed < 1 || seed > MAX_SEED) {
            throw new IllegalArgumentException("seed must be in 1.." + MAX_SEED + ", got " + seed);
        }
        this.state = (int) seed;
    }

    /** Advances and returns the next value as an unsigned 32-bit number. */
    public long next() {
        int x = state;
        x ^= x << 13;
        x ^= x >>> 17;
        x ^= x << 5;
        state = x;
        return Integer.toUnsignedLong(x);
    }
}
