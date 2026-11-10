#!/usr/bin/env python3
"""Generate the synthetic NCM cell production defect log used by the demo.

SYNTHETIC DATA - generated with a fixed seed for reproducibility.
No real production data, no real company data.
Run:  python scripts/generate_sample_data.py
"""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)

# defect_code -> (category (fishbone 6M), description, weight)
DEFECTS = {
    "ELEC-101": ("Material", "Electrode coating thickness out of spec", 0.26),
    "WELD-204": ("Machine", "Tab weld weak / burn-through", 0.20),
    "SEAL-310": ("Method", "Pouch seal leak at edge", 0.14),
    "CONT-118": ("Material", "Electrolyte contamination particles", 0.10),
    "ALIGN-207": ("Machine", "Cell stacking misalignment", 0.09),
    "TEMP-330": ("Environment", "Formation chamber temperature excursion", 0.07),
    "LABEL-410": ("Man", "Label / print mismatch on finished cell", 0.05),
    "CAL-512": ("Measurement", "Sensor calibration drift on coating line", 0.05),
    "MISC-999": ("Method", "Other / unclassified", 0.04),
}

LINES = ["Line A", "Line B", "Line C"]
SHIFTS = ["Day", "Night", "Swing"]
START = date(2026, 9, 28)  # ~6 weeks of production
DAYS = 40

CODES = list(DEFECTS)
WEIGHTS = [DEFECTS[c][2] for c in CODES]

rows = []
for day in range(DAYS):
    d = START + timedelta(days=day)
    # 6-12 incidents per day, more on weekdays
    n = random.randint(6, 12) if d.weekday() < 5 else random.randint(3, 6)
    for _ in range(n):
        code = random.choices(CODES, weights=WEIGHTS, k=1)[0]
        category, desc, _ = DEFECTS[code]
        rows.append(
            {
                "date": d.isoformat(),
                "line": random.choice(LINES),
                "defect_code": code,
                "category": category,
                "units_affected": random.randint(5, 220),
                "shift": random.choice(SHIFTS),
                "description": desc,
            }
        )

df = pd.DataFrame(rows)
df = df.sort_values(["date", "line"]).reset_index(drop=True)

out = Path(__file__).resolve().parent.parent / "data" / "defects.csv"
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="") as f:
    f.write("# SYNTHETIC DATA - generated for demonstration only, not real production data\n")
    df.to_csv(f, index=False)

print(f"Wrote {len(df)} rows to {out}")
print(df["defect_code"].value_counts().to_string())
