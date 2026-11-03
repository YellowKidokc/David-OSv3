import sqlite3
db = sqlite3.connect(r'D:\DONT TOUCH BOOT UP\filetagger\chi_catalog.db')
print("=" * 60)
print("  CHI FACTOR DISTRIBUTION -- Theophysics Vault v5")
print("  50,820 files scanned")
print("=" * 60)
for r in db.execute(
    "SELECT chi_primary, COUNT(*), ROUND(AVG(chi_confidence),1) "
    "FROM files WHERE chi_primary IS NOT NULL "
    "GROUP BY chi_primary ORDER BY COUNT(*) DESC"
):
    factor, count, avg_conf = r
    print(f"  [{factor:4s}]  {count:6d} files   avg confidence {avg_conf}%")

total = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
uc = db.execute("SELECT COUNT(*) FROM files WHERE chi_primary = 'UC' OR chi_primary IS NULL").fetchone()[0]
print(f"\n  Total: {total}")
print(f"  Classified: {total - uc}")
print(f"  Unclassified: {uc}")
print("=" * 60)

print("\n  TOP EXTENSIONS:")
for r in db.execute(
    "SELECT ext, COUNT(*) FROM files GROUP BY ext ORDER BY COUNT(*) DESC LIMIT 15"
):
    print(f"    {r[0] or '[none]':8s}  {r[1]:6d}")
db.close()
