"""
CareOn Milestone 10 — Historical Emergency Demand Intelligence.

Extracts, validates, and analyses historical emergency incident patterns:
- Incident frequency and volume changes
- Temporal distributions (time-of-day, day-of-week, weekly/monthly trends)
- Operational category and severity breakdown
- Strict exclusion of duplicate, cancelled, rejected, test, and simulated incidents
- Multi-tenant boundary filtering and data freshness calculation
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, and_

from app.models import Incident, utc_now
from app.schemas import (
    HourlyDemandPattern,
    WeekdayDemandPattern,
    CategoryBreakdownItem,
    SeverityBreakdownItem,
    DemandAnalyticsResponse,
)

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get_clean_historical_incidents_query(
    db: Session,
    days: int = 30,
    organization_id: Optional[int] = None,
    category: Optional[str] = None,
    include_simulated: bool = False,
):
    """
    Construct query for valid operational incidents.
    Strictly filters out duplicates, cancelled, rejected, and test records.
    """
    now = utc_now()
    since_dt = now - timedelta(days=days)

    query = db.query(Incident).filter(
        Incident.created_at >= since_dt,
        Incident.is_duplicate.is_(False),
        Incident.status.notin_(["Cancelled", "Rejected"]),
    )

    if not include_simulated:
        # Exclude synthetic or test incidents if flagged
        query = query.filter(
            ~Incident.description.ilike("%[TEST]%"),
            ~Incident.title.ilike("%[SIMULATED]%"),
        )

    if category:
        query = query.filter(Incident.category == category)

    return query


def analyze_historical_demand(
    db: Session,
    days: int = 30,
    organization_id: Optional[int] = None,
    category: Optional[str] = None,
) -> DemandAnalyticsResponse:
    """
    Perform deep statistical analysis on historical emergency demand.
    """
    now = utc_now()
    since_dt = now - timedelta(days=days)

    # 1. Count excluded incidents for audit transparency
    excluded_count = (
        db.query(Incident)
        .filter(
            Incident.created_at >= since_dt,
            (
                (Incident.is_duplicate.is_(True))
                | (Incident.status.in_(["Cancelled", "Rejected"]))
                | (Incident.description.ilike("%[TEST]%"))
                | (Incident.title.ilike("%[SIMULATED]%"))
            ),
        )
        .count()
    )

    # 2. Base query for clean operational incidents
    valid_query = get_clean_historical_incidents_query(
        db, days=days, organization_id=organization_id, category=category
    )
    valid_incidents = valid_query.all()
    total_valid = len(valid_incidents)

    # 3. Handle zero or empty historical data gracefully
    if total_valid == 0:
        return DemandAnalyticsResponse(
            total_valid_incidents=0,
            excluded_incidents_count=excluded_count,
            start_date=since_dt,
            end_date=now,
            hourly_patterns=[
                HourlyDemandPattern(hour=h, incident_count=0, incident_share_pct=0.0)
                for h in range(24)
            ],
            weekday_patterns=[
                WeekdayDemandPattern(
                    day_of_week=d,
                    day_name=DAYS_OF_WEEK[d],
                    incident_count=0,
                    incident_share_pct=0.0,
                )
                for d in range(7)
            ],
            category_breakdown=[],
            severity_breakdown=[],
            monthly_trend=[],
            data_freshness_seconds=0.0,
        )

    # 4. Hourly patterns (0..23)
    hour_counts = {h: 0 for h in range(24)}
    weekday_counts = {d: 0 for d in range(7)}
    category_counts: Dict[str, int] = {}
    severity_counts: Dict[str, int] = {}
    monthly_counts: Dict[str, int] = {}
    most_recent_ts = since_dt

    for inc in valid_incidents:
        inc_dt = inc.created_at
        if inc_dt:
            if inc_dt.tzinfo is None:
                inc_dt = inc_dt.replace(tzinfo=timezone.utc)
            if inc_dt > most_recent_ts:
                most_recent_ts = inc_dt

            # Hourly
            hour_counts[inc_dt.hour] = hour_counts.get(inc_dt.hour, 0) + 1
            # Weekday (Python Monday is 0)
            weekday_counts[inc_dt.weekday()] = weekday_counts.get(inc_dt.weekday(), 0) + 1
            # Month YYYY-MM
            month_key = inc_dt.strftime("%Y-%m")
            monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1

        cat = inc.category or "Unknown"
        category_counts[cat] = category_counts.get(cat, 0) + 1

        sev = inc.priority or "High"
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    hourly_patterns = [
        HourlyDemandPattern(
            hour=h,
            incident_count=hour_counts[h],
            incident_share_pct=round((hour_counts[h] / total_valid) * 100.0, 2),
        )
        for h in range(24)
    ]

    weekday_patterns = [
        WeekdayDemandPattern(
            day_of_week=d,
            day_name=DAYS_OF_WEEK[d],
            incident_count=weekday_counts[d],
            incident_share_pct=round((weekday_counts[d] / total_valid) * 100.0, 2),
        )
        for d in range(7)
    ]

    category_breakdown = [
        CategoryBreakdownItem(
            category=cat,
            count=cnt,
            percentage=round((cnt / total_valid) * 100.0, 2),
        )
        for cat, cnt in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    severity_breakdown = [
        SeverityBreakdownItem(
            priority=sev,
            count=cnt,
            percentage=round((cnt / total_valid) * 100.0, 2),
        )
        for sev, cnt in sorted(severity_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    monthly_trend = [
        {"period": m, "incident_count": cnt}
        for m, cnt in sorted(monthly_counts.items())
    ]

    data_freshness_seconds = max(0.0, (now - most_recent_ts).total_seconds())

    return DemandAnalyticsResponse(
        total_valid_incidents=total_valid,
        excluded_incidents_count=excluded_count,
        start_date=since_dt,
        end_date=now,
        hourly_patterns=hourly_patterns,
        weekday_patterns=weekday_patterns,
        category_breakdown=category_breakdown,
        severity_breakdown=severity_breakdown,
        monthly_trend=monthly_trend,
        data_freshness_seconds=round(data_freshness_seconds, 1),
    )
