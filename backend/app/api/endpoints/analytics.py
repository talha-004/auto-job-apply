"""
Conversion Funnel & Analytics API Endpoints.
Serves stage-by-stage funnel metrics, platform conversion ROI, and KPI summaries.
"""

from fastapi import APIRouter
from app.services.analytics_service import analytics_service, FunnelSummary, PlatformROIMetric

router = APIRouter()


@router.get("/funnel", response_model=FunnelSummary)
async def get_conversion_funnel():
    """Returns stage-by-stage application funnel statistics and conversion rates."""
    return analytics_service.compute_funnel_summary()


@router.get("/platform-roi")
async def get_platform_roi():
    """Returns platform-specific application volume and interview conversion rates."""
    roi = analytics_service.compute_platform_roi()
    return {"platforms": roi}


@router.get("/summary")
async def get_analytics_kpi_summary():
    """Returns top-level KPI overview metrics for the executive dashboard."""
    funnel = analytics_service.compute_funnel_summary()
    roi = analytics_service.compute_platform_roi()
    best_platform = roi[0].platform if roi and roi[0].applications_count > 0 else "N/A"

    return {
        "total_applications": funnel.total_applied,
        "interviews_scheduled": funnel.total_interviews,
        "interview_rate_pct": funnel.applied_to_interview_rate_pct,
        "top_performing_platform": best_platform,
        "offers_received": funnel.total_offers
    }
