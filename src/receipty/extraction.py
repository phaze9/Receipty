from __future__ import annotations

import hashlib
import io
import mimetypes
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExtractionResult:
    sha256: str
    size: int
    media_type: str
    text: str | None
    method: str | None


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_identity(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_dev}:{stat.st_ino}"


def extract(path: Path) -> ExtractionResult:
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    suffix = path.suffix.lower()
    text: str | None = None
    method: str | None = None

    if suffix in {".txt", ".text", ".md", ".csv", ".json"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        method = "text"
    elif suffix in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}:
        from PIL import Image
        import pytesseract

        with Image.open(path) as image:
            text = pytesseract.image_to_string(image, lang="eng+tha")
        method = "tesseract:eng+tha"
    elif suffix == ".pdf":
        try:
            import fitz
        except ImportError:
            method = "unavailable:pymupdf"
        else:
            document = fitz.open(path)
            pages: list[str] = []
            used_ocr = False
            for page in document:
                page_text = page.get_text().strip()
                if not page_text:
                    from PIL import Image
                    import pytesseract

                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
                    page_text = pytesseract.image_to_string(image, lang="eng+tha").strip()
                    used_ocr = True
                pages.append(page_text)
            text = "\n\n".join(pages)
            method = "pymupdf+tesseract:eng+tha" if used_ocr else "pymupdf"
    elif suffix == ".docx":
        try:
            import docx
        except ImportError:
            method = "unavailable:python-docx"
        else:
            document = docx.Document(path)
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
            method = "python-docx"

    return ExtractionResult(
        sha256=hash_file(path),
        size=path.stat().st_size,
        media_type=media_type,
        text=text,
        method=method,
    )

