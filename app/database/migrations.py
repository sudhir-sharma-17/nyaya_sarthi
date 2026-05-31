import sqlite3
from app.config import settings

def run_db_migrations():
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
    else:
        db_path = "court_ai.db"
        
    print(f"Connecting to database at {db_path} to run schema migrations...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Update cases table schema
    cursor.execute("PRAGMA table_info(cases)")
    columns = [row[1] for row in cursor.fetchall()]
    
    new_cols = {
        "evidence_notes": "TEXT",
        "evidence_deadline": "DATETIME",
        "evidence_uploaded": "BOOLEAN DEFAULT 0",
        "documents_verified": "BOOLEAN DEFAULT 0",
        "parties_notified": "BOOLEAN DEFAULT 0",
        "investigation_completed": "BOOLEAN DEFAULT 0",
        "postponed_until": "DATETIME",
        "postponement_reason": "TEXT",
        "is_bail_matter": "BOOLEAN DEFAULT 0",
        "is_child_protection": "BOOLEAN DEFAULT 0",
        "is_medical_emergency": "BOOLEAN DEFAULT 0",
        "is_domestic_violence": "BOOLEAN DEFAULT 0",
        "hearing_time": "TEXT",
        "court_room": "TEXT",
        "judge_name": "TEXT",
        # ── Unified Priority Score (master score 0-100) ──
        "priority_score": "REAL DEFAULT 0.0",
    }
    
    for col, col_type in new_cols.items():
        if col not in columns:
            try:
                cursor.execute(f"ALTER TABLE cases ADD COLUMN {col} {col_type}")
                print(f"Added column {col} to cases table.")
            except Exception as e:
                print(f"Migration error adding {col}: {e}")
                
    # 2. Create system_settings table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    
    # Initialize current simulated date if not exists
    cursor.execute("SELECT value FROM system_settings WHERE key = 'current_sim_date'")
    row = cursor.fetchone()
    if not row:
        from datetime import datetime
        cursor.execute("INSERT INTO system_settings (key, value) VALUES ('current_sim_date', ?)", (datetime.utcnow().strftime("%Y-%m-%d"),))
        print("Initialized current_sim_date in system_settings.")
        
    conn.commit()
    conn.close()
    print("Schema migrations completed successfully.")
