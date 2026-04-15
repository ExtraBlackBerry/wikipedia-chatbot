import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from db.database import get_conn, setup_db

if __name__ == "__main__":
    conn = get_conn()
    setup_db(conn)
    print("Database setup complete.")