"""
CareOn Master Demonstration Data Seeder.

Seeds comprehensive, realistic, fully connected synthetic records across:
1. Core Organizations & Classifications (EMS, Fire, Police, Hospitals)
2. Role-specific Development Accounts (Citizen, Dispatcher, Responder, Hospital Staff, Police, Fire, SuperAdmin)
3. Incident Lifecycle Records (Critical, High, Medium, Low across distinct zones)
4. Ambulances, Responders, Mission Assignments, and Telemetry Logs
5. Receiving Hospital Facilities, Granular Capacity, and Readiness Profiles
6. M7 Incoming Patient Requests (Pre-arrival notifications)
7. M8 Emergency Encounters, Patients, and Digital Clinical Handovers
8. M10 Predictive Demand Forecasts & Positioning Recommendations
9. M11 Incident Command Structure (ICS), Command Roles, and History
10. M11 Inter-Agency Collaborations and Granular 10-Scope Grants
11. M11 Cross-Agency Operational Tasks and Mutual Aid Resource Requests
12. M11 PostGIS Operational Zones (Hot, Warm, Cold, Evacuation)
"""

import json
import uuid
from datetime import datetime, date, timedelta, timezone
from sqlalchemy.orm import Session

from app.database import engine, get_db, Base
from app.auth import hash_password
from app.models import (
    User,
    Organization,
    OrganizationMembership,
    Resource,
    Incident,
    Assignment,
    IncidentUpdate,
    HospitalReadiness,
    HospitalFacility,
    HospitalCapacity,
    IncomingPatientRequest,
    Patient,
    EmergencyEncounter,
    DigitalHandoverRecord,
    DemandForecastRecord,
    PositioningRecommendation,
    CoverageSnapshotRecord,
    AgencyClassification,
    IncidentAgencyCollaboration,
    IncidentInformationGrant,
    IncidentCommandStructure,
    IncidentCommandAssignment,
    IncidentCommandHistory,
    AgencyOperationalTask,
    AgencyResourceRequest,
    IncidentOperationalZone,
    InterAgencyAuditLog,
    make_point_wkt,
    utc_now,
)


def seed_all_demo_data(db: Session):
    print(">>> Seeding CareOn Core Development Data...")
    now = utc_now()

    # ==========================================================================
    # 1. ORGANIZATIONS
    # ==========================================================================
    org_configs = [
        {"name": "Mysuru City Emergency Medical Services", "org_type": "ambulance_service", "phone": "+91 821 244 0108", "email": "ems@careon.org"},
        {"name": "Mysuru Fire & Emergency Rescue Service", "org_type": "fire", "phone": "+91 821 244 0101", "email": "fire@careon.org"},
        {"name": "Karnataka State Police - Mysuru City", "org_type": "police", "phone": "+91 821 244 0100", "email": "police@careon.org"},
        {"name": "KR Hospital Emergency Trauma Centre", "org_type": "hospital", "phone": "+91 821 244 5500", "email": "krhospital@careon.org"},
        {"name": "Apollo BGS Hospitals Mysuru", "org_type": "hospital", "phone": "+91 821 256 8888", "email": "apollobgs@careon.org"},
    ]

    org_map = {}
    for cfg in org_configs:
        org = db.query(Organization).filter(Organization.name == cfg["name"]).first()
        if not org:
            org = Organization(
                name=cfg["name"],
                org_type=cfg["org_type"],
                contact_phone=cfg["phone"],
                contact_email=cfg["email"],
                location_name="Mysuru, Karnataka",
                is_active=True,
                is_verified=True,
                created_at=now,
            )
            db.add(org)
            db.flush()
        org_map[cfg["org_type"] + ("_2" if cfg["name"].startswith("Apollo") else "")] = org

    org_ems = org_map["ambulance_service"]
    org_fire = org_map["fire"]
    org_police = org_map["police"]
    org_kr = org_map["hospital"]
    org_apollo = org_map.get("hospital_2", org_kr)

    # Classifications
    classifications = [
        (org_ems, "EMS", "Mysuru Metropolitan Area", "108", "MED-NET-1", ["ALS", "BLS", "NEONATAL_CARE"]),
        (org_fire, "FIRE_RESCUE", "Mysuru Urban & Industrial Zones", "101", "FIRE-TAC-2", ["HAZMAT", "EXTRICATION", "AERIAL_LADDER"]),
        (org_police, "POLICE", "Mysuru Police Commissionerate", "100", "POLICE-TAC-9", ["TRAFFIC_CONTROL", "PERIMETER_SECURITY", "INVESTIGATION"]),
        (org_kr, "HOSPITAL", "Mysuru Central Health District", "0821-2445500", "HOSP-MED-1", ["LEVEL_1_TRAUMA", "BURNS_UNIT", "NEURO_ICU"]),
        (org_apollo, "HOSPITAL", "Mysuru South Health District", "0821-2568888", "HOSP-MED-2", ["CARDIAC_CATH_LAB", "STROKE_UNIT", "PEDIATRIC_ICU"]),
    ]
    for org_obj, a_type, jur, hotline, radio, caps in classifications:
        cl = db.query(AgencyClassification).filter(AgencyClassification.organization_id == org_obj.id).first()
        if not cl:
            cl = AgencyClassification(
                organization_id=org_obj.id,
                agency_type=a_type,
                jurisdiction=jur,
                dispatch_hotline=hotline,
                radio_channel=radio,
                capabilities_json=json.dumps(caps),
                is_mutual_aid_signatory=True,
                created_at=now,
            )
            db.add(cl)

    # ==========================================================================
    # 2. DEVELOPMENT ACCOUNTS
    # ==========================================================================
    accounts = [
        ("citizen@careon.org", "Aastha Singh", "+91 98765 43210", "Password123!", "user", "Verified citizen resident reporter"),
        ("dispatcher@careon.org", "Dispatcher Sharma", "+91 821 244 5566", "Password123!", "admin", "Primary Emergency Dispatcher"),
        ("responder@careon.org", "Paramedic Vikram Rao", "+91 99999 80001", "Password123!", "admin", "Lead ALS Ambulance Paramedic"),
        ("hospital@careon.org", "Dr. Ananya Sen", "+91 821 244 5511", "Password123!", "admin", "Emergency Department Head - KR Hospital"),
        ("police@careon.org", "Superintendent Rajesh Patil", "+91 821 244 5522", "Password123!", "admin", "State Police Operations Coordinator"),
        ("fire@careon.org", "Battalion Chief Suresh Kumar", "+91 821 244 5533", "Password123!", "admin", "Metro Fire Battalion Commander"),
        ("superadmin@careon.org", "System Administrator", "+91 821 244 5599", "Password123!", "admin", "CareOn Global Super Administrator"),
    ]

    user_map = {}
    for email, name, phone, pwd, role, note in accounts:
        u = db.query(User).filter(User.email == email).first()
        if not u:
            u = User(
                email=email,
                name=name,
                phone=phone,
                hashed_password=hash_password(pwd),
                role=role,
                trust_score="Confirmed Genuine",
                trust_notes=note,
                is_active=True,
                created_at=now,
            )
            db.add(u)
            db.flush()
        else:
            u.hashed_password = hash_password(pwd)
            u.name = name
            u.role = role
        user_map[email] = u

    # Organization Memberships
    memberships = [
        (user_map["dispatcher@careon.org"], org_ems, "admin"),
        (user_map["responder@careon.org"], org_ems, "responder"),
        (user_map["hospital@careon.org"], org_kr, "admin"),
        (user_map["police@careon.org"], org_police, "admin"),
        (user_map["fire@careon.org"], org_fire, "admin"),
    ]
    for u_obj, o_obj, m_role in memberships:
        mem = db.query(OrganizationMembership).filter(
            OrganizationMembership.user_id == u_obj.id,
            OrganizationMembership.organization_id == o_obj.id,
        ).first()
        if not mem:
            mem = OrganizationMembership(
                user_id=u_obj.id,
                organization_id=o_obj.id,
                membership_role=m_role,
                status="active",
            )
            db.add(mem)

    # ==========================================================================
    # 3. RESOURCES & AMBULANCES
    # ==========================================================================
    fleet = [
        ("AMB-01", "Rapid LifeSupport ALS 01", "Ambulance", "ALS,ventilator,trauma_care,oxygen_support", "KR Hospital Station, Mysuru", 12.3142, 76.6490, "Assigned", 2, user_map["responder@careon.org"].id, org_ems.id),
        ("AMB-02", "CityCare BLS Ambulance 02", "Ambulance", "BLS,patient_transport,first_aid", "Jayalakshmipuram Station, Mysuru", 12.3164, 76.6315, "Available", 2, None, org_ems.id),
        ("AMB-03", "Highway Trauma Ambulance 03", "Ambulance", "ALS,trauma_care,extrication", "Bannimantap Ring Road Station", 12.3420, 76.6480, "Available", 2, None, org_ems.id),
        ("AMB-04", "Pediatric Care Ambulance 04", "Ambulance", "ALS,incubator,pediatric_support", "Kuvempunagar Station, Mysuru", 12.2912, 76.6320, "Available", 2, None, org_ems.id),
        ("FIRE-01", "Quick Intervention Fire Tender 01", "Fire Response", "fire_suppression,water_tender,smoke_rescue", "Saraswathipuram Fire Station", 12.3080, 76.6340, "Available", 5, None, org_fire.id),
        ("FIRE-02", "HAZMAT Decontamination Unit 02", "Fire Response", "hazmat_containment,chemical_decon,level_a_suits", "Hebbal Industrial Fire Station", 12.3605, 76.6015, "Available", 4, None, org_fire.id),
        ("POLICE-01", "Rapid Highway Patrol Unit 01", "Police Patrol", "traffic_control,perimeter_cordon,escort", "City Police Headquarters, Nazarbad", 12.3105, 76.6690, "Available", 3, None, org_police.id),
    ]

    res_map = {}
    for code, name, cat, caps, loc, lat, lon, st, cap, assigned_u, org_id in fleet:
        r = db.query(Resource).filter(Resource.resource_code == code).first()
        if not r:
            r = Resource(
                resource_code=code,
                name=name,
                category=cat,
                capabilities=caps,
                location_name=loc,
                latitude=lat,
                longitude=lon,
                geom=make_point_wkt(lat, lon),
                status=st,
                capacity=cap,
                assigned_user_id=assigned_u,
                organization_id=org_id,
                contact_phone="+91 821 244 0001",
                last_updated=now,
            )
            db.add(r)
            db.flush()
        else:
            r.status = st
            r.assigned_user_id = assigned_u
        res_map[code] = r

    # ==========================================================================
    # 4. HOSPITAL READINESS & FACILITIES
    # ==========================================================================
    # KR Hospital Readiness
    readiness_kr = db.query(HospitalReadiness).filter(HospitalReadiness.organization_id == org_kr.id).first()
    if not readiness_kr:
        readiness_kr = HospitalReadiness(
            organization_id=org_kr.id,
            total_er_beds=30,
            available_er_beds=18,
            icu_beds_total=12,
            icu_beds_available=5,
            trauma_bays_total=6,
            trauma_bays_available=3,
            operating_rooms_total=4,
            operating_rooms_available=2,
            divert_status=False,
            updated_at=now,
            updated_by_user_id=user_map["hospital@careon.org"].id,
        )
        db.add(readiness_kr)

    # Apollo BGS Readiness
    readiness_apollo = db.query(HospitalReadiness).filter(HospitalReadiness.organization_id == org_apollo.id).first()
    if not readiness_apollo:
        readiness_apollo = HospitalReadiness(
            organization_id=org_apollo.id,
            total_er_beds=25,
            available_er_beds=14,
            icu_beds_total=10,
            icu_beds_available=4,
            trauma_bays_total=4,
            trauma_bays_available=2,
            operating_rooms_total=3,
            operating_rooms_available=1,
            divert_status=False,
            updated_at=now,
            updated_by_user_id=user_map["hospital@careon.org"].id,
        )
        db.add(readiness_apollo)

    # KR Facility
    fac_kr = db.query(HospitalFacility).filter(HospitalFacility.facility_code == "FAC-KR-01").first()
    if not fac_kr:
        fac_kr = HospitalFacility(
            organization_id=org_kr.id,
            facility_code="FAC-KR-01",
            name="KR Hospital Emergency Trauma Centre",
            facility_type="General Hospital",
            location_name="Sayyaji Rao Rd, Medar Block, Mysuru",
            latitude=12.3142,
            longitude=76.6490,
            geom=make_point_wkt(12.3142, 76.6490),
            trauma_level="Level 1",
            capabilities="emergency,trauma,icu,ct_scan,blood_bank,ambulance_bay",
            operating_status="operational",
            emergency_phone="+91 821 244 5500",
            is_active=True,
            created_at=now,
        )
        db.add(fac_kr)
        db.flush()

    # Apollo Facility
    fac_apollo = db.query(HospitalFacility).filter(HospitalFacility.facility_code == "FAC-APOLLO-01").first()
    if not fac_apollo:
        fac_apollo = HospitalFacility(
            organization_id=org_apollo.id,
            facility_code="FAC-APOLLO-01",
            name="Apollo BGS Specialty Hospital",
            facility_type="Specialty Hospital",
            location_name="Adichunchanagiri Road, Kuvempunagar, Mysuru",
            latitude=12.2912,
            longitude=76.6320,
            geom=make_point_wkt(12.2912, 76.6320),
            trauma_level="Level 2",
            capabilities="emergency,trauma,icu,ct_scan,cath_lab,mri",
            operating_status="operational",
            emergency_phone="+91 821 256 8888",
            is_active=True,
            created_at=now,
        )
        db.add(fac_apollo)
        db.flush()

    # ==========================================================================
    # 5. EMERGENCY INCIDENTS
    # ==========================================================================
    incidents_data = [
        {
            "code": "CARE-2026-101",
            "category": "Disaster",
            "title": "Hebbal Industrial Chemical Tanker Explosion & Active Fire",
            "description": "Chemical transport tanker ruptured and ignited near manufacturing depot. Toxic vapor plume spreading; multiple personnel trapped with severe chemical flash burns and blast trauma.",
            "location": "Hebbal Industrial Area, Phase 2, Ring Road Junction, Mysuru",
            "lat": 12.3610,
            "lon": 76.6025,
            "priority": "Critical",
            "status": "Team Dispatched",
            "affected": 12,
            "help": "Multi-Agency Emergency Coordination Required (Ambulances, HAZMAT Fire Tenders, Traffic Diversion)",
            "contact_name": "Ramesh Gowda (Plant Security Supervisor)",
            "contact_phone": "+91 98450 77112",
            "is_disaster": True,
            "disaster_details": "Benzene/Toluene chemical vapor leak, active flame impingement on adjacent bulk storage tanks.",
        },
        {
            "code": "CARE-2026-102",
            "category": "Road accident",
            "title": "Multi-Vehicle Collision on Bangalore-Mysuru Expressway",
            "description": "High-speed collision involving two cars and an intercity passenger bus near Siddalingapura exit. Significant structural entrapment.",
            "location": "Siddalingapura Toll Plaza Approach, Mysuru",
            "lat": 12.3520,
            "lon": 76.6580,
            "priority": "High",
            "status": "Team Dispatched",
            "affected": 6,
            "help": "Advanced Life Support Ambulances & Extrication Squad",
            "contact_name": "NHAI Highway Patrol",
            "contact_phone": "+91 94480 33221",
            "is_disaster": False,
        },
        {
            "code": "CARE-2026-103",
            "category": "Medical",
            "title": "Acute Anaphylaxis and Cardiac Distress",
            "description": "38-year-old female experiencing severe airway compromise, stridor, and cyanosis following unknown insect sting in Chamundi Hill temple premises.",
            "location": "Chamundi Hill View Point Approach, Mysuru",
            "lat": 12.2740,
            "lon": 76.6710,
            "priority": "Critical",
            "status": "Assistance Search",
            "affected": 1,
            "help": "ALS Ambulance with Epinephrine & Intubation Protocol",
            "contact_name": "Temple Administration Helpdesk",
            "contact_phone": "+91 821 259 8812",
            "is_disaster": False,
        },
        {
            "code": "CARE-2026-104",
            "category": "Fire",
            "title": "Commercial Kitchen LPG Pipeline Flash Fire",
            "description": "Flash fire in central commercial restaurant basement kitchen on D. Devaraj Urs Road. Two cooks with 2nd-degree thermal burns; fire extinguished by automated suppression.",
            "location": "D. Devaraj Urs Road, Shivarampet, Mysuru",
            "lat": 12.3085,
            "lon": 76.6455,
            "priority": "Medium",
            "status": "Verified",
            "affected": 2,
            "help": "Burn Trauma Transport & Fire Inspection",
            "contact_name": "Restaurant Floor Manager",
            "contact_phone": "+91 98860 44556",
            "is_disaster": False,
        },
        {
            "code": "CARE-2026-105",
            "category": "Safety / Other",
            "title": "Elderly Fall with Suspected Hip Fracture",
            "description": "82-year-old male slipped in residential bathroom. Conscious and alert, severe pain on palpation of left femur.",
            "location": "14th Main, Saraswathipuram, Mysuru",
            "lat": 12.3010,
            "lon": 76.6290,
            "priority": "Low",
            "status": "Resolved",
            "affected": 1,
            "help": "BLS Ambulance with Scoop Stretcher",
            "contact_name": "Daughter",
            "contact_phone": "+91 94490 88990",
            "is_disaster": False,
        },
    ]

    inc_map = {}
    for idata in incidents_data:
        inc = db.query(Incident).filter(Incident.incident_code == idata["code"]).first()
        if not inc:
            inc = Incident(
                incident_code=idata["code"],
                tracking_token=str(uuid.uuid4()),
                category=idata["category"],
                title=idata["title"],
                description=idata["description"],
                location_name=idata["location"],
                latitude=idata["lat"],
                longitude=idata["lon"],
                geom=make_point_wkt(idata["lat"], idata["lon"]),
                priority=idata["priority"],
                status=idata["status"],
                affected_people=idata["affected"],
                help_required=idata["help"],
                contact_name=idata["contact_name"],
                contact_phone=idata["contact_phone"],
                user_id=user_map["citizen@careon.org"].id,
                is_verified=True,
                is_disaster=idata.get("is_disaster", False),
                disaster_details=idata.get("disaster_details"),
                created_at=now - timedelta(minutes=45),
            )
            db.add(inc)
            db.flush()
        else:
            inc.status = idata["status"]
            inc.priority = idata["priority"]
        inc_map[idata["code"]] = inc

    inc_disaster = inc_map["CARE-2026-101"]
    inc_collision = inc_map["CARE-2026-102"]

    # Active Assignment on AMB-01 for CARE-2026-101
    asgn_1 = db.query(Assignment).filter(Assignment.incident_id == inc_disaster.id, Assignment.resource_id == res_map["AMB-01"].id).first()
    if not asgn_1:
        asgn_1 = Assignment(
            incident_id=inc_disaster.id,
            resource_id=res_map["AMB-01"].id,
            status="Accepted",
            assigned_at=now - timedelta(minutes=25),
            acknowledged_at=now - timedelta(minutes=23),
            notes="Assigned as primary triage and transport unit for severe chemical burn casualties.",
        )
        db.add(asgn_1)
        db.flush()

    # ==========================================================================
    # 6. M7 INCOMING PATIENT REQUESTS (Pre-arrival to KR Hospital)
    # ==========================================================================
    inc_req = db.query(IncomingPatientRequest).filter(IncomingPatientRequest.incident_id == inc_disaster.id).first()
    if not inc_req:
        inc_req = IncomingPatientRequest(
            request_token=str(uuid.uuid4()),
            facility_id=fac_kr.id,
            incident_id=inc_disaster.id,
            assignment_id=asgn_1.id,
            dispatcher_id=user_map["dispatcher@careon.org"].id,
            status="accepted",
            emergency_severity="Critical",
            patient_condition_summary="32M, blast trauma & chemical vapor inhalation; GCS 12, intubated, 25% partial thickness burns",
            eta_minutes=8.5,
            eta_source="live_gps_telemetry",
            acknowledgement_deadline=now + timedelta(minutes=15),
            hospital_response_user_id=user_map["hospital@careon.org"].id,
            hospital_response_reason="Trauma Bay 1 and Burn ICU Bay prepped with ventilator and specialized irrigation fluids.",
            created_at=now - timedelta(minutes=15),
            updated_at=now - timedelta(minutes=10),
        )
        db.add(inc_req)
        db.flush()

    # ==========================================================================
    # 7. M8 CLINICAL ENCOUNTER & DIGITAL HANDOVER RECORD
    # ==========================================================================
    pat = db.query(Patient).filter(Patient.patient_identifier == "PAT-MY-2026-001").first()
    if not pat:
        pat = Patient(
            patient_identifier="PAT-MY-2026-001",
            full_name="Siddharth S. Varma",
            identity_status="verified",
            date_of_birth=date(1992, 7, 14),
            estimated_age=34,
            gender="male",
            contact_phone="+91 98450 99881",
            emergency_contact_name="Deepa Varma (Spouse)",
            emergency_contact_phone="+91 98450 99882",
            blood_group="O+",
            known_allergies="Penicillin",
            known_medical_conditions="Mild bronchial asthma",
            created_at=now,
        )
        db.add(pat)
        db.flush()

    enc = db.query(EmergencyEncounter).filter(EmergencyEncounter.encounter_code == "ENC-2026-101-01").first()
    if not enc:
        enc = EmergencyEncounter(
            encounter_code="ENC-2026-101-01",
            patient_id=pat.id,
            incident_id=inc_disaster.id,
            assignment_id=asgn_1.id,
            assigned_responder_id=user_map["responder@careon.org"].id,
            receiving_facility_id=fac_kr.id,
            status="in_transport",
            chief_complaint="Severe chemical burn injury, respiratory distress following industrial explosion",
            initial_acuity="Critical",
            started_at=now - timedelta(minutes=20),
            created_at=now - timedelta(minutes=20),
        )
        db.add(enc)
        db.flush()

    handover = db.query(DigitalHandoverRecord).filter(DigitalHandoverRecord.encounter_id == enc.id).first()
    if not handover:
        handover = DigitalHandoverRecord(
            handover_token=str(uuid.uuid4()),
            encounter_id=enc.id,
            facility_id=fac_kr.id,
            version=1,
            status="ready_for_handover",
            sending_responder_id=user_map["responder@careon.org"].id,
            submitted_at=now - timedelta(minutes=5),
            receiving_department="Emergency Resuscitation Unit",
            clinical_summary_json=json.dumps({
                "vitals": {"hr": 128, "bp": "95/60", "spo2": 92, "rr": 26, "temp": 37.1},
                "triage_category": "Red - Immediate",
                "interventions": [
                    "High flow O2 via non-rebreather mask (15L/min)",
                    "18G IV peripheral access left antecubital fossa",
                    "Normal Saline 1000ml infusion running",
                    "Copious sterile water irrigation of facial and upper thorax chemical burns",
                    "Morphine Sulfate 5mg IV titrated for severe pain",
                ],
                "glasgow_coma_scale": {"eye": 4, "verbal": 4, "motor": 5, "total": 13},
                "outstanding_clinical_concerns": "Risk of progressive airway edema from chemical vapor inhalation. Prepare immediate rapid sequence intubation (RSI) on arrival.",
            }),
            outstanding_clinical_concerns="Airway inhalation edema risk; monitor for laryngeal stridor.",
            is_final=False,
            created_at=now - timedelta(minutes=5),
            updated_at=now - timedelta(minutes=5),
        )
        db.add(handover)
        db.flush()

    # ==========================================================================
    # 8. M10 PREDICTIVE FORECASTS & POSITIONING RECOMMENDATIONS
    # ==========================================================================
    zones = ["Mysuru Central", "Hebbal Industrial", "Kuvempunagar", "Vijayanagar"]
    for z in zones:
        fc = db.query(DemandForecastRecord).filter(DemandForecastRecord.zone_or_region == z).first()
        if not fc:
            fc = DemandForecastRecord(
                forecast_uuid=str(uuid.uuid4()),
                organization_id=org_ems.id,
                zone_or_region=z,
                horizon_hours=4,
                start_time=now,
                end_time=now + timedelta(hours=4),
                expected_incidents=3.8 if "Central" in z else 2.1,
                confidence_lower=2.0 if "Central" in z else 1.0,
                confidence_upper=6.2 if "Central" in z else 4.0,
                confidence_level="HIGH",
                model_id="poisson_glm_v1",
                model_version="1.0.0",
                contributing_factors_json=json.dumps({"hour": now.hour, "day_of_week": now.weekday(), "baseline_density": 1.4}),
                created_at=now - timedelta(minutes=30),
            )
            db.add(fc)

    rec = db.query(PositioningRecommendation).filter(PositioningRecommendation.target_area == "Hebbal Industrial").first()
    if not rec:
        rec = PositioningRecommendation(
            recommendation_uuid=str(uuid.uuid4()),
            organization_id=org_ems.id,
            target_area="Hebbal Industrial",
            target_latitude=12.3610,
            target_longitude=76.6025,
            resource_id=res_map["AMB-02"].id,
            current_latitude=res_map["AMB-02"].latitude,
            current_longitude=res_map["AMB-02"].longitude,
            proposed_latitude=12.3580,
            proposed_longitude=76.6080,
            proposed_staging_name="Hebbal Ring Road Staging Depot",
            status="PENDING_REVIEW",
            expected_coverage_improvement=28.5,
            estimated_travel_time_minutes=8.0,
            confidence_level="HIGH",
            explanation="High forecasted industrial demand & active chemical incident coverage gap in Hebbal.",
            created_at=now - timedelta(minutes=15),
            expires_at=now + timedelta(hours=3),
        )
        db.add(rec)

    # ==========================================================================
    # 9. M11 UNIFIED INCIDENT COMMAND STRUCTURE (ICS)
    # ==========================================================================
    cmd_struct = db.query(IncidentCommandStructure).filter(IncidentCommandStructure.incident_id == inc_disaster.id).first()
    if not cmd_struct:
        cmd_struct = IncidentCommandStructure(
            command_uuid=str(uuid.uuid4()),
            incident_id=inc_disaster.id,
            structure_type="UNIFIED_COMMAND",
            lead_agency_id=org_ems.id,
            is_active=True,
            activation_notes="Unified Command established across EMS, Fire, and Police for mass casualty chemical fire incident.",
            created_at=now - timedelta(minutes=40),
            updated_at=now - timedelta(minutes=10),
        )
        db.add(cmd_struct)
        db.flush()

        # ICS Assignments
        cmd_assignments = [
            (cmd_struct.id, "INCIDENT_COMMANDER", user_map["dispatcher@careon.org"].id, org_ems.id, "UNIFIED-CMD-1", "+91 821 244 5566"),
            (cmd_struct.id, "OPERATIONS_CHIEF", user_map["fire@careon.org"].id, org_fire.id, "FIRE-OPS-1", "+91 821 244 5533"),
            (cmd_struct.id, "SAFETY_OFFICER", user_map["police@careon.org"].id, org_police.id, "SAFETY-CHIEF-1", "+91 821 244 5522"),
        ]
        for c_id, role_n, u_id, o_id, callsign, c_num in cmd_assignments:
            asgn = IncidentCommandAssignment(
                assignment_uuid=str(uuid.uuid4()),
                command_structure_id=c_id,
                command_role=role_n,
                assigned_user_id=u_id,
                assigned_organization_id=o_id,
                is_active=True,
                radio_callsign=callsign,
                contact_number=c_num,
                assigned_at=now - timedelta(minutes=35),
            )
            db.add(asgn)

        # History
        hist = IncidentCommandHistory(
            history_uuid=str(uuid.uuid4()),
            command_structure_id=cmd_struct.id,
            event_type="ESTABLISHED",
            previous_commander_id=None,
            new_commander_id=user_map["dispatcher@careon.org"].id,
            authorizing_user_id=user_map["superadmin@careon.org"].id,
            briefing_summary="Unified Command initiated with EMS lead, Fire tactical operations, and Police cordon security.",
            reason="Mass casualty chemical emergency classification",
            created_at=now - timedelta(minutes=40),
        )
        db.add(hist)

    # ==========================================================================
    # 10. M11 INTER-AGENCY COLLABORATIONS & 10 SCOPES
    # ==========================================================================
    all_scopes = [
        "INCIDENT_SUMMARY",
        "OPERATIONAL_LOCATION",
        "HAZARD_INFORMATION",
        "RESOURCE_STATUS",
        "AGENCY_TASKS",
        "CASUALTY_COUNTS",
        "HOSPITAL_DESTINATION",
        "CLINICAL_HANDOVER_REFERENCE",
        "COMMAND_INFORMATION",
        "OPERATIONAL_DOCUMENTS",
    ]

    collab_partners = [
        (org_fire, "Fire suppression, chemical vapor scrubbing, and structural search", all_scopes),
        (org_police, "500m hazard perimeter cordon and green-light ambulance corridor", all_scopes),
        (org_kr, "Receiving burn trauma hospital coordination & capacity reservation", all_scopes),
    ]

    for partner_org, purpose, scopes in collab_partners:
        collab = db.query(IncidentAgencyCollaboration).filter(
            IncidentAgencyCollaboration.incident_id == inc_disaster.id,
            IncidentAgencyCollaboration.organization_id == partner_org.id,
        ).first()
        if not collab:
            collab = IncidentAgencyCollaboration(
                collaboration_uuid=str(uuid.uuid4()),
                incident_id=inc_disaster.id,
                organization_id=partner_org.id,
                collaboration_status="ACCEPTED",
                inviting_organization_id=org_ems.id,
                inviting_user_id=user_map["dispatcher@careon.org"].id,
                accepted_by_user_id=user_map["superadmin@careon.org"].id,
                accepted_at=now - timedelta(minutes=35),
                collaboration_purpose=purpose,
                expires_at=now + timedelta(hours=24),
                created_at=now - timedelta(minutes=38),
                updated_at=now - timedelta(minutes=35),
            )
            db.add(collab)
            db.flush()

            for sc in scopes:
                grant = IncidentInformationGrant(
                    grant_uuid=str(uuid.uuid4()),
                    collaboration_id=collab.id,
                    scope=sc,
                    is_granted=True,
                    granted_by_user_id=user_map["dispatcher@careon.org"].id,
                    granted_at=now - timedelta(minutes=35),
                )
                db.add(grant)

    # ==========================================================================
    # 11. M11 OPERATIONAL TASKS & MUTUAL AID RESOURCE REQUESTS
    # ==========================================================================
    # Operational Tasks
    tasks_data = [
        (org_fire.id, "Deploy Chemical Vapor Water Curtains", "Direct deluge cannons downwind to suppress volatile toxic vapor cloud.", "CRITICAL", "IN_PROGRESS", "Fire Tender 01"),
        (org_police.id, "Establish 500m Outer Evacuation Cordon", "Block civilian traffic along Ring Road South and redirect toward Vijayanagar.", "HIGH", "ACKNOWLEDGED", "Patrol Unit 01"),
    ]
    for assigned_org_id, title, desc, prio, st, unit in tasks_data:
        t = db.query(AgencyOperationalTask).filter(AgencyOperationalTask.title == title).first()
        if not t:
            t = AgencyOperationalTask(
                task_uuid=str(uuid.uuid4()),
                incident_id=inc_disaster.id,
                command_structure_id=cmd_struct.id,
                assigning_organization_id=org_ems.id,
                assigned_organization_id=assigned_org_id,
                created_by_user_id=user_map["dispatcher@careon.org"].id,
                title=title,
                description=desc,
                priority=prio,
                status=st,
                assigned_unit_name=unit,
                deadline=now + timedelta(hours=2),
                created_at=now - timedelta(minutes=30),
                updated_at=now - timedelta(minutes=15),
            )
            db.add(t)

    # Mutual Aid Resource Requests
    requests_data = [
        (org_fire.id, "HAZMAT_UNIT", 2, "EMERGENCY", "ACCEPTED", "High casualty count with chemical burns requires immediate mass decontamination before transport.", "Sector 4 North Gate Staging", 12.3615, 76.6030, ["HZ-01", "HZ-02"]),
        (org_police.id, "POLICE_PATROL", 3, "URGENT", "ACCEPTED", "Green corridor route clearing from Hebbal to KR Hospital.", "Outer Ring Road Staging", 12.3480, 76.6320, ["PATROL-3", "PATROL-5"]),
    ]
    for req_org_id, r_type, qty, urg, st, just, s_name, s_lat, s_lon, assigned_units in requests_data:
        req = db.query(AgencyResourceRequest).filter(AgencyResourceRequest.operational_justification == just).first()
        if not req:
            req = AgencyResourceRequest(
                request_uuid=str(uuid.uuid4()),
                incident_id=inc_disaster.id,
                requesting_organization_id=org_ems.id,
                requested_organization_id=req_org_id,
                requested_by_user_id=user_map["dispatcher@careon.org"].id,
                resource_type=r_type,
                quantity=qty,
                urgency=urg,
                status=st,
                operational_justification=just,
                staging_location_name=s_name,
                staging_latitude=s_lat,
                staging_longitude=s_lon,
                decision_by_user_id=user_map["superadmin@careon.org"].id,
                decision_at=now - timedelta(minutes=25),
                decision_notes=f"Accepted and units {assigned_units} mobilized.",
                assigned_resource_ids_json=json.dumps(assigned_units),
                expires_at=now + timedelta(hours=6),
                created_at=now - timedelta(minutes=30),
                updated_at=now - timedelta(minutes=25),
            )
            db.add(req)

    # ==========================================================================
    # 12. M11 POSTGIS OPERATIONAL ZONES
    # ==========================================================================
    zones_data = [
        ("HOT_ZONE", "Chemical Tanker Blast & Vapor Zone", "Immediate hazardous area; flammable & toxic atmosphere.", 12.3610, 76.6025, 200.0, "CHEMICAL_TOXIC_VAPOR", "Authorized Level A Hazmat Entry Team Only"),
        ("WARM_ZONE", "Mass Decontamination & Triage Zone", "Active decontamination corridor and primary field stabilization.", 12.3590, 76.6045, 350.0, "DECONTAMINATION_AREA", "EMS Triage Personnel & Decontamination Staff"),
        ("COLD_ZONE", "Unified Incident Command & Staging", "Safe assembly area, ambulance staging, and mobile command post.", 12.3560, 76.6080, 500.0, None, "All Authorized Responding Units"),
        ("EVACUATION_ZONE", "Downwind Residential Sector 1", "Mandatory civilian evacuation due to toxic smoke dispersion.", 12.3650, 76.6000, 1000.0, "TOXIC_SMOKE_PLUME", "Civilian Ingress Prohibited; Evacuation in Progress"),
    ]
    for z_type, z_name, z_desc, z_lat, z_lon, z_rad, z_haz, z_restr in zones_data:
        z = db.query(IncidentOperationalZone).filter(IncidentOperationalZone.name == z_name).first()
        if not z:
            z = IncidentOperationalZone(
                zone_uuid=str(uuid.uuid4()),
                incident_id=inc_disaster.id,
                created_by_organization_id=org_ems.id,
                created_by_user_id=user_map["dispatcher@careon.org"].id,
                zone_type=z_type,
                name=z_name,
                description=z_desc,
                center_latitude=z_lat,
                center_longitude=z_lon,
                radius_meters=z_rad,
                hazard_type=z_haz,
                access_restrictions=z_restr,
                is_active=True,
                created_at=now - timedelta(minutes=25),
                updated_at=now - timedelta(minutes=25),
            )
            db.add(z)

    # Commit all changes cleanly
    db.commit()
    print(">>> All demonstration and development records seeded successfully!")


if __name__ == "__main__":
    db = next(get_db())
    try:
        seed_all_demo_data(db)
    finally:
        db.close()
