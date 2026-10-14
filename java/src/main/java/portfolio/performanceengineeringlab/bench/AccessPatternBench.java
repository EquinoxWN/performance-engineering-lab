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

/** Cache lines: the same gather through the identity or a random permutation (spec: access-pattern). */
@State(Scope.Benchmark)
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Fork(
        value = 3,
        jvmArgs = {"-Xmx512m", "-XX:-UsePerfData"})
@Warmup(iterations = 3, time = 500, timeUnit = TimeUnit.MILLISECONDS)
@Measurement(iterations = 5, time = 500, timeUnit = TimeUnit.MILLISECONDS)
public class AccessPatternBench {
    /** Number of elements gathered per call. */
    @Param({"4096", "16777216"})
    public int size;

    /** Index order: sequential (identity) or shuffled (random permutation). */
    @Param({"sequential", "shuffled"})
    public String variant;

    private int[] data;
    private int[] idx;

    /** Builds the input once per fork and checks both orders add the same values. */
    @Setup(Level.Trial)
    public void setUp() {
        data = Datasets.values(size, Datasets.VALUE_SEED, Datasets.VALUE_BITS);
        idx = switch (variant) {
            case "sequential" -> Datasets.identity(size);
            case "shuffled" -> Datasets.permutation(size, Datasets.PERMUTATION_SEED);
            default -> throw new IllegalArgumentException("unknown access-pattern variant " + variant);
        };
        if (Kernels.gather(data, idx) != Kernels.sumInts(data)) {
            throw new IllegalStateException("gather result differs from the plain sum");
        }
    }

    /** One pass over all elements. */
    @Benchmark
    public long run() {
        return Kernels.gather(data, idx);
    }
}
