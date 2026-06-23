from __future__ import annotations

import json
import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "data" / "index" / "policy_index.pkl"
POLICY_DIR = ROOT / "data" / "policies"
SEED_PATH = POLICY_DIR / "seed_policies.json"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


@dataclass
class RetrievedChunk:
    title: str
    level: str
    source_url: str
    text: str
    score: float
    source_file: str = ""
    chunk_id: int = 0


class PolicyVectorStore:
    """Persistent topic vector store for the legal compliance demo."""

    def __init__(self, index_path: Path = INDEX_PATH):
        self.index_path = index_path
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        self.docs: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        if self.index_path.exists():
            with self.index_path.open("rb") as f:
                state = pickle.load(f)
            self.vectorizer = state["vectorizer"]
            self.matrix = state["matrix"]
            self.docs = state["docs"]

    def ready(self) -> bool:
        return bool(self.docs) and self.vectorizer is not None and self.matrix is not None

    def build_from_seed(self, seed_path: Path = SEED_PATH) -> int:
        return self.build_from_policy_dir(seed_path.parent)

    def build_from_policy_dir(self, policy_dir: Path = POLICY_DIR) -> int:
        docs: list[dict[str, Any]] = []
        for file in sorted(policy_dir.glob("*.json")):
            for policy in self._read_policy_file(file):
                docs.extend(self._policy_to_docs(policy, file.name))
        if not docs:
            raise ValueError(f"No policy chunks found in {policy_dir}")
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
        self.matrix = self.vectorizer.fit_transform([self._index_text(d) for d in docs])
        self.docs = docs
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("wb") as f:
            pickle.dump({"vectorizer": self.vectorizer, "matrix": self.matrix, "docs": self.docs}, f)
        return len(docs)

    def search(self, query: str, k: int = 5) -> list[RetrievedChunk]:
        if not self.ready():
            self.build_from_seed()
        assert self.vectorizer is not None and self.matrix is not None
        q_vec = self.vectorizer.transform([self._expand_query(query)])
        scores = cosine_similarity(q_vec, self.matrix).ravel()
        if scores.size == 0:
            return []
        order = np.argsort(scores)[::-1][:k]
        results: list[RetrievedChunk] = []
        for idx in order:
            doc = self.docs[int(idx)]
            results.append(RetrievedChunk(
                title=doc["title"], level=doc["level"], source_url=doc["source_url"],
                text=doc["text"], score=float(scores[int(idx)]),
                source_file=doc.get("source_file", ""), chunk_id=int(doc.get("chunk_id", 0)),
            ))
        return results

    def stats(self) -> dict[str, Any]:
        policies: dict[tuple[str, str, str], dict[str, Any]] = {}
        for d in self.docs:
            key = (d["title"], d.get("level", "政策文件"), d.get("source_url", ""))
            item = policies.setdefault(key, {"title": d["title"], "level": d.get("level", "政策文件"), "source_url": d.get("source_url", ""), "chunks": 0, "source_files": set()})
            item["chunks"] += 1
            if d.get("source_file"):
                item["source_files"].add(d["source_file"])
        policy_list = []
        for item in policies.values():
            item["source_files"] = sorted(item["source_files"])
            policy_list.append(item)
        policy_list.sort(key=lambda x: (x["level"], x["title"]))
        return {"ready": self.ready(), "documents": len(policy_list), "chunks": len(self.docs), "titles": [p["title"] for p in policy_list], "policies": policy_list}

    @staticmethod
    def _read_policy_file(path: Path) -> list[dict[str, Any]]:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "policies" in raw:
            raw = raw["policies"]
        if isinstance(raw, dict):
            raw = [raw]
        if not isinstance(raw, list):
            raise ValueError(f"Policy file must contain a JSON list or object: {path}")
        return [x for x in raw if isinstance(x, dict)]

    @staticmethod
    def _policy_to_docs(policy: dict[str, Any], source_file: str) -> list[dict[str, Any]]:
        title = str(policy.get("title") or policy.get("name") or "未命名政策")
        level = str(policy.get("level") or "政策文件")
        source_url = str(policy.get("source_url") or policy.get("url") or "")
        docs: list[dict[str, Any]] = []

        articles = policy.get("articles") or []
        if isinstance(articles, dict):
            articles = [articles]
        if isinstance(articles, list) and articles:
            chunk_id = 1
            for ordinal, article in enumerate(articles, start=1):
                if not isinstance(article, dict):
                    continue
                article_no = str(article.get("article_no") or article.get("no") or article.get("number") or f"第{ordinal}条")
                heading = str(article.get("heading") or article.get("title") or "")
                text_parts = []
                if article.get("text"):
                    text_parts.append(str(article.get("text")))
                clauses = article.get("clauses") or []
                if isinstance(clauses, str):
                    clauses = [clauses]
                for clause in clauses:
                    if isinstance(clause, dict):
                        text_parts.append(str(clause.get("text") or clause.get("content") or ""))
                    else:
                        text_parts.append(str(clause))
                article_text = normalize_text(" ".join(text_parts))
                if not article_text:
                    continue
                splits = [article_text[i:i + 900] for i in range(0, len(article_text), 750)] or [article_text]
                for part in splits:
                    docs.append({
                        "title": title,
                        "level": level,
                        "source_url": source_url,
                        "chunk_id": chunk_id,
                        "source_file": source_file,
                        "text": normalize_text(part),
                        "article_no": article_no,
                        "heading": heading,
                        "article_text": article_text,
                    })
                    chunk_id += 1
            if docs:
                return docs

        chunks = policy.get("chunks") or []
        if isinstance(chunks, str):
            chunks = [chunks]
        if not chunks:
            text = normalize_text(str(policy.get("text") or policy.get("content") or ""))
            chunks = [text[i:i + 900] for i in range(0, len(text), 750)] if text else []
        for i, chunk in enumerate(chunks, start=1):
            text = normalize_text(str(chunk))
            if text:
                docs.append({"title": title, "level": level, "source_url": source_url, "chunk_id": i, "source_file": source_file, "text": text, "article_no": f"片段{i}", "heading": "", "article_text": text})
        return docs

    @staticmethod
    def _index_text(doc: dict[str, Any]) -> str:
        return " ".join([doc.get("title", ""), doc.get("level", ""), doc.get("text", "")])

    @staticmethod
    def _expand_query(query: str) -> str:
        hints = []
        if any(k in query for k in ["出境", "跨境", "境外"]):
            hints.append("数据出境 安全评估 标准合同 个人信息保护认证 境外接收方")
        if any(k in query for k in ["训练", "语料", "爬取", "大模型", "生成式"]):
            hints.append("生成式人工智能 训练数据 合法来源 知识产权 个人信息")
        if any(k in query for k in ["人脸", "生物识别", "摄像头"]):
            hints.append("人脸识别 人脸信息 单独同意 必要性 安全管理")
        if any(k in query for k in ["标识", "水印", "生成内容", "合成内容"]):
            hints.append("人工智能生成合成内容 显式标识 隐式标识 服务提供者")
        if any(k in query for k in ["审计", "合规审计", "个人信息处理者"]):
            hints.append("个人信息保护合规审计 定期审计 专业机构")
        return normalize_text(query + " " + " ".join(hints))