#!/usr/bin/env python3
"""
docx_to_ieee.py

Convert a DOCX manuscript into an IEEE-style LaTeX project.

What it does:
- Reads the DOCX body in document order
- Pulls out title, authors, abstract, keywords, headings, paragraphs, tables, figures, and references
- Exports embedded images into the output folder
- Writes a main.tex file using IEEEtran
- Optionally compiles the LaTeX project if pdflatex/latexmk is available

Usage:
    python docx_to_ieee.py input.docx -o out_dir
    python docx_to_ieee.py input.docx -o out_dir --compile

Dependencies:
    python-docx
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Tuple

from docx import Document
from docx.document import Document as _Document
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph


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
    "\u2013": "--",   # en dash
    "\u2014": "---",  # em dash
    "\u2018": "`",
    "\u2019": "'",
    "\u201c": "``",
    "\u201d": "''",
    "\u2026": r"\ldots{}",
    "\u00a0": " ",
    "\u2009": " ",
    "\u2212": "-",    # minus sign
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


def iter_block_items(parent) -> Iterator[object]:
    """Yield paragraphs and tables in document order."""
    if isinstance(parent, _Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise TypeError(f"Unsupported parent type: {type(parent)!r}")

    for child in parent_elm.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, parent)
        elif child.tag.endswith("}tbl"):
            yield Table(child, parent)


def run_text_with_formatting(run) -> str:
    text = run.text
    if not text:
        return ""
    text = latex_escape(text)
    if run.bold and run.italic:
        return r"\textbf{\emph{" + text + "}}"
    if run.bold:
        return r"\textbf{" + text + "}"
    if run.italic:
        return r"\emph{" + text + "}"
    return text


def paragraph_to_latex(paragraph: Paragraph) -> str:
    parts = []
    for run in paragraph.runs:
        if run.text:
            parts.append(run_text_with_formatting(run))
    return normalize_whitespace("".join(parts))


def paragraph_has_image(paragraph: Paragraph) -> List[str]:
    """Return a list of rIds for images embedded in the paragraph."""
    rids: List[str] = []
    for run in paragraph.runs:
        for el in run._element.iter():
            if el.tag.endswith("}blip"):
                rid = el.get(qn("r:embed"))
                if rid:
                    rids.append(rid)
    return rids


def save_image_from_rid(doc: _Document, rid: str, out_dir: Path, used: dict) -> Path:
    if rid in used:
        return used[rid]

    rel = doc.part.rels[rid]
    part = rel.target_part
    partname = str(part.partname)  # e.g. /word/media/image1.png
    ext = Path(partname).suffix or ".png"
    blob = part.blob

    idx = len(used) + 1
    safe_base = Path(partname).stem
    out_name = f"figure{idx}_{safe_base}{ext}"
    out_path = out_dir / out_name
    out_path.write_bytes(blob)
    used[rid] = out_path
    return out_path


def table_to_latex(table: Table) -> str:
    rows = table.rows
    if not rows:
        return ""

    ncols = len(rows[0].cells)
    header = [normalize_whitespace(cell.text) for cell in rows[0].cells]
    body_rows = []
    for row in rows[1:]:
        body_rows.append([normalize_whitespace(cell.text) for cell in row.cells])

    def cell_tex(text: str) -> str:
        text = text.replace("\n", " ")
        text = re.sub(r"\s*\|\s*", " ", text)
        text = normalize_whitespace(text)
        return latex_escape(text)

    col_spec = "@{}" + "".join([r">{\raggedright\arraybackslash}X" for _ in range(ncols)]) + "@{}"

    lines = []
    lines.append(r"\begin{tabularx}{\textwidth}{" + col_spec + "}")
    lines.append(r"\toprule")
    lines.append(" & ".join(cell_tex(c) for c in header) + r" \\")
    lines.append(r"\midrule")
    for row in body_rows:
        lines.append(" & ".join(cell_tex(c) for c in row) + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabularx}")
    return "\n".join(lines)


def parse_author_block(paragraphs: Sequence[Paragraph]) -> Tuple[str, str]:
    """
    Infer the author line and affiliation line from the paragraphs between title
    and abstract.
    """
    nonempty = [p for p in paragraphs if normalize_whitespace(p.text)]
    if not nonempty:
        return "", ""

    author_line = normalize_whitespace(nonempty[0].text)
    aff_line = normalize_whitespace(nonempty[1].text) if len(nonempty) > 1 else ""
    aff_line = re.sub(r"^\s*(?:\[\d+\])+\s*", "", aff_line)

    names = []
    for chunk in re.split(r"\s*,\s*", author_line):
        chunk = re.sub(r"^\[\d+\]\s*", "", chunk).strip()
        if chunk:
            names.append(chunk)
    if len(names) >= 2:
        if len(names) == 2:
            author_line = f"{names[0]} and {names[1]}"
        else:
            author_line = ", ".join(names[:-1]) + f", and {names[-1]}"
    elif names:
        author_line = names[0]

    return author_line, aff_line


def extract_references(paragraphs: Sequence[Paragraph]) -> List[Tuple[str, str]]:
    refs = []
    for p in paragraphs:
        text = normalize_whitespace(p.text)
        m = re.match(r"^\[(\d+)\]\s*(.+)$", text)
        if m:
            refs.append((m.group(1), m.group(2)))

    def key(item):
        try:
            return int(item[0])
        except ValueError:
            return 10**9

    return sorted(refs, key=key)


def compile_latex(tex_path: Path) -> None:
    cwd = tex_path.parent
    if shutil.which("latexmk"):
        subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", tex_path.name], cwd=cwd, check=True)
        return
    if shutil.which("pdflatex"):
        subprocess.run(["pdflatex", "-interaction=nonstopmode", tex_path.name], cwd=cwd, check=True)
        subprocess.run(["pdflatex", "-interaction=nonstopmode", tex_path.name], cwd=cwd, check=True)
        return
    raise RuntimeError("Neither latexmk nor pdflatex is available on this system.")


def convert_docx_to_ieee(docx_path: Path, out_dir: Path, compile_pdf: bool = False) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = Document(str(docx_path))

    blocks = list(iter_block_items(doc))
    paragraphs = [b for b in blocks if isinstance(b, Paragraph)]

    # Title.
    title = ""
    title_idx = None
    for i, p in enumerate(paragraphs):
        if p.style and p.style.name.startswith("Heading 1"):
            title = normalize_whitespace(p.text)
            title_idx = i
            break
    if not title:
        for i, p in enumerate(paragraphs):
            if normalize_whitespace(p.text):
                title = normalize_whitespace(p.text)
                title_idx = i
                break

    # Locate abstract and references headings.
    abstract_idx = None
    references_idx = None
    for i, p in enumerate(paragraphs):
        t = normalize_whitespace(p.text).lower()
        if t == "abstract":
            abstract_idx = i
        elif t == "references":
            references_idx = i

    # Extract authors/affiliation from the block between title and abstract.
    author_block = paragraphs[title_idx + 1:abstract_idx] if title_idx is not None and abstract_idx is not None else []
    authors, affiliation = parse_author_block(author_block)
    author_start_idx = title_idx + 1 if title_idx is not None else None
    author_end_idx = abstract_idx - 1 if abstract_idx is not None else None

    # Extract abstract and keywords.
    abstract_paras: List[str] = []
    keywords = ""
    abstract_end_idx = abstract_idx
    if abstract_idx is not None:
        i = abstract_idx + 1
        while i < len(paragraphs):
            p = paragraphs[i]
            t = normalize_whitespace(p.text)
            if t.lower().startswith("keywords:"):
                keywords = t.split(":", 1)[1].strip()
                abstract_end_idx = i
                break
            if p.style and p.style.name.startswith("Heading"):
                abstract_end_idx = i - 1
                break
            if t:
                abstract_paras.append(t)
            i += 1
        else:
            abstract_end_idx = i - 1

    refs = extract_references(paragraphs[references_idx + 1:] if references_idx is not None else [])

    image_used = {}
    pending_figures: List[Tuple[Path, Optional[str]]] = []
    pending_table_caption: Optional[str] = None

    fig_no = 0
    tbl_no = 0

    tex_lines: List[str] = [
        r"\documentclass[conference]{IEEEtran}",
        "",
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
        "",
        f"\\title{{{latex_escape(title)}}}",
        "",
        r"\author{",
        r"\IEEEauthorblockN{" + latex_escape(authors) + r"}" if authors else r"\IEEEauthorblockN{}",
        r"\IEEEauthorblockA{" + latex_escape(affiliation) + r"}" if affiliation else r"\IEEEauthorblockA{}",
        r"}",
        "",
        r"\begin{document}",
        r"\maketitle",
        "",
    ]

    if abstract_paras:
        tex_lines.append(r"\begin{abstract}")
        for para in abstract_paras:
            tex_lines.append(latex_escape(para))
            tex_lines.append("")
        tex_lines.append(r"\end{abstract}")
        tex_lines.append("")
    if keywords:
        tex_lines.append(r"\begin{IEEEkeywords}")
        tex_lines.append(latex_escape(keywords))
        tex_lines.append(r"\end{IEEEkeywords}")
        tex_lines.append("")

    in_references = False

    for idx, block in enumerate(blocks):
        if isinstance(block, Paragraph):
            p = block
            text = normalize_whitespace(p.text)

            # Skip title and abstract region, which we already emitted.
            if title_idx is not None and idx == title_idx:
                continue
            if author_start_idx is not None and author_end_idx is not None and author_start_idx <= idx <= author_end_idx:
                continue
            if abstract_idx is not None and idx == abstract_idx:
                continue
            if abstract_idx is not None and abstract_end_idx is not None and abstract_idx <= idx <= abstract_end_idx:
                continue

            if references_idx is not None and idx == references_idx:
                in_references = True
                tex_lines.append(r"\section{References}")
                tex_lines.append("")
                continue
            if in_references:
                continue

            # Figure caption.
            if p.style and p.style.name == "Caption" and text.lower().startswith("figure"):
                caption = text
                if pending_figures:
                    fig_no += 1
                    img_path, _ = pending_figures.pop(0)
                    body = caption.split(".", 1)[1].strip() if "." in caption else caption
                    label = f"fig:{fig_no}"
                    tex_lines.extend([
                        r"\begin{figure*}[!t]",
                        r"\centering",
                        rf"\includegraphics[width=0.88\textwidth]{{{img_path.name}}}",
                        rf"\caption{{{latex_escape(body)}}}",
                        rf"\label{{{label}}}",
                        r"\end{figure*}",
                        "",
                    ])
                continue

            # Table caption paragraph preceding the table.
            if text.startswith("Table "):
                pending_table_caption = text
                continue

            style = p.style.name if p.style else ""
            if style.startswith("Heading"):
                m = re.match(r"Heading\s+(\d+)", style)
                level = int(m.group(1)) if m else 1
                heading_text = strip_heading_numbering(text)
                if level == 1 or level == 2:
                    tex_lines.append(r"\section{" + latex_escape(heading_text) + "}")
                elif level == 3:
                    tex_lines.append(r"\subsection{" + latex_escape(heading_text) + "}")
                elif level == 4:
                    tex_lines.append(r"\subsubsection{" + latex_escape(heading_text) + "}")
                else:
                    tex_lines.append(r"\paragraph{" + latex_escape(heading_text) + "}")
                tex_lines.append("")
                continue

            # Images embedded in a paragraph.
            rids = paragraph_has_image(p)
            if rids:
                for rid in rids:
                    img_path = save_image_from_rid(doc, rid, out_dir, image_used)
                    pending_figures.append((img_path, None))
                # Do not emit a blank paragraph just because it contains an image.
                if not text:
                    continue

            if text:
                tex_lines.append(paragraph_to_latex(p))
                tex_lines.append("")

        elif isinstance(block, Table):
            table_tex = table_to_latex(block)
            if not table_tex:
                continue
            tbl_no += 1
            caption_text = pending_table_caption or ""
            cap_body = caption_text.split(".", 1)[1].strip() if "." in caption_text else caption_text
            tex_lines.extend([
                r"\begin{table*}[!t]",
                r"\centering",
                r"\small",
                r"\renewcommand{\arraystretch}{1.15}",
                table_tex,
                rf"\caption{{{latex_escape(cap_body)}}}" if cap_body else r"\caption{}",
                rf"\label{{tbl:{tbl_no}}}",
                r"\end{table*}",
                "",
            ])
            pending_table_caption = None

    if refs:
        if not any(line.strip() == r"\section{References}" for line in tex_lines):
            tex_lines.append(r"\section{References}")
            tex_lines.append("")
        tex_lines.append(r"\begin{thebibliography}{99}")
        for num, ref_text in refs:
            tex_lines.append(rf"\bibitem{{ref{num}}} {latex_escape(ref_text)}")
        tex_lines.append(r"\end{thebibliography}")

    tex_lines.append(r"\end{document}")

    tex_path = out_dir / "main.tex"
    tex_path.write_text("\n".join(tex_lines).replace("\n\n\n", "\n\n"), encoding="utf-8")

    if compile_pdf:
        compile_latex(tex_path)

    return tex_path


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert a DOCX manuscript to IEEE-style LaTeX.")
    p.add_argument("docx", type=Path, help="Input DOCX file")
    p.add_argument("-o", "--output", type=Path, default=Path("out_ieee"), help="Output directory")
    p.add_argument("--compile", action="store_true", help="Compile the generated LaTeX if pdflatex/latexmk is available")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_argparser().parse_args(argv)
    if not args.docx.exists():
        print(f"Input file not found: {args.docx}", file=sys.stderr)
        return 2

    try:
        tex_path = convert_docx_to_ieee(args.docx, args.output, compile_pdf=args.compile)
        print(f"Wrote {tex_path}")
        if args.compile:
            print(f"Compiled PDF in {tex_path.parent}")
        return 0
    except Exception as e:
        print(f"Conversion failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
