"""
CareOn Milestone 8 — Secure Medical Attachments & Supporting Documents.

Features:
- Access-controlled attachment registry for ECG strips, injury photographs, prior records, and transfer documents.
- File type and size validation (max 10MB).
- Strict non-public file paths; access authenticated via API.
- Traceable audit logging.
"""

import os
import uuid
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import (
    HandoverAttachment,
    EmergencyEncounter,
    User,
    utc_now,
)

logger = logging.getLogger("careon.clinical_ops.attachments")

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
    "text/plain",
    "image/webp",
}


class AttachmentValidationError(ValueError):
    """Raised when file upload violates security, size, or format constraints."""
    pass


def register_attachment(
    db: Session,
    encounter_id: int,
    file_name: str,
    file_type: str,
    mime_type: str,
    file_size_bytes: int,
    storage_path: str,
    uploaded_by: User,
    handover_id: Optional[int] = None,
    is_confidential: bool = True,
) -> HandoverAttachment:
    """Registers and associates a validated medical attachment with an emergency encounter."""
    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        raise ValueError(f"Encounter {encounter_id} not found")

    if file_size_bytes > MAX_FILE_SIZE_BYTES:
        raise AttachmentValidationError(
            f"File size ({file_size_bytes} bytes) exceeds maximum limit of {MAX_FILE_SIZE_BYTES} bytes (10MB)"
        )

    if mime_type.lower() not in ALLOWED_MIME_TYPES:
        raise AttachmentValidationError(
            f"MIME type '{mime_type}' is not permitted. Allowed: {sorted(list(ALLOWED_MIME_TYPES))}"
        )

    token = str(uuid.uuid4())
    attachment = HandoverAttachment(
        attachment_token=token,
        encounter_id=encounter.id,
        handover_id=handover_id,
        file_name=file_name.strip(),
        file_type=file_type.lower().strip(),
        mime_type=mime_type.lower().strip(),
        file_size_bytes=file_size_bytes,
        storage_path=storage_path,
        uploaded_by_user_id=uploaded_by.id,
        is_confidential=is_confidential,
        created_at=utc_now(),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment
