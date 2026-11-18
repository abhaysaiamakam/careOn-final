"""
CareOn M1-E — Spatial Query Foundation
=======================================
Reusable geospatial query functions using PostGIS ST_DWithin / ST_Distance
on PostgreSQL. Falls back to Haversine calculation on SQLite (unit tests).

All distances are in metres unless noted.
"""
from __future__ import annotations

import logging
import math
from typing import List, Optional

from sqlalchemy import cast, func as sa_func
from sqlalchemy.orm import Session

from app.database import is_postgres
from app.models import Incident, Resource, ExternalProvider, make_point_wkt

logger = logging.getLogger("careon.spatial")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in metres between two WGS-84 points."""
    R = 6_371_000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _postgis_dwithin(db: Session, model, point_wkt: str, radius_m: float, extra_filters):
    """Return a SQLAlchemy query filtered by ST_DWithin (geography type) using a GiST index."""
    from geoalchemy2 import Geography

    return (
        db.query(model)
        .filter(
            model.geom.isnot(None),
            sa_func.ST_DWithin(
                cast(model.geom, Geography),
                cast(sa_func.ST_GeomFromText(point_wkt, 4326), Geography),
                radius_m,
            ),
            *extra_filters,
        )
        .order_by(
            sa_func.ST_Distance(
                cast(model.geom, Geography),
                cast(sa_func.ST_GeomFromText(point_wkt, 4326), Geography),
            )
        )
        .all()
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_resources_within_radius(
    db: Session,
    lat: float,
    lon: float,
    radius_m: float = 15_000,
    status: Optional[str] = "Available",
    category: Optional[str] = None,
    capabilities: Optional[List[str]] = None,
) -> List[Resource]:
    """
    Return resources within *radius_m* metres ordered by distance ascending.

    Parameters
    ----------
    db        : SQLAlchemy session.
    lat / lon : Centre point in WGS-84 decimal degrees.
    radius_m  : Search radius in metres (default 15 km).
    status    : If set, filter resources to this status (e.g. "Available").
    category  : Optional resource category filter.
    capabilities : Optional list of capability strings; each must appear in
                   the resource's capabilities field (comma-separated).
    """
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"Invalid coordinates: lat={lat}, lon={lon}")

    point_wkt = make_point_wkt(lat, lon)

    extra: list = []
    if status:
        extra.append(Resource.status == status)
    if category:
        extra.append(Resource.category == category)

    if is_postgres():
        try:
            results = _postgis_dwithin(db, Resource, point_wkt, radius_m, extra)
        except Exception as exc:
            logger.warning(f"PostGIS resource radius query failed, falling back to Haversine: {exc}")
            results = None

        if results is not None:
            if capabilities:
                results = [
                    r for r in results
                    if r.capabilities and all(cap.lower() in r.capabilities.lower() for cap in capabilities)
                ]
            return results

    # SQLite / fallback
    query = db.query(Resource)
    for f in extra:
        query = query.filter(f)
    all_res = query.all()
    nearby = [r for r in all_res if _haversine_m(lat, lon, r.latitude or 0, r.longitude or 0) <= radius_m]
    if capabilities:
        nearby = [
            r for r in nearby
            if r.capabilities and all(cap.lower() in r.capabilities.lower() for cap in capabilities)
        ]
    nearby.sort(key=lambda r: _haversine_m(lat, lon, r.latitude or 0, r.longitude or 0))
    return nearby


def find_incidents_within_radius(
    db: Session,
    lat: float,
    lon: float,
    radius_m: float = 5_000,
    exclude_terminal: bool = True,
) -> List[Incident]:
    """
    Return incidents within *radius_m* metres ordered by distance ascending.

    Parameters
    ----------
    db               : SQLAlchemy session.
    lat / lon        : Centre point in WGS-84 decimal degrees.
    radius_m         : Search radius in metres (default 5 km).
    exclude_terminal : If True, exclude Resolved / Cancelled / Rejected incidents.
    """
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"Invalid coordinates: lat={lat}, lon={lon}")

    point_wkt = make_point_wkt(lat, lon)
    terminal = ["Resolved", "Cancelled", "Rejected"]

    extra: list = []
    if exclude_terminal:
        extra.append(Incident.status.notin_(terminal))

    if is_postgres():
        try:
            return _postgis_dwithin(db, Incident, point_wkt, radius_m, extra)
        except Exception as exc:
            logger.warning(f"PostGIS incident radius query failed, falling back to Haversine: {exc}")

    # SQLite / fallback
    query = db.query(Incident)
    for f in extra:
        query = query.filter(f)
    all_inc = query.all()
    nearby = [i for i in all_inc if _haversine_m(lat, lon, i.latitude or 0, i.longitude or 0) <= radius_m]
    nearby.sort(key=lambda i: _haversine_m(lat, lon, i.latitude or 0, i.longitude or 0))
    return nearby


def find_providers_within_radius(
    db: Session,
    lat: float,
    lon: float,
    radius_m: float = 20_000,
    active_only: bool = True,
) -> List[ExternalProvider]:
    """Return external providers within *radius_m* metres ordered by distance ascending."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"Invalid coordinates: lat={lat}, lon={lon}")

    point_wkt = make_point_wkt(lat, lon)
    extra: list = []
    if active_only:
        extra.append(ExternalProvider.is_active == True)  # noqa: E712

    if is_postgres():
        try:
            return _postgis_dwithin(db, ExternalProvider, point_wkt, radius_m, extra)
        except Exception as exc:
            logger.warning(f"PostGIS provider radius query failed, falling back to Haversine: {exc}")

    # SQLite / fallback
    query = db.query(ExternalProvider)
    for f in extra:
        query = query.filter(f)
    all_p = query.all()
    nearby = [p for p in all_p if _haversine_m(lat, lon, p.latitude or 0, p.longitude or 0) <= radius_m]
    nearby.sort(key=lambda p: _haversine_m(lat, lon, p.latitude or 0, p.longitude or 0))
    return nearby


def distance_between_points(
    db: Session,
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Return the geodesic distance in metres between two WGS-84 points.
    Uses PostGIS ST_Distance(geography) on PostgreSQL, Haversine otherwise.
    """
    if is_postgres():
        try:
            from geoalchemy2 import Geography

            wkt1 = make_point_wkt(lat1, lon1)
            wkt2 = make_point_wkt(lat2, lon2)
            result = db.execute(
                sa_func.ST_Distance(
                    cast(sa_func.ST_GeomFromText(wkt1, 4326), Geography),
                    cast(sa_func.ST_GeomFromText(wkt2, 4326), Geography),
                ).select()
            ).scalar()
            if result is not None:
                return float(result)
        except Exception as exc:
            logger.warning(f"PostGIS ST_Distance failed, falling back to Haversine: {exc}")

    return _haversine_m(lat1, lon1, lat2, lon2)
