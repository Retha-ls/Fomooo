import sqlite3
import sys
from pathlib import Path

conn = sqlite3.connect(Path(__file__).parent / "opportunities.db")
conn.row_factory = sqlite3.Row

total = conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
with_desc = conn.execute("SELECT COUNT(*) FROM opportunities WHERE description IS NOT NULL").fetchone()[0]
print("%d saved, %d with a description" % (total, with_desc))

term = sys.argv[1] if len(sys.argv) > 1 else "Developer"
rows = conn.execute(
    "SELECT title, company, positions, date_posted, description FROM opportunities WHERE title LIKE ? LIMIT 2",
    ("%" + term + "%",),
).fetchall()
for row in rows:
    print("\n---", row["title"], "|", row["company"], "|", row["positions"], "position(s) |", row["date_posted"])
    text = row["description"] or "NO DESCRIPTION"
    print(text[:600])
    if len(text) > 900:
        print("\n[... %d characters in total ...]\n" % len(text))
        print(text[-300:])