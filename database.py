import os
import psycopg2
from psycopg2.extras import RealDictCursor

DB_URL = os.environ.get("DATABASE_URL")

def get_conn():
    conn = psycopg2.connect(DB_URL)
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_filters (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            filter_type TEXT,
            filter_value TEXT,
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
            user_id BIGINT,
            job_id TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, job_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_counters (
            user_id BIGINT,
            counter_name TEXT,
            counter_value INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, counter_name)
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, username=None, first_name=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO users (user_id, username, first_name, active) 
           VALUES (%s, %s, %s, 1) 
           ON CONFLICT (user_id) DO UPDATE SET active = 1""",
        (user_id, username, first_name)
    )
    conn.commit()
    conn.close()

def add_filter(user_id, filter_type, filter_value):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO user_filters (user_id, filter_type, filter_value) 
           VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
        (user_id, filter_type, filter_value.lower())
    )
    conn.commit()
    conn.close()

def remove_filter(user_id, filter_type, filter_value):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "DELETE FROM user_filters WHERE user_id = %s AND filter_type = %s AND filter_value = %s",
        (user_id, filter_type, filter_value.lower())
    )
    conn.commit()
    conn.close()

def clear_filters(user_id, filter_type=None):
    conn = get_conn()
    c = conn.cursor()
    if filter_type:
        c.execute("DELETE FROM user_filters WHERE user_id = %s AND filter_type = %s", (user_id, filter_type))
    else:
        c.execute("DELETE FROM user_filters WHERE user_id = %s", (user_id,))
    conn.commit()
    conn.close()

def get_filters(user_id):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT filter_type, filter_value FROM user_filters WHERE user_id = %s", (user_id,))
    rows = c.fetchall()
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
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT user_id FROM users WHERE active = 1")
    rows = c.fetchall()
    conn.close()
    return [row["user_id"] for row in rows]

def add_job(job_id, title, organization, location, url, grade="", posted_at=None, source="unjobs"):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO jobs (job_id, title, organization, location, url, grade, posted_at, source) 
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
        (job_id, title, organization, location, url, grade, posted_at, source)
    )
    conn.commit()
    conn.close()

def get_unsent_jobs(user_id):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("""
        SELECT j.* FROM jobs j 
        WHERE j.job_id NOT IN (SELECT job_id FROM sent_jobs WHERE user_id = %s)
        ORDER BY j.scraped_at DESC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def mark_job_sent(user_id, job_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO sent_jobs (user_id, job_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user_id, job_id))
    conn.commit()
    conn.close()

def get_job_count():
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT COUNT(*) as cnt FROM jobs")
    count = c.fetchone()["cnt"]
    conn.close()
    return count

def get_user_counter(user_id, counter_name):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute(
        "SELECT counter_value FROM user_counters WHERE user_id = %s AND counter_name = %s",
        (user_id, counter_name)
    )
    row = c.fetchone()
    conn.close()
    return row["counter_value"] if row else 0

def increment_user_counter(user_id, counter_name):
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("""
        INSERT INTO user_counters (user_id, counter_name, counter_value) VALUES (%s, %s, 1)
        ON CONFLICT(user_id, counter_name) DO UPDATE SET counter_value = user_counters.counter_value + 1
        RETURNING counter_value
    """, (user_id, counter_name))
    val = c.fetchone()["counter_value"]
    conn.commit()
    conn.close()
    return val

if __name__ == "__main__":
    init_db()
    print("Postgres Database initialized.")
