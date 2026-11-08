# Vector Databases and Approximate Nearest Neighbour Search

A vector database stores high-dimensional embeddings and answers nearest-neighbour queries. Exact search compares the query against every stored vector, which becomes too slow beyond a few hundred thousand items. Approximate nearest neighbour (ANN) indexes trade a small amount of recall for large speedups.

HNSW builds a multi-layer proximity graph. Search starts at a sparse top layer and greedily descends to denser layers. The parameter m controls how many links each node keeps, and ef_search controls how many candidates are explored at query time. Higher values improve recall but cost latency and memory.

IVF indexes partition the space into clusters using k-means and probe only the closest clusters. They use less memory than HNSW but need a training step and are sensitive to the number of probes. Product quantization compresses vectors to cut memory further at the cost of precision.

pgvector adds a vector column type and HNSW and IVFFlat indexes to PostgreSQL, so embeddings can live next to relational data and be filtered with ordinary SQL.
