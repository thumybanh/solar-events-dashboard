"""Formal derivation of the NOAA/LMSAL matching window.

MODEL
-----
Pairs at lag d (minutes between NOAA begin and LMSAL begin, same date, same GOES class) are a
two-component mixture:

    n_d  =  s_d  +  b_d

    s_d : true matches   - the same flare recorded by both catalogues
    b_d : chance pairs   - unrelated flares of the same class, close in time by coincidence

ESTIMATOR
---------
b is estimated from a signal-free sideband, |lag| in [10, 60], where no pair can plausibly be the
same flare. b-hat is the sample mean over those lags, with standard error se = sd / sqrt(m).

LOCAL FALSE DISCOVERY RATE  (Efron 2004)
----------------------------------------
The probability that a pair observed at lag d is NOT a true match:

    lfdr(d) = b_d / n_d

Under 0-1 loss the Bayes-optimal rule accepts a lag when the posterior probability of a true match
exceeds 1/2, i.e. lfdr(d) < 0.5, which is equivalent to

    n_d > 2 * b_d

HYPOTHESIS TEST
---------------
For each lag d, test

    H0: n_d <= 2 * b        (a pair at this lag is no more likely real than chance)
    H1: n_d >  2 * b

Counts are Poisson, so Var(n_d) = n_d, and the estimate b-hat contributes 4 * se^2:

    z_d = (n_d - 2 * b_hat) / sqrt(n_d + 4 * se^2)

The window is the largest W such that H0 is rejected at every lag 1..W.

GLOBAL FDR
----------
Reported for completeness: the expected proportion of false matches among all pairs admitted by a
window W,

    FDR(W) = sum_{|d| <= W} b  /  sum_{|d| <= W} n_d

Read-only: writes nothing.
"""
import math
import os
import statistics
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import window_optimization as WO

SIDEBAND = (10, 60)   # lags where no pair can be the same flare
ALPHA_Z = 1.645       # one-sided 95%


def main():
    obs, _ = WO.lag_counts(WO.load_noaa(), WO.load_lmsal(), null=False)

    lo, hi = SIDEBAND
    side = [obs.get(d, 0) for d in range(-hi, hi + 1) if lo <= abs(d) <= hi]
    m = len(side)
    b_hat = statistics.mean(side)
    sd = statistics.stdev(side)
    se = sd / math.sqrt(m)

    print("BACKGROUND ESTIMATE")
    print(f"  sideband |lag| in [{lo}, {hi}]   m = {m} lags")
    print(f"  b_hat = {b_hat:.3f} pairs per signed lag")
    print(f"  sd    = {sd:.3f}   se = {se:.3f}")
    print(f"  95% CI for b: [{b_hat-1.96*se:.3f}, {b_hat+1.96*se:.3f}]")
    print(f"  per +/- lag pair: B = 2*b_hat = {2*b_hat:.3f}, se_B = {2*se:.3f}")

    B = 2 * b_hat
    seB = 2 * se

    print("\nPER-LAG TEST   H0: n_d <= 2B  (pair no more likely real than chance)")
    print(f"  reject when z > {ALPHA_Z} (one-sided, alpha = 0.05)")
    print(f"\n  {'lag':>4} {'n_d':>7} {'2B':>8} {'lfdr':>7} {'P(real)':>9} {'z':>7}  decision")

    accept_through = 0
    broken = False
    for d in range(1, 11):
        n = obs.get(d, 0) + obs.get(-d, 0)
        lfdr = B / n if n else float('inf')
        p_real = 1 - lfdr
        z = (n - 2 * B) / math.sqrt(n + 4 * seB ** 2) if n else float('-inf')
        ok = z > ALPHA_Z
        if ok and not broken:
            accept_through = d
        elif not ok:
            broken = True
        print(f"  {d:>4} {n:>7.0f} {2*B:>8.1f} {lfdr:>7.3f} {p_real:>8.1%} {z:>7.2f}  "
              f"{'accept' if ok else 'reject'}")

    print(f"\n  => contiguous acceptance through lag {accept_through}")
    print(f"     W = {accept_through}")

    print("\nSENSITIVITY: same test at the bounds of the background CI")
    for label, bb in [("b_hat - 1.96se", b_hat - 1.96 * se),
                      ("b_hat", b_hat),
                      ("b_hat + 1.96se", b_hat + 1.96 * se)]:
        Bx = 2 * bb
        w = 0
        for d in range(1, 31):
            n = obs.get(d, 0) + obs.get(-d, 0)
            if n and (n - 2 * Bx) / math.sqrt(n + 4 * seB ** 2) > ALPHA_Z:
                w = d
            else:
                break
        print(f"  {label:<16} B = {Bx:>6.2f}  ->  W = {w}")

    print("\nGLOBAL FDR — expected share of false matches admitted by window W")
    print(f"  {'W':>3} {'pairs admitted':>16} {'expected false':>16} {'FDR':>9}")
    cum_n = obs.get(0, 0)
    cum_b = b_hat
    print(f"  {0:>3} {cum_n:>16,.0f} {cum_b:>16.1f} {cum_b/cum_n:>9.4%}")
    for W in range(1, 11):
        cum_n += obs.get(W, 0) + obs.get(-W, 0)
        cum_b += B
        print(f"  {W:>3} {cum_n:>16,.0f} {cum_b:>16.1f} {cum_b/cum_n:>9.4%}")
    print("\n  Global FDR stays far below 1% for every W, so it imposes no constraint;")
    print("  the lag-0 spike dominates the numerator. The local test above is what discriminates.")


if __name__ == '__main__':
    main()
