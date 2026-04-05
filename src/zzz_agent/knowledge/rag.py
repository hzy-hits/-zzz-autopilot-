"""RAG (Retrieval-Augmented Generation) search over strategy guides.

This implementation uses a local TF-IDF index with cosine similarity:
- Indexes all markdown files under guides dir
- Splits documents into ~200-500 token chunks with overlap
- Persists index to disk
- Rebuilds automatically when guide files changed
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GuideExcerpt:
    """A relevant excerpt from a strategy guide."""

    source_file: str
    content: str
    relevance_score: float


class RAGIndex:
    """Vector search index over strategy guide documents."""

    def __init__(self, guides_dir: Path, index_dir: Path | None = None) -> None:
        self._guides_dir = guides_dir
        self._index_dir = index_dir or guides_dir / ".index"
        self._index_file = self._index_dir / "index.json"
        self._initialized = False
        self._index_data: dict[str, Any] = {}

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        # Keep both English words and Chinese runs.
        tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text.lower())
        return [token for token in tokens if token]

    @classmethod
    def _chunk_text(cls, text: str, min_tokens: int = 200, max_tokens: int = 500, overlap: int = 50) -> list[str]:
        tokens = cls._tokenize(text)
        if not tokens:
            return []

        if len(tokens) <= max_tokens:
            return [" ".join(tokens)]

        chunks: list[str] = []
        step = max(1, max_tokens - overlap)
        cursor = 0
        while cursor < len(tokens):
            end = min(len(tokens), cursor + max_tokens)
            current = tokens[cursor:end]
            if len(current) >= min_tokens or end == len(tokens):
                chunks.append(" ".join(current))
            if end == len(tokens):
                break
            cursor += step
        return chunks

    def _iter_guide_files(self) -> list[Path]:
        if not self._guides_dir.exists():
            return []
        return sorted(path for path in self._guides_dir.rglob("*.md") if path.is_file())

    def _manifest(self) -> dict[str, float]:
        return {str(path.resolve()): path.stat().st_mtime for path in self._iter_guide_files()}

    def _normalize_weights(self, weights: dict[str, float]) -> tuple[dict[str, float], float]:
        norm = math.sqrt(sum(v * v for v in weights.values()))
        return weights, norm

    @staticmethod
    def _chunk_id(path: Path, chunk_text: str, order: int) -> str:
        digest = hashlib.sha1(chunk_text.encode("utf-8", errors="ignore")).hexdigest()[:12]
        return f"{path.name}:{order}:{digest}"

    def _build_tfidf(self, chunks: list[dict[str, str]]) -> tuple[dict[str, float], list[dict[str, Any]]]:
        term_freqs: list[Counter[str]] = []
        doc_freq: Counter[str] = Counter()
        for item in chunks:
            freq = Counter(item["content"].split())
            term_freqs.append(freq)
            doc_freq.update(freq.keys())

        total_docs = max(1, len(chunks))
        idf = {term: math.log((1 + total_docs) / (1 + count)) + 1.0 for term, count in doc_freq.items()}

        vectors: list[dict[str, Any]] = []
        for idx, chunk in enumerate(chunks):
            weights: dict[str, float] = {}
            for term, count in term_freqs[idx].items():
                weights[term] = float(count) * idf.get(term, 0.0)
            weights, norm = self._normalize_weights(weights)
            vectors.append({"chunk": chunk, "weights": weights, "norm": norm})

        return idf, vectors

    def _persist(self) -> None:
        self._index_dir.mkdir(parents=True, exist_ok=True)
        with self._index_file.open("w", encoding="utf-8") as f:
            json.dump(self._index_data, f, ensure_ascii=False)

    def _load(self) -> bool:
        if not self._index_file.exists():
            return False
        try:
            with self._index_file.open(encoding="utf-8") as f:
                self._index_data = json.load(f)
            self._initialized = True
            return True
        except Exception:
            self._initialized = False
            self._index_data = {}
            return False

    def _is_stale(self) -> bool:
        if not self._index_file.exists():
            return True
        if not self._index_data and not self._load():
            return True
        return self._index_data.get("manifest", {}) != self._manifest()

    def build_index(self) -> int:
        """Build or rebuild the vector index from all guide files."""
        chunks: list[dict[str, str]] = []
        for path in self._iter_guide_files():
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            for order, chunk_text in enumerate(self._chunk_text(text), start=1):
                chunks.append(
                    {
                        "chunk_id": self._chunk_id(path, chunk_text, order),
                        "source_file": str(path),
                        "content": chunk_text,
                    }
                )

        idf, vectors = self._build_tfidf(chunks) if chunks else ({}, [])
        self._index_data = {
            "manifest": self._manifest(),
            "chunks_count": len(chunks),
            "idf": idf,
            "vectors": vectors,
        }
        self._persist()
        self._initialized = True
        return len(chunks)

    def search(self, query: str, top_k: int = 3) -> list[GuideExcerpt]:
        """Search for relevant guide excerpts."""
        if not query.strip():
            return []

        if not self._initialized and not self._load():
            return []

        if self._is_stale():
            self.build_index()

        idf: dict[str, float] = self._index_data.get("idf", {})
        vectors: list[dict[str, Any]] = self._index_data.get("vectors", [])
        if not vectors or not idf:
            return []

        query_tf = Counter(self._tokenize(query))
        query_weights: dict[str, float] = {}
        for term, count in query_tf.items():
            if term in idf:
                query_weights[term] = float(count) * idf[term]
        if not query_weights:
            return []
        query_weights, query_norm = self._normalize_weights(query_weights)
        if query_norm == 0.0:
            return []

        scored: list[tuple[float, dict[str, Any]]] = []
        for item in vectors:
            item_norm = float(item.get("norm", 0.0))
            if item_norm <= 0.0:
                continue
            weights: dict[str, float] = item.get("weights", {})
            dot = 0.0
            for term, w in query_weights.items():
                dot += w * weights.get(term, 0.0)
            score = dot / (query_norm * item_norm)
            if score > 0.0:
                scored.append((score, item["chunk"]))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[: max(1, top_k)]
        return [
            GuideExcerpt(
                source_file=chunk["source_file"],
                content=chunk["content"],
                relevance_score=round(score, 6),
            )
            for score, chunk in top
        ]

    def is_indexed(self) -> bool:
        """Check if the index exists and is up to date."""
        if not self._index_file.exists():
            return False
        if not self._initialized and not self._load():
            return False
        return not self._is_stale()
