// Turn "text [s17-c500-000](https://...)" into text segments and numbered citation markers.
import type { Citation } from "./types";

export const CITE_RE = /\[(s\d{2}-c\d+-\d{3})\]\((https?:\/\/[^\s)]+)\)/g;

export type Segment =
  | { kind: "text"; text: string }
  | { kind: "cite"; chunkId: string; href: string | null; n: number; citation: Citation | undefined };

export function safeUrl(u: string): string | null {
  try {
    const url = new URL(u);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}

export function parseAnswer(answer: string, citations: readonly Citation[]): {
  segments: Segment[];
  numberOf: Map<string, number>;
} {
  const segments: Segment[] = [];
  const numberOf = new Map<string, number>();
  let last = 0;
  for (const m of answer.matchAll(CITE_RE)) {
    const [whole, chunkId = "", url = ""] = m;
    const at = m.index;
    const before = answer.slice(last, at).replace(/\s+$/, "");
    if (before) segments.push({ kind: "text", text: before });
    let n = numberOf.get(chunkId);
    if (n === undefined) {
      n = numberOf.size + 1;
      numberOf.set(chunkId, n);
    }
    segments.push({
      kind: "cite", chunkId, href: safeUrl(url), n,
      citation: citations.find((c) => c.chunk_id === chunkId),
    });
    last = at + whole.length;
  }
  const rest = answer.slice(last);
  if (rest) segments.push({ kind: "text", text: rest });
  return { segments, numberOf };
}
