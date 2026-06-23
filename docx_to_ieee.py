#!/usr/bin/env python3
"""
docx_to_ieee.py

Backwards-compatible entry point. The converter now lives in the ``docx2latex``
package and supports several LaTeX formats (IEEE, ACM, Springer LNCS, Elsevier,
plain article). This shim keeps the original IEEE-only command working:

    python docx_to_ieee.py input.docx -o out_dir [--compile]

For other formats use the package CLI:

    python -m docx2latex.cli input.docx -o out_dir -f acm

Or the web UI:

    streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Sequence

from docx2latex.converter import convert


def convert_docx_to_ieee(docx_path: Path, out_dir: Path, compile_pdf: bool = False) -> Path:
    """Convert a DOCX manuscript to an IEEE-style LaTeX project (compat wrapper)."""
    return convert(docx_path, out_dir, fmt="ieee", compile_pdf=compile_pdf)


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Convert a DOCX manuscript to IEEE-style LaTeX.")
    p.add_argument("docx", type=Path, help="Input DOCX file")
    p.add_argument("-o", "--output", type=Path, default=Path("out_ieee"), help="Output directory")
    p.add_argument("--compile", action="store_true", help="Compile the generated LaTeX if pdflatex/latexmk is available")
    args = p.parse_args(argv)

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
