import json, csv
from pathlib import Path

data = json.loads(Path(r"D:\DONT TOUCH BOOT UP\filetagger\consciousness_math.json").read_text(encoding="utf-8"))
eqs = data["equations"]
real = [e for e in eqs if e["type"] in ("display_math", "inline_math", "eq_box")]

out = r"D:\DONT TOUCH BOOT UP\filetagger\consciousness_equations_for_excel.csv"
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["ID", "Type", "Equation_Raw", "Source_File", "Context",
                "English_Translation", "Term_By_Term",
                "Physics_Side", "Theology_Side", "Shared_Structure",
                "Difficulty", "Law_Reference"])
    for i, eq in enumerate(real):
        src = eq["source"].split("\\")[-1].replace(".html", "")[:40]
        w.writerow([
            f"EQ-{i+1:03d}", eq["type"], eq["raw"][:200], src,
            eq["context"][:150], "", "", "", "", "", "", ""
        ])

dm = sum(1 for e in real if e["type"] == "display_math")
im = sum(1 for e in real if e["type"] == "inline_math")
eb = sum(1 for e in real if e["type"] == "eq_box")
print(f"Wrote {len(real)} equations to CSV")
print(f"  display_math: {dm}")
print(f"  inline_math:  {im}")
print(f"  eq_box:       {eb}")
print(f"  Output: {out}")
