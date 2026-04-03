"""
J — Episodic Memory (ChromaDB)
Vector-based semantic memory for conversation recall.
Falls back to TF-IDF similarity if sentence-transformers is unavailable.
"""

import logging
from datetime import datetime
import chromadb
from config import CHROMA_DIR

logger = logging.getLogger("j.memory.episodic")

# ── Try loading sentence-transformers; fall back to TF-IDF ──────
_USE_SBERT = False
try:
    from sentence_transformers import SentenceTransformer
    _USE_SBERT = True
    logger.info("sentence-transformers available — using SBERT embeddings")
except Exception as e:
    logger.warning("sentence-transformers unavailable (%s) — using TF-IDF fallback", e)


class TFIDFEmbedder:
    """Lightweight TF-IDF fallback when sentence-transformers can't load."""

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vectorizer = TfidfVectorizer(max_features=384)
        self._corpus = []
        self._fitted = False

    def encode(self, text: str) -> list[float]:
        """Encode text into a fixed-size vector using TF-IDF."""
        if isinstance(text, list):
            texts = text
        else:
            texts = [text]

        self._corpus.extend(texts)

        # Re-fit on growing corpus
        if len(self._corpus) >= 2:
            self._vectorizer.fit(self._corpus)
            self._fitted = True

        if not self._fitted:
            # Not enough data to fit — return a simple hash-based vector
            import hashlib
            vec = []
            for t in texts:
                h = hashlib.sha256(t.encode()).digest()
                vec.append([float(b) / 255.0 for b in h[:384]])
            return vec[0] if len(vec) == 1 else vec

        matrix = self._vectorizer.transform(texts)
        result = matrix.toarray().tolist()

        # Pad or truncate to 384 dimensions for ChromaDB consistency
        padded = []
        for v in result:
            if len(v) < 384:
                v = v + [0.0] * (384 - len(v))
            elif len(v) > 384:
                v = v[:384]
            padded.append(v)

        return padded[0] if len(padded) == 1 else padded


class EpisodicMemory:
    """ChromaDB-backed episodic/semantic memory for J."""

    def __init__(self):
        self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.collection = self.client.get_or_create_collection(
            name="j_memory",
            metadata={"hnsw:space": "cosine"},
        )
        self._model = None
        logger.info("ChromaDB episodic memory initialised at %s", CHROMA_DIR)

    @property
    def model(self):
        if self._model is None:
            if _USE_SBERT:
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Loaded SBERT model: all-MiniLM-L6-v2")
            else:
                self._model = TFIDFEmbedder()
                logger.info("Loaded TF-IDF fallback embedder")
        return self._model

    def save(self, content: str, tags: list[str] = None, metadata: dict = None):
        """Save a piece of content to episodic memory."""
        doc_id = f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        try:
            embedding = self.model.encode(content)
            if hasattr(embedding, 'tolist'):
                embedding = embedding.tolist()
        except Exception as e:
            logger.error("Embedding failed: %s — skipping save", e)
            return

        meta = {
            "timestamp": datetime.now().isoformat(),
            "tags": ",".join(tags) if tags else "",
        }
        if metadata:
            meta.update({k: str(v) for k, v in metadata.items()})

        try:
            self.collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[meta],
            )
            logger.debug("Saved to episodic memory: %s (id=%s)", content[:80], doc_id)
        except Exception as e:
            logger.error("ChromaDB save failed: %s", e)

    def recall(self, query: str, n_results: int = 3) -> list[dict]:
        """Retrieve the top N semantically similar memories."""
        if self.collection.count() == 0:
            return []

        try:
            embedding = self.model.encode(query)
            if hasattr(embedding, 'tolist'):
                embedding = embedding.tolist()
        except Exception as e:
            logger.error("Embedding failed during recall: %s", e)
            return []

        try:
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=min(n_results, self.collection.count()),
            )
        except Exception as e:
            logger.error("ChromaDB query failed: %s", e)
            return []

        memories = []
        for i, doc in enumerate(results["documents"][0]):
            memories.append({
                "content": doc,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else None,
            })
        return memories

    def save_person_memory(self, name: str, info: str):
        """Save a piece of information about a person."""
        self.save(
            content=f"About {name}: {info}",
            tags=["person", name.lower()],
            metadata={"person_name": name},
        )

    def save_project_memory(self, project: str, update: str):
        """Save a project update."""
        self.save(
            content=f"Project '{project}': {update}",
            tags=["project", project.lower()],
            metadata={"project_name": project},
        )
