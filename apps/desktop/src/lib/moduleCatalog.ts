import { FileSpreadsheet, GraduationCap, UserPlus } from "lucide-react";

export type ModuleId = "formConverter" | "currentStudents" | "graduation";
export type ModuleStatus = "skeleton" | "ready";

export type ModuleContract = {
  version: string;
  inputs: string[];
  validations: string[];
  outputs: string[];
  events: string[];
};

export type ModuleDefinition = {
  id: ModuleId;
  status: ModuleStatus;
  icon: typeof GraduationCap;
  requiresCredits: boolean;
  pricingMode: "per_billable_record";
  creditPerUnit: number;
  productionDryRunEnabled: boolean;
  contract: ModuleContract;
};

export const moduleDefinitions: ModuleDefinition[] = [
  {
    id: "formConverter",
    status: "ready",
    icon: FileSpreadsheet,
    requiresCredits: true,
    pricingMode: "per_billable_record",
    creditPerUnit: 1,
    productionDryRunEnabled: false,
    contract: {
      version: "0.1-draft",
      inputs: ["scanned_pdf_path", "school_year", "template_type", "ai_processing_consent"],
      validations: ["pdf_file", "supported_template", "page_count", "credit_policy", "review_required"],
      outputs: ["excel_path", "conversion_report_path", "review_report_path", "warnings"],
      events: ["validate_form_pdf", "start_form_conversion", "save_review_edits", "export_converted_excel"],
    },
  },
  {
    id: "currentStudents",
    status: "skeleton",
    icon: UserPlus,
    requiresCredits: true,
    pricingMode: "per_billable_record",
    creditPerUnit: 1,
    productionDryRunEnabled: false,
    contract: {
      version: "0.1-draft",
      inputs: ["student_roster_excel_path", "operation_type", "school_year"],
      validations: ["required_columns_present", "student_id_format", "duplicate_student_check"],
      outputs: ["validated_rows", "review_rows", "operation_report_path"],
      events: ["module_opened", "roster_validated", "job_started", "job_completed"],
    },
  },
  {
    id: "graduation",
    status: "ready",
    icon: GraduationCap,
    requiresCredits: true,
    pricingMode: "per_billable_record",
    creditPerUnit: 1,
    productionDryRunEnabled: false,
    contract: {
      version: "0.1",
      inputs: ["obec_study_excel_path", "grade_level", "minimum_match_score"],
      validations: ["excel_schema", "status_mapping", "browser_runtime", "credit_policy"],
      outputs: ["obec_fill_report_csv", "obec_fill_review_csv", "run_summary"],
      events: ["validate_excel", "start_job", "progress", "job_done"],
    },
  },
];

export function getModuleDefinition(id: ModuleId): ModuleDefinition {
  const module = moduleDefinitions.find((item) => item.id === id);
  if (!module) {
    throw new Error(`Unknown module: ${id}`);
  }
  return module;
}
