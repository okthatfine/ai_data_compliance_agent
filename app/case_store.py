from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .rag import normalize_text

ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "data" / "cases"
CASE_FILES = [
    ROOT / "data" / "cases.json",
    ROOT / "data" / "cases.jsonl",
    ROOT / "data" / "cases.csv",
]


@dataclass
class CaseHit:
    title: str
    case_no: str
    court: str
    year: str
    cause: str
    risk_types: list[str]
    lifecycle_stage: str
    text: str
    source_url: str
    score: float
    source_file: str


class CaseStore:
    """Lightweight local case-library search for the compliance service.

    Supported inputs:
    - data/cases/*.json, *.jsonl, *.csv
    - data/cases.json, data/cases.jsonl, data/cases.csv

    The loader accepts common field names from the case-library Word plan,
    exported CSV/JSON files, and typical court-case datasets.
    """

    def __init__(self, case_dir: Path = CASE_DIR):
        self.case_dir = case_dir
        self._cases: list[dict[str, Any]] | None = None

    def stats(self) -> dict[str, Any]:
        cases = self.load()
        files = sorted({c.get("source_file", "") for c in cases if c.get("source_file")})
        risk_counts: dict[str, int] = {}
        for case in cases:
            for risk in case.get("risk_types", []):
                risk_counts[risk] = risk_counts.get(risk, 0) + 1
        return {
            "ready": bool(cases),
            "cases": len(cases),
            "source_files": files,
            "risk_counts": risk_counts,
        }

    def load(self) -> list[dict[str, Any]]:
        if self._cases is not None:
            return self._cases
        records: list[dict[str, Any]] = []
        for file in self._candidate_files():
            records.extend(self._read_file(file))
        self._cases = [self._normalize_case(r, source_file) for r, source_file in records]
        self._cases = [c for c in self._cases if c.get("title") or c.get("text")]
        return self._cases

    def search(self, query: str, risk_type: str = "", k: int = 3) -> list[CaseHit]:
        query = normalize_text(query)
        risk_type = normalize_text(risk_type)
        if not query and not risk_type:
            return []
        scored: list[tuple[float, dict[str, Any]]] = []
        for case in self.load():
            if risk_type and risk_type not in case.get("risk_types", []):
                continue
            score = self._score_case(query, risk_type, case)
            if score > 0:
                scored.append((score, case))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [self._to_hit(case, score) for score, case in scored[: max(1, min(k, 20))]]

    def _candidate_files(self) -> list[Path]:
        files = [p for p in CASE_FILES if p.exists()]
        if self.case_dir.exists():
            for pattern in ("*.json", "*.jsonl", "*.csv"):
                files.extend(sorted(self.case_dir.glob(pattern)))
        return files

    def _read_file(self, file: Path) -> list[tuple[dict[str, Any], str]]:
        try:
            if file.suffix.lower() == ".json":
                raw = json.loads(file.read_text(encoding="utf-8"))
                rows = raw.get("cases") if isinstance(raw, dict) and "cases" in raw else raw
                if isinstance(rows, dict):
                    rows = [rows]
                return [(r, file.name) for r in rows or [] if isinstance(r, dict)]
            if file.suffix.lower() == ".jsonl":
                rows = []
                for line in file.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        item = json.loads(line)
                        if isinstance(item, dict):
                            rows.append((item, file.name))
                return rows
            if file.suffix.lower() == ".csv":
                with file.open("r", encoding="utf-8-sig", newline="") as f:
                    return [(dict(r), file.name) for r in csv.DictReader(f)]
        except Exception:
            return []
        return []

    @staticmethod
    def _normalize_case(row: dict[str, Any], source_file: str) -> dict[str, Any]:
        title = _first(row, "title", "case_title", "Title", "案件名称", "标题")
        case_no = _first(row, "case_no", "case_flag", "CaseFlag", "案号")
        court = _first(row, "court", "Court", "法院")
        year = _first(row, "year", "年份", "裁判年份")
        cause = _first(row, "cause", "cause_of_action", "Category", "案由")
        lifecycle = _first(row, "lifecycle_stage", "stage", "生命周期", "企业阶段")
        source_url = _first(row, "source_url", "url", "Url", "链接", "北大法宝链接")
        text = " ".join([
            title,
            case_no,
            cause,
            _first(row, "identified", "Identified", "本院认为"),
            _first(row, "ascertain", "Ascertain", "本院查明"),
            _first(row, "referee_result", "RefereeResult", "裁判结果"),
            _first(row, "referee_basis", "RefereeBasis", "裁判依据"),
            _first(row, "content", "全文", "正文"),
        ])
        return {
            "title": title,
            "case_no": case_no,
            "court": court,
            "year": str(year),
            "cause": cause,
            "risk_types": _risk_list(row),
            "lifecycle_stage": lifecycle,
            "text": normalize_text(text),
            "source_url": source_url,
            "source_file": source_file,
        }

    @staticmethod
    def _score_case(query: str, risk_type: str, case: dict[str, Any]) -> float:
        text = " ".join([
            case.get("title", ""),
            case.get("case_no", ""),
            case.get("cause", ""),
            case.get("lifecycle_stage", ""),
            case.get("text", ""),
            " ".join(case.get("risk_types", [])),
        ]).lower()
        score = 0.0
        if risk_type and risk_type in case.get("risk_types", []):
            score += 3.0
        for token in _tokens(query):
            if token.lower() in text:
                score += 1.0 + min(len(token), 8) / 10
        return score

    @staticmethod
    def _to_hit(case: dict[str, Any], score: float) -> CaseHit:
        return CaseHit(
            title=case.get("title", ""),
            case_no=case.get("case_no", ""),
            court=case.get("court", ""),
            year=case.get("year", ""),
            cause=case.get("cause", ""),
            risk_types=list(case.get("risk_types", [])),
            lifecycle_stage=case.get("lifecycle_stage", ""),
            text=case.get("text", "")[:900],
            source_url=case.get("source_url", ""),
            score=round(score, 4),
            source_file=case.get("source_file", ""),
        )


def case_hit_to_dict(hit: CaseHit) -> dict[str, Any]:
    return {
        "title": hit.title,
        "case_no": hit.case_no,
        "court": hit.court,
        "year": hit.year,
        "cause": hit.cause,
        "risk_types": hit.risk_types,
        "lifecycle_stage": hit.lifecycle_stage,
        "text": hit.text,
        "source_url": hit.source_url,
        "score": hit.score,
        "source_file": hit.source_file,
    }


def _first(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _risk_list(row: dict[str, Any]) -> list[str]:
    raw = row.get("risk_types") or row.get("risks") or row.get("risk_type") or row.get("风险类型") or row.get("风险标签") or ""
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    parts = re.split(r"[,;，；|/\s]+", str(raw))
    return [p for p in parts if p.startswith("RISK-")]


def _tokens(query: str) -> list[str]:
    query = normalize_text(query)
    words = [w for w in re.split(r"[\s,，;；|/]+", query) if len(w) >= 2]
    if words:
        return words
    return [query[i:i + 2] for i in range(max(0, len(query) - 1)) if query[i:i + 2].strip()]
