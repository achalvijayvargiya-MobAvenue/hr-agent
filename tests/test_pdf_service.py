"""
Unit tests for the PDF extraction service.
These tests do not need an OpenAI key or a DB — pure unit tests.
"""
import pytest

from hr_agent.services.pdf_service import PDFExtractionError, _sanitize_text, extract_text


def test_sanitize_text_removes_nul_bytes():
    dirty = "Senior PHP Developer\x00with\x00NUL bytes"
    clean = _sanitize_text(dirty)
    assert "\x00" not in clean
    assert clean == "Senior PHP DeveloperwithNUL bytes"


def test_empty_bytes_raises():
    with pytest.raises(PDFExtractionError, match="empty"):
        extract_text(b"")


def test_non_pdf_bytes_raises():
    with pytest.raises(PDFExtractionError):
        extract_text(b"this is definitely not a pdf")


def test_whitespace_only_pdf_raises(tmp_path):
    """A valid but blank PDF should raise because extracted text is too short."""
    # Minimal valid PDF with no content
    blank_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type /Pages /Kids [3 0 R] /Count 1>>endobj\n"
        b"3 0 obj<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n"
        b"trailer<</Size 4 /Root 1 0 R>>\n"
        b"startxref\n190\n%%EOF"
    )
    with pytest.raises(PDFExtractionError, match="too short"):
        extract_text(blank_pdf)
