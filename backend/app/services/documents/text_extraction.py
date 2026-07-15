from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class DocumentTextExtractionError(ValueError):
    """Raised when readable text cannot be extracted from an uploaded file."""


def extract_document_text(file_name: str, file_bytes: bytes) -> str:
    """Extract readable text from a supported Markdown, text, or PDF upload."""

    extension = Path(file_name).suffix.lower()
    if extension in {".md", ".txt"}:
        content = _decode_utf8(file_bytes)
    elif extension == ".pdf":
        content = _extract_pdf_text(file_bytes)
    else:
        label = extension or "files without an extension"
        raise DocumentTextExtractionError(
            f"Text extraction is not supported for '{label}'."
        )

    content = content.strip()
    if not content:
        raise DocumentTextExtractionError(
            "The uploaded file does not contain readable text."
        )
    return content


def _decode_utf8(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentTextExtractionError(
            "Markdown and text files must use UTF-8 encoding."
        ) from exc


def _extract_pdf_text(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(file_bytes))
        if reader.is_encrypted:
            raise DocumentTextExtractionError(
                "Encrypted or password-protected PDF files are not supported."
            )
        page_text = [page.extract_text() or "" for page in reader.pages]
    except DocumentTextExtractionError:
        raise
    except (PdfReadError, OSError, ValueError) as exc:
        raise DocumentTextExtractionError(
            "The PDF file is invalid or could not be read."
        ) from exc

    content = "\n\n".join(text.strip() for text in page_text if text.strip())
    if not content:
        raise DocumentTextExtractionError(
            "The PDF does not contain extractable text. Scanned image-only PDFs require OCR."
        )
    return content
