from __future__ import annotations

from fastapi import APIRouter

from ..schemas import LicenseActivateRequest, LicenseStateResponse


router = APIRouter()


@router.post("/activate", response_model=LicenseStateResponse)
def activate_license(request: LicenseActivateRequest) -> LicenseStateResponse:
    return LicenseStateResponse(
        status="active",
        license_tier="trial",
        school_size_tier="le_500",
        billing_interval=None,
        student_count_total=0,
        expires_at="2026-05-06T00:00:00Z",
        modules_enabled=["graduation"],
        max_devices=3,
        offline_grace_days=7,
    )


@router.get("/heartbeat", response_model=LicenseStateResponse)
def heartbeat() -> LicenseStateResponse:
    return LicenseStateResponse(
        status="active",
        license_tier="trial",
        school_size_tier="le_500",
        billing_interval=None,
        student_count_total=0,
        expires_at="2026-05-06T00:00:00Z",
        modules_enabled=["graduation"],
        max_devices=3,
        offline_grace_days=7,
    )
