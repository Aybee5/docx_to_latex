"""Shared LaTeX text helpers: escaping, whitespace, and numeric-citation rewriting.

These are format-independent: escaping a `&` or turning ``[3, 4]`` into
``\\cite{ref3,ref4}`` works the same regardless of the document class, so every
template reuses this module.
"""

from __future__ import annotations

import re
from typing import List, Optional


LATEX_SPECIALS = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}

UNICODE_REPLACEMENTS = {
    "–": "--",   # en dash
    "—": "---",  # em dash
    "‘": "`",
    "’": "'",
    "“": "``",
    "”": "''",
    "…": r"\ldots{}",
    " ": " ",
    " ": " ",
    "−": "-",    # minus sign
}


def latex_escape(text: str) -> str:
    if not text:
        return ""
    for src, dst in UNICODE_REPLACEMENTS.items():
        text = text.replace(src, dst)
    out = []
    for ch in text:
        out.append(LATEX_SPECIALS.get(ch, ch))
    return "".join(out)


def normalize_whitespace(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def strip_heading_numbering(text: str) -> str:
    text = normalize_whitespace(text)
    # Removes prefixes like 1. , 2.1 , 3.2.4 etc.
    text = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", text)
    return text.strip()


def _expand_citation_content(content: str) -> List[int]:
    numbers: List[int] = []
    for part in re.split(r"\s*(?:,|;|&|\band\b)\s*", content.strip()):
        if not part:
            continue
        m = re.match(r"^(\d+)\s*(?:-|--|–|—|\bto\b)\s*(\d+)$", part)
        if m:
            start = int(m.group(1))
            end = int(m.group(2))
            step = 1 if end >= start else -1
            numbers.extend(range(start, end + step, step))
            continue
        if re.match(r"^\d+$", part):
            numbers.append(int(part))
    return numbers


def _citation_numbers_from_bracket(content: str) -> Optional[List[int]]:
    if not re.fullmatch(r"[\d\s,;,&\-–—A-Za-z]+", content.strip()):
        return None
    words = re.findall(r"[A-Za-z]+", content)
    if any(word.lower() not in {"and", "to"} for word in words):
        return None

    numbers = _expand_citation_content(content)
    if not numbers:
        return None
    return numbers


def convert_numeric_citations(text: str) -> str:
    """Rewrite bracketed numeric references like ``[3]`` or ``[3, 5-7]`` into
    ``\\cite{...}`` commands referencing ``refN`` bibitems."""
    if not text:
        return ""

    cluster_re = re.compile(r"(?:\[\s*[^\[\]]+\s*\]\s*)+")

    def repl(match: re.Match) -> str:
        cluster = match.group(0)
        trailing_ws = cluster[len(cluster.rstrip()):]
        cluster_core = cluster.rstrip()
        entries = re.findall(r"\[\s*([^\]]+?)\s*\]", cluster_core)
        if not entries:
            return cluster

        parsed_entries: List[List[int]] = []
        for entry in entries:
            parsed = _citation_numbers_from_bracket(entry)
            if parsed is None:
                return cluster
            parsed_entries.append(parsed)

        refs: List[str] = []
        seen = set()
        for nums in parsed_entries:
            for num in nums:
                ref = f"ref{num}"
                if ref not in seen:
                    seen.add(ref)
                    refs.append(ref)
        if not refs:
            return cluster
        return r"\cite{" + ",".join(refs) + "}" + trailing_ws

    return cluster_re.sub(repl, text)
