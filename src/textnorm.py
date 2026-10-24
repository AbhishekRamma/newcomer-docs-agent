"""Text normalisation and rule-based fact matching used by the evaluator and verifier."""

from __future__ import annotations

import re
import unicodedata

_APOS = re.compile(r"['\u2018\u2019\u02bc`]")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def normalize(text: str) -> str:
    """Lower-case, fold unicode, drop apostrophes and thousands separators, keep [a-z0-9 ]."""
    t = unicodedata.normalize("NFKC", text).lower()
    t = _APOS.sub("", t)
    t = _THOUSANDS.sub("", t)
    t = _NON_ALNUM.sub(" ", t)
    return " ".join(t.split())


def _alt_present(alt: str, norm_text: str) -> bool:
    a = normalize(alt)
    if not a:
        return False
    if any(ch.isdigit() for ch in a):
        # numbers must match on token boundaries so "4" does not match "40"
        return f" {a} " in f" {norm_text} "
    return a in norm_text


def fact_present(fact: str, text: str, *, normalized: bool = False) -> bool:
    """A key fact is 'alt1|alt2|...'; it is present if any alternative appears."""
    norm_text = text if normalized else normalize(text)
    return any(_alt_present(alt, norm_text) for alt in fact.split("|"))


def numbers_in(text: str) -> set[str]:
    """Numbers as canonical strings: '1,358' -> '1358', '$4.00' -> '4', '0.05' -> '0.05'."""
    out = set()
    for m in _NUMBER.finditer(unicodedata.normalize("NFKC", text)):
        raw = m.group(0)
        raw = _THOUSANDS.sub("", raw).replace(",", "")
        whole, _, frac = raw.partition(".")
        whole = whole.lstrip("0") or "0"
        frac = frac.rstrip("0")
        out.add(f"{whole}.{frac}" if frac else whole)
    return out
