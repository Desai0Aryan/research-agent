# Evaluating RAG Systems

Retrieval quality is measured with recall@k, mean reciprocal rank (MRR) and nDCG against a labelled set of question-to-passage pairs. Generation quality is measured separately: answer correctness compares the answer with a reference, while faithfulness measures whether every claim is supported by the retrieved context.

An unsupported claim is a statement in the answer that no retrieved passage entails. Tracking the unsupported-claim rate is the most direct way to quantify hallucination in a citation-based system.

Failed queries, where the gold passage was not retrieved or the answer was unsupported, should be logged and clustered. These clusters reveal systematic gaps such as chunking problems, missing synonyms or poorly chosen embedding models.
