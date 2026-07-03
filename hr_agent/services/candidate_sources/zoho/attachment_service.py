"""
Download resume attachments from Zoho Recruit candidates.
"""
from __future__ import annotations

import logging
from typing import Any

from hr_agent.models.zoho_candidate import ZohoCandidate
from hr_agent.services.candidate_sources.zoho.candidate_service import profile_to_raw_text
from hr_agent.services.candidate_sources.zoho.client import ZohoAPIError, ZohoClient
from hr_agent.services.pdf_service import PDFExtractionError, extract_text

logger = logging.getLogger(__name__)

_RESUME_KEYWORDS = ("resume", "cv", "curriculum")


def _is_resume_attachment(attachment: dict[str, Any]) -> bool:
    file_name = (attachment.get("File_Name") or attachment.get("$file_name") or "").lower()
    if file_name.endswith(".pdf"):
        return True
    return any(keyword in file_name for keyword in _RESUME_KEYWORDS)


def pick_resume_attachment(attachments: list[dict[str, Any]]) -> dict[str, Any] | None:
    pdfs = [a for a in attachments if _is_resume_attachment(a)]
    if not pdfs:
        return None
    pdfs.sort(key=lambda a: a.get("Modified_Time") or "", reverse=True)
    return pdfs[0]


def download_candidate_resume_text(
    client: ZohoClient,
    candidate_id: str,
    profile: dict[str, Any],
    *,
    demo_mode: bool = False,
) -> tuple[str | None, str | None]:
    """
    Download the best resume attachment and extract text.

    Returns (raw_text, attachment_id). Falls back to profile fields when no PDF exists.
    """
    if demo_mode:
        return profile_to_raw_text(profile), None

    try:
        payload = client.list_attachments(candidate_id)
    except ZohoAPIError as exc:
        logger.warning("[ZOHO:RESUME] Could not list attachments for %s: %s", candidate_id, exc)
        return profile_to_raw_text(profile), None

    attachments = payload.get("data") or []
    chosen = pick_resume_attachment(attachments)
    if chosen is None:
        logger.info("[ZOHO:RESUME] No resume attachment for candidate %s — using profile fields.", candidate_id)
        return profile_to_raw_text(profile), None

    attachment_id = str(chosen.get("id") or chosen.get("$attachment_id") or "")
    if not attachment_id:
        return profile_to_raw_text(profile), None

    try:
        file_bytes = client.download_attachment(candidate_id, attachment_id)
        raw_text = extract_text(file_bytes)
        return raw_text, attachment_id
    except (ZohoAPIError, PDFExtractionError) as exc:
        logger.warning(
            "[ZOHO:RESUME] Attachment download/parse failed for %s — falling back to profile: %s",
            candidate_id, exc,
        )
        return profile_to_raw_text(profile), attachment_id


def apply_resume_to_row(
    row: ZohoCandidate,
    raw_text: str,
    attachment_id: str | None,
) -> None:
    row.resume_downloaded = attachment_id is not None
    row.resume_attachment_id = attachment_id
    if row.raw_profile_json is None:
        row.raw_profile_json = {}
    row.raw_profile_json["_resume_text"] = raw_text
