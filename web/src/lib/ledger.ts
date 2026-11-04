import sample from "@/data/sample-assessment.json";

export type Occurrence = { path: string; line: number; kind: string; snippet: string; confidence: number };

export type Asset = {
  id: string;
  system: string;
  owner: string | null;
  algorithm: string;
  algorithm_name: string;
  parameter: string | null;
  usage: string;
  status: "quantum-broken" | "classically-broken" | "quantum-weakened" | "hybrid" | "quantum-safe" | string;
  replacement: string;
  occurrences: Occurrence[];
  x_years: number;
  x_source: string;
  y_years: number;
  exposure: number;
  deadline_year: number | null;
  years_late: number;
  priority: number;
  needs_owner_input: boolean;
  verdict: string;
};

export type Question = { system: string; owner: string | null; kind: string; text: string };

export type Assessment = {
  ref?: string | null;
  now_year: number;
  crqc_median_year: number;
  crqc_p05_year: number;
  target_exposure: number;
  readiness: number;
  summary: { assets: number; to_migrate: number; exposed: number; classically_broken: number; quantum_safe: number };
  pending_questions: Question[];
  assets: Asset[];
};

export type HistoryPoint = { seq: number; at: string; readiness: number; to_migrate: number; exposed: number };

export type LedgerView = {
  repo: string;
  source: "ledger" | "sample";
  updatedAt: string | null;
  assessment: Assessment;
  history: HistoryPoint[];
};

export const SAMPLE_REPO = "acme-payments";

export function sampleView(): LedgerView {
  return {
    repo: SAMPLE_REPO,
    source: "sample",
    updatedAt: null,
    assessment: sample as Assessment,
    history: [],
  };
}

/**
 * Reads a repository from the ledger API (LEDGER_URL, server-side only).
 * Falls back to the bundled sample so the page always renders.
 */
export async function loadLedger(repo?: string): Promise<LedgerView> {
  const base = process.env.LEDGER_URL;
  if (!base) return sampleView();
  try {
    let name = repo;
    if (!name) {
      const list = await fetchJson<{ repo: string }[]>(`${base}/v1/repos`);
      name = list[0]?.repo;
      if (!name) return sampleView();
    }
    const data = await fetchJson<{
      repo: string;
      updated_at: string;
      assessment: Assessment;
      history: HistoryPoint[];
    }>(`${base}/v1/repos/${encodeURIComponent(name)}`);
    return {
      repo: data.repo,
      source: "ledger",
      updatedAt: data.updated_at,
      assessment: data.assessment,
      history: data.history,
    };
  } catch {
    return sampleView();
  }
}

async function fetchJson<T>(url: string): Promise<T> {
  // Always fresh: the ledger is the live record a team is watching during a migration.
  const res = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(4000) });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return (await res.json()) as T;
}
