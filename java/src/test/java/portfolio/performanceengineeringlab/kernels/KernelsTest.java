package portfolio.performanceengineeringlab.kernels;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.ArrayList;
import java.util.List;
import java.util.SplittableRandom;
import org.junit.jupiter.api.Test;
import portfolio.performanceengineeringlab.data.Datasets;

class KernelsTest {
    @Test
    void gatherThroughAnyPermutationEqualsThePlainSum() {
        SplittableRandom rnd = new SplittableRandom(1);
        for (int t = 0; t < 200; t++) {
            int n = rnd.nextInt(500);
            long seed = 1 + rnd.nextLong(0xFFFF_FFFEL);
            int[] data = Datasets.values(n, seed, 20);
            long sum = Kernels.sumInts(data);
            assertEquals(sum, Kernels.gather(data, Datasets.identity(n)));
            assertEquals(sum, Kernels.gather(data, Datasets.permutation(n, seed)));
        }
    }

    @Test
    void branchyAndBranchlessAgreeOnSortedAndRandomBytes() {
        SplittableRandom rnd = new SplittableRandom(2);
        for (int t = 0; t < 200; t++) {
            int[] b = Datasets.values(rnd.nextInt(500), 1 + rnd.nextLong(0xFFFF_FFFEL), 8);
            long expected = Kernels.branchy(b);
            assertEquals(expected, Kernels.branchless(b));
            assertEquals(expected, Kernels.branchless(Datasets.sortedCopy(b)));
        }
    }

    @Test
    void branchKernelsOnTheEdgeValues() {
        int[] edge = {0, 127, 128, 255};
        assertEquals(383, Kernels.branchy(edge));
        assertEquals(383, Kernels.branchless(edge));
        assertEquals(0, Kernels.branchy(new int[0]));
        assertEquals(0, Kernels.branchless(new int[0]));
    }

    @Test
    void boxedVariantsReturnThePrimitiveSum() {
        SplittableRandom rnd = new SplittableRandom(3);
        for (int t = 0; t < 200; t++) {
            int[] v = Datasets.values(rnd.nextInt(500), 1 + rnd.nextLong(0xFFFF_FFFEL), 20);
            List<Integer> boxed = new ArrayList<>();
            for (int x : v) {
                boxed.add(x);
            }
            long sum = Kernels.sumInts(v);
            assertEquals(sum, Kernels.sumList(boxed));
            assertEquals(sum, Kernels.sumBoxedAccumulator(v));
        }
    }

    @Test
    void largeSumsDoNotOverflow() {
        int[] v = new int[1 << 16];
        java.util.Arrays.fill(v, Integer.MAX_VALUE);
        long expected = (long) Integer.MAX_VALUE * v.length;
        assertEquals(expected, Kernels.sumInts(v));
        assertEquals(expected, Kernels.sumBoxedAccumulator(v));
        assertEquals(expected, Kernels.gather(v, Datasets.identity(v.length)));
    }
}
