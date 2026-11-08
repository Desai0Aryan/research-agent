# Query Decomposition and Multi-Step Retrieval

Complex research questions often contain several sub-questions. A single embedding of the whole question tends to retrieve passages that match its general topic but miss the specific facts. Query decomposition splits the question into smaller self-contained queries, retrieves evidence for each, and merges the results.

Multi-step retrieval adds a feedback loop. After the first retrieval round the agent checks whether the evidence is sufficient. If it is not, the agent reformulates the query with different wording, synonyms or more specific terms, and searches again. This helps when the vocabulary of the question differs from the vocabulary of the documents.

Query expansion adds related terms to a keyword query to bridge that vocabulary gap. Expansions can be mined from failed searches: when a relevant passage is found by dense retrieval but missed by keyword retrieval, the words in the passage that the user did not type are candidates for synonyms.

Comparing sources requires retrieving from several documents and presenting agreements and conflicts side by side with separate citations.
