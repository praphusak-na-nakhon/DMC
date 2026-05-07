from __future__ import annotations

import pytest

from app.pii_guard import assert_payload_is_telemetry_safe


def test_assert_payload_is_telemetry_safe_accepts_allowlisted_shape() -> None:
    assert_payload_is_telemetry_safe(
        {
            "events": [
                {
                    "event": "job_completed",
                    "ts": "2026-04-22T00:00:00Z",
                    "module": "graduation",
                    "total": 300,
                    "succeeded": 290,
                    "failed": 10,
                    "duration_sec": 120,
                }
            ]
        }
    )


def test_assert_payload_is_telemetry_safe_rejects_pii_field_names() -> None:
    with pytest.raises(ValueError, match="student_no"):
        assert_payload_is_telemetry_safe(
            {
                "events": [
                    {
                        "event": "job_failed",
                        "ts": "2026-04-22T00:00:00Z",
                        "module": "graduation",
                        "student_no": "17217",
                        "processed": 25,
                        "error_code": "INPUT_STATUS_NOT_MAPPED",
                    }
                ]
            }
        )


def test_assert_payload_is_telemetry_safe_rejects_case_and_camel_variants() -> None:
    with pytest.raises(ValueError, match="StudentNo"):
        assert_payload_is_telemetry_safe(
            {
                "events": [
                    {
                        "event": "job_failed",
                        "ts": "2026-04-22T00:00:00Z",
                        "module": "graduation",
                        "StudentNo": "17217",
                        "processed": 25,
                        "error_code": "INPUT_STATUS_NOT_MAPPED",
                    }
                ]
            }
        )


def test_assert_payload_is_telemetry_safe_rejects_name_aliases() -> None:
    with pytest.raises(ValueError, match="portalName"):
        assert_payload_is_telemetry_safe(
            {
                "events": [
                    {
                        "event": "job_failed",
                        "ts": "2026-04-22T00:00:00Z",
                        "module": "graduation",
                        "portalName": "สมชาย ใจดี",
                        "processed": 25,
                        "error_code": "PORTAL_SESSION_EXPIRED",
                    }
                ]
            }
        )


def test_assert_payload_is_telemetry_safe_accepts_millisecond_timestamps() -> None:
    assert_payload_is_telemetry_safe({"events": [{"event": "tick", "created_ms": "1715025600000"}]})


def test_assert_payload_is_telemetry_safe_rejects_valid_thai_national_id_in_string() -> None:
    with pytest.raises(ValueError, match="PII value"):
        assert_payload_is_telemetry_safe({"events": [{"event": "failed", "error_code": "ID 1234567890121"}]})
