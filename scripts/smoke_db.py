from __future__ import annotations

import json
from pathlib import Path
import sys

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8018"


def show(label: str, payload) -> None:
    print(f"[{label}] {json.dumps(payload, ensure_ascii=False)}")


def main() -> None:
    health = requests.get(f"{BASE_URL}/api/health", timeout=10).json()
    show("health", {"version": health.get("version"), "db": health.get("db")})

    before = requests.get(f"{BASE_URL}/api/db/status", timeout=10).json()
    show("db_before", before.get("counts", {}))

    rebuild = requests.post(f"{BASE_URL}/api/kb/rebuild", timeout=60).json()
    show("rebuild", {"chunks": rebuild.get("chunks"), "db_sync": rebuild.get("db_sync")})

    text = "公司拟抓取公开网页语料训练大模型，收集手机号和人脸信息，并同步给海外供应商。"
    audit = requests.post(f"{BASE_URL}/api/audit", data={"text": text}, timeout=120).json()
    show("audit", {"level": audit.get("overall_level"), "risk_count": audit.get("risk_count"), "report_id": audit.get("report_id")})
    if not audit.get("report_id"):
        raise SystemExit("audit did not return report_id")

    after = requests.get(f"{BASE_URL}/api/db/status", timeout=10).json()
    show("db_after", after.get("counts", {}))
    counts = after.get("counts", {})
    required = ["legal_documents", "legal_versions", "legal_articles", "legal_chunks", "uploads", "reports", "risks"]
    missing = [name for name in required if counts.get(name, 0) <= 0]
    if missing:
        raise SystemExit(f"database counts missing: {missing}")

    reports = requests.get(f"{BASE_URL}/api/reports", timeout=10).json().get("items", [])
    uploads = requests.get(f"{BASE_URL}/api/uploads", timeout=10).json().get("items", [])
    policies = requests.get(f"{BASE_URL}/api/db/policies", timeout=10).json().get("items", [])
    show("lists", {"reports": len(reports), "uploads": len(uploads), "policies": len(policies)})
    if not reports or not uploads or not policies:
        raise SystemExit("list endpoints returned empty result")


if __name__ == "__main__":
    main()
