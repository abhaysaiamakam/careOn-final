#!/usr/bin/env python3
"""
CareOn M14 — Dedicated Test Database Seeder (careon_test ONLY).
Fails closed immediately if connected to any database other than careon_test.
"""

import sys
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from app.auth import hash_password

TEST_DB_URL = "postgresql+psycopg:///careon_test"

def seed_test_database():
    engine = create_engine(TEST_DB_URL)
    with engine.connect() as conn:
        current_db = conn.execute(text("SELECT current_database()")).scalar()
        print(f"[PRE-FLIGHT] Connected database: {current_db}")
        if current_db != "careon_test":
            raise RuntimeError(f"FATAL: Target database is '{current_db}', NOT 'careon_test'! Aborting immediately to prevent contamination.")

        # 1. Reset standard test passwords
        users_passwords = [
            ("m2_citizen@careon.org", "citizen123"),
            ("m2_dispatcher@careon.org", "dispatcher123"),
            ("m2_responder@careon.org", "responder123"),
            ("m2_hospital@careon.org", "hospital123"),
            ("admin@careon.org", "admin123"),
        ]
        for email, pwd in users_passwords:
            hp = hash_password(pwd)
            conn.execute(
                text("UPDATE users SET hashed_password = :hp WHERE email = :email"),
                {"hp": hp, "email": email}
            )
        print("[AUTH] Verified and updated test credentials for test accounts.")

        # 2. Check and seed hospital organization
        org_id = conn.execute(text("SELECT id FROM organizations WHERE name = 'Victoria Regional Hospital'")).scalar()
        if not org_id:
            res = conn.execute(
                text("""
                    INSERT INTO organizations (name, org_type, description, is_active, is_verified, created_at, updated_at)
                    VALUES ('Victoria Regional Hospital', 'hospital', 'Primary acute regional trauma network', true, true, NOW(), NOW())
                    RETURNING id
                """)
            )
            org_id = res.scalar()
            print(f"[ORG] Created hospital organization ID: {org_id}")
        else:
            print(f"[ORG] Hospital organization already exists with ID: {org_id}")

        # 3. Add m2_hospital user as organization member
        hospital_user_id = conn.execute(text("SELECT id FROM users WHERE email = 'm2_hospital@careon.org'")).scalar()
        if hospital_user_id:
            membership = conn.execute(
                text("SELECT id FROM organization_memberships WHERE organization_id = :org_id AND user_id = :user_id"),
                {"org_id": org_id, "user_id": hospital_user_id}
            ).fetchone()
            if not membership:
                conn.execute(
                    text("""
                        INSERT INTO organization_memberships (organization_id, user_id, membership_role, status, joined_at)
                        VALUES (:org_id, :user_id, 'member', 'active', NOW())
                    """),
                    {"org_id": org_id, "user_id": hospital_user_id}
                )
                print(f"[MEMBERSHIP] Added user {hospital_user_id} to organization {org_id}")

        # 4. Check and seed hospital facility (VRH-TRAUMA-01)
        fac = conn.execute(
            text("SELECT id FROM hospital_facilities WHERE facility_code = 'VRH-TRAUMA-01'")
        ).fetchone()
        if not fac:
            fac_id = conn.execute(
                text("""
                    INSERT INTO hospital_facilities (
                        organization_id, facility_code, name, facility_type, location_name,
                        latitude, longitude, geom, trauma_level, capabilities,
                        specialist_services, medical_equipment, ambulance_bays,
                        operating_status, emergency_phone, is_active, last_verified_at, created_at
                    ) VALUES (
                        :org_id, 'VRH-TRAUMA-01', 'Victoria Regional Trauma Centre', 'general_acute',
                        'Victoria Hospital Complex, Outer Ring Rd, Mysuru',
                        12.3052, 76.6552, ST_SetSRID(ST_MakePoint(76.6552, 12.3052), 4326),
                        'Level 1', 'emergency,trauma,icu,ct_scan,blood_bank,ambulance_bay',
                        'trauma_surgeon,cardiologist,neurologist,anesthesiologist',
                        'ct_scanner,mri,ventilators,defibrillators,dialysis', 6,
                        'open', '+91 80 2222 1111', true, NOW(), NOW()
                    ) RETURNING id
                """),
                {"org_id": org_id}
            ).scalar()
            print(f"[FACILITY] Created designated facility ID: {fac_id} (VRH-TRAUMA-01)")
        else:
            fac_id = fac[0]
            print(f"[FACILITY] Facility VRH-TRAUMA-01 already exists with ID: {fac_id}")

        # 5. Seed capacity for facility
        cap_count = conn.execute(
            text("SELECT count(*) FROM hospital_capacities WHERE facility_id = :fac_id"),
            {"fac_id": fac_id}
        ).scalar()
        if cap_count == 0:
            categories = [
                ("er_beds", 20, 5),       # available: 15
                ("trauma_bays", 6, 2),    # available: 4
                ("icu_beds", 10, 4),      # available: 6
                ("general_beds", 50, 18), # available: 32
            ]
            for cat, total, occ in categories:
                conn.execute(
                    text("""
                        INSERT INTO hospital_capacities (
                            facility_id, category, total_capacity, occupied_capacity,
                            reserved_capacity, unavailable_capacity, reporting_source,
                            verification_status, last_updated
                        ) VALUES (
                            :fac_id, :cat, :total, :occ, 0, 0, 'hospital_staff', 'verified', NOW()
                        )
                    """),
                    {"fac_id": fac_id, "cat": cat, "total": total, "occ": occ}
                )
            print("[CAPACITY] Seeded verified baseline capacity records.")

        # 6. Assign responder unit AMB-01 to m2_responder & clear demo assignment
        conn.execute(text("UPDATE assignments SET status = 'Completed' WHERE id = 1"))
        responder_user_id = conn.execute(text("SELECT id FROM users WHERE email = 'm2_responder@careon.org'")).scalar()
        if responder_user_id:
            conn.execute(
                text("""
                    UPDATE resources
                    SET assigned_user_id = :uid,
                        status = 'Available',
                        capabilities = 'ALS,BLS,patient_transport,trauma_care,oxygen_support,first_aid,critical_care,extrication',
                        equipment = 'ventilator,defibrillator,oxygen,monitor,als_kit,first_aid_kit,extrication_tools'
                    WHERE resource_code = 'AMB-01'
                """),
                {"uid": responder_user_id}
            )
            print(f"[RESOURCE] Assigned AMB-01 to responder user {responder_user_id} with available status.")

        conn.commit()
        print("[SUCCESS] careon_test seeding completed successfully!")

if __name__ == "__main__":
    seed_test_database()
