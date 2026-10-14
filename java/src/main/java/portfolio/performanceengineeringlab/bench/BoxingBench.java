package portfolio.performanceengineeringlab.bench;

import java.util.ArrayList;
import java.util.List;
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

/** Allocation and boxing: int[], ArrayList of Integer, or a boxed Long accumulator (spec: boxing). */
@State(Scope.Benchmark)
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Fork(
        value = 3,
        jvmArgs = {"-Xmx512m", "-XX:-UsePerfData"})
@Warmup(iterations = 3, time = 500, timeUnit = TimeUnit.MILLISECONDS)
@Measurement(iterations = 5, time = 500, timeUnit = TimeUnit.MILLISECONDS)
public class BoxingBench {
    /** Number of values per call. */
    @Param({"1048576"})
    public int size;

    /** Container and accumulator. */
    @Param({"int-array", "boxed-list", "boxed-accumulator"})
    public String variant;

    private int[] ints;
    private List<Integer> boxed;
    private int kind;

    /** Builds the values once per fork and checks every variant returns the same sum. */
    @Setup(Level.Trial)
    public void setUp() {
        ints = Datasets.values(size, Datasets.VALUE_SEED, Datasets.VALUE_BITS);
        boxed = new ArrayList<>(size);
        for (int v : ints) {
            boxed.add(v);
        }
        kind = switch (variant) {
            case "int-array" -> 0;
            case "boxed-list" -> 1;
            case "boxed-accumulator" -> 2;
            default -> throw new IllegalArgumentException("unknown boxing variant " + variant);
        };
        long expected = Kernels.sumInts(ints);
        if (Kernels.sumList(boxed) != expected || Kernels.sumBoxedAccumulator(ints) != expected) {
            throw new IllegalStateException("boxing variants disagree");
        }
        if (kind != 1) {
            boxed = List.of();
        }
    }

    /** One pass over all values with the selected variant. */
    @Benchmark
    public long run() {
        return switch (kind) {
            case 0 -> Kernels.sumInts(ints);
            case 1 -> Kernels.sumList(boxed);
            default -> Kernels.sumBoxedAccumulator(ints);
        };
    }
}
