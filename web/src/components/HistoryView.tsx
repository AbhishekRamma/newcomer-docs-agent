import { useCallback, useEffect, useState } from "react";
import type { ApiClient } from "../api";
import type { HistoryItem } from "../types";
import { HistoryList } from "./HistoryList";

const PAGE = 10;

export function HistoryView({ api }: { api: ApiClient }) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);

  const load = useCallback(async (offset: number) => {
    try {
      const page = await api.listHistory(PAGE, offset);
      setItems((cur) => (offset === 0 ? page.items : [...cur, ...page.items]));
      setTotal(page.total);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load your history.");
    } finally {
      setLoaded(true);
    }
  }, [api]);

  useEffect(() => { void load(0); }, [load]);

  async function remove(id: number) {
    setDeleting(id);
    try {
      await api.deleteHistory(id);
      setItems((cur) => cur.filter((h) => h.id !== id));
      setTotal((t) => Math.max(0, t - 1));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete that entry.");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <>
      <h1 className="pixel">Your history</h1>
      <p className="lede">Only you can see these. Deleting an entry removes it from the server.</p>
      {error && <p className="msg-error" role="alert">{error}</p>}
      {loaded
        ? <HistoryList items={items} total={total} deleting={deleting}
            onDelete={(id) => void remove(id)} onLoadMore={() => void load(items.length)} />
        : <p className="empty">Loading…</p>}
    </>
  );
}
