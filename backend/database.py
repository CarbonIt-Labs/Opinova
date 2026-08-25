import sqlite3
import os
import json
import uuid
import datetime

DB_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "data.db")

def get_connection():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')
    
    # Insert default admin if not exists
    cursor.execute("SELECT * FROM users WHERE username='admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (id, username, password) VALUES (?, ?, ?)", (str(uuid.uuid4()), 'admin', 'admin123'))
        
    # Files table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            filename TEXT,
            filepath TEXT,
            status TEXT DEFAULT 'uploaded',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Clusters (Issues) table - create if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clusters (
            id TEXT PRIMARY KEY,
            file_id TEXT,
            topic TEXT,
            category TEXT,
            priority_score INTEGER,
            status TEXT DEFAULT 'pending',
            is_suggestion INTEGER DEFAULT 0,
            full_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(file_id) REFERENCES files(id)
        )
    ''')
    
    # Feedback cache table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback_cache (
            hash TEXT PRIMARY KEY,
            cluster_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Metrics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT,
            tokens_before INTEGER,
            tokens_after INTEGER,
            reduction_percent REAL,
            duplicates_merged INTEGER,
            preprocessing_time REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(file_id) REFERENCES files(id)
        )
    ''')

    # Migration: add file_id column if it doesn't exist (for old databases)
    try:
        cursor.execute("ALTER TABLE clusters ADD COLUMN file_id TEXT")
        print("[DB Migration] Added file_id column to existing clusters table.")
    except Exception:
        pass  # Column already exists, that's fine

    
    conn.commit()
    conn.close()

def get_default_user():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users ORDER BY rowid LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"id": row[0], "username": row[1]}
        return {"id": None, "username": "admin"}
    except Exception as e:
        print(f"Error getting default user: {e}")
        return {"id": None, "username": "admin"}

def update_default_user(username, password=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users ORDER BY rowid LIMIT 1")
        row = cursor.fetchone()
        if row:
            user_id = row[0]
            if password:
                cursor.execute("UPDATE users SET username=?, password=? WHERE id=?", (username, password, user_id))
            else:
                cursor.execute("UPDATE users SET username=? WHERE id=?", (username, user_id))
        else:
            cursor.execute(
                "INSERT INTO users (id, username, password) VALUES (?, ?, ?)",
                (str(uuid.uuid4()), username, password or "admin123")
            )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating default user: {e}")
        return False

def authenticate(username, password):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()
        return bool(user)
    except Exception as e:
        print(f"Auth error: {e}")
        return False

def add_file(filename, filepath):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        file_id = str(uuid.uuid4())
        cursor.execute("INSERT INTO files (id, filename, filepath, status) VALUES (?, ?, ?, 'uploaded')", (file_id, filename, filepath))
        conn.commit()
        conn.close()
        return file_id
    except Exception as e:
        print(f"Error adding file: {e}")
        return None

def get_files():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, filepath, status, created_at FROM files ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [{"id": r[0], "filename": r[1], "filepath": r[2], "status": r[3], "created_at": r[4]} for r in rows]
    except Exception as e:
        print(f"Error getting files: {e}")
        return []

def get_file_by_id(file_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, filepath, status FROM files WHERE id=?", (file_id,))
        r = cursor.fetchone()
        conn.close()
        if r:
            return {"id": r[0], "filename": r[1], "filepath": r[2], "status": r[3]}
        return None
    except Exception as e:
        print(f"Error getting file: {e}")
        return None

def update_file_status(file_id, status):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE files SET status=? WHERE id=?", (status, file_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating file status: {e}")

def save_clusters(clusters, file_id=None):
    if not file_id:
        return
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clusters WHERE file_id=?", (file_id,))
        for c in clusters:
            c_id = c.get('id', str(uuid.uuid4()))
            c['id'] = c_id
            topic = c.get('topic', '')
            category = c.get('category', '')
            score = c.get('priority_score', 0)
            is_suggestion = 1 if 'suggestion' in category.lower() or 'suggestion' in c.get('issue_type', '').lower() else 0
            full_json = json.dumps(c)
            cursor.execute('''
                INSERT INTO clusters (id, file_id, topic, category, priority_score, status, is_suggestion, full_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (c_id, file_id, topic, category, score, 'pending', is_suggestion, full_json))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving clusters: {e}")

def load_clusters(file_id=None, filter_status=None, suggestions_only=False):
    if not file_id:
        return []
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = "SELECT full_json, status, id FROM clusters WHERE file_id=?"
        params = [file_id]
        
        if filter_status:
            query += " AND status=?"
            params.append(filter_status)
            
        if suggestions_only:
            query += " AND is_suggestion=1"
        else:
            query += " AND is_suggestion=0"
            
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            data = json.loads(row[0])
            data['status'] = row[1]
            data['id'] = row[2]
            results.append(data)
        return results
    except Exception as e:
        print(f"Error loading clusters: {e}")
        return []

def update_cluster_status(cluster_id, status):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE clusters SET status=? WHERE id=?", (status, cluster_id))
        
        # Also update the json payload for consistency
        cursor.execute("SELECT full_json FROM clusters WHERE id=?", (cluster_id,))
        row = cursor.fetchone()
        if row:
            data = json.loads(row[0])
            data['status'] = status
            cursor.execute("UPDATE clusters SET full_json=? WHERE id=?", (json.dumps(data), cluster_id))
            
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating status: {e}")
        return False

def delete_file(file_id):
    try:
        file_info = get_file_by_id(file_id)
        if not file_info:
            return False

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clusters WHERE file_id=?", (file_id,))
        cursor.execute("DELETE FROM files WHERE id=?", (file_id,))
        cursor.execute("DELETE FROM feedback_cache")
        conn.commit()
        conn.close()

        filepath = file_info.get("filepath")
        uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "uploads"))
        if filepath:
            abs_path = os.path.abspath(filepath)
            if abs_path.startswith(uploads_dir) and os.path.exists(abs_path):
                os.remove(abs_path)
        return True
    except Exception as e:
        print(f"Error deleting file: {e}")
        return False

# Cache and Metrics functions

def get_cached_feedback(hash_str: str):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cluster_json FROM feedback_cache WHERE hash=?", (hash_str,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return None
    except Exception as e:
        print(f"Error getting cached feedback: {e}")
        return None

def save_cached_feedback(hash_str: str, cluster_data: dict):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO feedback_cache (hash, cluster_json) VALUES (?, ?)", 
            (hash_str, json.dumps(cluster_data))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving cached feedback: {e}")

def save_metrics(file_id: str, tokens_before: int, tokens_after: int, reduction: float, dup_merged: int, prep_time: float):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO metrics (file_id, tokens_before, tokens_after, reduction_percent, duplicates_merged, preprocessing_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (file_id, tokens_before, tokens_after, reduction, dup_merged, prep_time))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving metrics: {e}")

