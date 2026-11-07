"""Pluggable embedding providers behind one tiny interface."""
import hashlib
import math
from abc import ABC, abstractmethod
from functools import lru_cache

from ..config import get_settings
from .text import tokenize


class Embedder(ABC):
    dim: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class HashEmbedder(Embedder):
    """Feature-hashing bag of unigrams+bigrams. Offline, deterministic, zero deps.

    Great for tests and demos; swap for `local` or `openai` for real semantic recall.
    """

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        toks = tokenize(text)
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        v = [0.0] * self.dim
        for f in feats:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
            v[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]


class LocalEmbedder(Embedder):
    def __init__(self, model: str, dim: int):
        from sentence_transformers import SentenceTransformer  # optional dependency

        self.model = SentenceTransformer(model)
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True, batch_size=32).tolist()


class OpenAIEmbedder(Embedder):
    def __init__(self, model: str, dim: int, api_key: str | None, base_url: str | None):
        import httpx

        self.model, self.dim = model, dim
        self.client = httpx.Client(
            base_url=(base_url or "https://api.openai.com/v1"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 96):
            r = self.client.post(
                "/embeddings",
                json={"model": self.model, "input": texts[i : i + 96], "dimensions": self.dim},
            )
            r.raise_for_status()
            out += [d["embedding"] for d in sorted(r.json()["data"], key=lambda d: d["index"])]
        return out


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_provider == "hash":
        return HashEmbedder(s.embedding_dim)
    if s.embedding_provider == "local":
        return LocalEmbedder(s.embedding_model, s.embedding_dim)
    if s.embedding_provider == "openai":
        return OpenAIEmbedder(s.embedding_model, s.embedding_dim, s.openai_api_key, s.openai_base_url)
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {s.embedding_provider}")
