#!/usr/bin/env python3
"""
paper_compare.py — Direct numerical comparison between ZAP paper and our reproduction.

Output:
    application/reproduction_diff.csv  — benchmark-by-benchmark delta
    stdout                              — summary table

The paper gives exactly ONE explicit number: qft_n10 F_wo_1q = 0.541 (Sec.VII.A).
All other paper values are visually estimated from Fig.7 bars (+-0.02 uncertainty).
"""

import json
import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# ---- Load our data --------------------------------------------------

def load_zap_results():
    zap_dir = PROJECT / "baselines" / "neutral-atom-compilation" / "results" / "tqe" / "log"
    results = {}
    for f in os.listdir(str(zap_dir)):
        if not f.endswith(".json"):
            continue
        name = f.replace(".json", "")
        data = json.loads((zap_dir / f).read_text())
        rec = data[-1] if isinstance(data, list) else data
        f_wo_1q = (
            rec["fidelity_2q_gate"]
            * rec["fidelity_idle"]
            * rec["fidelity_handover"]
            * rec["fidelity_decoherence"]
        )
        results[name] = {
            "F_total": round(rec["total_fidelity"], 6),
            "F_wo_1q": round(f_wo_1q, 6),
            "F_2q": round(rec["fidelity_2q_gate"], 6),
            "F_idle": round(rec["fidelity_idle"], 4),
            "F_tr": round(rec["fidelity_handover"], 4),
            "F_dec": round(rec["fidelity_decoherence"], 4),
            "n_1q": rec.get("n_1q_gate", 0),
            "n_2q": rec.get("n_2q_gate", 0),
            "dur_us": rec.get("total_duration", 0),
        }
    return results


def load_zac_results():
    path = PROJECT / "application" / "multi_compiler_results.json"
    if not path.exists():
        return {}
    all_data = json.loads(path.read_text())
    results = {}
    for r in all_data:
        if r["compiler"].upper() == "ZAC":
            results[r["benchmark"]] = {
                "F_total": round(r["f_total"], 6),
                "F_wo_1q": round(r["f_2q"] * r["f_idle"] * r["f_tr"] * r["f_dec"], 6),
                "F_2q": round(r["f_2q"], 6),
            }
    return results


# ---- Paper values --------------------------------------------------

TQE_ORDER = [
    "adder_n4", "qaoa_n6", "qft_n10", "sat_n11", "bv_n14",
    "multiplier_n15", "qnn_n15", "vqc_n15", "qram_n20",
    "knn_n25", "ising_n26", "wstate_n27", "ghz_n30", "cat_n35",
]

# Paper Fig.7 ZAP F_wo_1q values: visually read from stacked bar chart (+-0.02)
# The ONLY exact value from the paper text is qft_n10 = 0.541 (Sec.VII.A)
PAPER_FIG7_ZAP = {
    "adder_n4": 0.93, "qaoa_n6": 0.76, "qft_n10": 0.541,
    "sat_n11": 0.10, "bv_n14": 0.86, "multiplier_n15": 0.10,
    "qnn_n15": 0.47, "vqc_n15": 0.03, "qram_n20": 0.38,
    "knn_n25": 0.34, "ising_n26": 0.68, "wstate_n27": 0.52,
    "ghz_n30": 0.66, "cat_n35": 0.58,
}


def classify_match(benchmark, our_val, paper_val):
    """Classify how well our value matches the paper."""
    delta = our_val - paper_val
    if benchmark == "qft_n10":
        if abs(delta) <= 0.005:
            return "EXACT_MATCH", ""
        else:
            return "DELTA", f"paper={paper_val:.3f}, ours={our_val:.3f}, delta={delta:+.4f} ({delta/paper_val*100:+.1f}%)"
    if abs(delta) < 0.02:
        return "WITHIN_VISUAL_ERROR", ""
    elif abs(delta) < 0.04:
        return "BORDERLINE", f"delta={delta:+.3f}, near visual error bound"
    else:
        return "MISMATCH", f"delta={delta:+.3f}, exceeds +-0.02 visual error"


def main():
    zap = load_zap_results()
    zac = load_zac_results()

    rows = []
    visual_ok = 0
    borderline = 0
    mismatch = 0

    print("=" * 110)
    print("  ZAP Paper vs Our Reproduction")
    print("  Fidelity without single-qubit gates (F_wo_1q)")
    print("=" * 110)
    print()
    print("  Paper gives ONE exact value: qft_n10 = 0.541 (Sec.VII.A, Eq.5)")
    print("  All other paper values: visually read from Fig.7 stacked bars (+-0.02)")
    print()

    hdr = f"{'Benchmark':<18} {'Paper':>8} {'Ours':>8} {'Delta':>8} {'Status':<22} {'Our F_2q':>8} {'Our F_idle':>6}"
    print(hdr)
    print("-" * 90)

    for bm in TQE_ORDER:
        our = zap.get(bm, {})
        our_f = our.get("F_wo_1q", 0)
        pf = PAPER_FIG7_ZAP.get(bm)

        if pf is None:
            print(f"{bm:<18} {'N/A':>8} {our_f:>8.4f} {'N/A':>8}")
            continue

        delta = our_f - pf
        status, note = classify_match(bm, our_f, pf)

        if bm == "qft_n10":
            # Don't count qft_n10 in visual-error stats (it has an exact value)
            pass
        elif "VISUAL" in status:
            visual_ok += 1
        elif "BORDER" in status:
            borderline += 1
        else:
            mismatch += 1

        print(f"{bm:<18} {pf:>8.4f} {our_f:>8.4f} {delta:>+8.4f} {status:<22} "
              f"{our.get('F_2q',0):>8.4f} {our.get('F_idle',0):>6.4f}")

        rows.append({
            "benchmark": bm,
            "paper_F_wo_1q": pf,
            "our_F_wo_1q": our_f,
            "delta": round(delta, 6),
            "status": status,
            "note": note,
            "our_F_total": our.get("F_total", 0),
            "our_F_2q": our.get("F_2q", 0),
            "our_F_idle": our.get("F_idle", 0),
            "our_F_tr": our.get("F_tr", 0),
            "our_F_dec": our.get("F_dec", 0),
            "our_n_1q": our.get("n_1q", 0),
            "our_n_2q": our.get("n_2q", 0),
            "our_dur_us": our.get("dur_us", 0),
        })

    print("-" * 90)
    n_compared = visual_ok + borderline + mismatch
    print(f"  Within visual error (+-0.02): {visual_ok}/{n_compared}")
    print(f"  Borderline (0.02-0.04):      {borderline}/{n_compared}")
    print(f"  Mismatch (>0.04):            {mismatch}/{n_compared}")
    print(f"  qft_n10 (paper exact=0.541): our={zap['qft_n10']['F_wo_1q']:.4f}, "
          f"delta={zap['qft_n10']['F_wo_1q']-0.541:+.4f} "
          f"({zap['qft_n10']['F_wo_1q']/0.541*100-100:+.1f}%)")

    # ZAP vs ZAC ranking
    print()
    print("=" * 80)
    print("  ZAP vs ZAC: F_wo_1q ranking (paper claim: ZAP > ZAC on all)")
    print("=" * 80)
    print(f"{'Benchmark':<18} {'ZAP':>10} {'ZAC':>10} {'Delta':>10} {'ZAP>ZAC?':>10}")
    print("-" * 60)
    zap_wins = 0
    zac_wins = 0
    for bm in TQE_ORDER:
        zf = zap.get(bm, {}).get("F_wo_1q", 0)
        zc = zac.get(bm, {}).get("F_wo_1q", 0)
        if zf and zc:
            delta = zf - zc
            win = "YES" if delta > 0 else "NO"
            if delta > 0:
                zap_wins += 1
            elif delta < 0:
                zac_wins += 1
            print(f"{bm:<18} {zf:>10.6f} {zc:>10.6f} {delta:>+10.6f} {win:>10}")
    print("-" * 60)
    print(f"  ZAP > ZAC: {zap_wins}/{zap_wins+zac_wins} benchmarks")
    print(f"  ZAC > ZAP: {zac_wins}/{zap_wins+zac_wins} benchmarks")

    # Save CSV
    csv_path = PROJECT / "application" / "reproduction_diff.csv"
    with open(str(csv_path), "w") as f:
        keys = rows[0].keys()
        f.write(",".join(keys) + "\n")
        for row in rows:
            f.write(",".join(str(row[k]) for k in keys) + "\n")
    print(f"\n  CSV: {csv_path}")

    print()
    print("  VERDICT:")
    if mismatch == 0 and borderline <= 1:
        print("  [PASS] All benchmark values match within visual reading error.")
        print("  The paper's F_wo_1q data is reproducible under the same Qiskit version.")
    elif mismatch <= 2:
        print(f"  [PARTIAL] {mismatch} benchmark(s) outside visual error.")
        print("  Likely qiskit version drift in compiler-dependent channels.")
    else:
        print("  [CONCERN] Multiple benchmarks outside visual error range.")


if __name__ == "__main__":
    main()
