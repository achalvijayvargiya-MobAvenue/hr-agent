"""
PDF → plain-text extraction service.

Wraps pdfminer.six so the rest of the application never imports pdfminer directly.
This makes it trivial to swap in a different PDF backend without touching any other module.
"""
import logging
from io import BytesIO

from pdfminer.high_level import extract_text as _pdfminer_extract

logger = logging.getLogger(__name__)

MIN_TEXT_LENGTH = 50


def _sanitize_text(text: str) -> str:
    """
    Remove characters PostgreSQL cannot store in text columns.
    PDFs converted from Word (.docx → .pdf) often embed NUL (0x00) bytes.
    """
    # NUL bytes cause: ValueError: A string literal cannot contain NUL (0x00) characters.
    text = text.replace("\x00", "")
    # Strip other non-printable control chars except common whitespace
    return "".join(ch for ch in text if ch in "\n\r\t" or ord(ch) >= 32)


class PDFExtractionError(Exception):
    """Raised when text cannot be extracted from the provided PDF bytes."""


def extract_text(file_bytes: bytes) -> str:
    """
    Extract plain text from PDF bytes.

    Raises:
        PDFExtractionError: If empty, invalid, or image-only PDF.
    """
    if not file_bytes:
        logger.error("[PDF] Received empty file bytes — aborting extraction.")
        raise PDFExtractionError("Received empty file bytes.")

    file_size_kb = len(file_bytes) / 1024
    logger.info("[PDF] Starting extraction — file size: %.1f KB", file_size_kb)

    try:
        text = _pdfminer_extract(BytesIO(file_bytes))
    except Exception as exc:
        logger.exception("[PDF] pdfminer failed to parse the PDF: %s", exc)
        raise PDFExtractionError(f"PDF parsing failed: {exc}") from exc

    text = _sanitize_text(text)

    # Collapse excessive whitespace while preserving paragraph breaks
    cleaned = "\n".join(
        line.strip() for line in text.splitlines() if line.strip()
    )

    char_count = len(cleaned)
    logger.debug("[PDF] Raw extracted text preview (first 200 chars):\n  %s", cleaned[:200])

    if char_count < MIN_TEXT_LENGTH:
        logger.error(
            "[PDF] Extracted only %d characters — PDF appears to be image-only or blank.",
            char_count,
        )
        raise PDFExtractionError(
            "Extracted text is too short — the PDF may be image-only or blank. "
            "Please provide a text-based PDF or run OCR before uploading."
        )

    logger.info("[PDF] Extraction successful — %d characters extracted.", char_count)
    return cleaned
