import sqlite3

conn = sqlite3.connect("data.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS samples (
    timestamp DATE,
    temperature REAL,
    humidity REAL,
    button INTEGER,
    abnormal_movement INTEGER,
    sound_alert INTEGER,
    person_present INTEGER,
    status TEXT
);
""")

conn.commit()
conn.close()

print("Database created!")