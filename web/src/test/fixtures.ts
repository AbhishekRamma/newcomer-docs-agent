import type { AskResponse, HistoryItem } from "../types";

export const answered: AskResponse = {
  question: "How do I apply for a SIN?",
  route: "answer",
  answer:
    "Apply online or in person [s17-c500-000](https://www.canada.ca/en/employment-social-development/services/sin/apply.html). " +
    "Bring a primary document [s17-c500-001](https://www.canada.ca/en/employment-social-development/services/sin/apply.html#docs). " +
    "It is free [s17-c500-000](https://www.canada.ca/en/employment-social-development/services/sin/apply.html).",
  refused: false,
  refusal_reason: null,
  citations: [
    { chunk_id: "s17-c500-000", url: "https://www.canada.ca/en/employment-social-development/services/sin/apply.html",
      title: "Apply for a SIN", heading: "How to apply", fetched_at: "2026-10-01T12:00:00Z" },
    { chunk_id: "s17-c500-001", url: "https://www.canada.ca/en/employment-social-development/services/sin/apply.html#docs",
      title: "SIN documents", heading: "Documents", fetched_at: "2026-10-01T12:00:00Z" },
  ],
  disclaimer: "General information only.",
  served_models: ["cached"],
  history_id: 7,
};

export const refused: AskResponse = {
  question: "Should I claim refugee status?",
  route: "needs_professional",
  answer: "I can't advise on your own case. Please talk to a licensed immigration consultant or lawyer.",
  refused: true,
  refusal_reason: "needs_professional",
  citations: [],
  disclaimer: "General information only.",
  served_models: ["cached"],
  history_id: 8,
};

export function historyItem(id: number, question: string, data: AskResponse = answered): HistoryItem {
  return { id, question, route: data.route, created_at: "2026-10-24T14:00:00Z",
    answer: { ...data, question, history_id: id } };
}
