export type Verdict = "supported" | "partial" | "unsupported";

export interface Doc {
  id: string; filename: string; title: string; mime: string; num_pages: number; num_chunks: number; ocr_pages: number;
  status: "pending" | "processing" | "ready" | "failed"; error?: string | null; created_at: string;
}
export interface Claim {
  id: string; text: string; evidence_ids: string[]; citations: number[]; verdict: Verdict;
  support_score: number; quote?: string | null; quote_verified: boolean; reason?: string | null;
}
export interface Section { heading: string; claims: Claim[] }
export interface Citation { n: number; evidence_id: string; chunk_id: string; document_id: string; document_title: string; page: number; url: string }
export interface Evidence {
  id: string; chunk_id: string; document_id: string; document_title: string; filename: string;
  page: number; text: string; relevance: number; url: string;
}
export interface Metrics {
  claims_total: number; supported: number; partial: number; unsupported: number; removed: number;
  citation_coverage: number; faithfulness: number; unsupported_rate: number; evidence_count: number;
  documents_used: number; retrieval_rounds: number; latency_ms: number;
}
export interface ResearchResult {
  run_id: string | null; question: string; title: string; sub_questions: string[]; sections: Section[];
  removed_claims: Claim[]; gaps: string[]; citations: Citation[]; evidence: Evidence[]; markdown: string;
  metrics: Metrics; engine: string; warnings: string[];
}
export interface RunSummary { id: string; question: string; status: string; duration_ms: number | null; metrics: Metrics | null; created_at: string }

export type AgentEvent =
  | { type: "start"; run_id: string }
  | { type: "status"; message: string }
  | { type: "plan"; sub_questions: string[]; engine: string }
  | { type: "retrieve"; sub_question: number; round: number; query: string; hits: number }
  | { type: "rerank"; sub_question: number; round: number; kept: number; best_score: number }
  | { type: "gap"; sub_question: number; message: string; queries: string[] }
  | { type: "evidence"; count: number; documents: number }
  | { type: "done"; result: ResearchResult }
  | { type: "error"; message: string };

export interface EvalSet { id: string; name: string; n_cases: number; n_answerable: number; created_at: string; cases?: unknown[] }
export interface EvalFailure { case_id: string; question: string; kind: string; label: string; details: Record<string, unknown> }
export interface Recommendation { label: string; count: number; action: string }
export interface EvalReport {
  config: Record<string, unknown>;
  retrieval: { n_cases: number; modes: Record<string, Record<string, number>> };
  answers: null | {
    n_cases: number; answer_correctness: number; faithfulness: number; unsupported_claim_rate: number;
    gold_citation_rate: number; abstention_accuracy: number | null;
  };
  failures: EvalFailure[];
  failure_summary: { total: number; by_label: Record<string, number>; recommendations: Recommendation[] };
}
export interface EvalRunMeta { id: string; set_id: string; name: string; config: Record<string, unknown>; summary: Record<string, number>; created_at: string }
export interface EvalRun extends EvalRunMeta { report: EvalReport }
export interface Cluster { size: number; top_terms: string[]; labels: Record<string, number>; examples: string[] }
export interface ProdFailures {
  window_days: number; runs_considered: number; failures: EvalFailure[]; clusters: Cluster[];
  summary: EvalReport["failure_summary"]; out_of_vocabulary_terms: [string, number][]; ratings: Record<string, number>;
}
export interface Expansion { id: string; term: string; expansions: string[]; status: "proposed" | "enabled" | "rejected"; support: number; examples?: string[] | null }
