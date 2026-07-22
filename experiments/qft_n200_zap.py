#!/usr/bin/env python3
"""ZAP QFT N=200 — single point for Fig.12."""
import json, time, os, sys
os.chdir("d:/neutral-atom-compiler-lab/baselines/neutral-atom-compilation")
sys.path.insert(0, os.getcwd())
from zap.zap import Zap

arch = json.loads(open("architecture/scale_to_500.json").read())
t0 = time.time()
zap = Zap(benchmark="scalability/qft/qft_n200.qasm", architecture=arch,
          initial_mapping=[], output_dir="fig12_qft_n200",
          scheduling_strategy="asap_separate", routing_strategy="baseline")
zap.solve(simulation=False)
t = time.time() - t0
print(f"QFT N=200: {t:.3f}s")

# Append to CSV
with open("d:/neutral-atom-compiler-lab/application/fig12_scalability.csv", "a") as f:
    f.write(f"QFT,200,ZAP,{t:.3f}\n")
print("CSV updated")
