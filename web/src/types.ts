// Shapes returned by the FastAPI service, with runtime guards so nothing untyped leaks in.

export interface Citation {
  chunk_id: string;
  url: string;
  title: string;
  heading: string;
  fetched_at: string;
}

export interface AskResponse {
  question: string;
  route: string;
  answer: string;
  refused: boolean;
  refusal_reason: string | null;
  citations: Citation[];
  disclaimer: string;
  served_models: string[];
  history_id: number | null;
}

export interface HistoryItem {
  id: number;
  question: string;
  route: string;
  created_at: string;
  answer: AskResponse;
}

export interface HistoryPage {
  items: HistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

type Obj = Record<string, unknown>;

const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const isStr = (v: unknown): v is string => typeof v === "string";
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

export function isCitation(v: unknown): v is Citation {
  return (
    isObj(v) && isStr(v.chunk_id) && isStr(v.url) && isStr(v.title) && isStr(v.heading) &&
    isStr(v.fetched_at)
  );
}

export function isAskResponse(v: unknown): v is AskResponse {
  return (
    isObj(v) && isStr(v.question) && isStr(v.route) && isStr(v.answer) &&
    typeof v.refused === "boolean" && (v.refusal_reason === null || isStr(v.refusal_reason)) &&
    Array.isArray(v.citations) && v.citations.every(isCitation) && isStr(v.disclaimer) &&
    Array.isArray(v.served_models) && v.served_models.every(isStr) &&
    (v.history_id === undefined || v.history_id === null || isNum(v.history_id))
  );
}

export function isHistoryItem(v: unknown): v is HistoryItem {
  return (
    isObj(v) && isNum(v.id) && isStr(v.question) && isStr(v.route) && isStr(v.created_at) &&
    isAskResponse(v.answer)
  );
}

export function isHistoryPage(v: unknown): v is HistoryPage {
  return (
    isObj(v) && Array.isArray(v.items) && v.items.every(isHistoryItem) && isNum(v.total) &&
    isNum(v.limit) && isNum(v.offset)
  );
}

export const ROUTE_LABELS: Readonly<Record<string, string>> = {
  out_of_scope: "Out of scope",
  needs_professional: "Needs a professional",
  unclear: "Unclear question",
  not_in_sources: "Could not find it",
  failed_verification: "Could not verify",
  llm_cache_miss: "Not cached (offline mode)",
};

export function refusalRoute(r: Pick<AskResponse, "refusal_reason" | "route">): string {
  return r.refusal_reason ?? r.route;
}
