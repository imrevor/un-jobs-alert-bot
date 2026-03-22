import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "jobs.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filter_type TEXT,
            filter_value TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            UNIQUE(user_id, filter_type, filter_value)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            organization TEXT,
            location TEXT,
            url TEXT,
            grade TEXT,
            posted_at TIMESTAMP,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS sent_jobs (
            user_id INTEGER,
            job_id TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, job_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (job_id) REFERENCES jobs(job_id)
        )
    """)
    
    conn.commit()
    conn.close()

def add_user(user_id, username=None, first_name=None):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO users (user_id, username, first_name, active) VALUES (?, ?, ?, 1)",
        (user_id, username, first_name)
    )
    conn.commit()
    conn.close()

def add_filter(user_id, filter_type, filter_value):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO user_filters (user_id, filter_type, filter_value) VALUES (?, ?, ?)",
        (user_id, filter_type, filter_value.lower())
    )
    conn.commit()
    conn.close()

def remove_filter(user_id, filter_type, filter_value):
    conn = get_conn()
    conn.execute(
        "DELETE FROM user_filters WHERE user_id = ? AND filter_type = ? AND filter_value = ?",
        (user_id, filter_type, filter_value.lower())
    )
    conn.commit()
    conn.close()

def clear_filters(user_id, filter_type=None):
    conn = get_conn()
    if filter_type:
        conn.execute("DELETE FROM user_filters WHERE user_id = ? AND filter_type = ?", (user_id, filter_type))
    else:
        conn.execute("DELETE FROM user_filters WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_filters(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT filter_type, filter_value FROM user_filters WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    filters = {}
    for row in rows:
        ft = row["filter_type"]
        if ft not in filters:
            filters[ft] = []
        filters[ft].append(row["filter_value"])
    return filters

def get_all_active_users():
    conn = get_conn()
    rows = conn.execute("SELECT user_id FROM users WHERE active = 1").fetchall()
    conn.close()
    return [row["user_id"] for row in rows]

def add_job(job_id, title, organization, location, url, grade="", posted_at=None, source="unjobs"):
    conn = get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO jobs (job_id, title, organization, location, url, grade, posted_at, source) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, title, organization, location, url, grade, posted_at, source)
    )
    conn.commit()
    conn.close()

def get_unsent_jobs(user_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT j.* FROM jobs j 
        WHERE j.job_id NOT IN (SELECT job_id FROM sent_jobs WHERE user_id = ?)
        ORDER BY j.scraped_at DESC
    """, (user_id,)).fetchall()
    conn.close()
    return rows

def mark_job_sent(user_id, job_id):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO sent_jobs (user_id, job_id) VALUES (?, ?)", (user_id, job_id))
    conn.commit()
    conn.close()

def get_job_count():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) as cnt FROM jobs").fetchone()["cnt"]
    conn.close()
    return count

def get_user_counter(user_id, counter_name):
    """Get a named counter for a user (returns 0 if not exists)"""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_counters (
            user_id INTEGER,
            counter_name TEXT,
            counter_value INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, counter_name)
        )
    """)
    conn.commit()
    row = conn.execute(
        "SELECT counter_value FROM user_counters WHERE user_id = ? AND counter_name = ?",
        (user_id, counter_name)
    ).fetchone()
    conn.close()
    return row["counter_value"] if row else 0

def increment_user_counter(user_id, counter_name):
    """Increment a named counter, return new value"""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_counters (
            user_id INTEGER,
            counter_name TEXT,
            counter_value INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, counter_name)
        )
    """)
    conn.execute("""
        INSERT INTO user_counters (user_id, counter_name, counter_value) VALUES (?, ?, 1)
        ON CONFLICT(user_id, counter_name) DO UPDATE SET counter_value = counter_value + 1
    """, (user_id, counter_name))
    conn.commit()
    row = conn.execute(
        "SELECT counter_value FROM user_counters WHERE user_id = ? AND counter_name = ?",
        (user_id, counter_name)
    ).fetchone()
    conn.close()
    return row["counter_value"]

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
