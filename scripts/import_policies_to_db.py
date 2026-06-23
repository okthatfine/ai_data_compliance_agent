from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repository import db_counts, sync_policies_to_db

if __name__ == "__main__":
    result = sync_policies_to_db()
    print(f"Synced {result['documents']} legal documents and {result['chunks']} chunks into database")
    print(db_counts())
