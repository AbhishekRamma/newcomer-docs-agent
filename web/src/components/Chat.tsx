import { type FormEvent, type KeyboardEvent, useRef, useState } from "react";
import { type ApiClient, ApiError, UnauthorizedError } from "../api";
import type { AskResponse } from "../types";
import { Result } from "./Result";

type Entry =
  | { id: number; kind: "user"; text: string }
  | { id: number; kind: "result"; data: AskResponse }
  | { id: number; kind: "error"; text: string }
  | { id: number; kind: "loading" };

const EXAMPLES: readonly (readonly [string, string])[] = [
  ["SIN", "How do I apply for a Social Insurance Number?"],
  ["OHIP", "Is there a waiting period before OHIP coverage starts?"],
  ["Bank account", "What ID do I need to open a bank account?"],
  ["First tax return", "Do I need to file a tax return in my first year in Canada?"],
  ["Driver's licence", "How long can I drive in Ontario on a licence from another country?"],
];

export function Chat({ api }: { api: ApiClient }) {
  const [log, setLog] = useState<Entry[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const nextId = useRef(1);
  const id = () => nextId.current++;

  async function ask(raw: string) {
    const question = raw.trim();
    if (question.length < 3 || busy) return;
    const pending = id();
    setLog((l) => [...l, { id: id(), kind: "user", text: question }, { id: pending, kind: "loading" }]);
    setText("");
    setBusy(true);
    let done: Entry;
    try {
      done = { id: pending, kind: "result", data: await api.ask(question) };
    } catch (e) {
      const msg = e instanceof UnauthorizedError || e instanceof ApiError
        ? e.message
        : "I can't reach the server right now. Check that the API is running, then try again.";
      done = { id: pending, kind: "error", text: msg };
    }
    setLog((l) => l.map((x) => (x.id === pending ? done : x)));
    setBusy(false);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(text);
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void ask(text);
    }
  }

  return (
    <>
      <h1 id="title" className="pixel">Ask about settling in Ontario</h1>
      <p className="lede">
        Answers come only from 20 official Canada.ca and ontario.ca pages, and every sentence
        links to its source. If the pages don&apos;t say, or you need advice about your own
        situation, I&apos;ll tell you so instead of guessing.
      </p>
      <p className="disclaimer" role="note">
        <strong>Not legal, tax or immigration advice.</strong> This is general information from
        official government pages. Check the linked page, or ask a licensed professional about
        your own case.
      </p>
      <section aria-label="Example questions">
        <ul className="chips">
          {EXAMPLES.map(([label, q]) => (
            <li key={label}>
              <button type="button" className="chip" disabled={busy} onClick={() => void ask(q)}>
                {label}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section id="log" className="log" aria-label="Conversation" aria-live="polite" aria-busy={busy}>
        {log.map((m) => {
          switch (m.kind) {
            case "user":
              return <article key={m.id} className="msg user"><p className="bubble">{m.text}</p></article>;
            case "result":
              return <Result key={m.id} data={m.data} />;
            case "error":
              return (
                <article key={m.id} className="msg bot error" role="alert">
                  <div className="bubble glass-inset">
                    <p className="meta"><span className="tag">Error</span></p>
                    <p className="text">{m.text}</p>
                  </div>
                </article>
              );
            case "loading":
              return (
                <article key={m.id} className="msg bot loading">
                  <div className="bubble glass-inset">
                    <p className="meta"><span className="tag">Thinking</span></p>
                    <p className="text">Searching the official pages…</p>
                    <div className="bar" aria-hidden="true" />
                  </div>
                </article>
              );
          }
        })}
      </section>

      <form className="composer glass-inset" autoComplete="off" onSubmit={onSubmit}>
        <label htmlFor="q" className="visually-hidden">Your question</label>
        <textarea id="q" name="q" rows={2} maxLength={500} required value={text}
          placeholder="Ask a question. Enter sends, Shift+Enter adds a line."
          onChange={(e) => { setText(e.target.value); }} onKeyDown={onKey} />
        <button type="submit" className="gel" disabled={busy}>Ask</button>
      </form>
      <p className="fineprint">
        Each source shows the date its page was fetched. Pages change, so check the linked page
        before you act.
      </p>
    </>
  );
}
