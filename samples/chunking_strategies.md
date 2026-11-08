# Chunking Strategies for Document Retrieval

Chunking splits documents into passages that are embedded and retrieved independently. Chunks that are too small lose context and produce vague embeddings. Chunks that are too large dilute the signal, so a single relevant sentence is buried among irrelevant text and the language model receives more noise.

Fixed-size chunking cuts text every N tokens and is simple but may split sentences or ideas in half. Sentence-aware chunking packs whole sentences up to a size budget, which preserves meaning. Overlap repeats the tail of one chunk at the start of the next so that facts straddling a boundary are still retrievable.

For citations, chunks should not cross page boundaries. Keeping every passage on a single page lets the system link each claim to an exact page of the source PDF, which makes answers easy to verify by a human reader.

Structure-aware chunking uses headings and sections as natural boundaries. Tables and code blocks are usually kept intact because splitting them destroys their meaning.
