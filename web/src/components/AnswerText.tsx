import type { ReactNode } from "react";
import { parseAnswer } from "../citations";
import type { Citation } from "../types";

export function AnswerText({ answer, citations }: {
  answer: string;
  citations: readonly Citation[];
}) {
  const { segments } = parseAnswer(answer, citations);
  const nodes: ReactNode[] = segments.map((s, i) => {
    if (s.kind === "text") return s.text;
    const label = `Source ${s.n}${s.citation ? `: ${s.citation.title}` : ""}`;
    return s.href ? (
      <a key={i} className="cite" href={s.href} target="_blank" rel="noopener noreferrer"
        aria-label={`${label} (opens in a new tab)`}
        title={s.citation ? `${s.citation.title}: ${s.citation.heading}` : undefined}>
        {s.n}
      </a>
    ) : (
      <span key={i} className="cite">{s.n}</span>
    );
  });
  return <p className="text">{nodes}</p>;
}
