"""HTML cleaning and heading-first chunking.

Token counts use a simple regex tokenizer (words and punctuation marks). It needs no
model download, so CI can chunk without the embedding model; it undercounts the
model's WordPiece tokens by roughly 10-20% on these pages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

TOKEN_RE = re.compile(r"\w+|[^\w\s]")
BLOCK_TAGS = ["h1", "h2", "h3", "h4", "p", "li", "tr", "dt", "dd"]
LEAF_PARENTS = {"p", "li", "tr", "dt", "dd"}
DROP_TAGS = ["script", "style", "nav", "form", "button", "noscript", "svg", "aside", "template"]
SKIP_HEADINGS = ("on this page", "page details", "report a problem", "related links",
                 "related information", "questions or comments")
MIN_SECTION_TOKENS = 40


def count_tokens(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class Section:
    path: list[str]
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass
class Page:
    title: str
    sections: list[Section]
    last_updated: str | None


def _page_updated(soup: BeautifulSoup) -> str | None:
    text = soup.get_text(" ", strip=True)
    m = re.search(r"Date modified:?\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    m = re.search(r"Page details\s*(?:Date modified:?)?\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    m = re.search(r"Updated:\s*([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    return m.group(1) if m else None


def _is_container(el: Tag) -> bool:
    return el.name in {"li", "dd", "dt"} and el.find(["h1", "h2", "h3", "h4", "p"]) is not None


def parse_html(html: str) -> Page:
    soup = BeautifulSoup(html, "html.parser")
    updated = _page_updated(soup)
    main = soup.find("main") or soup.body or soup
    for t in main.find_all(DROP_TAGS):
        t.decompose()
    for t in main.select(".pagedetails, #wb-dtmd, .gc-pg-hlpfl"):
        t.decompose()
    h1 = main.find("h1")
    title = _norm(h1.get_text(" ")) if h1 else _norm(soup.title.get_text() if soup.title else "")
    sections: list[Section] = [Section(path=[title])]
    heads: dict[int, str] = {1: title}
    skipping = False
    for el in main.find_all(BLOCK_TAGS):
        if not isinstance(el, Tag):
            continue
        if _is_container(el):
            continue  # e.g. a step <li> that wraps headings and paragraphs: descend
        if any(p.name in LEAF_PARENTS and not _is_container(p) for p in el.parents
               if p is not main):
            continue  # its text is already included by the enclosing block
        text = _norm(el.get_text(" "))
        if not text:
            continue
        if el.name in {"h1", "h2", "h3", "h4"}:
            level = int(el.name[1])
            if level == 1:
                continue
            skipping = text.lower().startswith(SKIP_HEADINGS)
            heads = {k: v for k, v in heads.items() if k < level}
            heads[level] = text
            sections.append(Section(path=[heads[k] for k in sorted(heads)]))
            continue
        if skipping:
            continue
        if el.name == "li":
            text = "- " + text
        elif el.name == "tr":
            cells = [_norm(c.get_text(" ")) for c in el.find_all(["td", "th"])]
            text = " | ".join(c for c in cells if c)
        sections[-1].lines.append(text)
    sections = [s for s in sections if s.lines]
    return Page(title=title, sections=sections, last_updated=updated)


@dataclass
class Chunk:
    heading: str
    body: str
    n_tokens: int


def _windows(words: list[str], size: int, overlap: int) -> list[list[str]]:
    """Slide over whitespace words so that each window holds about `size` tokens."""
    tok_counts = [count_tokens(w) for w in words]
    out, start = [], 0
    while start < len(words):
        total, end = 0, start
        while end < len(words) and (total + tok_counts[end] <= size or end == start):
            total += tok_counts[end]
            end += 1
        out.append(words[start:end])
        if end >= len(words):
            break
        # step back so that roughly `overlap` tokens are repeated
        back, j = 0, end
        while j > start + 1 and back < overlap:
            j -= 1
            back += tok_counts[j]
        start = j
    return out


def chunk_page(page: Page, size: int = 500, overlap: int = 80) -> list[Chunk]:
    """Split on headings first; merge tiny sections; window long ones."""
    merged: list[Section] = []
    for sec in page.sections:
        if merged and count_tokens(merged[-1].text) < MIN_SECTION_TOKENS:
            prev = merged[-1]
            prev.lines = prev.lines + [" > ".join(sec.path[1:]) + ":"] + sec.lines
            continue
        merged.append(Section(path=list(sec.path), lines=list(sec.lines)))
    chunks: list[Chunk] = []
    for sec in merged:
        heading = " > ".join(sec.path)
        body = sec.text
        n = count_tokens(body)
        if n <= size:
            chunks.append(Chunk(heading=heading, body=body, n_tokens=n))
            continue
        # keep line breaks inside windows by windowing over "words" that carry newlines
        words = re.findall(r"\S+\n?|\n", body.replace("\n", "\n "))
        for w in _windows([w for w in words if w.strip()], size, overlap):
            text = " ".join(w).replace("\n ", "\n").strip()
            chunks.append(Chunk(heading=heading, body=text, n_tokens=count_tokens(text)))
    return chunks


def parse_markdown(md: str) -> tuple[dict, Page]:
    """Parse a fixture file: `key: value` front matter between `---` lines, then
    markdown with `#`/`##`/`###` headings and `-` list items."""
    meta: dict[str, str] = {}
    lines = md.splitlines()
    if lines and lines[0].strip() == "---":
        end = lines.index("---", 1)
        for ln in lines[1:end]:
            k, _, v = ln.partition(":")
            meta[k.strip()] = v.strip()
        lines = lines[end + 1 :]
    title = meta.get("title", "")
    sections = [Section(path=[title])]
    heads: dict[int, str] = {1: title}
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            level = len(m.group(1))
            if level == 1:
                title = m.group(2).strip()
                heads = {1: title}
                sections[0].path = [title]
                continue
            heads = {k: v for k, v in heads.items() if k < level}
            heads[level] = m.group(2).strip()
            sections.append(Section(path=[heads[k] for k in sorted(heads)]))
            continue
        sections[-1].lines.append(s)
    sections = [s for s in sections if s.lines]
    return meta, Page(title=title, sections=sections, last_updated=meta.get("last_updated"))
