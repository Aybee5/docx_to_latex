# docx2latex

Convert a DOCX research / review paper into a LaTeX project for a popular
publisher format. Started life as an IEEE-only script; it now supports several
formats and ships with a web UI.

## Supported formats

| Key        | Format                              | Bundled class files |
|------------|-------------------------------------|---------------------|
| `ieee`     | IEEE (IEEEtran, conference)         | `IEEEtran.cls` |
| `acm`      | ACM (acmart, sigconf)               | `acmart.cls`, `ACM-Reference-Format.bst` |
| `lncs`     | Springer LNCS (llncs)               | `llncs.cls`, `splncs04.bst` |
| `elsevier` | Elsevier (elsarticle, preprint)     | `elsarticle.cls`, `elsarticle-*.bst` |
| `article`  | Plain LaTeX `article`               | none (standard class) |

Every generated project includes the class (`.cls`) and bibliography-style
(`.bst`) files it needs, copied in next to `main.tex`, so you don't have to
install any publisher class separately — just a LaTeX engine. The master copies
live in [`docx2latex/texclasses/<format>/`](docx2latex/texclasses) and were taken
from TeX Live (CTAN `tlnet`).

## Install

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv sync
```

Or with pip:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Web UI

```bash
uv run streamlit run app.py        # or: streamlit run app.py
```

Upload a `.docx`, pick a target format, optionally tick **Compile to PDF**
(requires `latexmk`/`pdflatex`), then download the LaTeX project as a `.zip`
(and the PDF, if compiled).

## Command line

```bash
# Multi-format CLI (console script installed by uv sync)
uv run docx2latex input.docx -o out_dir -f acm
uv run docx2latex input.docx -o out_dir -f ieee --compile
uv run docx2latex --help           # lists all formats

# Backwards-compatible IEEE-only entry point
uv run python docx_to_ieee.py input.docx -o out_dir [--compile]
```

## Compiling the generated project

Because each project ships with its own `.cls`/`.bst` files, you only need a
LaTeX engine — no separate publisher-class install:

- **Locally:** run `latexmk -pdf main.tex` (or `pdflatex main.tex`) in the
  output folder, or pass `--compile` / tick *Compile to PDF* in the UI. A
  reasonably complete TeX distribution (TeX Live, MacTeX, MiKTeX) is assumed —
  the bundled classes still rely on standard packages that ship with those.
- **Overleaf:** upload the downloaded `.zip`, set `main.tex` as the main
  document, and compile. The bundled class files are picked up automatically.

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
  `Template`, adding it to `REGISTRY`, and dropping its `.cls`/`.bst` files in
  `docx2latex/texclasses/<key>/`.
- **`converter.py`** ties it together: it parses once, renders the shared body
  (headings, paragraphs, tables, figures, bibliography), writes `main.tex` plus
  any exported images, copies bundled class files, and optionally compiles.
