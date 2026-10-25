import { parseAnswer, safeUrl } from "../citations";
import type { AskResponse } from "../types";
import { AnswerText } from "./AnswerText";

export function Answer({ data }: { data: AskResponse }) {
  const { numberOf } = parseAnswer(data.answer, data.citations);
  const cited = data.citations
    .filter((c) => numberOf.has(c.chunk_id))
    .sort((a, b) => (numberOf.get(a.chunk_id) ?? 0) - (numberOf.get(b.chunk_id) ?? 0));
  return (
    <article className="msg bot" aria-label="Answer">
      <div className="bubble glass-inset">
        <p className="meta"><span className="tag">Answer · {data.route}</span></p>
        <AnswerText answer={data.answer} citations={data.citations} />
        {cited.length > 0 && (
          <div className="sources">
            <h2 className="pixel">Sources</h2>
            <ol>
              {cited.map((c) => {
                const href = safeUrl(c.url);
                return (
                  <li key={c.chunk_id} value={numberOf.get(c.chunk_id)}>
                    {href
                      ? <a href={href} target="_blank" rel="noopener noreferrer">{c.title || c.url}</a>
                      : <span>{c.title || c.url}</span>}
                    <span className="where"> · {c.heading} · fetched {c.fetched_at.slice(0, 10)}</span>
                  </li>
                );
              })}
            </ol>
          </div>
        )}
        <p className="disc">{data.disclaimer}</p>
      </div>
    </article>
  );
}
