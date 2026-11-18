"""
CareOn Milestone 10 — Resource Availability & Predictive Coverage Analysis.

Assesses:
- Real-time ambulance operational availability integrating M5 and M6 state
- Strict exclusion of occupied ambulances and active assignments
- Exclusion of resources with stale or unverified GPS telemetry (>15 mins)
- Travel-time coverage using road routing (with clearly labeled fallback)
- Identification of regional coverage gaps and underserved populations
"""

import math
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.models import (
    Resource,
    Assignment,
    ResponderTelemetryLog,
    MissionEventLog,
    utc_now,
)
from app.schemas import (
    CoverageAnalysisRequest,
    ZoneCoverageResponse,
)
from app.dispatch.routing import RoutingEngine
from app.algorithms.prediction import ZONES

# Default operational urban zones
DEFAULT_OPERATIONAL_ZONES = [
    {"name": "Central Mysuru", "lat": 12.3052, "lon": 76.6552, "baseline_demand": 3.0},
    {"name": "Kuvempunagar", "lat": 12.2880, "lon": 76.6280, "baseline_demand": 2.0},
    {"name": "Gokulam", "lat": 12.3250, "lon": 76.6350, "baseline_demand": 1.5},
    {"name": "Hebbal Industrial Suburb", "lat": 12.3600, "lon": 76.6100, "baseline_demand": 2.5},
    {"name": "Chamundi Foothills", "lat": 12.2850, "lon": 76.6750, "baseline_demand": 1.0},
]

MAX_GPS_FRESHNESS_MINUTES = 15.0


def is_resource_telemetry_fresh(db: Session, resource: Resource) -> Tuple[bool, float, float]:
    """
    Check if resource has fresh GPS telemetry within MAX_GPS_FRESHNESS_MINUTES.
    Returns (is_fresh, current_lat, current_lon).
    """
    now = utc_now()
    
    # 1. Check latest telemetry log
    latest_telemetry = (
        db.query(ResponderTelemetryLog)
        .filter(ResponderTelemetryLog.resource_id == resource.id)
        .order_by(ResponderTelemetryLog.server_timestamp.desc())
        .first()
    )

    if latest_telemetry:
        ts = latest_telemetry.server_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        diff_mins = (now - ts).total_seconds() / 60.0
        if diff_mins <= MAX_GPS_FRESHNESS_MINUTES:
            return True, latest_telemetry.latitude, latest_telemetry.longitude
        return False, latest_telemetry.latitude, latest_telemetry.longitude

    # 2. Check resource.last_updated
    if resource.last_updated:
        ts = resource.last_updated
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        diff_mins = (now - ts).total_seconds() / 60.0
        if diff_mins <= MAX_GPS_FRESHNESS_MINUTES:
            return True, resource.latitude, resource.longitude

    # If no recent timestamp exists, telemetry is unverified/stale
    return False, resource.latitude, resource.longitude


def get_available_operational_ambulances(
    db: Session,
    organization_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Inspect all ambulances and partition into:
    1. available_ambulances (freely available, fresh GPS, no active assignments)
    2. occupied_ambulances (active assignment, en_route, on_scene, transporting)
    3. stale_gps_ambulances (available status but GPS is older than threshold)
    """
    query = db.query(Resource).filter(
        Resource.category.ilike("%Ambulance%"),
        Resource.status.notin_(["Unavailable", "Under Maintenance"]),
    )
    if organization_id:
        query = query.filter(Resource.organization_id == organization_id)

    ambulances = query.all()

    # Active assignments
    active_assignments = (
        db.query(Assignment)
        .filter(Assignment.status == "Active")
        .all()
    )
    occupied_resource_ids = {a.resource_id for a in active_assignments}

    available_list = []
    occupied_list = []
    stale_list = []

    for amb in ambulances:
        is_occupied = (amb.id in occupied_resource_ids) or (amb.status in ["Assigned", "Busy"])
        is_fresh, lat, lon = is_resource_telemetry_fresh(db, amb)

        amb_info = {
            "resource": amb,
            "id": amb.id,
            "code": amb.resource_code,
            "name": amb.name,
            "capabilities": amb.capabilities or "ALS",
            "latitude": lat,
            "longitude": lon,
            "status": amb.status,
            "is_fresh": is_fresh,
        }

        if is_occupied:
            occupied_list.append(amb_info)
        elif not is_fresh:
            stale_list.append(amb_info)
        else:
            available_list.append(amb_info)

    return available_list, occupied_list, stale_list


def analyze_regional_coverage(
    db: Session,
    request: CoverageAnalysisRequest,
    organization_id: Optional[int] = None,
) -> List[ZoneCoverageResponse]:
    """
    Calculate coverage metrics, travel-time coverage, and gaps across operational zones.
    """
    routing = RoutingEngine()
    available, occupied, stale = get_available_operational_ambulances(db, organization_id)
    total_operational = len(available) + len(occupied) + len(stale)

    zones_to_evaluate = [
        z for z in DEFAULT_OPERATIONAL_ZONES
        if not request.zone_or_region or z["name"].lower() == request.zone_or_region.lower()
    ]
    if not zones_to_evaluate:
        zones_to_evaluate = DEFAULT_OPERATIONAL_ZONES

    responses: List[ZoneCoverageResponse] = []

    for zone in zones_to_evaluate:
        z_lat = zone["lat"]
        z_lon = zone["lon"]
        demand_forecast = zone.get("baseline_demand", 2.0)

        # Find travel times for all available ambulances
        ambulance_etas: List[Tuple[Dict[str, Any], float, str]] = []
        for amb in available:
            res = routing.calculate_eta(amb["latitude"], amb["longitude"], z_lat, z_lon)
            ambulance_etas.append((amb, res.eta_minutes, res.source))

        # Sort by nearest
        ambulance_etas.sort(key=lambda x: x[1])

        if ambulance_etas:
            nearest_amb, nearest_eta, r_source = ambulance_etas[0]
            nearest_code = nearest_amb["code"]
            nearest_time = nearest_eta
            avg_travel = round(sum(x[1] for x in ambulance_etas[:3]) / min(3, len(ambulance_etas)), 1)
        else:
            nearest_code = None
            nearest_time = None
            avg_travel = 99.0
            r_source = "no_available_resources"

        # Count available ambulances within threshold travel time
        coverage_count = len([x for x in ambulance_etas if x[1] <= request.response_threshold_minutes])
        coverage_ratio = round(coverage_count / max(1.0, demand_forecast), 2)

        # Flag coverage gap if 0 resources within threshold or nearest ETA exceeds threshold
        is_gap = (coverage_count == 0) or (nearest_time is not None and nearest_time > request.response_threshold_minutes)

        responses.append(
            ZoneCoverageResponse(
                zone_or_region=zone["name"],
                operational_resources_count=total_operational,
                available_resources_count=len(available),
                occupied_resources_count=len(occupied),
                stale_gps_resources_count=len(stale),
                forecasted_demand_next_3h=demand_forecast,
                coverage_ratio=coverage_ratio,
                avg_travel_time_minutes=avg_travel,
                is_coverage_gap=is_gap,
                nearest_available_resource_code=nearest_code,
                nearest_travel_time_minutes=nearest_time,
                routing_source=r_source,
            )
        )

    return responses
