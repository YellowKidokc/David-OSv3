import sqlite3
db = sqlite3.connect(r"D:\DONT TOUCH BOOT UP\filetagger\site_claims.db")
total = db.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
files = db.execute("SELECT COUNT(DISTINCT file_path) FROM claims").fetchone()[0]
whats = db.execute("SELECT COUNT(*) FROM claims WHERE [primary]='WHAT'").fetchone()[0]
hows = db.execute("SELECT COUNT(*) FROM claims WHERE [primary]='HOW'").fetchone()[0]
whys = db.execute("SELECT COUNT(*) FROM claims WHERE [primary]='WHY'").fetchone()[0]
mixed = db.execute("SELECT COUNT(*) FROM claims WHERE mixed=1").fetchone()[0]
overreach = db.execute("SELECT COUNT(*) FROM claims WHERE overreach_risk IN ('medium','high')").fetchone()[0]
pos_mm = db.execute("SELECT COUNT(*) FROM claims WHERE pos_mismatch=1").fetchone()[0]
print(f"SITE CLAIMS SUMMARY")
print(f"  Files scanned:     {files}")
print(f"  Total claims:      {total}")
print(f"  WHAT-primary:      {whats} ({round(whats/total*100,1)}%)")
print(f"  HOW-primary:       {hows} ({round(hows/total*100,1)}%)")
print(f"  WHY-primary:       {whys} ({round(whys/total*100,1)}%)")
print(f"  Mixed:             {mixed}")
print(f"  Overreach flags:   {overreach}")
print(f"  POS mismatches:    {pos_mm}")
print()
print("TOP FILES BY CLAIM COUNT:")
for r in db.execute("SELECT file_path, COUNT(*) as c FROM claims GROUP BY file_path ORDER BY c DESC LIMIT 10"):
    name = r[0].split("\\")[-1][:50]
    print(f"  {r[1]:4d}  {name}")
