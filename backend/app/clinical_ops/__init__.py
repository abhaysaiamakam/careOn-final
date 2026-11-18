"""
CareOn Milestone 8 — Clinical Operations & Digital Handover Package.

Exports:
- Encounters: create_or_register_patient, update_patient_identity, create_emergency_encounter, transition_encounter_status, IdentityStatus, EncounterStatus
- Records: record_clinical_assessment, record_vital_signs, record_prehospital_intervention, record_medication_administration, generate_deterministic_clinical_summary, ClinicalValidationError
- Handover: create_handover_draft, submit_handover_document, receive_handover_document, acknowledge_handover_document, complete_transfer_of_care, request_handover_clarification, submit_handover_correction, HandoverStatus, HandoverStateError
- Attachments: register_attachment, AttachmentValidationError
"""

from app.clinical_ops.encounters import (
    IdentityStatus,
    EncounterStatus,
    create_or_register_patient,
    update_patient_identity,
    create_emergency_encounter,
    transition_encounter_status,
)
from app.clinical_ops.records import (
    ClinicalValidationError,
    record_clinical_assessment,
    record_vital_signs,
    record_prehospital_intervention,
    record_medication_administration,
    generate_deterministic_clinical_summary,
)
from app.clinical_ops.handover import (
    HandoverStatus,
    HandoverStateError,
    create_handover_draft,
    submit_handover_document,
    receive_handover_document,
    acknowledge_handover_document,
    complete_transfer_of_care,
    request_handover_clarification,
    submit_handover_correction,
)
from app.clinical_ops.attachments import (
    register_attachment,
    AttachmentValidationError,
)

__all__ = [
    "IdentityStatus",
    "EncounterStatus",
    "create_or_register_patient",
    "update_patient_identity",
    "create_emergency_encounter",
    "transition_encounter_status",
    "ClinicalValidationError",
    "record_clinical_assessment",
    "record_vital_signs",
    "record_prehospital_intervention",
    "record_medication_administration",
    "generate_deterministic_clinical_summary",
    "HandoverStatus",
    "HandoverStateError",
    "create_handover_draft",
    "submit_handover_document",
    "receive_handover_document",
    "acknowledge_handover_document",
    "complete_transfer_of_care",
    "request_handover_clarification",
    "submit_handover_correction",
    "register_attachment",
    "AttachmentValidationError",
]
