# Hybrid Search in Retrieval-Augmented Generation

Hybrid search combines dense vector retrieval with sparse keyword retrieval such as BM25. Dense retrieval captures semantic similarity, so a query about "car" can match passages about "automobile". Keyword retrieval excels at exact identifiers, rare terms, error codes and acronyms that embeddings often blur together.

Reciprocal Rank Fusion (RRF) merges the two ranked lists by summing 1/(k+rank) for each document. It needs no score calibration, which makes it robust. A common default is k=60.

Cross-encoder rerankers re-score the top candidates by reading the query and passage together. They are slower than bi-encoders but substantially more accurate, so they are applied only to the top 20-50 fused candidates.
