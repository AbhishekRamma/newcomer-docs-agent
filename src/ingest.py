"""Fetch, clean, chunk, embed and store the source pages.

    python -m src.ingest                 # fetch (if needed) + build c300, c500, c800
    python -m src.ingest --refetch       # force re-download
    python -m src.ingest --fixtures ci/fixtures/docs --sizes 500   # CI fixture corpus

Raw HTML goes to data/local/raw/ (gitignored). Page text is never committed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx

from src import db
from src.chunking import Page, chunk_page, parse_html, parse_markdown
from src.config import DATA_DIR, LOCAL_DIR, get_settings
from src.embed import Embedder

RAW_DIR = LOCAL_DIR / "raw"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 newcomer-docs-agent (portfolio project; one fetch per page)"
)
OVERLAP = 80


def load_sources() -> list[dict]:
    return json.loads((DATA_DIR / "sources.json").read_text())


def _fetch_httpx(url: str) -> str:
    r = httpx.get(url, headers={"User-Agent": UA, "Accept-Language": "en-CA"},
                  timeout=20, follow_redirects=True)
    r.raise_for_status()
    return r.text


def _fetch_chrome(url: str) -> str:
    # Canada.ca stalls plain HTTP clients from this machine; a headless browser works.
    out = subprocess.run(
        ["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu",
         "--dump-dom", url],
        capture_output=True, text=True, timeout=90, check=True,
    )
    return out.stdout


def fetch(src: dict, refetch: bool = False) -> tuple[str, dict]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    html_path = RAW_DIR / f"{src['id']}.html"
    meta_path = RAW_DIR / f"{src['id']}.json"
    if html_path.exists() and meta_path.exists() and not refetch:
        return html_path.read_text(), json.loads(meta_path.read_text())
    method = "httpx"
    try:
        html = _fetch_httpx(src["url"])
    except Exception as exc:  # noqa: BLE001 - any network failure -> browser fallback
        print(f"  {src['id']}: httpx failed ({type(exc).__name__}); using headless Chrome")
        method = "chrome"
        html = _fetch_chrome(src["url"])
    if "<title>Not Found" in html or "Page not found" in html[:5000]:
        raise RuntimeError(f"{src['url']} returned a not-found page")
    meta = {"fetched_at": datetime.now(UTC).strftime("%Y-%m-%d"), "method": method}
    html_path.write_text(html)
    meta_path.write_text(json.dumps(meta))
    time.sleep(1.0)  # be polite
    return html, meta


def build_rows(pages: list[tuple[dict, Page, str]], size: int, embedder: Embedder) -> list[dict]:
    index_name = f"c{size}"
    rows = []
    for src, page, fetched_at in pages:
        for n, ch in enumerate(chunk_page(page, size=size, overlap=OVERLAP)):
            rows.append({
                "id": f"{src['id']}-{index_name}-{n:03d}",
                "index_name": index_name,
                "source_id": src["id"],
                "url": src["url"],
                "title": page.title,
                "heading": ch.heading,
                "text": ch.body,
                "n_tokens": ch.n_tokens,
                "fetched_at": fetched_at,
            })
    vecs = embedder.embed([f"{r['heading']}\n{r['text']}" for r in rows], kind="passage")
    for r, v in zip(rows, vecs, strict=True):
        r["embedding"] = v
    return rows


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true")
    ap.add_argument("--sizes", default="300,500,800")
    ap.add_argument("--fixtures", help="directory of markdown fixture docs (CI)")
    args = ap.parse_args(argv)
    s = get_settings()
    embedder = Embedder(s.embed_cache_path, provider=s.embed_provider)

    pages: list[tuple[dict, Page, str]] = []
    if args.fixtures:
        for f in sorted(Path(args.fixtures).glob("*.md")):
            meta, page = parse_markdown(f.read_text())
            pages.append(({"id": meta["id"], "url": meta["url"]}, page, meta.get("written", "")))
    else:
        for src in load_sources():
            html, meta = fetch(src, refetch=args.refetch)
            page = parse_html(html)
            meta["page_updated"] = page.last_updated
            meta["title"] = page.title
            (RAW_DIR / f"{src['id']}.json").write_text(json.dumps(meta))
            pages.append((src, page, meta["fetched_at"]))

    conn = db.connect(s.database_url)
    db.init_schema(conn)
    for size in [int(x) for x in args.sizes.split(",")]:
        rows = build_rows(pages, size, embedder)
        db.replace_index(conn, f"c{size}", rows)
        counts = Counter(r["source_id"] for r in rows)
        print(f"\nindex c{size}: {len(rows)} chunks")
        for src, page, _ in pages:
            print(f"  {src['id']}  {counts[src['id']]:3d} chunks  {page.title[:70]}")
    print(f"\nembedding cache: {embedder.hits} hits, {embedder.misses} computed")


if __name__ == "__main__":
    main()
