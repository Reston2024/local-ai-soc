"""Check chainsaw dedup table status."""
import sqlite3

conn = sqlite3.connect("data/graph.db")
c = conn.cursor()

# List all tables
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])

# Check chainsaw_scanned_files schema
schema = c.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='chainsaw_scanned_files'"
).fetchone()
print("\nchainsaw_scanned_files schema:", schema)

# Count rows
if schema:
    count = c.execute("SELECT COUNT(*) FROM chainsaw_scanned_files").fetchone()[0]
    print(f"Rows: {count}")
    if count > 0:
        rows = c.execute("SELECT * FROM chainsaw_scanned_files LIMIT 3").fetchall()
        for row in rows:
            print(row)

conn.close()
