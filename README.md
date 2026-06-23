# docx2latex

Convert a DOCX research / review paper into a LaTeX project for a popular
publisher format. Started life as an IEEE-only script; it now supports several
formats and ships with a web UI.

## Supported formats

| Key        | Format                              | Notes |
|------------|-------------------------------------|-------|
| `ieee`     | IEEE (IEEEtran, conference)         | `IEEEtran.cls` is bundled into the output, so it compiles anywhere. |
| `acm`      | ACM (acmart, sigconf)               | Needs the `acmart` class (TeX Live: `texlive-publishers`). |
| `lncs`     | Springer LNCS (llncs)               | Needs the `llncs` class (Springer LNCS bundle). |
| `elsevier` | Elsevier (elsarticle, preprint)     | Needs the `elsarticle` class (TeX Live: `texlive-publishers`). |
| `article`  | Plain LaTeX `article`               | Compiles with any standard LaTeX install. |

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Web UI

```bash
streamlit run app.py
```

Upload a `.docx`, pick a target format, optionally tick **Compile to PDF**
(requires `latexmk`/`pdflatex`), then download the LaTeX project as a `.zip`
(and the PDF, if compiled).

## Command line

```bash
# New multi-format CLI
python -m docx2latex.cli input.docx -o out_dir -f acm
python -m docx2latex.cli input.docx -o out_dir -f ieee --compile

# Backwards-compatible IEEE-only entry point
python docx_to_ieee.py input.docx -o out_dir [--compile]
```

## Library

```python
from docx2latex import convert, list_formats

convert("paper.docx", "out", fmt="lncs", compile_pdf=False)
print(list_formats())   # [(key, name, notes), ...]
```

## How it works

```
DOCX ──parser.py──▶ Manuscript (IR) ──templates.py──▶ main.tex
                         model.py        converter.py
```

- **`parser.py`** reads the DOCX in document order and extracts the title,
  authors, abstract, keywords, headings, paragraphs, tables, figures, and
  references into a format-independent `Manuscript` (see `model.py`). Numeric
  citations like `[3, 5-7]` become `\cite{...}` here.
- **`templates.py`** holds one `Template` per format. A template only defines
  the bits that differ between formats: the document class, packages, and the
  title/author/abstract/keyword blocks. Add a new format by subclassing
  `Template` and adding it to `REGISTRY`.
- **`converter.py`** ties it together: it parses once, renders the shared body
  (headings, paragraphs, tables, figures, bibliography), writes `main.tex` plus
  any exported images, copies bundled class files, and optionally compiles.
