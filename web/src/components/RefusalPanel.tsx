import { ROUTE_LABELS, refusalRoute, type AskResponse } from "../types";
import { AnswerText } from "./AnswerText";

export function RefusalPanel({ data }: { data: AskResponse }) {
  const route = refusalRoute(data);
  const label = ROUTE_LABELS[route] ?? "Refused";
  return (
    <article className="msg bot refusal" aria-label={`Refused: ${label}`}>
      <div className="bubble glass-inset">
        <p className="meta">
          <span className="tag" data-testid="route-label">{label} · {route}</span>
        </p>
        <AnswerText answer={data.answer} citations={data.citations} />
        <p className="disc">{data.disclaimer}</p>
      </div>
    </article>
  );
}
