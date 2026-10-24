"""Pre-push scan: secrets and third-party page text.

Checks every tracked file and the full `git log -p` for:
1. the DEEPSEEK_API_KEY value from the environment (compared, never printed) and
   anything shaped like an API key;
2. runs of 12 consecutive words copied from the official pages cached in
   data/local/raw/ (gitignored). Needs a local ingest to have run.

Prints file names and counts only. Exit 1 if anything is found.
Usage: python scripts/prepush_scan.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.chunking import parse_html  # noqa: E402

SHINGLE = 12
KEY_SHAPE = re.compile(r"\bsk-[A-Za-z0-9]{20,}")
WORD = re.compile(r"[a-z0-9]+")


def shingles(text: str) -> set[tuple[str, ...]]:
    words = WORD.findall(text.lower())
    return {tuple(words[i : i + SHINGLE]) for i in range(len(words) - SHINGLE + 1)}


def page_shingles() -> set[tuple[str, ...]]:
    out: set[tuple[str, ...]] = set()
    raw = sorted((ROOT / "data/local/raw").glob("*.html"))
    if not raw:
        sys.exit("No cached pages in data/local/raw; run an ingest first.")
    for p in raw:
        page = parse_html(p.read_text(errors="ignore"))
        body = " ".join(s.text for s in page.sections)
        out |= shingles(page.title + " " + body)
    return out


def git(*args: str, check: bool = True) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          errors="ignore", check=check).stdout


def main() -> int:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    pages = page_shingles()
    blobs = {}
    for f in git("ls-files", "--cached", "--others", "--exclude-standard").splitlines():
        try:
            blobs[f] = (ROOT / f).read_text(errors="ignore")
        except (FileNotFoundError, IsADirectoryError):
            continue
    if git("rev-parse", "--verify", "-q", "HEAD", check=False).strip():
        blobs["<git log -p --all>"] = git("log", "-p", "--all")
    problems = 0
    for name, text in blobs.items():
        if key and key in text:
            print(f"SECRET: DEEPSEEK_API_KEY value found in {name}")
            problems += 1
        if KEY_SHAPE.search(text):
            print(f"SECRET: key-shaped string in {name}")
            problems += 1
        hits = len(shingles(text) & pages)
        if hits:
            print(f"PAGE TEXT: {hits} copied {SHINGLE}-word runs in {name}")
            problems += 1
    print(f"scanned {len(blobs)} items against {len(pages)} page shingles: "
          + ("FAIL" if problems else "clean"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
