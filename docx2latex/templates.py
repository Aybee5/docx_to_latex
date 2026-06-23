"""LaTeX format templates.

Each template knows how to render the *front matter* of one publisher format
(document class, packages, title/author/abstract/keyword blocks). The shared
body, tables, figures, and bibliography are rendered by ``converter`` using the
small set of knobs each template exposes (``float_star``, ``bundled_class``).

Add a new format by subclassing ``Template`` and registering it in ``REGISTRY``.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .latex import latex_escape
from .model import Manuscript


_COMMON_PACKAGES = [
    r"\usepackage[T1]{fontenc}",
    r"\usepackage[utf8]{inputenc}",
    r"\usepackage{graphicx}",
    r"\usepackage{booktabs}",
    r"\usepackage{tabularx}",
    r"\usepackage{array}",
    r"\usepackage{multirow}",
    r"\usepackage{makecell}",
    r"\usepackage{amsmath,amssymb}",
    r"\usepackage{url}",
]


def format_author_names(authors: List[str]) -> str:
    """Join names as "A", "A and B", or "A, B, and C"."""
    names = [latex_escape(a) for a in authors if a]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


class Template:
    key: str = ""
    name: str = ""
    documentclass: str = ""
    float_star: bool = False            # use figure*/table* (two-column layouts)
    bundled_class: Optional[str] = None  # .cls filename to copy next to main.tex
    notes: str = ""                      # shown in the UI / docs

    def packages(self) -> List[str]:
        return list(_COMMON_PACKAGES) + [r"\usepackage[hidelinks]{hyperref}"]

    def preamble_meta(self, ms: Manuscript) -> List[str]:
        """Title/author/keyword definitions that belong before \\begin{document}."""
        return []

    def frontmatter(self, ms: Manuscript) -> List[str]:
        """Lines emitted right after \\begin{document}, before the body."""
        return []

    def preamble(self, ms: Manuscript) -> List[str]:
        lines = [self.documentclass, ""]
        lines += self.packages()
        meta = self.preamble_meta(ms)
        if meta:
            lines += [""] + meta
        return lines


class IEEETemplate(Template):
    key = "ieee"
    name = "IEEE (IEEEtran, conference)"
    documentclass = r"\documentclass[conference]{IEEEtran}"
    float_star = True
    bundled_class = "IEEEtran.cls"
    notes = "Bundled IEEEtran.cls ships with the output, so it compiles anywhere."

    def packages(self) -> List[str]:
        return [
            r"\usepackage[T1]{fontenc}",
            r"\usepackage[utf8]{inputenc}",
            r"\usepackage{lmodern}",
            r"\usepackage{cite}",
            r"\usepackage{amsmath,amssymb}",
            r"\usepackage{graphicx}",
            r"\usepackage{booktabs}",
            r"\usepackage{tabularx}",
            r"\usepackage{array}",
            r"\usepackage{multirow}",
            r"\usepackage{makecell}",
            r"\usepackage{url}",
            r"\usepackage[hidelinks]{hyperref}",
        ]

    def preamble_meta(self, ms: Manuscript) -> List[str]:
        authors = format_author_names(ms.authors)
        return [
            f"\\title{{{latex_escape(ms.title)}}}",
            "",
            r"\author{",
            r"\IEEEauthorblockN{" + authors + r"}",
            r"\IEEEauthorblockA{" + latex_escape(ms.affiliation) + r"}",
            r"}",
        ]

    def frontmatter(self, ms: Manuscript) -> List[str]:
        lines = [r"\maketitle", ""]
        if ms.abstract:
            lines.append(r"\begin{abstract}")
            for para in ms.abstract:
                lines.append(para)
                lines.append("")
            lines.append(r"\end{abstract}")
            lines.append("")
        if ms.keywords:
            lines += [r"\begin{IEEEkeywords}", latex_escape(ms.keywords), r"\end{IEEEkeywords}", ""]
        return lines


class ACMTemplate(Template):
    key = "acm"
    name = "ACM (acmart, sigconf)"
    documentclass = r"\documentclass[sigconf]{acmart}"
    float_star = True
    notes = "Requires the acmart class (TeX Live: texlive-publishers)."

    def packages(self) -> List[str]:
        # acmart already loads graphicx, amsmath, hyperref, etc.
        return [
            r"\usepackage{booktabs}",
            r"\usepackage{tabularx}",
            r"\usepackage{array}",
            r"\usepackage{multirow}",
            r"\usepackage{makecell}",
        ]

    def preamble_meta(self, ms: Manuscript) -> List[str]:
        lines = [
            r"\settopmatter{printacmref=false}",
            r"\setcopyright{none}",
            "",
            f"\\title{{{latex_escape(ms.title)}}}",
            "",
        ]
        authors = [a for a in ms.authors if a] or [""]
        for name in authors:
            lines.append(r"\author{" + latex_escape(name) + r"}")
            lines.append(r"\affiliation{\institution{" + latex_escape(ms.affiliation) + r"}}")
        if ms.keywords:
            lines.append(r"\keywords{" + latex_escape(ms.keywords) + r"}")
        return lines

    def frontmatter(self, ms: Manuscript) -> List[str]:
        lines: List[str] = []
        if ms.abstract:
            lines.append(r"\begin{abstract}")
            for para in ms.abstract:
                lines.append(para)
                lines.append("")
            lines.append(r"\end{abstract}")
            lines.append("")
        lines += [r"\maketitle", ""]
        return lines


class LNCSTemplate(Template):
    key = "lncs"
    name = "Springer LNCS (llncs)"
    documentclass = r"\documentclass{llncs}"
    float_star = False
    notes = "Requires the llncs class (Springer LNCS bundle)."

    def packages(self) -> List[str]:
        return list(_COMMON_PACKAGES) + [r"\usepackage{cite}", r"\usepackage[hidelinks]{hyperref}"]

    def preamble_meta(self, ms: Manuscript) -> List[str]:
        authors = " \\and ".join(latex_escape(a) for a in ms.authors if a) or ""
        return [
            f"\\title{{{latex_escape(ms.title)}}}",
            r"\author{" + authors + r"}",
            r"\institute{" + latex_escape(ms.affiliation) + r"}",
        ]

    def frontmatter(self, ms: Manuscript) -> List[str]:
        lines = [r"\maketitle", ""]
        if ms.abstract:
            lines.append(r"\begin{abstract}")
            for para in ms.abstract:
                lines.append(para)
                lines.append("")
            if ms.keywords:
                lines.append(r"\keywords{" + latex_escape(ms.keywords) + r"}")
            lines.append(r"\end{abstract}")
            lines.append("")
        return lines


class ElsevierTemplate(Template):
    key = "elsevier"
    name = "Elsevier (elsarticle, preprint)"
    documentclass = r"\documentclass[preprint,12pt]{elsarticle}"
    float_star = False
    notes = "Requires the elsarticle class (TeX Live: texlive-publishers)."

    def packages(self) -> List[str]:
        return list(_COMMON_PACKAGES) + [r"\usepackage[hidelinks]{hyperref}"]

    def frontmatter(self, ms: Manuscript) -> List[str]:
        lines = [r"\begin{frontmatter}", "", f"\\title{{{latex_escape(ms.title)}}}", ""]
        for name in (a for a in ms.authors if a):
            lines.append(r"\author{" + latex_escape(name) + r"}")
        if ms.affiliation:
            lines.append(r"\affiliation{organization={" + latex_escape(ms.affiliation) + r"}}")
        lines.append("")
        if ms.abstract:
            lines.append(r"\begin{abstract}")
            for para in ms.abstract:
                lines.append(para)
                lines.append("")
            lines.append(r"\end{abstract}")
        if ms.keywords:
            kw = " \\sep ".join(latex_escape(k.strip()) for k in ms.keywords.split(",") if k.strip())
            lines += [r"\begin{keyword}", kw, r"\end{keyword}"]
        lines += ["", r"\end{frontmatter}", ""]
        return lines


class ArticleTemplate(Template):
    key = "article"
    name = "Plain article (LaTeX article class)"
    documentclass = r"\documentclass[11pt]{article}"
    float_star = False
    notes = "Generic article class. Compiles with any standard LaTeX install."

    def packages(self) -> List[str]:
        return (
            [r"\usepackage[margin=1in]{geometry}"]
            + list(_COMMON_PACKAGES)
            + [r"\usepackage{cite}", r"\usepackage[hidelinks]{hyperref}"]
        )

    def preamble_meta(self, ms: Manuscript) -> List[str]:
        author = format_author_names(ms.authors)
        if ms.affiliation:
            author = author + r" \\ \small " + latex_escape(ms.affiliation)
        return [
            f"\\title{{{latex_escape(ms.title)}}}",
            r"\author{" + author + r"}",
            r"\date{}",
        ]

    def frontmatter(self, ms: Manuscript) -> List[str]:
        lines = [r"\maketitle", ""]
        if ms.abstract:
            lines.append(r"\begin{abstract}")
            for para in ms.abstract:
                lines.append(para)
                lines.append("")
            lines.append(r"\end{abstract}")
            lines.append("")
        if ms.keywords:
            lines += [r"\noindent\textbf{Keywords:} " + latex_escape(ms.keywords), ""]
        return lines


REGISTRY: Dict[str, Template] = {
    t.key: t
    for t in (
        IEEETemplate(),
        ACMTemplate(),
        LNCSTemplate(),
        ElsevierTemplate(),
        ArticleTemplate(),
    )
}


def list_formats() -> List[tuple]:
    """Return a list of (key, display name, notes) for every available format."""
    return [(t.key, t.name, t.notes) for t in REGISTRY.values()]


def get_template(fmt: str) -> Template:
    try:
        return REGISTRY[fmt]
    except KeyError:
        valid = ", ".join(REGISTRY)
        raise ValueError(f"Unknown format {fmt!r}. Choose one of: {valid}")
