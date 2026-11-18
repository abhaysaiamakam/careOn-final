"""
CareOn Milestone 5 — Road-Network ETA & Distance Engine.

Features:
- Dedicated routing abstraction (RoutingProvider protocol)
- OSRM-compatible HTTP routing provider with configurable URL and timeout
- Redis caching layer (careon:routing:eta:...) with controlled TTLs
- Resilient fallback provider (haversine_fallback) clearly identified and never labeled as live traffic
- Metadata tracking: source, timestamp, distance_km, eta_minutes, and is_fallback
"""

import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import urllib.request
import urllib.error

from app.redis_client import get_redis_client

logger = logging.getLogger("careon.dispatch.routing")

# Environment configuration
OSRM_URL = os.getenv("OSRM_URL", "http://router.project-osrm.org")
ROUTING_TIMEOUT_SECONDS = float(os.getenv("ROUTING_TIMEOUT_SECONDS", "2.0"))
ROUTING_CACHE_TTL_SECONDS = int(os.getenv("ROUTING_CACHE_TTL_SECONDS", "300"))


@dataclass
class RoutingResult:
    distance_km: float
    eta_minutes: float
    source: str  # "osrm_road_network", "cache_osrm", "haversine_fallback"
    is_fallback: bool
    calculated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self):
        return {
            "distance_km": self.distance_km,
            "eta_minutes": self.eta_minutes,
            "source": self.source,
            "is_fallback": self.is_fallback,
            "calculated_at": self.calculated_at,
        }


def calculate_haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometers."""
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


class RoutingEngine:
    def __init__(
        self,
        osrm_base_url: str = OSRM_URL,
        timeout_seconds: float = ROUTING_TIMEOUT_SECONDS,
        cache_ttl: int = ROUTING_CACHE_TTL_SECONDS,
    ):
        self.osrm_base_url = osrm_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.cache_ttl = cache_ttl

    def _get_cache_key(self, lat1: float, lon1: float, lat2: float, lon2: float) -> str:
        return f"careon:routing:eta:{lat1:.4f}:{lon1:.4f}:{lat2:.4f}:{lon2:.4f}"

    def calculate_eta(
        self,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float,
        use_cache: bool = True,
    ) -> RoutingResult:
        """
        Calculate travel time and distance from origin to destination.
        Attempts Redis cache -> OSRM road-network -> Haversine fallback.
        """
        # Coordinate sanity check
        if from_lat == to_lat and from_lon == to_lon:
            return RoutingResult(
                distance_km=0.0,
                eta_minutes=1.0,
                source="exact_match",
                is_fallback=False,
            )

        cache_key = self._get_cache_key(from_lat, from_lon, to_lat, to_lon)
        r = get_redis_client() if use_cache else None

        # 1. Check Redis Cache
        if r:
            try:
                cached_bytes = r.get(cache_key)
                if cached_bytes:
                    data = json.loads(cached_bytes)
                    return RoutingResult(
                        distance_km=data["distance_km"],
                        eta_minutes=data["eta_minutes"],
                        source="cache_osrm",
                        is_fallback=False,
                    )
            except Exception as exc:
                logger.debug(f"Redis routing cache read error: {exc}")

        # 2. Query OSRM Road Network
        osrm_result = self._query_osrm(from_lat, from_lon, to_lat, to_lon)
        if osrm_result:
            # Write to Redis Cache
            if r:
                try:
                    r.set(
                        cache_key,
                        json.dumps({
                            "distance_km": osrm_result.distance_km,
                            "eta_minutes": osrm_result.eta_minutes,
                        }),
                        ex=self.cache_ttl,
                    )
                except Exception as exc:
                    logger.debug(f"Redis routing cache write error: {exc}")
            return osrm_result

        # 3. Fallback to Haversine with urban traffic factors
        return self._haversine_fallback(from_lat, from_lon, to_lat, to_lon)

    def _query_osrm(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> Optional[RoutingResult]:
        """Query OSRM driving service."""
        # Format: /route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false
        url = f"{self.osrm_base_url}/route/v1/driving/{lon1:.6f},{lat1:.6f};{lon2:.6f},{lat2:.6f}?overview=false"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "CareOn-Emergency-Dispatcher/1.0"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    routes = data.get("routes")
                    if routes and len(routes) > 0:
                        route = routes[0]
                        distance_meters = route.get("distance", 0.0)
                        duration_seconds = route.get("duration", 0.0)
                        dist_km = round(distance_meters / 1000.0, 2)
                        # Add emergency vehicle urban congestion margin (1.15x)
                        eta_mins = max(1.0, round((duration_seconds / 60.0) * 1.15, 1))
                        return RoutingResult(
                            distance_km=dist_km,
                            eta_minutes=eta_mins,
                            source="osrm_road_network",
                            is_fallback=False,
                        )
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, Exception) as exc:
            logger.debug(f"OSRM routing query failed ({exc}), falling back to haversine calculation")

        return None

    def _haversine_fallback(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> RoutingResult:
        """
        Deterministic, clearly-labeled straight-line urban travel estimation fallback.
        Assumes 35 km/h urban average speed with 1.30 detour/delay multiplier.
        """
        dist_km = calculate_haversine_km(lat1, lon1, lat2, lon2)
        raw_hours = dist_km / 35.0
        # 1.30 detour factor for street grid navigation
        eta_minutes = max(2.0, round(raw_hours * 60.0 * 1.30, 1))

        return RoutingResult(
            distance_km=dist_km,
            eta_minutes=eta_minutes,
            source="haversine_fallback",
            is_fallback=True,
        )


# Global singleton instance
routing_engine = RoutingEngine()
