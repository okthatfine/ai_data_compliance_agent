from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

import requests

from .case_store import CaseHit
from .rag import RetrievedChunk, normalize_text


DEFAULT_CASE_KEYWORD_URL = "https://apim-gateway.pkulaw.com/mcp-case"
DEFAULT_CASE_SEMANTIC_URL = "https://apim-gateway.pkulaw.com/mcp-case-search-service"
DEFAULT_LAW_SEMANTIC_URL = "https://apim-gateway.pkulaw.com/mcp-law-search-service"
DEFAULT_LAW_KEYWORD_URL = "https://apim-gateway.pkulaw.com/mcp-law"
DEFAULT_FATIAO_KEYWORD_URL = "https://apim-gateway.pkulaw.com/mcp-fatiao"


@dataclass
class PkulawStatus:
    enabled: bool
    ready: bool
    reason: str
    endpoints: dict[str, str]
    last_error: str = ""


class PkulawMCPClient:
    """Small adapter for PKULaw streamable HTTP MCP services.

    The adapter normalizes remote statutes and cases into the application's
    evidence types. Callers can clearly report an empty result when PKULaw is
    unavailable instead of silently presenting stale local evidence as current.
    """

    def __init__(self) -> None:
        self.token = (os.getenv("PKULAW_TOKEN") or os.getenv("PKULAW_ACCESS_TOKEN") or "").strip()
        self.enabled = os.getenv("PKULAW_MCP_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
        self.timeout = float(os.getenv("PKULAW_TIMEOUT", "35"))
        self.min_interval = float(os.getenv("PKULAW_MIN_INTERVAL_SECONDS", "1.2"))
        self.case_keyword_url = os.getenv("PKULAW_CASE_KEYWORD_URL", DEFAULT_CASE_KEYWORD_URL).strip()
        self.case_semantic_url = os.getenv("PKULAW_CASE_SEMANTIC_URL", DEFAULT_CASE_SEMANTIC_URL).strip()
        self.law_semantic_url = os.getenv("PKULAW_LAW_SEMANTIC_URL", DEFAULT_LAW_SEMANTIC_URL).strip()
        self.law_keyword_url = os.getenv("PKULAW_LAW_KEYWORD_URL", DEFAULT_LAW_KEYWORD_URL).strip()
        self.fatiao_keyword_url = os.getenv("PKULAW_FATIAO_KEYWORD_URL", DEFAULT_FATIAO_KEYWORD_URL).strip()
        self.last_error = ""
        self._last_call_at = 0.0

    def ready(self) -> bool:
        return bool(self.enabled and self.token)

    def status(self) -> dict[str, Any]:
        reason = "ready"
        if not self.enabled:
            reason = "disabled_by_PKULAW_MCP_ENABLED"
        elif not self.token:
            reason = "missing_PKULAW_TOKEN_or_PKULAW_ACCESS_TOKEN"
        return PkulawStatus(
            enabled=self.enabled,
            ready=self.ready(),
            reason=reason,
            endpoints={
                "case_keyword": self.case_keyword_url,
                "case_semantic": self.case_semantic_url,
                "law_semantic": self.law_semantic_url,
                "law_keyword": self.law_keyword_url,
                "fatiao_keyword": self.fatiao_keyword_url,
            },
            last_error=self.last_error,
        ).__dict__

    def search_cases(self, query: str, risk_type: str = "", k: int = 3) -> list[CaseHit]:
        if not self.ready():
            return []
        k = max(1, min(int(k or 3), 20))
        errors: list[str] = []
        hits: list[CaseHit] = []

        # Semantic search is better for the natural-language risk queries this
        # app generates. Keyword search is kept as a second pass for titles.
        try:
            records = self._call_tool(
                self.case_semantic_url,
                "search_case",
                {"text": query},
                accept_sse=False,
            )
            hits.extend(self._records_to_case_hits(records, query, risk_type, "pkulaw_case_semantic"))
        except Exception as exc:
            errors.append(f"semantic: {exc}")

        if len(hits) < k:
            try:
                records = self._call_tool(
                    self.case_keyword_url,
                    "get_case_list",
                    {"title": query},
                    accept_sse=True,
                )
                hits.extend(self._records_to_case_hits(records, query, risk_type, "pkulaw_case_keyword"))
            except Exception as exc:
                errors.append(f"keyword: {exc}")

        deduped = _dedupe_hits(hits)
        if errors and not deduped:
            self.last_error = "; ".join(errors)
        elif errors:
            self.last_error = "partial: " + "; ".join(errors)
        else:
            self.last_error = ""
        return deduped[:k]

    def search_policies(self, query: str, k: int = 5) -> list[RetrievedChunk]:
        if not self.ready():
            return []
        k = max(1, min(int(k or 5), 20))
        errors: list[str] = []
        chunks: list[RetrievedChunk] = []

        for url, tool_name, args, source in [
            (self.law_semantic_url, "search_article", {"text": query}, "pkulaw_law_semantic"),
            (self.law_keyword_url, "get_law_list", {"keyword": query}, "pkulaw_law_keyword"),
            (self.fatiao_keyword_url, "get_fatiao_list", {"keyword": query}, "pkulaw_fatiao_keyword"),
        ]:
            if len(chunks) >= k:
                break
            try:
                records = self._call_tool(url, tool_name, args, accept_sse=True)
                chunks.extend(self._records_to_policy_chunks(records, query, source))
            except Exception as exc:
                errors.append(f"{tool_name}: {exc}")

        deduped = _dedupe_chunks(chunks)
        if errors and not deduped:
            self.last_error = "; ".join(errors)
        elif errors:
            self.last_error = "partial: " + "; ".join(errors)
        else:
            self.last_error = ""
        return deduped[:k]

    def _call_tool(self, url: str, tool_name: str, arguments: dict[str, Any], accept_sse: bool) -> Any:
        if not url:
            raise ValueError("PKULaw endpoint url is empty")
        payloads = [
            {
                "jsonrpc": "2.0",
                "id": f"ai-data-compliance-{int(time.time() * 1000)}",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            },
            {
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            },
        ]
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream" if accept_sse else "application/json",
        }
        last_error: Exception | None = None
        for payload in payloads:
            try:
                self._respect_rate_limit()
                resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                if resp.status_code in {401, 403}:
                    resp.raise_for_status()
                if resp.status_code in {400, 422}:
                    last_error = RuntimeError(resp.text[:500])
                    continue
                resp.raise_for_status()
                return self._extract_result(resp.text, resp.headers.get("content-type", ""))
            except Exception as exc:
                last_error = exc
        if last_error:
            raise last_error
        raise RuntimeError("PKULaw MCP call failed without response")

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_call_at
        if self.min_interval > 0 and elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call_at = time.monotonic()

    @staticmethod
    def _extract_result(raw_text: str, content_type: str = "") -> Any:
        text = raw_text.strip()
        if "text/event-stream" in content_type or text.startswith("data:"):
            text = _collect_sse_data(text)
        parsed = _loads_maybe_json(text)
        if isinstance(parsed, dict) and "error" in parsed:
            raise RuntimeError(json.dumps(parsed["error"], ensure_ascii=False))
        if isinstance(parsed, dict) and "result" in parsed:
            parsed = parsed["result"]
        if isinstance(parsed, dict) and "content" in parsed:
            content = parsed.get("content") or []
            if content and isinstance(content[0], dict):
                parsed = _loads_maybe_json(str(content[0].get("text", "")))
        if isinstance(parsed, dict) and "result" in parsed:
            parsed = parsed["result"]
        return parsed

    @staticmethod
    def _records_to_case_hits(records: Any, query: str, risk_type: str, source_file: str) -> list[CaseHit]:
        rows = _as_records(records)
        hits: list[CaseHit] = []
        for idx, row in enumerate(rows):
            title = _first(row, "title", "Title", "case_title", "name", "案件名称", "标题")
            case_no = _first(row, "case_no", "case_number", "case_flag", "CaseFlag", "案号")
            court = _first(row, "court", "courthouse_name", "Court", "法院")
            cause = _first(row, "cause", "cause_of_action", "Category", "案由")
            year = _first(row, "year", "decision_date", "Year", "裁判年份", "年份", "LastInstanceDate")
            source_url = _first(row, "source_url", "url", "Url", "Link", "链接", "北大法宝链接")
            text = normalize_text(" ".join([
                title,
                case_no,
                cause,
                court,
                _first(row, "case_type", "caseType", "案件类型"),
                _first(row, "doc_type", "docType", "文书类型"),
                _first(row, "TrialStep", "trial_step", "审理程序"),
                _first(row, "Identified", "identified", "本院认为"),
                _first(row, "Ascertain", "ascertain", "本院查明"),
                _first(row, "RefereeBasis", "referee_basis", "裁判依据"),
                _first(row, "RefereeResult", "referee_result", "裁判结果"),
                _first(row, "content", "Content", "全文", "正文", "summary", "摘要"),
            ]))
            score = _safe_float(_first(row, "score", "Score", "similarity", "rankScore")) or max(1.0, 10.0 - idx)
            hits.append(CaseHit(
                title=title,
                case_no=case_no,
                court=court,
                year=str(year),
                cause=cause,
                risk_types=[risk_type] if risk_type else [],
                lifecycle_stage="",
                text=text[:900],
                source_url=source_url,
                score=round(score, 4),
                source_file=source_file,
            ))
        return [hit for hit in hits if hit.title or hit.text]

    @staticmethod
    def _records_to_policy_chunks(records: Any, query: str, source_file: str) -> list[RetrievedChunk]:
        rows = _as_records(records)
        chunks: list[RetrievedChunk] = []
        for idx, row in enumerate(rows):
            title = _first(row, "title", "Title", "name", "Name", "法规名称", "标题") or query
            level = _first(row, "level", "Level", "效力级别", "DocumentAttr", "documentAttr") or "北大法宝法规"
            source_url = _first(row, "source_url", "url", "Url", "Link", "链接")
            text = normalize_text(" ".join([
                _first(row, "article", "Article", "法条", "条文"),
                _first(row, "content", "Content", "fulltext", "FullText", "全文", "正文"),
                _first(row, "summary", "Summary", "摘要"),
                _first(row, "effectiveStatus", "EffectiveStatus", "效力状态"),
            ])) or title
            score = _safe_float(_first(row, "score", "Score", "similarity", "rankScore")) or max(1.0, 10.0 - idx)
            chunks.append(RetrievedChunk(
                title=title,
                level=level,
                source_url=source_url,
                text=text[:1200],
                score=round(score, 4),
                source_file=source_file,
                chunk_id=idx,
            ))
        return [chunk for chunk in chunks if chunk.title or chunk.text]


def _collect_sse_data(text: str) -> str:
    parts: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(":"):
            continue
        if line.startswith("data:"):
            data = line[5:].strip()
            if data == "[DONE]":
                continue
            parts.append(data)
    return "\n".join(parts).strip()


def _loads_maybe_json(value: str) -> Any:
    text = value.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return text


def _as_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        value = _loads_maybe_json(value)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("result", "data", "items", "list", "records", "cases", "laws"):
            rows = value.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
            if isinstance(rows, dict):
                nested = _as_records(rows)
                if nested:
                    return nested
        return [value]
    return []


def _first(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _safe_float(value: str) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _dedupe_hits(hits: list[CaseHit]) -> list[CaseHit]:
    seen: set[str] = set()
    deduped: list[CaseHit] = []
    for hit in sorted(hits, key=lambda item: item.score, reverse=True):
        key = hit.case_no or hit.source_url or hit.title
        key = normalize_text(key).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
    return deduped


def _dedupe_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    seen: set[str] = set()
    deduped: list[RetrievedChunk] = []
    for chunk in sorted(chunks, key=lambda item: item.score, reverse=True):
        key = f"{chunk.title}|{chunk.source_url}|{chunk.text[:80]}"
        key = normalize_text(key).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)
    return deduped
