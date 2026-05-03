from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from dmc_sidecar import config as sidecar_config
from dmc_sidecar.p_sar_readiness import P_SAR_REQUIREMENT_MATRIX, PsarReadinessService, compute_psar_readiness
from dmc_sidecar.schemas import PsarEvidenceMapping, PsarRequirement


NOW = "2026-05-04T00:00:00Z"


def _mapping(
    requirement_id: str,
    evidence_type: str,
    *,
    confidence: float = 0.9,
    status: str = "accepted",
) -> PsarEvidenceMapping:
    return PsarEvidenceMapping(
        requirement_id=requirement_id,
        evidence_type=evidence_type,
        source_file_id=f"file-{requirement_id}-{evidence_type}",
        source_file_name=f"{evidence_type}.pdf",
        extracted_summary=f"summary for {evidence_type}",
        confidence_score=confidence,
        page_number=None,
        location=None,
        status=status,  # type: ignore[arg-type]
        created_at=NOW,
        updated_at=NOW,
    )


def _requirement(requirement_id: str, *, weight: float) -> PsarRequirement:
    return PsarRequirement(
        requirement_id=requirement_id,
        section_id="section",
        section_title="Section",
        section_order=1,
        title=requirement_id,
        category="test",
        required_evidence=[f"{requirement_id}-evidence"],
        optional_evidence=[],
        weight=weight,
        minimum_required_items=1,
        description="test requirement",
    )


def _find_requirement(response, requirement_id: str):
    for section in response.sections:
        for requirement in section.requirements:
            if requirement.requirement_id == requirement_id:
                return requirement
    raise AssertionError(f"requirement not found: {requirement_id}")


def test_all_requirements_missing_score_zero() -> None:
    response = compute_psar_readiness(project_id="default", mappings=[])

    assert response.overall_completion_score == 0
    assert response.total_requirements == len(P_SAR_REQUIREMENT_MATRIX)
    assert response.missing_count == len(P_SAR_REQUIREMENT_MATRIX)
    assert response.complete_count == 0
    assert response.missing_evidence_recommendations


def test_partial_evidence_does_not_mark_requirement_complete() -> None:
    requirement = P_SAR_REQUIREMENT_MATRIX[0]
    response = compute_psar_readiness(
        project_id="default",
        mappings=[
            _mapping(requirement.requirement_id, requirement.required_evidence[0]),
        ],
    )

    item = _find_requirement(response, requirement.requirement_id)
    assert item.status == "partial"
    assert 0 < item.completion_score < 1
    assert item.missing_evidence


def test_complete_evidence_requires_minimum_required_items() -> None:
    requirement = P_SAR_REQUIREMENT_MATRIX[0]
    response = compute_psar_readiness(
        project_id="default",
        mappings=[
            _mapping(requirement.requirement_id, requirement.required_evidence[0]),
            _mapping(requirement.requirement_id, requirement.required_evidence[1]),
            _mapping(requirement.requirement_id, requirement.required_evidence[2]),
        ],
    )

    item = _find_requirement(response, requirement.requirement_id)
    assert item.status == "complete"
    assert item.completion_score == 1
    assert item.missing_evidence == []


def test_low_confidence_evidence_needs_review() -> None:
    requirement = P_SAR_REQUIREMENT_MATRIX[3]
    response = compute_psar_readiness(
        project_id="default",
        mappings=[
            _mapping(requirement.requirement_id, requirement.required_evidence[0], confidence=0.52),
        ],
    )

    item = _find_requirement(response, requirement.requirement_id)
    assert item.status == "needs_review"
    assert item.completion_score < 1
    assert item.priority == "high"


def test_weighted_score_uses_requirement_weights() -> None:
    requirements = (
        _requirement("low_weight", weight=1),
        _requirement("high_weight", weight=3),
    )
    response = compute_psar_readiness(
        project_id="weighted",
        requirements=requirements,
        mappings=[
            _mapping("low_weight", "low_weight-evidence"),
        ],
    )

    assert response.overall_completion_score == 0.25
    assert response.complete_count == 1
    assert response.missing_count == 1


def test_generate_report_writes_docx(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sidecar_config, "default_data_dir", lambda: tmp_path)
    service = PsarReadinessService()

    result = service.generate_report("default")

    report_path = Path(result.report_path)
    assert report_path.exists()
    assert report_path.suffix == ".docx"
    with ZipFile(report_path) as archive:
        names = set(archive.namelist())
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "word/header1.xml" in names
    assert "รายงานผลการปฏิบัติงาน" in document_xml
    assert "จัดเตรียม/แนบผลสัมฤทธิ์ทางการเรียน" in document_xml
    assert "P-SAR Report Draft" not in document_xml
