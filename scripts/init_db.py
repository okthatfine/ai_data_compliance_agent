from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import db_status, init_db
from app.repository import db_counts

if __name__ == "__main__":
    init_db()
    print("Database initialized")
    print(db_status())
    print(db_counts())
