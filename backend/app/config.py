from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/research"
    data_dir: str = "./data"
    cors_origins: str = "http://localhost:3000"

    embedding_provider: str = "hash"  # hash | local | openai
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 384
    openai_api_key: str | None = None
    openai_base_url: str | None = None

    chunk_target_words: int = 180
    chunk_overlap_words: int = 40
    max_upload_mb: int = 50

    # ---- LLM / agent ----
    llm_provider: str = "none"  # none (offline heuristic engine) | anthropic | openai
    llm_model: str = ""  # defaults: claude-sonnet-5-5 / gpt-4o-mini
    anthropic_api_key: str | None = None
    reranker: str = "lexical"  # lexical | llm | cross-encoder
    cross_encoder_model: str = "BAAI/bge-reranker-base"
    max_subquestions: int = 4
    max_rounds: int = 2
    candidate_k: int = 20
    evidence_per_subq: int = 5
    max_evidence: int = 16
    sufficiency_threshold: float = 0.35
    strict_citations: bool = True

    # ---- security / ops ----
    api_keys: str = ""  # comma-separated; empty = auth disabled (dev). Sent as X-API-Key or Bearer.
    rate_limit_per_min: int = 0  # 0 = off. Per API key (or client IP when auth is off)
    rate_limit_heavy_per_min: int = 0  # agent runs & evals are expensive; limit them harder

    # ---- OCR for scanned PDFs (needs tesseract; see requirements-ocr.txt) ----
    ocr_enabled: bool = False
    ocr_lang: str = "eng"
    ocr_min_chars: int = 25  # a PDF page with less extractable text than this is treated as scanned

    rrf_k: int = 60
    candidate_pool: int = 50

    @property
    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def upload_dir(self) -> Path:
        p = Path(self.data_dir) / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
