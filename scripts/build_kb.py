from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.rag import PolicyVectorStore

if __name__ == "__main__":
    store = PolicyVectorStore()
    count = store.build_from_seed()
    print(f"Built policy vector index with {count} chunks at {store.index_path}")
