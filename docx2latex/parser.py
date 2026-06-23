"""Parse a DOCX manuscript into a format-independent ``Manuscript`` IR.

This is the shared front end: it reads the document body in order and pulls out
the title, authors, abstract, keywords, headings, paragraphs, tables, figures,
and references. None of this logic depends on the chosen LaTeX format.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Tuple

from docx import Document
from docx.document import Document as _Document
from docx.oxml.ns import qn
from docx.table import Table as _DocxTable, _Cell
from docx.text.paragraph import Paragraph as _DocxParagraph

from .latex import (
    convert_numeric_citations,
    latex_escape,
    normalize_whitespace,
    strip_heading_numbering,
)
from .model import Figure, Heading, Manuscript, Paragraph, Table


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
            yield _DocxParagraph(child, parent)
        elif child.tag.endswith("}tbl"):
            yield _DocxTable(child, parent)


def _run_text_with_formatting(run) -> str:
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


def _paragraph_to_latex(paragraph) -> str:
    parts = []
    for run in paragraph.runs:
        if run.text:
            parts.append(_run_text_with_formatting(run))
    text = normalize_whitespace("".join(parts))
    return convert_numeric_citations(text)


def _paragraph_image_rids(paragraph) -> List[str]:
    rids: List[str] = []
    for run in paragraph.runs:
        for el in run._element.iter():
            if el.tag.endswith("}blip"):
                rid = el.get(qn("r:embed"))
                if rid:
                    rids.append(rid)
    return rids


def _image_bytes_from_rid(doc, rid: str, used: dict) -> Tuple[str, bytes]:
    if rid in used:
        return used[rid]

    rel = doc.part.rels[rid]
    part = rel.target_part
    partname = str(part.partname)  # e.g. /word/media/image1.png
    ext = Path(partname).suffix or ".png"
    idx = len(used) + 1
    safe_base = Path(partname).stem
    filename = f"figure{idx}_{safe_base}{ext}"
    result = (filename, part.blob)
    used[rid] = result
    return result


def _parse_author_block(paragraphs: Sequence) -> Tuple[List[str], str]:
    """Infer author names and the affiliation line from the paragraphs between
    the title and the abstract."""
    nonempty = [p for p in paragraphs if normalize_whitespace(p.text)]
    if not nonempty:
        return [], ""

    author_line = normalize_whitespace(nonempty[0].text)
    aff_line = normalize_whitespace(nonempty[1].text) if len(nonempty) > 1 else ""
    aff_line = re.sub(r"^\s*(?:\[\d+\])+\s*", "", aff_line)

    names = []
    for chunk in re.split(r"\s*,\s*", author_line):
        chunk = re.sub(r"^\[\d+\]\s*", "", chunk).strip()
        if chunk:
            names.append(chunk)

    return names, aff_line


def _extract_references(paragraphs: Sequence) -> List[Tuple[str, str]]:
    refs = []
    for p in paragraphs:
        text = normalize_whitespace(p.text)
        m = re.match(r"^\[(\d+)\]\s*(.+)$", text)
        if m:
            refs.append((m.group(1), latex_escape(m.group(2))))

    def key(item):
        try:
            return int(item[0])
        except ValueError:
            return 10 ** 9

    return sorted(refs, key=key)


def _table_to_ir(table, label: str, caption: str) -> Optional[Table]:
    rows = table.rows
    if not rows:
        return None
    ncols = len(rows[0].cells)
    header = [normalize_whitespace(cell.text) for cell in rows[0].cells]
    body_rows = [
        [normalize_whitespace(cell.text) for cell in row.cells] for row in rows[1:]
    ]
    return Table(header=header, rows=body_rows, caption=caption, label=label, ncols=ncols)


def parse_docx(docx_path: Path) -> Manuscript:
    """Read a DOCX file and return a ``Manuscript`` IR."""
    doc = Document(str(docx_path))

    blocks = list(iter_block_items(doc))
    paragraphs = [b for b in blocks if isinstance(b, _DocxParagraph)]

    # Title: first Heading 1, else first non-empty paragraph.
    title = ""
    title_idx = None
    for i, p in enumerate(paragraphs):
        style_name = p.style.name if p.style and p.style.name else ""
        if style_name.startswith("Heading 1"):
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

    # Authors / affiliation from the block between title and abstract.
    author_block = (
        paragraphs[title_idx + 1:abstract_idx]
        if title_idx is not None and abstract_idx is not None
        else []
    )
    authors, affiliation = _parse_author_block(author_block)
    author_start_idx = title_idx + 1 if title_idx is not None else None
    author_end_idx = abstract_idx - 1 if abstract_idx is not None else None

    # Abstract paragraphs and keywords.
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
            style_name = p.style.name if p.style and p.style.name else ""
            if style_name.startswith("Heading"):
                abstract_end_idx = i - 1
                break
            if t:
                abstract_paras.append(convert_numeric_citations(latex_escape(t)))
            i += 1
        else:
            abstract_end_idx = i - 1

    references = _extract_references(
        paragraphs[references_idx + 1:] if references_idx is not None else []
    )

    ms = Manuscript(
        title=title,
        authors=authors,
        affiliation=affiliation,
        abstract=abstract_paras,
        keywords=keywords,
        references=references,
    )

    image_used: dict = {}
    pending_figures: List[Tuple[str, bytes]] = []
    pending_table_caption: Optional[str] = None
    fig_no = 0
    tbl_no = 0
    in_references = False

    for idx, block in enumerate(blocks):
        if isinstance(block, _DocxParagraph):
            p = block
            text = normalize_whitespace(p.text)

            # Skip regions already captured as metadata.
            if title_idx is not None and idx == title_idx:
                continue
            if (
                author_start_idx is not None
                and author_end_idx is not None
                and author_start_idx <= idx <= author_end_idx
            ):
                continue
            if abstract_idx is not None and idx == abstract_idx:
                continue
            if (
                abstract_idx is not None
                and abstract_end_idx is not None
                and abstract_idx <= idx <= abstract_end_idx
            ):
                continue

            if references_idx is not None and idx == references_idx:
                in_references = True
                continue
            if in_references:
                continue

            # Figure caption: emit the next pending image with this caption.
            if p.style and p.style.name == "Caption" and text.lower().startswith("figure"):
                if pending_figures:
                    fig_no += 1
                    filename, data = pending_figures.pop(0)
                    body = text.split(".", 1)[1].strip() if "." in text else text
                    ms.body.append(
                        Figure(
                            filename=filename,
                            data=data,
                            caption=latex_escape(body),
                            label=f"fig:{fig_no}",
                        )
                    )
                continue

            # Table caption paragraph preceding the table.
            if text.startswith("Table "):
                pending_table_caption = text
                continue

            style = p.style.name if p.style and p.style.name else ""
            if style.startswith("Heading"):
                m = re.match(r"Heading\s+(\d+)", style)
                level = int(m.group(1)) if m else 1
                ms.body.append(
                    Heading(level=level, text=latex_escape(strip_heading_numbering(text)))
                )
                continue

            # Images embedded in a paragraph: queue them for the next caption.
            rids = _paragraph_image_rids(p)
            if rids:
                for rid in rids:
                    pending_figures.append(_image_bytes_from_rid(doc, rid, image_used))
                if not text:
                    continue

            if text:
                ms.body.append(Paragraph(tex=_paragraph_to_latex(p)))

        elif isinstance(block, _DocxTable):
            tbl_no += 1
            caption_text = pending_table_caption or ""
            cap_body = (
                caption_text.split(".", 1)[1].strip()
                if "." in caption_text
                else caption_text
            )
            table_ir = _table_to_ir(block, label=f"tbl:{tbl_no}", caption=latex_escape(cap_body))
            if table_ir is not None:
                ms.body.append(table_ir)
            pending_table_caption = None

    return ms
