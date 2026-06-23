from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KEYWORDS = [
    "个人信息",
    "数据安全",
    "网络安全",
    "数据出境",
    "重要数据",
    "算法推荐",
    "生成式人工智能",
    "人工智能",
    "深度合成",
    "网络数据",
]


def iter_json_files(path: Path):
    if path.is_file() and path.suffix.lower() == ".json":
        yield path
    elif path.is_dir():
        yield from path.rglob("*.json")


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def extract_text(obj) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return "\n".join(extract_text(x) for x in obj)
    if isinstance(obj, dict):
        preferred = []
        for key in ["title", "name", "fullText", "content", "body", "text", "articles"]:
            if key in obj:
                preferred.append(extract_text(obj[key]))
        return "\n".join(preferred or [extract_text(v) for v in obj.values()])
    return ""


def main() -> None:
    source = Path(input("Path to unzipped twang2218/law-datasets law-and-regulations JSON dir/file: ").strip()).expanduser()
    output = ROOT / "data" / "policies" / "imported_open_laws.json"
    records = []
    for path in iter_json_files(source):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        text = compact(extract_text(obj))
        if not text or not any(k in text for k in KEYWORDS):
            continue
        title = obj.get("title") or obj.get("name") or path.stem if isinstance(obj, dict) else path.stem
        chunks = [text[i:i + 900] for i in range(0, min(len(text), 12000), 750)]
        records.append({
            "title": str(title),
            "level": "开源法规语料",
            "source_url": "https://github.com/twang2218/law-datasets",
            "chunks": chunks,
        })
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Imported {len(records)} data-compliance related records to {output}")
    print("Review the imported file, then merge selected records into data/policies/seed_policies.json and run scripts/build_kb.py.")


if __name__ == "__main__":
    main()
