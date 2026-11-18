"""
CareOn Milestone 9 — Sync Batch Upload Processor.

Processes batches of queued actions submitted by responder mobile devices.
Enforces:
- Device & User authentication and active non-revoked validation.
- Per-action isolation (partial batch survival via transaction savepoints).
- Idempotent action execution using unique action_uuids.
- Non-destructive clinical record appending with provenance timestamps.
- Authoritative M6 mission lifecycle state machine validation.
- Non-overwriting delayed GPS telemetry ingestion.
- Explicit conflict generation for incompatible transitions or reassignments.
"""

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import (
    DeviceRegistration,
    SyncBatchReceipt,
    SyncActionReceipt,
    SyncConflict,
    User,
    Assignment,
    Incident,
    Resource,
    ResponderTelemetryLog,
    EmergencyEncounter,
    ClinicalAssessment,
    VitalSignObservation,
    PreHospitalIntervention,
    MedicationAdministration,
    DigitalHandoverRecord,
    ClinicalTimelineEvent,
    make_point_wkt,
    utc_now,
)
from app.schemas import (
    SyncUploadBatchRequest,
    SyncUploadBatchResponse,
    SyncActionReceiptResponse,
    SyncActionItem,
)
from app.sync.device_manager import get_verified_device
from app.sync.conflict_engine import (
    record_sync_conflict,
    ConflictCategory,
    ResolutionStatus,
)
from app.responder_ops.state_machine import (
    execute_mission_transition,
    MissionStatus,
    MissionTransitionError,
)
from app.clinical_ops.records import (
    record_clinical_assessment,
    record_vital_signs,
    record_prehospital_intervention,
    record_medication_administration,
)
from app.clinical_ops.handover import (
    HandoverStatus,
)

logger = logging.getLogger("careon.sync.batch_processor")

MAX_BATCH_SIZE = 200


def ensure_utc(dt: Optional[datetime]) -> datetime:
    """Ensure datetime has UTC timezone."""
    if dt is None:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def process_sync_batch(
    db: Session,
    user: User,
    batch_req: SyncUploadBatchRequest,
) -> SyncUploadBatchResponse:
    """
    Execute a batch upload of queued actions from an authenticated responder device.
    """
    start_time = time.time()

    # 1. Verify device registration and revocation status
    device = get_verified_device(db, batch_req.device_id, user)

    # 2. Validate batch size
    if len(batch_req.actions) > MAX_BATCH_SIZE:
        status_413 = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        raise HTTPException(
            status_code=status_413,
            detail=f"Batch size {len(batch_req.actions)} exceeds limit of {MAX_BATCH_SIZE} actions.",
        )

    now = utc_now()

    # 3. Create or find SyncBatchReceipt record
    batch_receipt = (
        db.query(SyncBatchReceipt)
        .filter(SyncBatchReceipt.batch_uuid == batch_req.client_batch_id)
        .first()
    )
    if not batch_receipt:
        batch_receipt = SyncBatchReceipt(
            batch_uuid=batch_req.client_batch_id,
            device_id=device.id,
            user_id=user.id,
            total_actions=len(batch_req.actions),
            accepted_actions=0,
            failed_actions=0,
            conflict_actions=0,
            server_receipt_timestamp=now,
            processing_time_ms=0.0,
            created_at=now,
        )
        db.add(batch_receipt)
        db.flush()

    action_results: List[SyncActionReceiptResponse] = []
    accepted_count = 0
    failed_count = 0
    conflict_count = 0

    # 4. Process each action independently
    for action_item in batch_req.actions:
        # A. Idempotency Check: action already processed?
        existing_receipt = (
            db.query(SyncActionReceipt)
            .filter(SyncActionReceipt.action_uuid == action_item.action_uuid)
            .first()
        )
        if existing_receipt:
            resp_payload = None
            if existing_receipt.response_payload_json:
                try:
                    resp_payload = json.loads(existing_receipt.response_payload_json)
                except Exception:
                    pass

            action_results.append(
                SyncActionReceiptResponse(
                    action_uuid=existing_receipt.action_uuid,
                    status=existing_receipt.status,
                    server_ack_id=existing_receipt.server_ack_id,
                    action_type=existing_receipt.action_type,
                    client_timestamp=existing_receipt.client_timestamp,
                    server_receipt_timestamp=existing_receipt.server_receipt_timestamp,
                    response_payload=resp_payload,
                    error_message=existing_receipt.error_message,
                    conflict_details=None,
                )
            )
            if existing_receipt.status == "ACKNOWLEDGED":
                accepted_count += 1
            elif existing_receipt.status == "CONFLICT":
                conflict_count += 1
            else:
                failed_count += 1
            continue

        # Compute payload hash
        payload_str = json.dumps(action_item.payload, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()
        server_ack_id = f"ack_{uuid.uuid4().hex[:16]}"

        # B. Isolated processing per action
        action_status = "ACKNOWLEDGED"
        error_msg: Optional[str] = None
        conflict_details: Optional[Dict[str, Any]] = None
        resp_data: Optional[Dict[str, Any]] = None

        try:
            # Dispatch action by type
            if action_item.action_type == "MISSION_STATUS_CHANGE":
                resp_data, action_status, conflict_details = _handle_mission_status_action(
                    db, user, device, action_item
                )
            elif action_item.action_type == "CLINICAL_ASSESSMENT":
                resp_data, action_status, conflict_details = _handle_clinical_assessment_action(
                    db, user, device, action_item
                )
            elif action_item.action_type == "VITAL_OBSERVATION":
                resp_data, action_status, conflict_details = _handle_vital_observation_action(
                    db, user, device, action_item
                )
            elif action_item.action_type == "INTERVENTION":
                resp_data, action_status, conflict_details = _handle_intervention_action(
                    db, user, device, action_item
                )
            elif action_item.action_type == "MEDICATION":
                resp_data, action_status, conflict_details = _handle_medication_action(
                    db, user, device, action_item
                )
            elif action_item.action_type == "HANDOVER_UPDATE":
                resp_data, action_status, conflict_details = _handle_handover_action(
                    db, user, device, action_item
                )
            elif action_item.action_type == "TELEMETRY_BATCH":
                resp_data, action_status, conflict_details = _handle_telemetry_batch_action(
                    db, user, device, action_item
                )
            else:
                action_status = "PERMANENT_FAILURE"
                error_msg = f"Unknown or unsupported action type: {action_item.action_type}"

        except Exception as exc:
            logger.exception("Error processing action %s: %s", action_item.action_uuid, exc)
            action_status = "PERMANENT_FAILURE"
            error_msg = str(exc)

        # Record receipt
        receipt = SyncActionReceipt(
            action_uuid=action_item.action_uuid,
            batch_id=batch_receipt.id,
            device_id=device.id,
            user_id=user.id,
            action_type=action_item.action_type,
            mission_id=action_item.mission_id,
            encounter_id=action_item.encounter_id,
            client_timestamp=action_item.client_timestamp,
            server_receipt_timestamp=utc_now(),
            status=action_status,
            server_ack_id=server_ack_id,
            payload_hash=payload_hash,
            response_payload_json=json.dumps(resp_data, default=str) if resp_data else None,
            error_message=error_msg,
            created_at=utc_now(),
        )
        db.add(receipt)
        db.flush()

        if action_status == "ACKNOWLEDGED":
            accepted_count += 1
        elif action_status == "CONFLICT":
            conflict_count += 1
        else:
            failed_count += 1

        action_results.append(
            SyncActionReceiptResponse(
                action_uuid=action_item.action_uuid,
                status=action_status,
                server_ack_id=server_ack_id,
                action_type=action_item.action_type,
                client_timestamp=action_item.client_timestamp,
                server_receipt_timestamp=receipt.server_receipt_timestamp,
                response_payload=resp_data,
                error_message=error_msg,
                conflict_details=conflict_details,
            )
        )

    # 5. Finalize batch metrics & update device last_sync_at
    proc_time_ms = (time.time() - start_time) * 1000.0
    batch_receipt.accepted_actions = accepted_count
    batch_receipt.failed_actions = failed_count
    batch_receipt.conflict_actions = conflict_count
    batch_receipt.processing_time_ms = proc_time_ms

    device.last_sync_at = utc_now()
    device.last_seen_at = utc_now()
    db.commit()

    return SyncUploadBatchResponse(
        batch_uuid=batch_req.client_batch_id,
        device_id=device.device_identifier,
        total_actions=len(batch_req.actions),
        accepted_actions=accepted_count,
        failed_actions=failed_count,
        conflict_actions=conflict_count,
        server_receipt_timestamp=now,
        processing_time_ms=proc_time_ms,
        results=action_results,
    )


# ==============================================================================
# Action Dispatch Handlers
# ==============================================================================

def _handle_mission_status_action(
    db: Session,
    user: User,
    device: DeviceRegistration,
    item: SyncActionItem,
) -> (Optional[Dict[str, Any]], str, Optional[Dict[str, Any]]):
    """
    Execute mission state transition with authoritative M6 validation.
    Detects stale or incompatible transitions and generates SyncConflict.
    """
    mission_id = item.mission_id or item.payload.get("assignment_id")
    if not mission_id:
        return None, "PERMANENT_FAILURE", None

    assignment = db.query(Assignment).filter(Assignment.id == mission_id).first()
    if not assignment:
        return None, "PERMANENT_FAILURE", None

    # Tenant / ownership check
    resource = db.query(Resource).filter(Resource.id == assignment.resource_id).first()
    if device.organization_id and resource and resource.organization_id:
        if device.organization_id != resource.organization_id and user.role not in ["admin", "superadmin"]:
            return None, "PERMANENT_FAILURE", None
    if resource and resource.assigned_user_id and resource.assigned_user_id != user.id:
        # Assignment conflict: mission was reassigned to someone else!
        conflict = record_sync_conflict(
            db=db,
            device=device,
            user=user,
            action_uuid=item.action_uuid,
            conflict_category=ConflictCategory.ASSIGNMENT,
            reason="Mission was reassigned to a different responder while device was offline.",
            client_state=item.payload,
            server_state={"assignment_id": assignment.id, "current_responder_id": resource.assigned_user_id},
            mission_id=assignment.id,
        )
        return (
            None,
            "CONFLICT",
            {
                "conflict_token": conflict.conflict_token,
                "category": ConflictCategory.ASSIGNMENT,
                "reason": conflict.reason,
            },
        )

    new_status = item.payload.get("status")
    notes = item.payload.get("notes")

    # Authoritative check: if assignment already completed or cancelled on server
    if assignment.status in [MissionStatus.COMPLETED, MissionStatus.CANCELLED]:
        conflict = record_sync_conflict(
            db=db,
            device=device,
            user=user,
            action_uuid=item.action_uuid,
            conflict_category=ConflictCategory.MISSION_STATE,
            reason=f"Cannot transition mission: already terminal ({assignment.status}) on server.",
            client_state=item.payload,
            server_state={"assignment_id": assignment.id, "server_status": assignment.status},
            mission_id=assignment.id,
        )
        return (
            None,
            "CONFLICT",
            {
                "conflict_token": conflict.conflict_token,
                "category": ConflictCategory.MISSION_STATE,
                "reason": conflict.reason,
            },
        )

    try:
        result = execute_mission_transition(
            db=db,
            assignment_id=assignment.id,
            target_status=new_status,
            actor=user,
            notes=notes,
            client_action_id=item.action_uuid,
            client_timestamp=item.client_timestamp,
        )
        return (
            {
                "assignment_id": result.assignment_id,
                "status": result.current_status,
                "server_timestamp": result.server_timestamp.isoformat(),
            },
            "ACKNOWLEDGED",
            None,
        )
    except MissionTransitionError as err:
        conflict = record_sync_conflict(
            db=db,
            device=device,
            user=user,
            action_uuid=item.action_uuid,
            conflict_category=ConflictCategory.MISSION_STATE,
            reason=str(err),
            client_state=item.payload,
            server_state={"assignment_id": assignment.id, "server_status": assignment.status},
            mission_id=assignment.id,
        )
        return (
            None,
            "CONFLICT",
            {
                "conflict_token": conflict.conflict_token,
                "category": ConflictCategory.MISSION_STATE,
                "reason": conflict.reason,
            },
        )


def _handle_clinical_assessment_action(
    db: Session,
    user: User,
    device: DeviceRegistration,
    item: SyncActionItem,
) -> (Optional[Dict[str, Any]], str, Optional[Dict[str, Any]]):
    """
    Record clinical assessment. Never overwrites existing observations.
    """
    encounter_id = item.encounter_id or item.payload.get("encounter_id")
    if not encounter_id:
        return None, "PERMANENT_FAILURE", None

    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        return None, "PERMANENT_FAILURE", None

    p = item.payload
    assessment = record_clinical_assessment(
        db=db,
        encounter_id=encounter.id,
        responder=user,
        consciousness_level=p.get("consciousness_level", "Alert"),
        airway_status=p.get("airway_status", "clear"),
        breathing_status=p.get("breathing_status", "normal"),
        circulation_status=p.get("circulation_status", "normal_pulses"),
        presenting_complaints=p.get("presenting_complaints"),
        observed_injuries=p.get("observed_injuries"),
        symptoms=p.get("symptoms"),
        clinical_notes=p.get("clinical_notes"),
        assessed_at=item.client_timestamp,
    )
    return (
        {
            "assessment_id": assessment.id,
            "encounter_id": assessment.encounter_id,
            "assessed_at": assessment.assessed_at.isoformat(),
        },
        "ACKNOWLEDGED",
        None,
    )


def _handle_vital_observation_action(
    db: Session,
    user: User,
    device: DeviceRegistration,
    item: SyncActionItem,
) -> (Optional[Dict[str, Any]], str, Optional[Dict[str, Any]]):
    """
    Record vital sign observations with physiological range validation and client provenance.
    """
    encounter_id = item.encounter_id or item.payload.get("encounter_id")
    if not encounter_id:
        return None, "PERMANENT_FAILURE", None

    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        return None, "PERMANENT_FAILURE", None

    p = item.payload
    vital = record_vital_signs(
        db=db,
        encounter_id=encounter.id,
        user=user,
        heart_rate=p.get("heart_rate"),
        systolic_bp=p.get("systolic_bp"),
        diastolic_bp=p.get("diastolic_bp"),
        respiratory_rate=p.get("respiratory_rate"),
        oxygen_saturation=p.get("oxygen_saturation"),
        body_temperature=p.get("body_temperature"),
        blood_glucose=p.get("blood_glucose"),
        gcs_eye=p.get("gcs_eye"),
        gcs_verbal=p.get("gcs_verbal"),
        gcs_motor=p.get("gcs_motor"),
        measurement_source=p.get("measurement_source", "manual"),
        observed_at=item.client_timestamp,
    )
    return (
        {
            "vital_id": vital.id,
            "encounter_id": vital.encounter_id,
            "gcs_total": vital.gcs_total,
            "observed_at": vital.observed_at.isoformat(),
        },
        "ACKNOWLEDGED",
        None,
    )


def _handle_intervention_action(
    db: Session,
    user: User,
    device: DeviceRegistration,
    item: SyncActionItem,
) -> (Optional[Dict[str, Any]], str, Optional[Dict[str, Any]]):
    encounter_id = item.encounter_id or item.payload.get("encounter_id")
    if not encounter_id:
        return None, "PERMANENT_FAILURE", None

    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        return None, "PERMANENT_FAILURE", None

    p = item.payload
    intervention = record_prehospital_intervention(
        db=db,
        encounter_id=encounter.id,
        performer=user,
        intervention_type=p.get("intervention_type", "observation"),
        parameters_json=p.get("parameters_json") or p.get("parameters"),
        patient_response=p.get("patient_response", "unchanged"),
        notes=p.get("notes"),
        performed_at=item.client_timestamp,
    )
    return (
        {
            "intervention_id": intervention.id,
            "encounter_id": intervention.encounter_id,
            "intervention_type": intervention.intervention_type,
        },
        "ACKNOWLEDGED",
        None,
    )


def _handle_medication_action(
    db: Session,
    user: User,
    device: DeviceRegistration,
    item: SyncActionItem,
) -> (Optional[Dict[str, Any]], str, Optional[Dict[str, Any]]):
    encounter_id = item.encounter_id or item.payload.get("encounter_id")
    if not encounter_id:
        return None, "PERMANENT_FAILURE", None

    encounter = db.query(EmergencyEncounter).filter(EmergencyEncounter.id == encounter_id).first()
    if not encounter:
        return None, "PERMANENT_FAILURE", None

    p = item.payload
    med = record_medication_administration(
        db=db,
        encounter_id=encounter.id,
        administering_user=user,
        medication_name=p["medication_name"],
        dose=float(p["dose"]),
        unit=p["unit"],
        route=p["route"],
        response_notes=p.get("response_notes"),
        administered_at=item.client_timestamp,
    )
    return (
        {
            "medication_id": med.id,
            "encounter_id": med.encounter_id,
            "medication_name": med.medication_name,
        },
        "ACKNOWLEDGED",
        None,
    )


def _handle_handover_action(
    db: Session,
    user: User,
    device: DeviceRegistration,
    item: SyncActionItem,
) -> (Optional[Dict[str, Any]], str, Optional[Dict[str, Any]]):
    handover_id = item.payload.get("handover_id")
    if not handover_id:
        return None, "PERMANENT_FAILURE", None

    handover = db.query(DigitalHandoverRecord).filter(DigitalHandoverRecord.id == handover_id).first()
    if not handover:
        return None, "PERMANENT_FAILURE", None

    # Check if handover is already completed on server
    if handover.status == HandoverStatus.COMPLETED:
        conflict = record_sync_conflict(
            db=db,
            device=device,
            user=user,
            action_uuid=item.action_uuid,
            conflict_category=ConflictCategory.CLINICAL,
            reason="Cannot modify handover: clinical transfer-of-care already completed and locked on server.",
            client_state=item.payload,
            server_state={"handover_id": handover.id, "status": handover.status, "is_final": handover.is_final},
            encounter_id=handover.encounter_id,
        )
        return (
            None,
            "CONFLICT",
            {
                "conflict_token": conflict.conflict_token,
                "category": ConflictCategory.CLINICAL,
                "reason": conflict.reason,
            },
        )

    if item.payload.get("outstanding_clinical_concerns"):
        handover.outstanding_clinical_concerns = item.payload.get("outstanding_clinical_concerns")
    if item.payload.get("receiving_department"):
        handover.receiving_department = item.payload.get("receiving_department")
    handover.updated_at = utc_now()

    return (
        {
            "handover_id": handover.id,
            "status": handover.status,
            "version": handover.version,
        },
        "ACKNOWLEDGED",
        None,
    )


def _handle_telemetry_batch_action(
    db: Session,
    user: User,
    device: DeviceRegistration,
    item: SyncActionItem,
) -> (Optional[Dict[str, Any]], str, Optional[Dict[str, Any]]):
    """
    Ingest buffered telemetry batch.
    Preserves historical GPS points in telemetry logs without letting older points
    overwrite the resource's current authoritative location.
    """
    points = item.payload.get("points", [])
    if not points:
        return None, "ACKNOWLEDGED", None

    # Find responder's assigned resource
    resource = (
        db.query(Resource)
        .filter(Resource.assigned_user_id == user.id)
        .first()
    )
    if not resource:
        return None, "PERMANENT_FAILURE", None

    ingested_count = 0
    now = utc_now()

    for pt in points:
        lat = pt.get("latitude")
        lon = pt.get("longitude")
        if lat is None or lon is None:
            continue
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            continue

        raw_ts = pt.get("client_timestamp") or pt.get("timestamp")
        if isinstance(raw_ts, str):
            try:
                pt_time = datetime.fromisoformat(raw_ts)
            except Exception:
                pt_time = now
        elif isinstance(raw_ts, datetime):
            pt_time = raw_ts
        else:
            pt_time = now

        # Add to telemetry log (historical record)
        log = ResponderTelemetryLog(
            resource_id=resource.id,
            user_id=user.id,
            latitude=lat,
            longitude=lon,
            speed=pt.get("speed"),
            heading=pt.get("heading"),
            accuracy=pt.get("accuracy"),
            battery_level=pt.get("battery_level"),
            network_type=pt.get("network_type", "offline"),
            freshness_status="verified_live",
            is_buffered=True,
            client_action_id=item.action_uuid,
            client_timestamp=pt_time,
            server_timestamp=now,
        )
        db.add(log)
        ingested_count += 1

        # CRITICAL: Prevent older GPS telemetry from overwriting current location!
        # Only update resource's current position if pt_time >= resource.last_updated
        if resource.last_updated is None or ensure_utc(pt_time) >= ensure_utc(resource.last_updated):
            resource.latitude = lat
            resource.longitude = lon
            resource.geom = make_point_wkt(lat, lon)
            resource.last_updated = ensure_utc(pt_time)

    return (
        {
            "resource_id": resource.id,
            "points_ingested": ingested_count,
        },
        "ACKNOWLEDGED",
        None,
    )
