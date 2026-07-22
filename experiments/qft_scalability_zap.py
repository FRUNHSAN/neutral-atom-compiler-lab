#!/usr/bin/env python3
"""Run ZAP QFT scalability — direct Zap class."""
import json, time, os, csv, sys

LOG = "d:/neutral-atom-compiler-lab/application/compare/ZAP_NAC/qft_scalability_zap_log.txt"
os.chdir("d:/neutral-atom-compiler-lab/baselines/neutral-atom-compilation")
sys.path.insert(0, os.getcwd())

from zap.zap import Zap

arch = json.loads(open("architecture/scale_to_500.json").read())
ns = [10, 50, 100, 150]
results = {}

with open(LOG, "w") as log:
    for n in ns:
        bm = f"scalability/qft/qft_n{n}.qasm"
        log.write(f"ZAP QFT n={n}... ")
        log.flush()
        t0 = time.time()
        try:
            zap = Zap(
                benchmark=bm, architecture=arch,
                initial_mapping=[], output_dir=f"fig12_zap_qft_{n}",
                scheduling_strategy="asap_separate", routing_strategy="baseline",
            )
            zap.solve(simulation=False)
            t = time.time() - t0
            results[n] = round(t, 3)
            log.write(f"{t:.3f}s\n")
        except Exception as e:
            log.write(f"ERR: {e}\n")
            results[n] = None
        log.flush()

csv_path = "d:/neutral-atom-compiler-lab/application/fig12_scalability.csv"
with open(csv_path, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["algorithm","n_qubits","compiler","compilation_time_s"])
    for n, t in sorted(results.items()):
        if t is not None:
            w.writerow({"algorithm":"QFT","n_qubits":str(n),"compiler":"ZAP","compilation_time_s":str(t)})

with open(LOG, "a") as log:
    log.write(f"Done. {len([v for v in results.values() if v])} points\n")
