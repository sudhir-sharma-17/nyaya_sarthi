import sqlite3

def migrate():
    conn = sqlite3.connect('court_ai.db')
    cursor = conn.cursor()
    
    columns_to_add = [
        ("backlog_score", "FLOAT DEFAULT 0.0"),
        ("case_age_days", "INTEGER DEFAULT 0"),
        ("last_hearing_date", "DATETIME"),
        ("hearing_date", "DATETIME"),
        ("judgment_date", "DATETIME"),
        ("inactivity_days", "INTEGER DEFAULT 0"),
        ("adjournment_count", "INTEGER DEFAULT 0"),
        ("cluster_id", "VARCHAR"),
        ("cluster_label", "VARCHAR"),
        ("citations", "TEXT"),
        ("parties_involved", "TEXT"),
        ("extraction_method", "VARCHAR")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE cases ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists.")
            else:
                print(f"Error adding {col_name}: {e}")
                
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
