"""
CareOn Milestone 10 — Resilient Intelligence & Positioning Worker.

Maintenance cycle that:
- Automatically marks stale positioning recommendations past their expiry as EXPIRED
- Audits expiration events in PositioningAuditLog
- Takes periodic regional coverage snapshots and stores in coverage_snapshot_records
- Monitors model health and data freshness
"""

import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import (
    PositioningRecommendation,
    PositioningAuditLog,
    CoverageSnapshotRecord,
    utc_now,
)
from app.schemas import CoverageAnalysisRequest
from app.intelligence.coverage_engine import analyze_regional_coverage
from app.intelligence.model_registry import check_intelligence_model_health

logger = logging.getLogger("careon.intelligence.worker")


def ensure_utc(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def execute_intelligence_maintenance_cycle(db: Session) -> Dict[str, Any]:
    """
    Execute maintenance tasks for intelligence and positioning subsystem.
    """
    now = utc_now()
    stats = {
        "expired_recommendations_count": 0,
        "coverage_snapshots_created": 0,
        "model_health": "UNKNOWN",
    }

    # 1. Sweep expired recommendations
    pending_recs = (
        db.query(PositioningRecommendation)
        .filter(
            PositioningRecommendation.status.in_(["PENDING_REVIEW", "MODIFIED", "GENERATED"]),
        )
        .all()
    )

    for rec in pending_recs:
        if ensure_utc(rec.expires_at) < now:
            prev_status = rec.status
            rec.status = "EXPIRED"
            rec.updated_at = now

            audit = PositioningAuditLog(
                log_uuid=str(uuid.uuid4()),
                recommendation_id=rec.id,
                actor_id=None,
                action="EXPIRED",
                previous_status=prev_status,
                new_status="EXPIRED",
                details_json=json.dumps({"reason": "Recommendation exceeded operational validity window without dispatcher action."}),
                created_at=now,
            )
            db.add(audit)
            stats["expired_recommendations_count"] += 1

    # 2. Capture coverage snapshots for operational audit
    coverage_items = analyze_regional_coverage(db, CoverageAnalysisRequest())
    for item in coverage_items:
        snap = CoverageSnapshotRecord(
            snapshot_uuid=str(uuid.uuid4()),
            organization_id=None,
            zone_or_region=item.zone_or_region,
            operational_resources_count=item.operational_resources_count,
            available_resources_count=item.available_resources_count,
            forecasted_demand=item.forecasted_demand_next_3h,
            coverage_ratio=item.coverage_ratio,
            avg_travel_time_minutes=item.avg_travel_time_minutes,
            is_gap=item.is_coverage_gap,
            threshold_travel_time_minutes=15.0,
            created_at=now,
        )
        db.add(snap)
        stats["coverage_snapshots_created"] += 1

    # 3. Model health check
    health = check_intelligence_model_health(db)
    stats["model_health"] = health.status

    db.commit()
    logger.info(f"Intelligence maintenance cycle completed: {stats}")
    return stats
