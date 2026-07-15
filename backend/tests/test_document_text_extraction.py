from io import BytesIO
import sys
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.documents.text_extraction import (
    DocumentTextExtractionError,
    extract_document_text,
)


def build_text_pdf(text: str) -> bytes:
    """Build a small in-memory PDF with an extractable text layer."""

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def assert_extraction_error(file_name: str, file_bytes: bytes, message: str) -> None:
    try:
        extract_document_text(file_name, file_bytes)
    except DocumentTextExtractionError as exc:
        if message not in str(exc):
            raise AssertionError(f"Expected error containing {message!r}, got {str(exc)!r}")
    else:
        raise AssertionError(f"Expected extraction to fail for {file_name}.")


def check_document_text_extraction() -> None:
    markdown = extract_document_text("guide.md", b"# API guide\n\nUse JSON.")
    if "Use JSON" not in markdown:
        raise AssertionError("Markdown content was not extracted.")

    text = extract_document_text("logging.txt", b"Log errors with context.")
    if text != "Log errors with context.":
        raise AssertionError("Text content was not extracted.")

    pdf = extract_document_text(
        "database.pdf",
        build_text_pdf("Use transactions for related writes."),
    )
    if "Use transactions for related writes." not in pdf:
        raise AssertionError("PDF text layer was not extracted.")

    assert_extraction_error("bad.txt", b"\xff\xfe", "UTF-8")
    assert_extraction_error("bad.pdf", b"not a pdf", "invalid")

    blank_writer = PdfWriter()
    blank_writer.add_blank_page(width=612, height=792)
    blank_output = BytesIO()
    blank_writer.write(blank_output)
    assert_extraction_error("scan.pdf", blank_output.getvalue(), "image-only")

    print("Document text extraction OK.")


if __name__ == "__main__":
    try:
        check_document_text_extraction()
    except Exception as exc:
        print("Document text extraction test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
