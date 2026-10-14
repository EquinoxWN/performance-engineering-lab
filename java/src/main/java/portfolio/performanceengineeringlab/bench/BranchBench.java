package portfolio.performanceengineeringlab.bench;

import java.util.concurrent.TimeUnit;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.Warmup;
import portfolio.performanceengineeringlab.data.Datasets;
import portfolio.performanceengineeringlab.kernels.Kernels;

/** Branch prediction: an if or a mask, over sorted or random bytes (spec: branch). */
@State(Scope.Benchmark)
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Fork(
        value = 3,
        jvmArgs = {"-Xmx512m", "-XX:-UsePerfData"})
@Warmup(iterations = 3, time = 500, timeUnit = TimeUnit.MILLISECONDS)
@Measurement(iterations = 5, time = 500, timeUnit = TimeUnit.MILLISECONDS)
public class BranchBench {
    /** Number of bytes per call. */
    @Param({"65536"})
    public int size;

    /** Kernel and byte order. */
    @Param({"branchy-sorted", "branchy-shuffled", "branchless-sorted", "branchless-shuffled"})
    public String variant;

    private int[] bytes;
    private boolean branchless;

    /** Builds the bytes once per fork and checks both kernels agree on them. */
    @Setup(Level.Trial)
    public void setUp() {
        int[] raw = Datasets.values(size, Datasets.VALUE_SEED, Datasets.BYTE_BITS);
        switch (variant) {
            case "branchy-sorted", "branchless-sorted" -> bytes = Datasets.sortedCopy(raw);
            case "branchy-shuffled", "branchless-shuffled" -> bytes = raw;
            default -> throw new IllegalArgumentException("unknown branch variant " + variant);
        }
        branchless = variant.startsWith("branchless");
        if (Kernels.branchy(bytes) != Kernels.branchless(bytes)) {
            throw new IllegalStateException("branchy and branchless kernels disagree");
        }
    }

    /** One pass over all bytes with the selected kernel. */
    @Benchmark
    public long run() {
        return branchless ? Kernels.branchless(bytes) : Kernels.branchy(bytes);
    }
}
