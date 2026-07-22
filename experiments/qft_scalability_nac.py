#!/usr/bin/env python3
"""Run NAC QFT scalability — no stdout during loop, write to file."""
import json, time, os, sys

LOG = "d:/neutral-atom-compiler-lab/application/compare/ZAP_NAC/qft_scalability_log.txt"
os.chdir("d:/neutral-atom-compiler-lab/baselines/neutral-atom-compilation")
sys.path.insert(0, "d:/neutral-atom-compiler-lab")

from instances.nac.implementation.compiler import Compiler

arch = json.loads(open("architecture/scale_to_500.json").read())
ns = [10, 50, 100, 150]
results = {}

with open(LOG, "w") as log:
    for n in ns:
        bm = f"scalability/qft/qft_n{n}.qasm"
        log.write(f"QFT n={n}... ")
        log.flush()
        t0 = time.time()
        try:
            comp = Compiler(
                benchmark=bm, architecture=arch,
                output_dir=f"fig12_qft_{n}",
                scheduling_strategy="asap_separate",
                routing_strategy="baseline",
            )
            comp.solve(simulation=False)
            t = time.time() - t0
            results[n] = round(t, 3)
            log.write(f"{t:.3f}s\n")
        except Exception as e:
            log.write(f"ERR: {e}\n")
            results[n] = None
        log.flush()

# Merge
out_path = "d:/neutral-atom-compiler-lab/application/compare/ZAP_NAC/fig12_nac_results.json"
data = json.loads(open(out_path).read())
data["QFT"] = {str(k): v for k, v in results.items() if v is not None}
with open(out_path, "w") as f:
    json.dump(data, f, indent=2)
with open(LOG, "a") as log:
    log.write(f"Done. {len(data['QFT'])} points saved\n")
