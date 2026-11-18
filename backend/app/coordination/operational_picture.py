"""
Common Operational Picture (COP) & Geospatial Operational Zones Service.
Constructs a unified, scope-filtered situational overview for participating agencies.
Strictly protects clinical isolation: CLINICAL_HANDOVER_REFERENCE only exposes reference tokens.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import (
    Incident,
    Organization,
    User,
    IncidentOperationalZone,
    IncidentCommandStructure,
    IncidentCommandAssignment,
    AgencyOperationalTask,
    AgencyResourceRequest,
    IncidentAgencyCollaboration,
    IncidentInformationGrant,
    Assignment,
    Resource,
    DigitalHandoverRecord,
    EmergencyEncounter,
    utc_now,
)
from app.coordination.collaboration_service import (
    verify_incident_scope_access,
    log_inter_agency_audit,
)
from app.realtime.event_publisher import record_and_publish_event

VALID_ZONE_TYPES = {
    "INCIDENT_PERIMETER",
    "HOT_ZONE",
    "WARM_ZONE",
    "COLD_ZONE",
    "STAGING_AREA",
    "EVACUATION_ZONE",
    "ACCESS_RESTRICTED_ZONE",
    "HAZARD_ZONE",
    "SAFE_ASSEMBLY_AREA",
}


def create_operational_zone(
    db: Session,
    incident_id: int,
    acting_org_id: int,
    acting_user_id: int,
    zone_type: str,
    name: str,
    description: Optional[str] = None,
    center_latitude: Optional[float] = None,
    center_longitude: Optional[float] = None,
    radius_meters: Optional[float] = None,
    polygon_geojson: Optional[str] = None,
    hazard_type: Optional[str] = None,
    access_restrictions: Optional[str] = None,
) -> IncidentOperationalZone:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {incident_id} not found.")

    ztype = zone_type.upper()
    if ztype not in VALID_ZONE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid zone type: {zone_type}")

    zone = IncidentOperationalZone(
        zone_uuid=str(uuid.uuid4()),
        incident_id=incident_id,
        created_by_organization_id=acting_org_id,
        created_by_user_id=acting_user_id,
        zone_type=ztype,
        name=name,
        description=description,
        center_latitude=center_latitude,
        center_longitude=center_longitude,
        radius_meters=radius_meters,
        polygon_geojson=polygon_geojson,
        hazard_type=hazard_type,
        access_restrictions=access_restrictions,
        is_active=True,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(zone)
    db.flush()

    log_inter_agency_audit(
        db=db,
        incident_id=incident_id,
        acting_org_id=acting_org_id,
        acting_user_id=acting_user_id,
        action_type="OPERATIONAL_ZONE_CREATED",
        target_resource_type="OPERATIONAL_ZONE",
        target_resource_id=zone.zone_uuid,
        details={"zone_type": ztype, "name": name, "hazard_type": hazard_type},
    )

    record_and_publish_event(
        db=db,
        event_type="operational_picture.zone.created",
        payload={
            "zone_uuid": zone.zone_uuid,
            "incident_id": incident_id,
            "zone_type": ztype,
            "name": name,
        },
        organization_id=acting_org_id,
        incident_id=incident_id,
        actor_id=acting_user_id,
    )

    db.commit()
    db.refresh(zone)
    return zone


def get_incident_operational_picture(
    db: Session,
    incident_id: int,
    requesting_org_id: Optional[int],
    requesting_user_id: int,
    is_superadmin: bool = False,
) -> Dict[str, Any]:
    """
    Assemble the Common Operational Picture, filtering every section through the granted scopes.
    Deny-by-default: If a scope is missing, its section is strictly None.
    """
    granted_scopes = verify_incident_scope_access(
        db=db,
        incident_id=incident_id,
        user_org_id=requesting_org_id,
        user_id=requesting_user_id,
        required_scope=None,
        is_superadmin=is_superadmin,
    )

    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    cop: Dict[str, Any] = {
        "incident_id": incident_id,
        "requesting_agency_id": requesting_org_id or 0,
        "granted_scopes": sorted(list(granted_scopes)),
        "summary": None,
        "location": None,
        "hazard_information": None,
        "participating_agencies": [],
        "resource_status": None,
        "agency_tasks": None,
        "casualty_counts": None,
        "hospital_destinations": None,
        "clinical_handover_reference": None,
        "command_information": None,
        "operational_zones": None,
    }

    # Participating Agencies (visible if at least collaboration is established)
    collabs = (
        db.query(IncidentAgencyCollaboration, Organization)
        .join(Organization, IncidentAgencyCollaboration.organization_id == Organization.id)
        .filter(IncidentAgencyCollaboration.incident_id == incident_id)
        .all()
    )
    for c, org in collabs:
        cop["participating_agencies"].append({
            "collaboration_uuid": c.collaboration_uuid,
            "organization_id": org.id,
            "organization_name": org.name,
            "organization_type": org.org_type,
            "status": c.collaboration_status,
            "purpose": c.collaboration_purpose,
        })

    # Scope: INCIDENT_SUMMARY
    if "INCIDENT_SUMMARY" in granted_scopes:
        cop["summary"] = {
            "title": incident.title or f"Incident #{incident.id}",
            "description": incident.description,
            "status": incident.status,
            "priority": incident.priority,
            "created_at": incident.created_at.isoformat() if incident.created_at else None,
            "is_disaster": incident.is_disaster,
            "disaster_details": incident.disaster_details,
        }

    # Scope: OPERATIONAL_LOCATION
    if "OPERATIONAL_LOCATION" in granted_scopes:
        cop["location"] = {
            "latitude": incident.latitude,
            "longitude": incident.longitude,
            "location_name": incident.location_name,
        }

    # Scope: HAZARD_INFORMATION
    if "HAZARD_INFORMATION" in granted_scopes:
        hazards = []
        zones = (
            db.query(IncidentOperationalZone)
            .filter(
                IncidentOperationalZone.incident_id == incident_id,
                IncidentOperationalZone.is_active == True,
                IncidentOperationalZone.hazard_type.isnot(None),
            )
            .all()
        )
        for z in zones:
            hazards.append({
                "zone_name": z.name,
                "hazard_type": z.hazard_type,
                "access_restrictions": z.access_restrictions,
                "description": z.description,
            })
        cop["hazard_information"] = hazards

    # Scope: RESOURCE_STATUS
    if "RESOURCE_STATUS" in granted_scopes:
        assignments = (
            db.query(Assignment, Resource)
            .join(Resource, Assignment.resource_id == Resource.id)
            .filter(Assignment.incident_id == incident_id)
            .all()
        )
        resources_list = []
        for asgn, res in assignments:
            resources_list.append({
                "assignment_id": asgn.id,
                "resource_id": res.id,
                "resource_name": res.name,
                "resource_type": res.type,
                "assignment_status": asgn.status,
                "organization_id": res.organization_id,
            })
        cop["resource_status"] = resources_list

    # Scope: AGENCY_TASKS
    if "AGENCY_TASKS" in granted_scopes:
        tasks = (
            db.query(AgencyOperationalTask)
            .filter(AgencyOperationalTask.incident_id == incident_id)
            .all()
        )
        tasks_list = []
        for t in tasks:
            tasks_list.append({
                "task_uuid": t.task_uuid,
                "title": t.title,
                "priority": t.priority,
                "status": t.status,
                "assigning_org_id": t.assigning_organization_id,
                "assigned_org_id": t.assigned_organization_id,
                "assigned_unit": t.assigned_unit_name,
                "deadline": t.deadline.isoformat() if t.deadline else None,
            })
        cop["agency_tasks"] = tasks_list

    # Scope: CASUALTY_COUNTS
    if "CASUALTY_COUNTS" in granted_scopes:
        # Casualty breakdown summary
        cop["casualty_counts"] = {
            "reported_count": incident.casualty_count if hasattr(incident, "casualty_count") else 0,
            "status": "TRIAGE_IN_PROGRESS",
        }

    # Scope: HOSPITAL_DESTINATION
    if "HOSPITAL_DESTINATION" in granted_scopes:
        destinations = []
        if hasattr(incident, "receiving_facility_id") and incident.receiving_facility_id:
            destinations.append({
                "facility_id": incident.receiving_facility_id,
                "status": "DESIGNATED_RECEIVING_FACILITY",
            })
        cop["hospital_destinations"] = destinations

    # Scope: CLINICAL_HANDOVER_REFERENCE
    # STRICT PRIVACY PRESERVATION: Only reference tokens/status, NEVER raw vitals or clinical records!
    if "CLINICAL_HANDOVER_REFERENCE" in granted_scopes:
        handovers = (
            db.query(DigitalHandoverRecord)
            .join(EmergencyEncounter, DigitalHandoverRecord.encounter_id == EmergencyEncounter.id)
            .filter(EmergencyEncounter.incident_id == incident_id)
            .all()
        )
        if handovers:
            latest = handovers[-1]
            cop["clinical_handover_reference"] = {
                "handover_token": latest.handover_token,
                "status": latest.status,
                "facility_id": latest.facility_id,
                "version": latest.version,
                "is_reference_only": True,
            }
        else:
            cop["clinical_handover_reference"] = {"status": "NONE_ACTIVE", "is_reference_only": True}

    # Scope: COMMAND_INFORMATION
    if "COMMAND_INFORMATION" in granted_scopes:
        cmd_struct = (
            db.query(IncidentCommandStructure)
            .filter(
                IncidentCommandStructure.incident_id == incident_id,
                IncidentCommandStructure.is_active == True,
            )
            .first()
        )
        if cmd_struct:
            active_assignments = (
                db.query(IncidentCommandAssignment, User)
                .join(User, IncidentCommandAssignment.assigned_user_id == User.id)
                .filter(
                    IncidentCommandAssignment.command_structure_id == cmd_struct.id,
                    IncidentCommandAssignment.is_active == True,
                )
                .all()
            )
            roles_info = []
            commander_info = None
            for asgn, u in active_assignments:
                entry = {
                    "role": asgn.command_role,
                    "user_id": u.id,
                    "user_name": u.name or u.email,
                    "organization_id": asgn.assigned_organization_id,
                    "radio_callsign": asgn.radio_callsign,
                    "contact_number": asgn.contact_number,
                }
                roles_info.append(entry)
                if asgn.command_role == "INCIDENT_COMMANDER":
                    commander_info = entry

            cop["command_information"] = {
                "command_uuid": cmd_struct.command_uuid,
                "structure_type": cmd_struct.structure_type,
                "lead_agency_id": cmd_struct.lead_agency_id,
                "commander": commander_info,
                "active_roles": roles_info,
            }

    # Scope: OPERATIONAL_DOCUMENTS / ZONES
    if "OPERATIONAL_DOCUMENTS" in granted_scopes or "OPERATIONAL_LOCATION" in granted_scopes:
        active_zones = (
            db.query(IncidentOperationalZone)
            .filter(
                IncidentOperationalZone.incident_id == incident_id,
                IncidentOperationalZone.is_active == True,
            )
            .all()
        )
        zones_data = []
        for z in active_zones:
            zones_data.append({
                "zone_uuid": z.zone_uuid,
                "zone_type": z.zone_type,
                "name": z.name,
                "center_latitude": z.center_latitude,
                "center_longitude": z.center_longitude,
                "radius_meters": z.radius_meters,
                "hazard_type": z.hazard_type,
                "access_restrictions": z.access_restrictions,
            })
        cop["operational_zones"] = zones_data

    return cop
