package portfolio.performanceengineeringlab.data;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.SplittableRandom;
import org.junit.jupiter.api.Test;
import portfolio.performanceengineeringlab.SpecJson;

class DatasetsTest {
    private static final Map<String, Object> SPEC = SpecJson.load();

    private static long num(Object... path) {
        return (Long) SpecJson.at(SPEC, path);
    }

    private static long[] firsts(Object... path) {
        return ((List<?>) SpecJson.at(SPEC, path))
                .stream().mapToLong(o -> (Long) o).toArray();
    }

    @Test
    void xorShift32MatchesTheSharedReferenceSequence() {
        XorShift32 rng = new XorShift32(1);
        assertArrayEquals(firsts("checks", "xorshift32_seed1_first"), new long[] {rng.next(), rng.next(), rng.next()});
    }

    @Test
    void xorShift32RejectsSeedsOutside32BitsAndNeverReachesZero() {
        assertThrows(IllegalArgumentException.class, () -> new XorShift32(0));
        assertThrows(IllegalArgumentException.class, () -> new XorShift32(1L << 32));
        XorShift32 rng = new XorShift32(0xFFFF_FFFFL);
        for (int i = 0; i < 100_000; i++) {
            assertNotEquals(0L, rng.next());
        }
    }

    @Test
    void seedsAndBitWidthsMatchTheSpec() {
        assertEquals(num("data", "value_seed"), Datasets.VALUE_SEED);
        assertEquals(num("data", "permutation_seed"), Datasets.PERMUTATION_SEED);
        assertEquals(num("data", "value_bits"), Datasets.VALUE_BITS);
        assertEquals(num("data", "byte_bits"), Datasets.BYTE_BITS);
    }

    @Test
    void valuesPermutationAndBytesMatchTheSpecChecksums() {
        int[] v = Datasets.values(4096, Datasets.VALUE_SEED, Datasets.VALUE_BITS);
        assertEquals(
                num("checks", "values_4096", "sum"),
                Arrays.stream(v).asLongStream().sum());
        assertArrayEquals(firsts("checks", "values_4096", "first"), new long[] {v[0], v[1], v[2]});
        int[] p = Datasets.permutation(4096, Datasets.PERMUTATION_SEED);
        assertEquals(num("checks", "permutation_4096", "weighted"), Datasets.weightedChecksum(p));
        assertArrayEquals(firsts("checks", "permutation_4096", "first"), new long[] {p[0], p[1], p[2]});
        int[] b = Datasets.values(65536, Datasets.VALUE_SEED, Datasets.BYTE_BITS);
        long high = Arrays.stream(b).filter(x -> x >= 128).asLongStream().sum();
        long count = Arrays.stream(b).filter(x -> x >= 128).count();
        assertEquals(num("checks", "bytes_65536", "sum_at_least_128"), high);
        assertEquals(num("checks", "bytes_65536", "count_at_least_128"), count);
    }

    @Test
    void permutationsArePermutationsAndValuesStayInRange() {
        SplittableRandom rnd = new SplittableRandom(5);
        for (int t = 0; t < 50; t++) {
            int n = rnd.nextInt(3000);
            int[] p = Datasets.permutation(n, 1 + rnd.nextLong(0xFFFF_FFFEL));
            assertArrayEquals(Datasets.identity(n), Datasets.sortedCopy(p));
        }
        assertTrue(Arrays.stream(Datasets.values(5000, 99, 8)).allMatch(x -> x >= 0 && x < 256));
        assertTrue(Arrays.stream(Datasets.values(5000, 99, 20)).allMatch(x -> x >= 0 && x < 1 << 20));
    }

    @Test
    void rejectsBadSizesAndBitWidths() {
        assertThrows(IllegalArgumentException.class, () -> Datasets.values(-1, 1, 20));
        assertThrows(IllegalArgumentException.class, () -> Datasets.values(Datasets.MAX_SIZE + 1, 1, 20));
        assertThrows(IllegalArgumentException.class, () -> Datasets.values(10, 1, 0));
        assertThrows(IllegalArgumentException.class, () -> Datasets.values(10, 1, 32));
        assertThrows(IllegalArgumentException.class, () -> Datasets.identity(-5));
    }
}
