#!/usr/bin/env python3
"""Render a LaTeX table snippet/file into PDF or PNG."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=Path("outputs/data/aggregate/manifest_aggregate_summary_method_means.tex"),
        type=Path,
    )
    parser.add_argument(
        "--output",
        default=Path("outputs/data/aggregate/manifest_aggregate_summary_method_means.pdf"),
        type=Path,
        help="Output path (.pdf or .png).",
    )
    return parser.parse_args()


def wrap_if_needed(tex: str) -> str:
    if "\\documentclass" in tex:
        return tex
    return (
        "\\documentclass{article}\n"
        "\\usepackage[margin=1in]{geometry}\n"
        "\\usepackage{booktabs}\n"
        "\\begin{document}\n"
        f"{tex}\n"
        "\\end{document}\n"
    )


def run_cmd(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        msg = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{msg}")


def render_pdf(tex_input: Path, pdf_output: Path) -> Path:
    if shutil.which("pdflatex") is None:
        raise RuntimeError("pdflatex not found. Install TeX Live/MacTeX or use Overleaf.")
    if not tex_input.exists():
        raise FileNotFoundError(f"Input tex file not found: {tex_input}")

    tex_content = wrap_if_needed(tex_input.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="latex_table_") as td:
        tmp_dir = Path(td)
        src = tmp_dir / "table.tex"
        src.write_text(tex_content, encoding="utf-8")
        run_cmd(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "table.tex"], cwd=tmp_dir)
        pdf_src = tmp_dir / "table.pdf"
        if not pdf_src.exists():
            raise RuntimeError("pdflatex completed but PDF was not generated.")
        pdf_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf_src, pdf_output)
    return pdf_output


def render_png_from_pdf(pdf_path: Path, png_output: Path) -> None:
    png_output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("pdftoppm") is not None:
        with tempfile.TemporaryDirectory(prefix="latex_png_") as td:
            tmp_prefix = Path(td) / "page"
            run_cmd(
                ["pdftoppm", "-singlefile", "-png", str(pdf_path), str(tmp_prefix)],
                cwd=Path(td),
            )
            out = Path(f"{tmp_prefix}.png")
            if not out.exists():
                raise RuntimeError("pdftoppm did not generate PNG output.")
            shutil.copy2(out, png_output)
        return

    if shutil.which("magick") is not None:
        run_cmd(["magick", "-density", "220", str(pdf_path), str(png_output)], cwd=pdf_path.parent)
        return

    raise RuntimeError(
        "PNG conversion tool not found. Install poppler (pdftoppm) or ImageMagick (magick)."
    )


def main() -> int:
    args = parse_args()
    suffix = args.output.suffix.lower()
    if suffix not in {".pdf", ".png"}:
        raise ValueError("Output extension must be .pdf or .png")

    if suffix == ".pdf":
        out = render_pdf(args.input, args.output)
        print(f"Wrote PDF: {out}")
        return 0

    with tempfile.TemporaryDirectory(prefix="latex_pdf_tmp_") as td:
        tmp_pdf = Path(td) / "table.pdf"
        render_pdf(args.input, tmp_pdf)
        render_png_from_pdf(tmp_pdf, args.output)
    print(f"Wrote PNG: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
