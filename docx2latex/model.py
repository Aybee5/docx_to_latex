"""Intermediate representation produced by the parser and consumed by templates.

The parser turns a DOCX into a ``Manuscript`` made of ordered body nodes plus
front-matter metadata. Templates render this IR; they never touch python-docx.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple, Union


@dataclass
class Heading:
    level: int      # 1 = section, 2 = section, 3 = subsection, 4 = subsubsection, 5+ = paragraph
    text: str       # already LaTeX-escaped, numbering stripped


@dataclass
class Paragraph:
    tex: str        # fully rendered LaTeX (escaped, formatting + citations applied)


@dataclass
class Figure:
    filename: str   # filename to write the image as, referenced by \includegraphics
    data: bytes     # raw image bytes
    caption: str    # LaTeX-escaped caption body
    label: str      # e.g. "fig:1"


@dataclass
class Table:
    header: List[str]        # raw header cell text (escaped at render time)
    rows: List[List[str]]    # raw body cell text
    caption: str             # LaTeX-escaped caption body
    label: str               # e.g. "tbl:1"
    ncols: int


BodyNode = Union[Heading, Paragraph, Figure, Table]


@dataclass
class Manuscript:
    title: str = ""                                   # raw (escaped by template)
    authors: List[str] = field(default_factory=list)  # raw author names
    affiliation: str = ""                             # raw affiliation line
    abstract: List[str] = field(default_factory=list) # rendered LaTeX paragraphs
    keywords: str = ""                                # raw keywords line
    body: List[BodyNode] = field(default_factory=list)
    references: List[Tuple[str, str]] = field(default_factory=list)  # (number, escaped text)

    def figures(self) -> List[Figure]:
        return [n for n in self.body if isinstance(n, Figure)]
