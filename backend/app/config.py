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

    rrf_k: int = 60
    candidate_pool: int = 50

    @property
    def upload_dir(self) -> Path:
        p = Path(self.data_dir) / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
