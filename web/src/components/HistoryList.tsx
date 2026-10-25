import { ROUTE_LABELS, refusalRoute, type HistoryItem } from "../types";
import { Result } from "./Result";

const fmt = new Intl.DateTimeFormat("en-CA", { dateStyle: "medium", timeStyle: "short" });

export function HistoryList({ items, total, onDelete, onLoadMore, deleting }: {
  items: readonly HistoryItem[];
  total: number;
  onDelete: (id: number) => void;
  onLoadMore?: () => void;
  deleting?: number | null;
}) {
  if (items.length === 0) {
    return <p className="empty">No saved questions yet. Ask one and it will appear here.</p>;
  }
  return (
    <>
      <p className="count">Showing {items.length} of {total}, newest first.</p>
      <ul className="history" aria-label="Your past questions">
        {items.map((h) => {
          const label = h.answer.refused
            ? ROUTE_LABELS[refusalRoute(h.answer)] ?? "Refused"
            : "Answer";
          return (
            <li key={h.id} className="hist glass-inset">
              <details>
                <summary>
                  <span className="q">{h.question}</span>
                  <span className="hmeta">
                    <span className={h.answer.refused ? "tag warn" : "tag"}>{label}</span>
                    <time dateTime={h.created_at}>{fmt.format(new Date(h.created_at))}</time>
                  </span>
                </summary>
                <div className="hbody"><Result data={h.answer} /></div>
              </details>
              <button type="button" className="del" disabled={deleting === h.id}
                aria-label={`Delete “${h.question}”`} onClick={() => { onDelete(h.id); }}>
                Delete
              </button>
            </li>
          );
        })}
      </ul>
      {onLoadMore && items.length < total && (
        <button type="button" className="chip more" onClick={onLoadMore}>Load more</button>
      )}
    </>
  );
}
