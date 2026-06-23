"""Orchestration: parse a DOCX, render it with a chosen template, write the
LaTeX project, and optionally compile it."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from .latex import latex_escape, normalize_whitespace
from .model import Figure, Heading, Manuscript, Paragraph, Table
from .parser import parse_docx
from .templates import Template, get_template


def _render_heading(node: Heading) -> str:
    if node.level in (1, 2):
        return r"\section{" + node.text + "}"
    if node.level == 3:
        return r"\subsection{" + node.text + "}"
    if node.level == 4:
        return r"\subsubsection{" + node.text + "}"
    return r"\paragraph{" + node.text + "}"


def _render_table(node: Table) -> List[str]:
    def cell_tex(text: str) -> str:
        text = text.replace("\n", " ")
        text = re.sub(r"\s*\|\s*", " ", text)
        return latex_escape(normalize_whitespace(text))

    col_spec = "@{}" + "".join(r">{\raggedright\arraybackslash}X" for _ in range(node.ncols)) + "@{}"
    lines = [
        r"\begin{tabularx}{\linewidth}{" + col_spec + "}",
        r"\toprule",
        " & ".join(cell_tex(c) for c in node.header) + r" \\",
        r"\midrule",
    ]
    for row in node.rows:
        lines.append(" & ".join(cell_tex(c) for c in row) + r" \\")
    lines += [r"\bottomrule", r"\end{tabularx}"]
    return lines


def _render_figure(node: Figure, star: bool) -> List[str]:
    env = "figure*" if star else "figure"
    return [
        rf"\begin{{{env}}}[!t]",
        r"\centering",
        rf"\includegraphics[width={'0.88' if star else '0.95'}\linewidth]{{{node.filename}}}",
        rf"\caption{{{node.caption}}}",
        rf"\label{{{node.label}}}",
        rf"\end{{{env}}}",
        "",
    ]


def render_latex(ms: Manuscript, template: Template) -> str:
    lines: List[str] = []
    lines += template.preamble(ms)
    lines += ["", r"\begin{document}", ""]
    lines += template.frontmatter(ms)

    star = template.float_star
    for node in ms.body:
        if isinstance(node, Heading):
            lines.append(_render_heading(node))
            lines.append("")
        elif isinstance(node, Paragraph):
            lines.append(node.tex)
            lines.append("")
        elif isinstance(node, Figure):
            lines += _render_figure(node, star)
        elif isinstance(node, Table):
            env = "table*" if star else "table"
            lines += [
                rf"\begin{{{env}}}[!t]",
                r"\centering",
                r"\small",
                r"\renewcommand{\arraystretch}{1.15}",
            ]
            lines += _render_table(node)
            lines.append(rf"\caption{{{node.caption}}}" if node.caption else r"\caption{}")
            lines.append(rf"\label{{{node.label}}}")
            lines += [rf"\end{{{env}}}", ""]

    if ms.references:
        lines.append(r"\begin{thebibliography}{99}")
        for num, ref_text in ms.references:
            lines.append(rf"\bibitem{{ref{num}}} {ref_text}")
        lines.append(r"\end{thebibliography}")

    lines.append(r"\end{document}")
    return "\n".join(lines).replace("\n\n\n", "\n\n")


def _texclasses_dir(fmt: str) -> Optional[Path]:
    """Locate the bundled class/bst files for ``fmt`` (texclasses/<fmt>/)."""
    here = Path(__file__).resolve().parent
    candidates = [
        here / "texclasses" / fmt,            # shipped inside the package
        here.parent / "texclasses" / fmt,     # repo layout (dev checkout)
        Path.cwd() / "texclasses" / fmt,
    ]
    for d in candidates:
        if d.is_dir():
            return d
    return None


def _copy_bundled_classes(template: Template, out_dir: Path) -> List[Path]:
    """Copy the bundled .cls/.bst files for this format next to main.tex so the
    project compiles standalone, even if the class is not installed system-wide."""
    if not template.bundle_classes:
        return []
    src_dir = _texclasses_dir(template.key)
    if src_dir is None:
        return []
    copied = []
    for src in sorted(src_dir.iterdir()):
        if src.is_file() and not src.name.startswith("."):
            dst = out_dir / src.name
            shutil.copy2(src, dst)
            copied.append(dst)
    return copied


def compile_latex(tex_path: Path) -> None:
    cwd = tex_path.parent
    if shutil.which("latexmk"):
        subprocess.run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", tex_path.name],
            cwd=cwd, check=True,
        )
        return
    if shutil.which("pdflatex"):
        for _ in range(2):
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", tex_path.name],
                cwd=cwd, check=True,
            )
        return
    raise RuntimeError("Neither latexmk nor pdflatex is available on this system.")


def convert(
    docx_path,
    out_dir,
    fmt: str = "ieee",
    compile_pdf: bool = False,
) -> Path:
    """Convert ``docx_path`` into a LaTeX project in ``out_dir`` using format
    ``fmt``. Returns the path to the generated ``main.tex``."""
    docx_path = Path(docx_path)
    out_dir = Path(out_dir)
    template = get_template(fmt)

    out_dir.mkdir(parents=True, exist_ok=True)
    ms = parse_docx(docx_path)

    # Write images referenced by figures.
    for fig in ms.figures():
        (out_dir / fig.filename).write_bytes(fig.data)

    tex = render_latex(ms, template)
    tex_path = out_dir / "main.tex"
    tex_path.write_text(tex, encoding="utf-8")

    _copy_bundled_classes(template, out_dir)

    if compile_pdf:
        compile_latex(tex_path)

    return tex_path
