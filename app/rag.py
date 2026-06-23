from __future__ import annotations

import json
import os
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
MODEL_CACHE_DIR = ROOT / "data" / "models"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"


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
    """Persistent semantic vector store for the legal compliance demo."""

    def __init__(self, index_path: Path = INDEX_PATH):
        self.index_path = index_path
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        self.embedding_dim: int = 0
        self.embedding_error: str = ""
        self.embedding_matrix: np.ndarray | None = None
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        self.docs: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        if self.index_path.exists():
            try:
                with self.index_path.open("rb") as f:
                    state = pickle.load(f)
                self.docs = state["docs"]
                self.vectorizer = state.get("vectorizer")
                self.matrix = state.get("matrix")
                self.embedding_matrix = state.get("embedding_matrix")
                self.embedding_model_name = state.get("embedding_model") or self.embedding_model_name
                self.embedding_dim = int(state.get("embedding_dim") or 0)
                self.embedding_error = str(state.get("embedding_error") or "")
            except Exception as exc:
                self.embedding_error = f"索引加载失败：{exc}"

    def ready(self) -> bool:
        return bool(self.docs) and (
            self.embedding_matrix is not None or (self.vectorizer is not None and self.matrix is not None)
        )

    def backend(self) -> str:
        if self.embedding_matrix is not None:
            return "embedding"
        if self.vectorizer is not None and self.matrix is not None:
            return "tfidf"
        return "not_ready"

    def build_from_seed(self, seed_path: Path = SEED_PATH) -> int:
        return self.build_from_policy_dir(seed_path.parent)

    def build_from_policy_dir(self, policy_dir: Path = POLICY_DIR) -> int:
        docs: list[dict[str, Any]] = []
        for file in sorted(policy_dir.glob("*.json")):
            for policy in self._read_policy_file(file):
                docs.extend(self._policy_to_docs(policy, file.name))
        if not docs:
            raise ValueError(f"No policy chunks found in {policy_dir}")
        index_texts = [self._index_text(d) for d in docs]
        self.embedding_error = ""
        self.embedding_matrix = self._encode_texts(index_texts)
        self.embedding_dim = int(self.embedding_matrix.shape[1]) if self.embedding_matrix is not None else 0
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
        self.matrix = self.vectorizer.fit_transform(index_texts)
        self.docs = docs
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("wb") as f:
            pickle.dump({
                "docs": self.docs,
                "embedding_matrix": self.embedding_matrix,
                "embedding_model": self.embedding_model_name,
                "embedding_dim": self.embedding_dim,
                "embedding_error": self.embedding_error,
                "vectorizer": self.vectorizer,
                "matrix": self.matrix,
            }, f)
        return len(docs)

    def search(self, query: str, k: int = 5) -> list[RetrievedChunk]:
        if not self.ready():
            self.build_from_seed()
        expanded = self._expand_query(query)
        if self.embedding_matrix is not None:
            q_vec = self._encode_query(expanded)
            scores = np.dot(self.embedding_matrix, q_vec).ravel() if q_vec is not None else self._tfidf_scores(expanded)
        else:
            scores = self._tfidf_scores(expanded)
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
        return {
            "ready": self.ready(),
            "backend": self.backend(),
            "embedding_model": self.embedding_model_name if self.embedding_matrix is not None else "",
            "embedding_dim": self.embedding_dim,
            "embedding_error": self.embedding_error,
            "documents": len(policy_list),
            "chunks": len(self.docs),
            "titles": [p["title"] for p in policy_list],
            "policies": policy_list,
        }

    def _tfidf_scores(self, query: str) -> np.ndarray:
        if self.vectorizer is None or self.matrix is None:
            return np.array([])
        q_vec = self.vectorizer.transform([query])
        return cosine_similarity(q_vec, self.matrix).ravel()

    def _encode_texts(self, texts: list[str]) -> np.ndarray | None:
        try:
            model = self._load_embedding_model()
            embeddings = np.asarray(list(model.embed(texts, batch_size=32)), dtype=np.float32)
            return self._normalize_rows(embeddings)
        except Exception as exc:
            self.embedding_error = f"Embedding 不可用，已回退 TF-IDF：{exc}"
            return None

    def _encode_query(self, query: str) -> np.ndarray | None:
        try:
            model = self._load_embedding_model()
            query_text = self._embedding_query_text(query)
            embedding = np.asarray(list(model.embed([query_text])), dtype=np.float32)
            return self._normalize_rows(embedding)[0]
        except Exception as exc:
            self.embedding_error = f"查询 embedding 失败，已回退 TF-IDF：{exc}"
            return None

    def _load_embedding_model(self):
        from fastembed import TextEmbedding

        MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return TextEmbedding(model_name=self.embedding_model_name, cache_dir=str(MODEL_CACHE_DIR))

    @staticmethod
    def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return matrix / norms

    def _embedding_query_text(self, query: str) -> str:
        if "bge" in self.embedding_model_name.lower() and "zh" in self.embedding_model_name.lower():
            return f"为这个句子生成表示以用于检索相关文章：{query}"
        return query

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
