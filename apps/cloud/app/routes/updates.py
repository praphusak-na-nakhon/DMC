from __future__ import annotations

from fastapi import APIRouter, Query, Response

from ..config import settings


router = APIRouter()


@router.get("/manifest", response_model=None)
def get_update_manifest(
    current_version: str = Query(default=""),
    target: str = Query(default=""),
    arch: str = Query(default=""),
) -> Response | dict[str, str]:
    latest_version = settings.updater_latest_version.strip()
    artifact_url = settings.updater_windows_x86_64_url.strip()
    artifact_signature = settings.updater_windows_x86_64_signature.strip()

    if current_version == latest_version:
        return Response(status_code=204)

    if target != "windows" or arch != "x86_64":
        return Response(status_code=204)

    if not artifact_url or not artifact_signature:
        return Response(status_code=204)

    return {
        "version": latest_version,
        "pub_date": settings.updater_pub_date,
        "url": artifact_url,
        "signature": artifact_signature,
        "notes": settings.updater_notes,
    }
