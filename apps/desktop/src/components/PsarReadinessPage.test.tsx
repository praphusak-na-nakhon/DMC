import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PsarReadinessPage } from "./PsarReadinessPage";
import type { PsarReadinessResponse } from "../types/contracts";

const mockRpc = vi.hoisted(() => ({
  getPsarReadiness: vi.fn(),
  addPsarEvidence: vi.fn(),
  generatePsarReport: vi.fn(),
  openEvidenceDialog: vi.fn(),
}));

vi.mock("../lib/rpcClient", () => mockRpc);

function readiness(overrides: Partial<PsarReadinessResponse> = {}): PsarReadinessResponse {
  const base: PsarReadinessResponse = {
    project_id: "default",
    overall_completion_score: 0.72,
    warning_threshold: 0.8,
    confidence_threshold: 0.75,
    total_requirements: 1,
    complete_count: 0,
    partial_count: 1,
    missing_count: 0,
    needs_review_count: 0,
    uploaded_files: [
      {
        file_id: "file-1",
        file_name: "lesson-plan.docx",
        file_path: "C:\\data\\lesson-plan.docx",
        file_type: "docx",
        extracted_summary: "Lesson plan summary",
        created_at: "2026-05-04T00:00:00Z",
        updated_at: "2026-05-04T00:00:00Z",
      },
    ],
    mapped_files: [
      {
        requirement_id: "teaching.lesson_plans",
        evidence_type: "lesson plans",
        source_file_id: "file-1",
        source_file_name: "lesson-plan.docx",
        extracted_summary: "Lesson plan summary",
        confidence_score: 0.88,
        page_number: null,
        location: "filename and extracted metadata",
        status: "accepted",
        created_at: "2026-05-04T00:00:00Z",
        updated_at: "2026-05-04T00:00:00Z",
      },
    ],
    sections: [
      {
        section_id: "standard_3_teaching",
        section_title: "Standard 3: Teaching and Learning Process",
        completion_score: 0.72,
        complete_count: 0,
        partial_count: 1,
        missing_count: 0,
        needs_review_count: 0,
        requirements: [
          {
            requirement_id: "teaching.lesson_plans",
            requirement_title: "Lesson plans and learning design",
            category: "teaching_process",
            description: "Learning plans and course planning.",
            required_evidence: ["lesson plans", "course plan"],
            optional_evidence: [],
            weight: 9,
            minimum_required_items: 2,
            status: "partial",
            completion_score: 0.5,
            missing_evidence: ["course plan"],
            found_evidence: [
              {
                requirement_id: "teaching.lesson_plans",
                evidence_type: "lesson plans",
                source_file_id: "file-1",
                source_file_name: "lesson-plan.docx",
                extracted_summary: "Lesson plan summary",
                confidence_score: 0.88,
                page_number: null,
                location: "filename and extracted metadata",
                status: "accepted",
                created_at: "2026-05-04T00:00:00Z",
                updated_at: "2026-05-04T00:00:00Z",
              },
            ],
            recommendation: "Not enough evidence yet. Upload or confirm course plan.",
            priority: "medium",
          },
        ],
      },
    ],
    missing_evidence_recommendations: [
      {
        evidence_name: "course plan",
        requirement_id: "teaching.lesson_plans",
        requirement_title: "Lesson plans and learning design",
        section_id: "standard_3_teaching",
        section_title: "Standard 3: Teaching and Learning Process",
        why_needed: "Not enough evidence yet. Upload or confirm course plan.",
        priority: "medium",
        suggested_file_types: ["PDF", "DOCX", "XLSX", "image"],
      },
    ],
  };
  return { ...base, ...overrides };
}

describe("PsarReadinessPage", () => {
  it("loads readiness, expands requirement evidence, and uploads another file", async () => {
    const initial = readiness();
    const updated = readiness({
      overall_completion_score: 1,
      complete_count: 1,
      partial_count: 0,
      missing_evidence_recommendations: [],
      sections: [
        {
          ...initial.sections[0],
          completion_score: 1,
          complete_count: 1,
          partial_count: 0,
          requirements: [
            {
              ...initial.sections[0].requirements[0],
              status: "complete",
              completion_score: 1,
              missing_evidence: [],
              recommendation: "Evidence found meets the current readiness rule for this requirement.",
            },
          ],
        },
      ],
    });
    mockRpc.getPsarReadiness.mockResolvedValue(initial);
    mockRpc.addPsarEvidence.mockResolvedValue({
      project_id: "default",
      file: initial.uploaded_files[0],
      mappings: initial.mapped_files,
      readiness: updated,
    });

    render(<PsarReadinessPage onBackHome={vi.fn()} onRevealPath={vi.fn()} />);

    await screen.findByText("Your report is 72% ready");
    expect(screen.getByText("Recommended uploads")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Lesson plans and learning design/i }));
    expect(screen.getByText("Evidence found")).toBeInTheDocument();
    expect(screen.getByText("Lesson plan summary")).toBeInTheDocument();

    fireEvent.change(screen.getAllByRole("textbox")[1], {
      target: { value: "C:\\data\\course-plan.docx" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Upload missing evidence/i }));

    await waitFor(() => expect(mockRpc.addPsarEvidence).toHaveBeenCalledWith("default", "C:\\data\\course-plan.docx"));
    await screen.findByText("Your report is 100% ready");
  });

  it("generates an official P-SAR form after acknowledging low readiness", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const initial = readiness();
    mockRpc.getPsarReadiness.mockResolvedValue(initial);
    mockRpc.generatePsarReport.mockResolvedValue({
      project_id: "default",
      report_path: "C:\\reports\\psar\\default\\p-sar-report.docx",
      readiness: initial,
      generated_at: "2026-05-04T00:00:00Z",
    });

    render(<PsarReadinessPage onBackHome={vi.fn()} onRevealPath={vi.fn()} />);

    await screen.findByText("Your report is 72% ready");
    fireEvent.click(screen.getByRole("button", { name: /Generate anyway/i }));

    await waitFor(() => expect(mockRpc.generatePsarReport).toHaveBeenCalledWith("default"));
    expect(screen.getByText(/Generated official P-SAR form from template/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Open report/i })).toBeInTheDocument();
  });
});
