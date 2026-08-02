"""Deterministic LaTeX compilation and document storage."""

import os
import subprocess
from pathlib import Path

from config.settings import settings


class DocumentService:
    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or Path(__file__).parent.parent / settings.output_dir
        self.output_dir.mkdir(exist_ok=True)

    def compiler_candidates(self) -> list[str]:
        configured = os.getenv("LATEX_COMPILER") or os.getenv("PDFLATEX_PATH")
        candidates = [configured] if configured else ["lualatex", "pdflatex"]
        return [candidate for candidate in candidates if candidate]

    def verify_compiler(self) -> str:
        for candidate in self.compiler_candidates():
            try:
                result = subprocess.run(
                    [candidate, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode == 0:
                    return candidate
            except (OSError, subprocess.SubprocessError):
                continue
        raise RuntimeError("LaTeX compiler could not start")

    def compile(self, tex_source: str, output_name: str) -> Path:
        compiler = self.verify_compiler()
        tex_path = self.output_dir / f"{output_name}.tex"
        pdf_path = self.output_dir / f"{output_name}.pdf"
        tex_path.write_text(tex_source, encoding="utf-8")
        try:
            result = subprocess.run(
                [
                    compiler,
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    f"-output-directory={self.output_dir.resolve()}",
                    str(tex_path.resolve()),
                ],
                capture_output=True,
                text=True,
                timeout=settings.latex_timeout_seconds,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode != 0 or not pdf_path.exists() or pdf_path.stat().st_size == 0:
                raise RuntimeError((result.stderr or result.stdout or "LaTeX compilation failed")[-1000:])
            return pdf_path
        finally:
            for extension in (".aux", ".log", ".out", ".tex"):
                intermediate = self.output_dir / f"{output_name}{extension}"
                if intermediate.exists():
                    intermediate.unlink()
