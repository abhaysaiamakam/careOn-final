"""
CareOn Milestone 10 — Operational Scenario Simulation Engine.

Enables dispatch and operational planning teams to simulate "what-if" scenarios:
- BASELINE_NORMAL
- REGIONAL_DEMAND_SURGE
- MASS_CASUALTY_EVENT
- RESOURCE_SHORTAGE
- HOSPITAL_DIVERSION

Strict Isolation Guarantee:
- Simulations execute entirely in-memory with analytical models.
- NEVER mutates live missions, live assignments, hospital reservations, or clinical data.
"""

import uuid
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import (
    Resource,
    HospitalFacility,
    HospitalCapacity,
    ScenarioSimulationRecord,
    User,
    utc_now,
)
from app.schemas import (
    ScenarioSimulationRequest,
    ScenarioSimulationResponse,
)
from app.intelligence.coverage_engine import (
    get_available_operational_ambulances,
    DEFAULT_OPERATIONAL_ZONES,
)

logger = logging.getLogger("careon.intelligence.simulator")


def simulate_operational_scenario(
    db: Session,
    request: ScenarioSimulationRequest,
    user: Optional[User] = None,
    organization_id: Optional[int] = None,
) -> ScenarioSimulationResponse:
    """
    Run an isolated scenario simulation to project the impact on response times,
    coverage gaps, hospital readiness, and resource bottlenecks.
    """
    now = utc_now()
    scenario_type = request.scenario_type.upper()
    scenario_name = request.scenario_name or f"Simulated {scenario_type}"

    # 1. Fetch current live fleet snapshot (READ ONLY)
    available, occupied, stale = get_available_operational_ambulances(db, organization_id)
    total_operational = len(available) + len(occupied) + len(stale)

    # Clone available list into simulation scope
    sim_available = list(available)

    # 2. Base demand across zones
    baseline_demand = sum(z.get("baseline_demand", 2.0) for z in DEFAULT_OPERATIONAL_ZONES)
    simulated_demand = baseline_demand
    response_time_impact = 0.0
    coverage_gaps: List[str] = []
    bottleneck_alerts: List[str] = []
    recommendations: List[Dict[str, Any]] = []

    # Apply scenario dynamics
    if scenario_type == "BASELINE_NORMAL":
        simulated_demand = baseline_demand
        response_time_impact = 0.0

    elif scenario_type == "REGIONAL_DEMAND_SURGE":
        surge = request.surge_factor or 2.0
        target_z = request.target_zone or "Central Mysuru"
        simulated_demand = baseline_demand + (2.5 * surge)
        response_time_impact = round(3.5 * surge, 1)
        coverage_gaps.append(f"{target_z} (Demand surged by {surge*100:.0f}%)")
        bottleneck_alerts.append(
            f"Expected surge in {target_z} will overwhelm local available buffer within 45 minutes."
        )
        recommendations.append({
            "action": "STAGE_AMBULANCES_ADVANCE",
            "zone": target_z,
            "recommended_units": max(1, int(surge)),
        })

    elif scenario_type == "MASS_CASUALTY_EVENT":
        surge = request.surge_factor or 3.5
        simulated_demand = baseline_demand + 15.0
        response_time_impact = 14.5
        target_z = request.target_zone or "Hebbal Industrial Suburb"
        coverage_gaps.extend([target_z, "Central Mysuru"])
        bottleneck_alerts.append(
            f"Mass-casualty simulation ({target_z}): Immediate requirement for 6 ALS ambulances and 2 trauma teams."
        )
        bottleneck_alerts.append(
            "Trauma bay saturation threshold reached at primary receiving hospital."
        )
        recommendations.append({
            "action": "ACTIVATE_MUTUAL_AID",
            "details": "Trigger regional mutual-aid agreement and notify secondary trauma centres.",
        })

    elif scenario_type == "RESOURCE_SHORTAGE":
        # Simulate removal of specified resources or 50% fleet reduction
        if request.unavailable_resource_ids:
            sim_available = [a for a in sim_available if a["id"] not in request.unavailable_resource_ids]
        else:
            sim_available = sim_available[:max(1, len(sim_available) // 2)]
        
        lost_units = len(available) - len(sim_available)
        response_time_impact = round(lost_units * 4.2, 1)
        coverage_gaps.extend(["Kuvempunagar", "Chamundi Foothills"])
        bottleneck_alerts.append(
            f"Fleet shortage: {lost_units} ambulances taken out of service. Average response time increases by {response_time_impact} mins."
        )
        recommendations.append({
            "action": "CONSERVE_FLEET_ALS",
            "details": "Reserve ALS ambulances strictly for Priority 1 / Critical incidents; dispatch BLS for low priority.",
        })

    elif scenario_type == "HOSPITAL_DIVERSION":
        # Simulate diversion of receiving hospitals
        diverted_ids = request.diverted_hospital_ids or [1]
        response_time_impact = 9.8  # Diverted transport adds travel time
        bottleneck_alerts.append(
            f"Hospital Facility #{diverted_ids[0]} on DIVERSION: Emergency admissions rerouted to alternative facilities (+10-15 min transport time)."
        )
        recommendations.append({
            "action": "REROUTE_TRANSPORT_CORRIDOR",
            "details": "Pre-notify secondary hospital ER and stage standby ambulance along northern transport bypass.",
        })

    else:
        # Default scenario
        simulated_demand = baseline_demand

    sim_uuid = str(uuid.uuid4())
    record = ScenarioSimulationRecord(
        simulation_uuid=sim_uuid,
        organization_id=organization_id,
        scenario_type=scenario_type,
        scenario_name=scenario_name,
        parameters_json=json.dumps({
            "surge_factor": request.surge_factor,
            "target_zone": request.target_zone,
            "unavailable_resource_ids": request.unavailable_resource_ids,
            "diverted_hospital_ids": request.diverted_hospital_ids,
        }),
        results_summary_json=json.dumps({
            "baseline_demand": baseline_demand,
            "simulated_demand": simulated_demand,
            "response_time_impact_minutes": response_time_impact,
        }),
        coverage_impact_json=json.dumps(coverage_gaps),
        bottleneck_alerts_json=json.dumps(bottleneck_alerts),
        simulated_by_user_id=user.id if user else None,
        created_at=now,
    )
    db.add(record)
    db.commit()

    return ScenarioSimulationResponse(
        simulation_uuid=sim_uuid,
        scenario_type=scenario_type,
        scenario_name=scenario_name,
        baseline_expected_demand=round(baseline_demand, 2),
        simulated_demand=round(simulated_demand, 2),
        operational_resources_count=total_operational,
        available_resources_count=len(sim_available),
        response_time_impact_minutes=round(response_time_impact, 1),
        coverage_gaps_identified=coverage_gaps,
        bottleneck_alerts=bottleneck_alerts,
        recommended_positioning_actions=recommendations,
        created_at=now,
    )
