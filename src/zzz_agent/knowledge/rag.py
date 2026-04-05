"""RAG (Retrieval-Augmented Generation) vector search over strategy guides.

Provides semantic search over markdown documents in config/game_knowledge/guides/.
Uses lightweight embedding (gensim or sentence-transformers) for local vector search.

TODO(codex): Full implementation. Acceptance criteria:
  - Index all .md files in guides/ directory into a vector store
  - Support incremental re-indexing when files change
  - Return top-k relevant text chunks with source attribution
  - Each chunk should be 200-500 tokens for optimal LLM context
  - Persist index to disk so it doesn't rebuild on every startup
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class GuideExcerpt:
    """A relevant excerpt from a strategy guide."""

    source_file: str
    content: str
    relevance_score: float


class RAGIndex:
    """Vector search index over strategy guide documents.

    Args:
        guides_dir: Path to config/game_knowledge/guides/ containing .md files.
        index_dir: Path to store the persisted vector index.
    """

    def __init__(self, guides_dir: Path, index_dir: Path | None = None) -> None:
        self._guides_dir = guides_dir
        self._index_dir = index_dir or guides_dir / ".index"
        self._initialized = False

    def build_index(self) -> int:
        """Build or rebuild the vector index from all guide files.

        Returns:
            Number of chunks indexed.

        TODO(codex): Implement.
        - Read all .md files from guides_dir
        - Split into chunks (200-500 tokens each, with overlap)
        - Generate embeddings (gensim Word2Vec or sentence-transformers)
        - Store in a simple FAISS or numpy-based index
        - Persist to index_dir
        """
        raise NotImplementedError

    def search(self, query: str, top_k: int = 3) -> list[GuideExcerpt]:
        """Search for relevant guide excerpts.

        Args:
            query: Natural language search query.
            top_k: Number of results to return.

        Returns:
            List of GuideExcerpt sorted by relevance (highest first).

        TODO(codex): Implement.
        - Embed the query using the same model as build_index
        - Search the vector index for nearest neighbors
        - Return top_k results with source file and relevance score
        """
        raise NotImplementedError

    def is_indexed(self) -> bool:
        """Check if the index exists and is up to date."""
        return self._initialized and self._index_dir.exists()
