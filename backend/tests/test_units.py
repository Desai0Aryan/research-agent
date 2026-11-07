import math

from app.services.chunking import chunk_document, chunk_page, normalize
from app.services.embeddings import HashEmbedder
from app.services.fusion import rrf
from app.services.text import keyword_terms, to_or_tsquery


def test_normalize_dehyphenates_and_joins_lines():
    assert normalize("retrie-\nval is use-\nful\nfor RAG") == "retrieval is useful for RAG"


def test_chunks_never_cross_pages_and_keep_page_numbers():
    pages = [("Alpha sentence here. " * 120), ("Beta sentence there. " * 120)]
    chunks = chunk_document(pages, target=60, overlap=10)
    assert {c.page for c in chunks} == {1, 2}
    assert all(("Alpha" in c.text) == (c.page == 1) for c in chunks)
    assert all(c.word_count <= 60 + 20 for c in chunks)


def test_overlap_shares_text_between_neighbours():
    text = " ".join(f"Sentence number {i} talks about topic {i}." for i in range(60))
    chunks = chunk_page(text, 1, target=40, overlap=12)
    assert len(chunks) > 2
    assert set(chunks[0].text.split()[-6:]) & set(chunks[1].text.split()[:20])


def test_long_unpunctuated_blob_is_split():
    chunks = chunk_page("word " * 1000, 1, target=100, overlap=10)
    assert len(chunks) >= 8


def test_empty_page_yields_nothing():
    assert chunk_page("   \n ", 1) == []


def test_hash_embedder_is_deterministic_normalized_and_similarity_aware():
    e = HashEmbedder(256)
    a, b, c = e.embed(["vector search with pgvector", "vector search using pgvector index", "banana bread recipe"])
    assert math.isclose(sum(x * x for x in a), 1.0, rel_tol=1e-6)
    assert e.embed_one("vector search with pgvector") == a
    dot = lambda x, y: sum(i * j for i, j in zip(x, y))
    assert dot(a, b) > dot(a, c)


def test_rrf_rewards_agreement_between_rankers():
    s = rrf([["a", "b", "c"], ["c", "b", "d"]], k=60)
    order = sorted(s, key=s.get, reverse=True)
    assert set(order[:2]) == {"b", "c"}  # items found by both rankers beat single-list items
    assert min(s["b"], s["c"]) > max(s["a"], s["d"])


def test_keyword_terms_drop_stopwords_and_dedupe():
    assert keyword_terms("What is the difference between BM25 and BM25 ranking?") == [
        "difference", "bm25", "ranking"
    ]


def test_tsquery_is_injection_safe():
    q = to_or_tsquery("robert'); DROP TABLE chunks;-- & | !")
    assert q is not None and all(ch.isalnum() or ch in " |" for ch in q)
    assert to_or_tsquery("the of and") is None
