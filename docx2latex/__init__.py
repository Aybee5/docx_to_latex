"""docx2latex - convert DOCX manuscripts into LaTeX projects for popular formats.

Public API:
    from docx2latex import convert, list_formats
    convert("paper.docx", "out", fmt="ieee", compile_pdf=False)
"""

from .converter import convert
from .templates import list_formats, get_template

__all__ = ["convert", "list_formats", "get_template"]
