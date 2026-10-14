package portfolio.performanceengineeringlab.bench;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import portfolio.performanceengineeringlab.SpecJson;
import portfolio.performanceengineeringlab.data.Datasets;
import portfolio.performanceengineeringlab.kernels.Kernels;

class BenchStateTest {
    private static final Map<String, Object> SPEC = SpecJson.load();

    private static List<?> plan(int experiment, String key) {
        return (List<?>) SpecJson.at(SPEC, "experiments", experiment, "runtimes", "java", key);
    }

    private static String[] params(Class<?> bench, String field) throws NoSuchFieldException {
        return bench.getField(field).getAnnotation(Param.class).value();
    }

    @Test
    void paramDefaultsAreExactlyTheSpecSizesAndVariants() throws NoSuchFieldException {
        Class<?>[] benches = {AccessPatternBench.class, BranchBench.class, BoxingBench.class};
        for (int e = 0; e < benches.length; e++) {
            assertArrayEquals(plan(e, "sizes").stream().map(String::valueOf).toArray(), params(benches[e], "size"));
            assertArrayEquals(plan(e, "variants").toArray(), params(benches[e], "variant"));
            assertEquals(
                    Mode.AverageTime,
                    benches[e].getAnnotation(BenchmarkMode.class).value()[0]);
            assertEquals(
                    TimeUnit.NANOSECONDS,
                    benches[e].getAnnotation(OutputTimeUnit.class).value());
        }
    }

    @Test
    void everyAccessPatternVariantReturnsThePlainSum() {
        long expected = Kernels.sumInts(Datasets.values(4096, Datasets.VALUE_SEED, Datasets.VALUE_BITS));
        for (Object v : plan(0, "variants")) {
            AccessPatternBench b = new AccessPatternBench();
            b.size = 4096;
            b.variant = (String) v;
            b.setUp();
            assertEquals(expected, b.run(), b.variant);
        }
    }

    @Test
    void everyBranchVariantReturnsTheSumOfHighBytes() {
        long expected = (Long) SpecJson.at(SPEC, "checks", "bytes_65536", "sum_at_least_128");
        for (Object v : plan(1, "variants")) {
            BranchBench b = new BranchBench();
            b.size = 65536;
            b.variant = (String) v;
            b.setUp();
            assertEquals(expected, b.run(), b.variant);
        }
    }

    @Test
    void everyBoxingVariantReturnsThePlainSum() {
        long expected = (Long) SpecJson.at(SPEC, "checks", "values_4096", "sum");
        for (Object v : plan(2, "variants")) {
            BoxingBench b = new BoxingBench();
            b.size = 4096;
            b.variant = (String) v;
            b.setUp();
            assertEquals(expected, b.run(), b.variant);
        }
    }

    @Test
    void unknownVariantsAreRejected() {
        AccessPatternBench a = new AccessPatternBench();
        a.size = 16;
        a.variant = "reversed";
        assertThrows(IllegalArgumentException.class, a::setUp);
        BranchBench b = new BranchBench();
        b.size = 16;
        b.variant = "branchy-random";
        assertThrows(IllegalArgumentException.class, b::setUp);
        BoxingBench x = new BoxingBench();
        x.size = 16;
        x.variant = "long-array";
        assertThrows(IllegalArgumentException.class, x::setUp);
    }
}
