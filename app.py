"""Streamlit UI for docx2latex.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

from docx2latex import convert
from docx2latex.converter import compile_latex
from docx2latex.templates import list_formats


def _zip_dir(directory: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(directory))
    return buf.getvalue()


st.set_page_config(page_title="DOCX → LaTeX Converter", page_icon="📄", layout="centered")
st.title("📄 DOCX → LaTeX Converter")
st.caption("Convert a research / review paper from Word into a LaTeX project for a popular publisher format.")

formats = list_formats()
format_labels = {f"{name}": key for key, name, _ in formats}
notes_by_key = {key: notes for key, _, notes in formats}

uploaded = st.file_uploader("Upload a .docx manuscript", type=["docx"])

chosen_label = st.selectbox("Target format", list(format_labels.keys()))
chosen_fmt = format_labels[chosen_label]
if notes_by_key.get(chosen_fmt):
    st.info(notes_by_key[chosen_fmt])

has_tex = shutil.which("latexmk") or shutil.which("pdflatex")
compile_pdf = st.checkbox(
    "Compile to PDF",
    value=False,
    disabled=not has_tex,
    help="Requires latexmk or pdflatex on this machine."
    + ("" if has_tex else " No LaTeX toolchain detected."),
)
if not has_tex:
    st.caption(
        "No LaTeX engine detected — download the project below and compile it on "
        "[Overleaf](https://overleaf.com) (upload the .zip, set main.tex as the "
        "main document)."
    )

if st.button("Convert", type="primary", disabled=uploaded is None):
    if uploaded is None:
        st.warning("Please upload a .docx file first.")
        st.stop()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        docx_path = tmp_path / uploaded.name
        docx_path.write_bytes(uploaded.getvalue())
        out_dir = tmp_path / "out"

        try:
            with st.spinner("Converting…"):
                tex_path = convert(docx_path, out_dir, fmt=chosen_fmt, compile_pdf=False)
        except Exception as e:  # noqa: BLE001 - surface any conversion error to the user
            st.error(f"Conversion failed: {e}")
            st.stop()

        st.success(f"Generated LaTeX project ({chosen_label}).")

        tex_source = tex_path.read_text(encoding="utf-8")
        with st.expander("Preview main.tex", expanded=True):
            st.code(tex_source, language="latex")

        pdf_bytes = None
        if compile_pdf:
            try:
                with st.spinner("Compiling PDF…"):
                    compile_latex(tex_path)
                pdf_candidate = tex_path.with_suffix(".pdf")
                if pdf_candidate.exists():
                    pdf_bytes = pdf_candidate.read_bytes()
            except Exception as e:  # noqa: BLE001
                st.warning(f"PDF compilation failed (the LaTeX source is still available): {e}")

        zip_bytes = _zip_dir(out_dir)
        stem = Path(uploaded.name).stem

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "⬇️ Download LaTeX project (.zip)",
                data=zip_bytes,
                file_name=f"{stem}_{chosen_fmt}.zip",
                mime="application/zip",
            )
        with col2:
            if pdf_bytes:
                st.download_button(
                    "⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name=f"{stem}_{chosen_fmt}.pdf",
                    mime="application/pdf",
                )
