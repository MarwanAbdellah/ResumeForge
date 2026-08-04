"""Local filesystem storage for generated documents."""

from pathlib import Path

from config.settings import settings


class LocalDocumentStorage:
    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or Path(__file__).parent.parent / settings.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def path(self, filename: str) -> Path:
        return self.output_dir / filename

    def remove_intermediates(self, output_name: str, keep_log: bool = False) -> None:
        extensions = [".aux", ".out", ".tex"]
        if not keep_log:
            extensions.append(".log")
        for extension in extensions:
            intermediate = self.path(f"{output_name}{extension}")
            if intermediate.exists():
                intermediate.unlink()
