#!/usr/bin/env python3
"""
Prepares comprehensive operational demo data for Responder Web visual verification.
- 1 Active Mission (en_route_incident)
- 1 Pending Mission (assigned in Inbox)
- 2 Completed Past Missions (completed in History)
"""

import psycopg
from datetime import datetime, timezone, timedelta

def main():
    conn = psycopg.connect("postgresql:///careon")
    cur = conn.cursor()

    now = datetime.now(timezone.utc)

    # 1. Ensure responder user (id 112) is linked to resource 2 (AMB-02)
    cur.execute("""
        UPDATE resources 
        SET assigned_user_id = 112, 
            status = 'Assigned',
            latitude = 12.9716,
            longitude = 77.5946,
            location_name = 'Indiranagar EMS Base, Bengaluru'
        WHERE id = 2;
    """)

    # 2. Create Active Mission Incident & Assignment
    cur.execute("""
        INSERT INTO incidents (
            incident_code, title, user_id, category, description, location_name,
            latitude, longitude, status, priority, affected_people, help_required,
            contact_name, contact_phone, created_at, updated_at
        ) VALUES (
            'CARE-ACT-501', 'Suspected Acute Myocardial Infarction', 110, 'Medical',
            'Severe chest pain, crushing sensation radiating to left jaw, diaphoresis, dyspnea.',
            '45 Lavelle Road, Shanthala Nagar, Bengaluru',
            12.9698, 77.5982, 'Team Dispatched', 'P1', 1, 'Ambulance',
            'Vikram Seth', '+919876543210',
            %s, %s
        ) RETURNING id;
    """, (now - timedelta(minutes=14), now - timedelta(minutes=14)))
    act_inc_id = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO assignments (
            incident_id, resource_id, assigned_by, status, acknowledgement_status, notes, assigned_at
        ) VALUES (
            %s, 2, 'M2 Dispatcher', 'en_route_incident', 'Acknowledged',
            'Priority 1 dispatch. Suspected acute myocardial infarction.',
            %s
        ) RETURNING id;
    """, (act_inc_id, now - timedelta(minutes=14)))
    act_assign_id = cur.fetchone()[0]

    # Clinical encounter for active incident
    cur.execute("""
        INSERT INTO emergency_encounters (
            encounter_code, patient_id, incident_id, assignment_id, chief_complaint, initial_acuity, status, started_at, created_at, updated_at
        ) VALUES (
            'ENC-ACT-501', 2, %s, %s, 'Acute crushing chest pain, diaphoresis', 'Critical', 'In Progress', %s, %s, %s
        ) RETURNING id;
    """, (act_inc_id, act_assign_id, now - timedelta(minutes=10), now - timedelta(minutes=10), now - timedelta(minutes=10)))
    enc_id = cur.fetchone()[0]

    # Vitals
    cur.execute("""
        INSERT INTO vital_sign_observations (
            encounter_id, heart_rate, systolic_bp, diastolic_bp, respiratory_rate,
            oxygen_saturation, body_temperature, gcs_total, measurement_source, data_quality, observed_at, created_at
        ) VALUES (
            %s, 94, 138, 88, 18, 97.0, 36.7, 15, 'Manual', 'Valid', %s, %s
        );
    """, (enc_id, now - timedelta(minutes=8), now - timedelta(minutes=8)))

    # 3. Create Pending Mission for Inbox
    cur.execute("""
        INSERT INTO incidents (
            incident_code, title, user_id, category, description, location_name,
            latitude, longitude, status, priority, affected_people, help_required,
            contact_name, contact_phone, created_at, updated_at
        ) VALUES (
            'CARE-INB-702', 'Road Traffic Accident - Lower Limb Trauma', 110, 'Road accident',
            'Two-wheeler collision with median. Conscious but bleeding from lower limb.',
            'Near Trinity Circle, MG Road, Bengaluru',
            12.9725, 77.6180, 'Reported', 'P1', 1, 'Ambulance',
            'Deepak Verma', '+919811223344',
            %s, %s
        ) RETURNING id;
    """, (now - timedelta(minutes=3), now - timedelta(minutes=3)))
    inb_inc_id = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO assignments (
            incident_id, resource_id, assigned_by, status, acknowledgement_status, notes, assigned_at
        ) VALUES (
            %s, 2, 'M2 Dispatcher', 'assigned', 'Pending',
            'Standby queue allocation. Rapid trauma deployment.',
            %s
        );
    """, (inb_inc_id, now - timedelta(minutes=3)))

    # 4. Create Completed History Missions
    for i, (code, title, cat, desc, mins_ago) in enumerate([
        ('CARE-HIST-301', 'Asthma Exacerbation', 'Medical', 'Asthmatic respiratory distress treated with nebulization', 180),
        ('CARE-HIST-302', 'Slip & Fall Injury', 'Rescue', 'Pedestrian slip and fall with suspected wrist fracture', 360)
    ]):
        cur.execute("""
            INSERT INTO incidents (
                incident_code, title, user_id, category, description, location_name,
                latitude, longitude, status, priority, affected_people, help_required,
                contact_name, contact_phone, created_at, updated_at
            ) VALUES (
                %s, %s, 110, %s, %s, 'Koramangala 5th Block, Bengaluru',
                12.9352, 77.6245, 'Resolved', 'P2', 1, 'Ambulance',
                'Pooja Sharma', '+919988776655',
                %s, %s
            ) RETURNING id;
        """, (code, title, cat, desc, now - timedelta(minutes=mins_ago), now - timedelta(minutes=mins_ago - 40)))
        h_inc_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO assignments (
                incident_id, resource_id, assigned_by, status, acknowledgement_status, notes, assigned_at, released_at
            ) VALUES (
                %s, 2, 'M2 Dispatcher', 'completed', 'Acknowledged', 'Mission successfully completed.',
                %s, %s
            );
        """, (h_inc_id, now - timedelta(minutes=mins_ago), now - timedelta(minutes=mins_ago - 40)))

    conn.commit()
    conn.close()
    print("Demo responder data seeded successfully: 1 active mission (en_route_incident), 1 pending inbox (assigned), 2 completed history.")

if __name__ == '__main__':
    main()
