// Newcomer Desk front end: calls POST /ask and GET /health on the same origin.
// Builds every node with textContent / createElement (never innerHTML) so model output
// and page titles can't inject markup.
"use strict";

const ROUTE_LABELS = {
  out_of_scope: "Out of scope",
  needs_professional: "Needs a professional",
  unclear: "Unclear question",
  not_in_sources: "Could not find it",
  failed_verification: "Could not verify",
  llm_cache_miss: "Not cached (offline mode)",
};
const CITE_RE = /\[(s\d{2}-c\d+-\d{3})\]\((https?:\/\/[^\s)]+)\)/g;

const $ = (sel) => document.querySelector(sel);
const log = $("#log");
const form = $("#ask");
const box = $("#q");
const send = $("#send");

function fromTemplate(id) {
  return document.getElementById(id).content.firstElementChild.cloneNode(true);
}

function safeUrl(u) {
  try {
    const url = new URL(u);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch { return null; }
}

function addUser(text) {
  const el = fromTemplate("tpl-user");
  el.querySelector(".bubble").textContent = text;
  log.append(el);
}

function botShell(kind, tagText) {
  const el = fromTemplate("tpl-answer");
  el.classList.add(kind);
  el.querySelector(".tag").textContent = tagText;
  log.append(el);
  el.scrollIntoView({ block: "end", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  return el;
}

// Turn "text [s17-c500-000](https://...)" into text plus numbered superscript links.
function renderAnswer(target, answer, numberOf, citations) {
  let last = 0;
  for (const m of answer.matchAll(CITE_RE)) {
    target.append(answer.slice(last, m.index).replace(/\s+$/, ""));
    const id = m[1];
    const href = safeUrl(m[2]);
    if (!numberOf.has(id)) numberOf.set(id, numberOf.size + 1);
    const c = citations.find((x) => x.chunk_id === id);
    const a = document.createElement(href ? "a" : "span");
    a.className = "cite";
    a.textContent = numberOf.get(id);
    if (href) {
      a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer";
      a.setAttribute("aria-label", `Source ${numberOf.get(id)}${c ? ": " + c.title : ""} (opens in a new tab)`);
      if (c) a.title = `${c.title}: ${c.heading}`;
    }
    target.append(a);
    last = m.index + m[0].length;
  }
  target.append(answer.slice(last));
}

function renderResult(el, data) {
  const refused = data.refused;
  el.classList.remove("loading");
  el.querySelector(".bar")?.remove();
  if (refused) el.classList.add("refusal");
  const reason = data.refusal_reason || data.route;
  el.querySelector(".tag").textContent = refused
    ? `${ROUTE_LABELS[reason] || "Refused"} · ${reason}`
    : `Answer · ${data.route}`;

  const text = el.querySelector(".text");
  text.textContent = "";
  const numberOf = new Map();
  renderAnswer(text, data.answer, numberOf, data.citations || []);

  const ol = el.querySelector(".sources ol");
  const cited = (data.citations || []).filter((c) => numberOf.has(c.chunk_id))
    .sort((a, b) => numberOf.get(a.chunk_id) - numberOf.get(b.chunk_id));
  for (const c of cited) {
    const li = document.createElement("li");
    li.value = numberOf.get(c.chunk_id);
    const href = safeUrl(c.url);
    const a = document.createElement(href ? "a" : "span");
    a.textContent = c.title || c.url;
    if (href) { a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer"; }
    const where = document.createElement("span");
    where.className = "where";
    where.textContent = ` · ${c.heading} · fetched ${String(c.fetched_at).slice(0, 10)}`;
    li.append(a, where);
    ol.append(li);
  }
  if (!cited.length) el.querySelector(".sources").remove();
  el.querySelector(".disc").textContent = data.disclaimer;
}

function renderError(el, message) {
  el.classList.remove("loading");
  el.classList.add("error");
  el.querySelector(".bar")?.remove();
  el.querySelector(".tag").textContent = "Error";
  el.querySelector(".text").textContent = message;
}

async function ask(question) {
  question = question.trim();
  if (question.length < 3) { box.focus(); return; }
  addUser(question);
  box.value = "";
  send.disabled = true;
  log.setAttribute("aria-busy", "true");
  const el = botShell("loading", "Thinking");
  el.querySelector(".text").textContent = "Searching the official pages…";
  const bar = document.createElement("div");
  bar.className = "bar"; bar.setAttribute("aria-hidden", "true");
  el.querySelector(".bubble").insertBefore(bar, el.querySelector(".sources"));

  try {
    const res = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) {
      let detail = "";
      try { const j = await res.json(); detail = typeof j.detail === "string" ? j.detail : ""; } catch { /* not JSON */ }
      const msg = res.status === 503
        ? "The service has paused new answers (spending limit reached). Please try again later."
        : res.status === 422 ? "Please write a question between 3 and 500 characters."
        : `The server answered with an error (HTTP ${res.status}). ${detail}`.trim();
      renderError(el, msg);
    } else {
      renderResult(el, await res.json());
    }
  } catch {
    renderError(el, "I can't reach the server right now. Check that the API is running, then try again.");
    checkHealth();
  } finally {
    send.disabled = false;
    log.setAttribute("aria-busy", "false");
    el.scrollIntoView({ block: "nearest" });
    box.focus();
  }
}

async function checkHealth() {
  const pill = $("#health");
  const label = pill.querySelector(".label");
  const detail = pill.querySelector(".detail");
  pill.classList.remove("ok", "warn", "down");
  detail.textContent = "";
  try {
    const res = await fetch("/health", { cache: "no-store" });
    const h = await res.json();
    if (h.status === "ok") {
      pill.classList.add("ok");
      label.textContent = "online";
      detail.textContent = ` · ${h.chunks} passages · ${h.llm_provider}`;
    } else {
      pill.classList.add("warn");
      label.textContent = h.status === "empty_index" ? "index empty" : "database unavailable";
    }
  } catch {
    pill.classList.add("down");
    label.textContent = "API offline";
  }
}

form.addEventListener("submit", (e) => { e.preventDefault(); if (!send.disabled) ask(box.value); });
box.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
});
document.querySelectorAll(".chip").forEach((b) =>
  b.addEventListener("click", () => { if (!send.disabled) ask(b.dataset.q); }));

checkHealth();
setInterval(checkHealth, 30000);
