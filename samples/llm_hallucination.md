# Hallucination and Grounding in Language Models

A hallucination is generated text that is fluent but not supported by the source material or by reality. Retrieval-augmented generation reduces hallucination by supplying relevant passages, but the model can still ignore the passages, blend them with memorised knowledge, or invent details such as numbers and names.

Grounding means every statement can be traced to evidence. Attributed generation asks the model to attach a citation to each claim. A citation is only useful when it is verified: an automatic checker should confirm that the cited passage actually entails the claim, and a verbatim supporting quote makes that check transparent.

Abstention is the desired behaviour when the evidence does not contain the answer. A trustworthy research assistant says that the sources do not cover the question instead of guessing. Measuring the abstention rate on unanswerable questions reveals whether the system overreaches.

Contradictions between sources should be surfaced rather than hidden. A good report states that two documents disagree and cites both sides.
