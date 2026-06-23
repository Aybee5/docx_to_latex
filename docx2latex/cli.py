"""Command-line interface for docx2latex."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from .converter import convert
from .templates import list_formats


def build_argparser() -> argparse.ArgumentParser:
    formats = list_formats()
    epilog = "Available formats:\n" + "\n".join(
        f"  {key:9s} {name}" for key, name, _ in formats
    )
    p = argparse.ArgumentParser(
        description="Convert a DOCX manuscript to a LaTeX project in a popular format.",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("docx", type=Path, help="Input DOCX file")
    p.add_argument("-o", "--output", type=Path, default=Path("out_latex"), help="Output directory")
    p.add_argument(
        "-f", "--format", default="ieee", choices=[k for k, _, _ in formats],
        help="Target LaTeX format (default: ieee)",
    )
    p.add_argument(
        "--compile", action="store_true",
        help="Compile the generated LaTeX if pdflatex/latexmk is available",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_argparser().parse_args(argv)
    if not args.docx.exists():
        print(f"Input file not found: {args.docx}", file=sys.stderr)
        return 2

    try:
        tex_path = convert(args.docx, args.output, fmt=args.format, compile_pdf=args.compile)
        print(f"Wrote {tex_path} ({args.format})")
        if args.compile:
            print(f"Compiled PDF in {tex_path.parent}")
        return 0
    except Exception as e:
        print(f"Conversion failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
